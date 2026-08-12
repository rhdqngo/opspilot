"""Runtime-safe Agent Search request and response contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

DocumentType = Literal["runbook", "prior_rca", "architecture", "ownership", "known_error"]
ALLOWED_SERVICES = frozenset({"shared", "order-service", "payment-service", "inventory-service"})
ALLOWED_DOCUMENT_TYPES = frozenset(
    {"runbook", "prior_rca", "architecture", "ownership", "known_error"}
)
MAX_CHUNK_BYTES = 24 * 1024


class SearchKnowledgeInput(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    service: str | None = None
    document_types: list[DocumentType] = Field(default_factory=list)
    top_k: int = Field(default=6, ge=1, le=8)

    @model_validator(mode="after")
    def validate_filters(self) -> Self:
        if self.service is not None and self.service not in ALLOWED_SERVICES:
            raise ValueError("knowledge service is not allowlisted")
        if len(self.document_types) != len(set(self.document_types)):
            raise ValueError("document type filters must be unique")
        return self


class KnowledgeHit(BaseModel):
    document_id: str
    title: str
    document_type: DocumentType
    service: str | None = None
    version: str | None = None
    updated_at: datetime | None = None
    uri: str | None = None
    section: str | None = None
    chunk_text: str
    relevance_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    staleness_warning: str | None = None
    safety_flags: list[str] = Field(default_factory=list)


def build_search_filter(request: SearchKnowledgeInput) -> str:
    clauses: list[str] = []
    if request.service is not None:
        clauses.append(f'service: ANY("{request.service}")')
    if request.document_types:
        values = ", ".join(f'"{value}"' for value in request.document_types)
        clauses.append(f"document_type: ANY({values})")
    return " AND ".join(clauses)


def build_agent_search_request(request: SearchKnowledgeInput) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": request.query,
        "pageSize": request.top_k,
        "contentSearchSpec": {"searchResultMode": "CHUNKS"},
        "relevanceScoreSpec": {"returnRelevanceScore": True},
    }
    filter_value = build_search_filter(request)
    if filter_value:
        body["filter"] = filter_value
    return body


def _bounded_utf8(value: str, remaining: int) -> str:
    encoded = value.encode("utf-8")[:remaining]
    while encoded:
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError:
            encoded = encoded[:-1]
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def normalize_search_response(
    payload: Mapping[str, Any], request: SearchKnowledgeInput
) -> list[KnowledgeHit]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []
    hits: list[KnowledgeHit] = []
    used_bytes = 0
    for raw_result in raw_results[: request.top_k]:
        if not isinstance(raw_result, dict):
            continue
        raw_chunk = raw_result.get("chunk")
        raw_document = raw_result.get("document")
        chunk = raw_chunk if isinstance(raw_chunk, dict) else {}
        document = raw_document if isinstance(raw_document, dict) else {}
        raw_metadata = chunk.get("documentMetadata")
        document_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        chunk_struct = document_metadata.get("structData")
        document_struct = document.get("structData")
        metadata = (
            chunk_struct
            if isinstance(chunk_struct, dict)
            else document_struct
            if isinstance(document_struct, dict)
            else {}
        )
        raw_derived = document.get("derivedStructData")
        derived = raw_derived if isinstance(raw_derived, dict) else {}
        document_id = metadata.get("document_id") or raw_result.get("id") or document.get("id")
        title = metadata.get("title") or document_metadata.get("title") or derived.get("title")
        document_type = metadata.get("document_type")
        if not all(isinstance(value, str) for value in (document_id, title, document_type)):
            continue
        if document_type not in ALLOWED_DOCUMENT_TYPES:
            continue
        chunk_text = str(chunk.get("content", ""))
        chunks = derived.get("chunks")
        if not chunk_text and isinstance(chunks, list) and chunks and isinstance(chunks[0], dict):
            chunk_text = str(chunks[0].get("content", ""))
        if not chunk_text:
            segments = derived.get("extractive_segments")
            if isinstance(segments, list) and segments and isinstance(segments[0], dict):
                chunk_text = str(segments[0].get("content", ""))
        if not chunk_text:
            chunk_text = str(metadata.get("description", ""))
        remaining = MAX_CHUNK_BYTES - used_bytes
        if remaining <= 0:
            break
        bounded_chunk = _bounded_utf8(chunk_text, remaining)
        used_bytes += len(bounded_chunk.encode("utf-8"))
        raw_score = chunk.get("relevanceScore")
        score = (
            max(-1.0, min(1.0, float(raw_score))) if isinstance(raw_score, int | float) else None
        )
        review_due_at = _parse_datetime(metadata.get("review_due_at"))
        hits.append(
            KnowledgeHit(
                document_id=str(document_id),
                title=str(title),
                document_type=document_type,
                service=str(metadata["service"])
                if isinstance(metadata.get("service"), str)
                else None,
                version=str(metadata["version"])
                if isinstance(metadata.get("version"), str)
                else None,
                updated_at=_parse_datetime(metadata.get("updated_at")),
                uri=(
                    str(metadata["canonical_uri"])
                    if isinstance(metadata.get("canonical_uri"), str)
                    and str(metadata["canonical_uri"]).startswith("opspilot://knowledge/")
                    else None
                ),
                section=str(metadata["section"])
                if isinstance(metadata.get("section"), str)
                else None,
                chunk_text=bounded_chunk,
                relevance_score=score,
                staleness_warning=(
                    "REVIEW_OVERDUE"
                    if review_due_at is not None and review_due_at < datetime.now(UTC)
                    else None
                ),
                safety_flags=(
                    ["UNTRUSTED_INSTRUCTION_CONTENT"]
                    if metadata.get("security_test") is True
                    else []
                ),
            )
        )
    return hits
