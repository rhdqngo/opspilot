"""Synthetic operational knowledge corpus and bounded Agent Search utilities."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Self
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml
from pydantic import BaseModel, Field, model_validator

DocumentType = Literal["runbook", "prior_rca", "architecture", "ownership", "known_error"]
KnowledgeBackend = Literal["local", "agent-search"]
KnowledgeSyncMode = Literal["plan", "apply"]

ALLOWED_SERVICES = frozenset({"shared", "order-service", "payment-service", "inventory-service"})
ALLOWED_DOCUMENT_TYPES = frozenset(
    {"runbook", "prior_rca", "architecture", "ownership", "known_error"}
)
REQUIRED_RUNBOOK_SECTIONS = frozenset(
    {
        "Symptoms",
        "Impact",
        "Metrics",
        "Log signatures",
        "Recent changes",
        "Immediate mitigation",
        "Safety conditions",
        "Recovery verification",
        "Escalation",
    }
)
MAX_CHUNK_BYTES = 24 * 1024
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


class KnowledgeDocumentMetadata(BaseModel):
    document_id: str = Field(pattern=r"^(RB|RCA|ARC|OWN|SEC)-[A-Z0-9-]+$")
    document_type: DocumentType
    service: str
    version: str = Field(pattern=r"^\d+\.\d+$")
    owner: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    updated_at: datetime
    review_due_at: datetime
    canonical_uri: str
    tags: list[str] = Field(min_length=1)
    security_test: bool = False

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.service not in ALLOWED_SERVICES:
            raise ValueError("knowledge service is not allowlisted")
        for value in (self.updated_at, self.review_due_at):
            if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
                raise ValueError("knowledge datetimes must be timezone-aware UTC")
        if self.review_due_at <= self.updated_at:
            raise ValueError("review_due_at must be after updated_at")
        if self.canonical_uri != f"opspilot://knowledge/{self.document_id}":
            raise ValueError("canonical_uri must use the stable logical knowledge URI")
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("knowledge tags must be unique")
        if self.security_test and self.document_type != "known_error":
            raise ValueError("security test documents must use known_error type")
        return self


class KnowledgeDocument(BaseModel):
    metadata: KnowledgeDocumentMetadata
    source_path: str
    title: str
    body: str
    sections: list[str] = Field(default_factory=list)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class KnowledgeSmokeCase(BaseModel):
    case_id: str = Field(pattern=r"^KQ-\d{3}$")
    query: str = Field(min_length=3, max_length=500)
    expected_document_id: str
    service: str | None = None
    document_types: list[DocumentType] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=8)

    @model_validator(mode="after")
    def validate_filters(self) -> Self:
        if self.service is not None and self.service not in ALLOWED_SERVICES:
            raise ValueError("smoke case service is not allowlisted")
        return self


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


class KnowledgeValidationResult(BaseModel):
    valid: bool
    document_count: int = Field(ge=0)
    query_count: int = Field(ge=0)
    catalog_matches: bool
    errors: list[str] = Field(default_factory=list)


class KnowledgeSmokeResult(BaseModel):
    backend: KnowledgeBackend
    query_count: int = Field(ge=0)
    executed_query_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    failed_case_ids: list[str] = Field(default_factory=list)
    backend_ready: bool = True
    citation_metadata_complete: bool
    untrusted_content_flagged: bool
    untrusted_instruction_executed: bool = False

    @property
    def passed(self) -> bool:
        return (
            self.query_count == self.passed_count
            and self.executed_query_count == self.query_count
            and self.backend_ready
            and self.citation_metadata_complete
            and self.untrusted_content_flagged
            and not self.untrusted_instruction_executed
        )


class KnowledgeSyncResult(BaseModel):
    mode: KnowledgeSyncMode
    changed_document_count: int = Field(ge=0)
    removed_document_count: int = Field(ge=0)
    manifest_changed: bool
    import_requested: bool
    import_success_count: int = Field(default=0, ge=0)
    import_failure_count: int = Field(default=0, ge=0)
    snapshot_updated: bool
    no_op: bool


class KnowledgeImportOutcome(BaseModel):
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    completed: bool


class KnowledgeIndexStatus(BaseModel):
    document_count: int = Field(ge=0)
    indexed_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    exact_document_set: bool

    @property
    def ready(self) -> bool:
        return (
            self.exact_document_set
            and self.document_count == self.indexed_count
            and self.error_count == 0
        )


def default_knowledge_dir() -> Path:
    return Path.cwd() / "knowledge"


def _normalize_text(value: str) -> str:
    return (
        "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n")).strip() + "\n"
    )


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError("knowledge document must start with YAML frontmatter")
    try:
        raw_metadata, body = normalized[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("knowledge frontmatter must end with ---") from exc
    payload = yaml.safe_load(raw_metadata)
    if not isinstance(payload, dict):
        raise ValueError("knowledge frontmatter must be a mapping")
    return payload, body


def load_knowledge_document(path: Path, root: Path | None = None) -> KnowledgeDocument:
    corpus_root = root or default_knowledge_dir()
    raw = path.read_text(encoding="utf-8")
    metadata_payload, body = _parse_frontmatter(raw)
    metadata = KnowledgeDocumentMetadata.model_validate(metadata_payload)
    headings = re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)
    title_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    if title_match is None:
        raise ValueError("knowledge document must contain one H1 title")
    if metadata.document_type == "runbook":
        missing = sorted(REQUIRED_RUNBOOK_SECTIONS - set(headings))
        if missing:
            raise ValueError("runbook missing required sections: " + ", ".join(missing))
    normalized = _normalize_text(raw)
    return KnowledgeDocument(
        metadata=metadata,
        source_path=path.relative_to(corpus_root).as_posix(),
        title=title_match.group(1).strip(),
        body=_normalize_text(body),
        sections=headings,
        content_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def load_corpus(root: Path | None = None) -> list[KnowledgeDocument]:
    corpus_root = root or default_knowledge_dir()
    documents = [
        load_knowledge_document(path, corpus_root) for path in sorted(corpus_root.glob("**/*.md"))
    ]
    ids = [document.metadata.document_id for document in documents]
    hashes = [document.content_sha256 for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("knowledge document IDs must be unique")
    if len(hashes) != len(set(hashes)):
        raise ValueError("knowledge document contents must be unique")
    return documents


def load_smoke_cases(root: Path | None = None) -> list[KnowledgeSmokeCase]:
    corpus_root = root or default_knowledge_dir()
    payload = yaml.safe_load(
        (corpus_root / "evaluation" / "queries.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(payload, list):
        raise ValueError("knowledge smoke queries must be a list")
    cases = [KnowledgeSmokeCase.model_validate(item) for item in payload]
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("knowledge smoke case IDs must be unique")
    return cases


def catalog_jsonl(documents: Sequence[KnowledgeDocument]) -> str:
    lines: list[str] = []
    for document in sorted(documents, key=lambda item: item.metadata.document_id):
        payload = document.metadata.model_dump(mode="json")
        payload.update(
            {
                "source_path": document.source_path,
                "content_sha256": document.content_sha256,
            }
        )
        lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def validate_knowledge(root: Path | None = None) -> KnowledgeValidationResult:
    corpus_root = root or default_knowledge_dir()
    errors: list[str] = []
    documents: list[KnowledgeDocument] = []
    cases: list[KnowledgeSmokeCase] = []
    try:
        documents = load_corpus(corpus_root)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    try:
        cases = load_smoke_cases(corpus_root)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    catalog_matches = False
    if documents:
        catalog_path = corpus_root / "metadata.jsonl"
        if catalog_path.is_file():
            catalog_matches = catalog_path.read_text(encoding="utf-8") == catalog_jsonl(documents)
        if not catalog_matches:
            errors.append("metadata.jsonl does not match the deterministic corpus catalog")
    document_ids = {document.metadata.document_id for document in documents}
    missing_expected = sorted(
        case.expected_document_id for case in cases if case.expected_document_id not in document_ids
    )
    if missing_expected:
        errors.append("smoke cases reference unknown documents: " + ", ".join(missing_expected))
    if len(documents) != 13:
        errors.append("knowledge corpus must contain exactly 13 documents")
    if len(cases) != 10:
        errors.append("knowledge evaluation must contain exactly 10 queries")
    return KnowledgeValidationResult(
        valid=not errors,
        document_count=len(documents),
        query_count=len(cases),
        catalog_matches=catalog_matches,
        errors=errors,
    )


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(value)]


def local_search(
    request: SearchKnowledgeInput, documents: Sequence[KnowledgeDocument]
) -> list[KnowledgeHit]:
    query_counts = Counter(_tokens(request.query))
    ranked: list[tuple[int, str, KnowledgeDocument]] = []
    for document in documents:
        metadata = document.metadata
        if request.service is not None and metadata.service != request.service:
            continue
        if request.document_types and metadata.document_type not in request.document_types:
            continue
        weighted = Counter(_tokens(document.body))
        weighted.update(
            {token: count * 6 for token, count in Counter(_tokens(document.title)).items()}
        )
        weighted.update(
            {token: count * 4 for token, count in Counter(_tokens(" ".join(metadata.tags))).items()}
        )
        weighted.update(
            {
                token: count * 2
                for token, count in Counter(_tokens(" ".join(document.sections))).items()
            }
        )
        score = sum(weighted[token] * count for token, count in query_counts.items())
        ranked.append((score, metadata.document_id, document))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    hits: list[KnowledgeHit] = []
    for score, _, document in ranked[: request.top_k]:
        metadata = document.metadata
        hits.append(
            KnowledgeHit(
                document_id=metadata.document_id,
                title=document.title,
                document_type=metadata.document_type,
                service=metadata.service,
                version=metadata.version,
                updated_at=metadata.updated_at,
                uri=metadata.canonical_uri,
                section=document.sections[0] if document.sections else None,
                chunk_text=document.body[:2_000],
                relevance_score=min(1.0, score / 50) if score else 0.0,
                staleness_warning=(
                    "REVIEW_OVERDUE" if metadata.review_due_at < datetime.now(UTC) else None
                ),
                safety_flags=(["UNTRUSTED_INSTRUCTION_CONTENT"] if metadata.security_test else []),
            )
        )
    return hits


def build_search_filter(request: SearchKnowledgeInput) -> str:
    clauses: list[str] = []
    if request.service is not None:
        clauses.append(f'service: ANY("{request.service}")')
    if request.document_types:
        values = ", ".join(f'"{value}"' for value in request.document_types)
        clauses.append(f"document_type: ANY({values})")
    return " AND ".join(clauses)


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


def _operation_count(metadata: Mapping[str, Any], name: str) -> int:
    value = metadata.get(name, 0)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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
        document_metadata = chunk.get("documentMetadata")
        chunk_document_metadata = document_metadata if isinstance(document_metadata, dict) else {}
        chunk_struct_data = chunk_document_metadata.get("structData")
        document_struct_data = document.get("structData")
        metadata = (
            chunk_struct_data
            if isinstance(chunk_struct_data, dict)
            else document_struct_data
            if isinstance(document_struct_data, dict)
            else {}
        )
        derived_data = document.get("derivedStructData")
        derived = derived_data if isinstance(derived_data, dict) else {}
        document_id = (
            metadata.get("document_id")
            or raw_result.get("id")
            or chunk.get("id")
            or document.get("id")
        )
        title = (
            metadata.get("title") or chunk_document_metadata.get("title") or derived.get("title")
        )
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
        model_scores = raw_result.get("modelScores")
        raw_chunk_score = chunk.get("relevanceScore")
        relevance_score = (
            max(-1.0, min(1.0, float(raw_chunk_score)))
            if isinstance(raw_chunk_score, (int, float))
            else None
        )
        if relevance_score is None and isinstance(model_scores, dict):
            relevance = model_scores.get("relevance_score")
            if isinstance(relevance, dict):
                values = relevance.get("values")
                if isinstance(values, list) and values and isinstance(values[0], (int, float)):
                    relevance_score = max(-1.0, min(1.0, float(values[0])))
        review_due_at = _parse_datetime(metadata.get("review_due_at"))
        security_test = metadata.get("security_test") is True
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
                relevance_score=relevance_score,
                staleness_warning=(
                    "REVIEW_OVERDUE"
                    if review_due_at is not None and review_due_at < datetime.now(UTC)
                    else None
                ),
                safety_flags=["UNTRUSTED_INSTRUCTION_CONTENT"] if security_test else [],
            )
        )
    return hits


def run_local_smoke(root: Path | None = None) -> KnowledgeSmokeResult:
    documents = load_corpus(root)
    cases = load_smoke_cases(root)
    failed: list[str] = []
    citation_complete = True
    untrusted_content_flagged = False
    for case in cases:
        request = SearchKnowledgeInput(
            query=case.query,
            service=case.service,
            document_types=case.document_types,
            top_k=case.top_k,
        )
        hits = local_search(request, documents)
        if case.expected_document_id not in {hit.document_id for hit in hits}:
            failed.append(case.case_id)
        if case.expected_document_id == "SEC-001":
            untrusted_content_flagged = any(
                hit.document_id == "SEC-001" and "UNTRUSTED_INSTRUCTION_CONTENT" in hit.safety_flags
                for hit in hits
            )
        citation_complete = citation_complete and all(
            hit.document_id and hit.title and hit.uri and hit.section for hit in hits
        )
    return KnowledgeSmokeResult(
        backend="local",
        query_count=len(cases),
        executed_query_count=len(cases),
        passed_count=len(cases) - len(failed),
        failed_case_ids=failed,
        citation_metadata_complete=citation_complete,
        untrusted_content_flagged=untrusted_content_flagged,
    )


class KnowledgeCloudClient(Protocol):
    def read_snapshot(self) -> dict[str, str]: ...

    def upload_text(self, object_name: str, content: str) -> None: ...

    def import_documents(self, manifest_object: str) -> str: ...

    def wait_for_operation(self, operation_name: str) -> KnowledgeImportOutcome: ...

    def read_index_status(self, expected_document_ids: Sequence[str]) -> KnowledgeIndexStatus: ...


def _snapshot(documents: Sequence[KnowledgeDocument]) -> dict[str, str]:
    return {document.metadata.document_id: document.content_sha256 for document in documents}


def _manifest_jsonl(documents: Sequence[KnowledgeDocument], bucket_name: str) -> str:
    lines: list[str] = []
    for document in sorted(documents, key=lambda item: item.metadata.document_id):
        metadata = document.metadata.model_dump(mode="json")
        metadata["title"] = document.title
        metadata["section"] = document.sections[0] if document.sections else "Document"
        metadata["description"] = document.body[:2_000]
        payload = {
            "id": document.metadata.document_id.lower(),
            "structData": metadata,
            "content": {
                "mimeType": "text/plain",
                "uri": f"gs://{bucket_name}/documents/{document.metadata.document_id}.txt",
            },
        }
        lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def sync_knowledge(
    client: KnowledgeCloudClient,
    *,
    bucket_name: str,
    mode: KnowledgeSyncMode = "plan",
    root: Path | None = None,
) -> KnowledgeSyncResult:
    documents = load_corpus(root)
    desired = _snapshot(documents)
    current = client.read_snapshot()
    changed = sorted(key for key, value in desired.items() if current.get(key) != value)
    removed = sorted(set(current) - set(desired))
    no_op = not changed and not removed
    if mode == "plan" or no_op:
        return KnowledgeSyncResult(
            mode=mode,
            changed_document_count=len(changed),
            removed_document_count=len(removed),
            manifest_changed=not no_op,
            import_requested=False,
            snapshot_updated=False,
            no_op=no_op,
        )
    if os.environ.get("OPSPILOT_KNOWLEDGE_APPLY_ENABLED") != "true":
        raise RuntimeError("knowledge apply gate is disabled")
    by_id = {document.metadata.document_id: document for document in documents}
    for document_id in changed:
        document = by_id[document_id]
        client.upload_text(f"documents/{document_id}.txt", document.body)
    manifest_object = "manifests/import.jsonl"
    client.upload_text(manifest_object, _manifest_jsonl(documents, bucket_name))
    operation_name = client.import_documents(manifest_object)
    outcome = client.wait_for_operation(operation_name)
    if (
        not outcome.completed
        or outcome.success_count != len(documents)
        or outcome.failure_count != 0
        or outcome.total_count != len(documents)
    ):
        raise RuntimeError("knowledge import did not complete successfully")
    client.upload_text(
        "snapshots/current.json",
        json.dumps(desired, sort_keys=True, separators=(",", ":")) + "\n",
    )
    return KnowledgeSyncResult(
        mode=mode,
        changed_document_count=len(changed),
        removed_document_count=len(removed),
        manifest_changed=True,
        import_requested=True,
        import_success_count=outcome.success_count,
        import_failure_count=outcome.failure_count,
        snapshot_updated=True,
        no_op=False,
    )


@dataclass(frozen=True)
class _CloudContext:
    project_id: str
    project_number: str
    bucket_name: str
    location: str = "global"
    data_store_id: str = "opspilot-dev-knowledge"
    engine_id: str = "opspilot-dev-knowledge"


def _gcloud(arguments: Sequence[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    return subprocess.run(
        [executable, *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _cloud_context(environment: str) -> _CloudContext:
    if environment != "dev":
        raise ValueError("knowledge environment must be dev")
    project = _gcloud(("config", "get-value", "project")).stdout.strip()
    project_number = _gcloud(
        ("projects", "describe", project, "--format=value(projectNumber)")
    ).stdout.strip()
    if not project or not project_number:
        raise RuntimeError("default Google Cloud project is unavailable")
    return _CloudContext(
        project_id=project,
        project_number=project_number,
        bucket_name=f"opspilot-dev-knowledge-{project_number}",
    )


class GcloudKnowledgeClient:
    """Operator-only sync client. Its outputs are never surfaced by the CLI."""

    def __init__(self, context: _CloudContext) -> None:
        self.context = context

    def read_snapshot(self) -> dict[str, str]:
        result = _gcloud(
            (
                "storage",
                "cat",
                f"gs://{self.context.bucket_name}/snapshots/current.json",
            )
        )
        if result.returncode != 0 or not result.stdout:
            return {}
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def upload_text(self, object_name: str, content: str) -> None:
        with tempfile.TemporaryDirectory(prefix="opspilot-knowledge-") as directory:
            source = Path(directory) / "payload"
            source.write_text(content, encoding="utf-8", newline="\n")
            result = _gcloud(
                (
                    "storage",
                    "cp",
                    str(source),
                    f"gs://{self.context.bucket_name}/{object_name}",
                    "--quiet",
                ),
                timeout=120,
            )
        if result.returncode != 0:
            raise RuntimeError("knowledge object upload failed")

    def _token(self) -> str:
        token = _gcloud(("auth", "print-access-token")).stdout.strip()
        if not token:
            raise RuntimeError("Google user credential is unavailable")
        return token

    def _request(self, method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": self.context.project_id,
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("Agent Search request failed") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Agent Search returned an unexpected response")
        return payload

    def import_documents(self, manifest_object: str) -> str:
        context = self.context
        parent = (
            f"projects/{context.project_id}/locations/{context.location}/collections/"
            f"default_collection/dataStores/{context.data_store_id}/branches/default_branch"
        )
        payload = self._request(
            "POST",
            f"https://discoveryengine.googleapis.com/v1/{parent}/documents:import",
            {
                "gcsSource": {
                    "inputUris": [f"gs://{context.bucket_name}/{manifest_object}"],
                    "dataSchema": "document",
                },
                "reconciliationMode": "FULL",
            },
        )
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("Agent Search import operation was not created")
        return name

    def wait_for_operation(self, operation_name: str) -> KnowledgeImportOutcome:
        for _ in range(180):
            payload = self._request(
                "GET", f"https://discoveryengine.googleapis.com/v1/{operation_name}"
            )
            if payload.get("done") is True:
                metadata = payload.get("metadata")
                counts = metadata if isinstance(metadata, dict) else {}
                return KnowledgeImportOutcome(
                    success_count=_operation_count(counts, "successCount"),
                    failure_count=_operation_count(counts, "failureCount"),
                    total_count=_operation_count(counts, "totalCount"),
                    completed="error" not in payload,
                )
            time.sleep(10)
        raise RuntimeError("knowledge import did not finish within the bounded wait")

    def read_index_status(self, expected_document_ids: Sequence[str]) -> KnowledgeIndexStatus:
        context = self.context
        parent = (
            f"projects/{context.project_id}/locations/{context.location}/collections/"
            f"default_collection/dataStores/{context.data_store_id}/branches/default_branch"
        )
        payload = self._request(
            "GET",
            f"https://discoveryengine.googleapis.com/v1/{parent}/documents?pageSize=100",
        )
        raw_documents = payload.get("documents")
        documents = raw_documents if isinstance(raw_documents, list) else []
        observed_ids: set[str] = set()
        indexed_count = 0
        error_count = 0
        for raw_document in documents:
            if not isinstance(raw_document, dict):
                continue
            raw_id = raw_document.get("id")
            if isinstance(raw_id, str):
                observed_ids.add(raw_id.lower())
            if isinstance(raw_document.get("indexTime"), str):
                indexed_count += 1
            index_status = raw_document.get("indexStatus")
            status = index_status if isinstance(index_status, dict) else {}
            error_samples = status.get("errorSamples")
            if isinstance(error_samples, list) and error_samples:
                error_count += 1
        expected = {document_id.lower() for document_id in expected_document_ids}
        return KnowledgeIndexStatus(
            document_count=len(documents),
            indexed_count=indexed_count,
            error_count=error_count,
            exact_document_set=observed_ids == expected and "nextPageToken" not in payload,
        )

    def search(self, request: SearchKnowledgeInput) -> list[KnowledgeHit]:
        context = self.context
        serving_config = (
            f"projects/{context.project_id}/locations/{context.location}/collections/"
            f"default_collection/engines/{context.engine_id}/servingConfigs/default_search"
        )
        body: dict[str, Any] = {
            "query": request.query,
            "pageSize": request.top_k,
            "contentSearchSpec": {"searchResultMode": "CHUNKS"},
            "relevanceScoreSpec": {"returnRelevanceScore": True},
        }
        filter_value = build_search_filter(request)
        if filter_value:
            body["filter"] = filter_value
        payload = self._request(
            "POST",
            f"https://discoveryengine.googleapis.com/v1/{serving_config}:search",
            body,
        )
        return normalize_search_response(payload, request)


def run_agent_search_smoke(environment: str, root: Path | None = None) -> KnowledgeSmokeResult:
    if os.environ.get("OPSPILOT_KNOWLEDGE_SMOKE_ENABLED") != "true":
        raise RuntimeError("Agent Search smoke gate is disabled")
    cases = load_smoke_cases(root)
    documents = load_corpus(root)
    client = GcloudKnowledgeClient(_cloud_context(environment))
    index_status = client.read_index_status(
        [document.metadata.document_id for document in documents]
    )
    if not index_status.ready:
        return KnowledgeSmokeResult(
            backend="agent-search",
            query_count=len(cases),
            executed_query_count=0,
            passed_count=0,
            backend_ready=False,
            citation_metadata_complete=False,
            untrusted_content_flagged=False,
        )
    failed: list[str] = []
    citation_complete = True
    untrusted_content_flagged = False
    for case in cases:
        hits = client.search(
            SearchKnowledgeInput(
                query=case.query,
                service=case.service,
                document_types=case.document_types,
                top_k=case.top_k,
            )
        )
        if case.expected_document_id not in {hit.document_id for hit in hits}:
            failed.append(case.case_id)
        if case.expected_document_id == "SEC-001":
            untrusted_content_flagged = any(
                hit.document_id == "SEC-001" and "UNTRUSTED_INSTRUCTION_CONTENT" in hit.safety_flags
                for hit in hits
            )
        citation_complete = citation_complete and all(
            hit.document_id and hit.title and hit.uri and hit.section for hit in hits
        )
    return KnowledgeSmokeResult(
        backend="agent-search",
        query_count=len(cases),
        executed_query_count=len(cases),
        passed_count=len(cases) - len(failed),
        failed_case_ids=failed,
        citation_metadata_complete=citation_complete,
        untrusted_content_flagged=untrusted_content_flagged,
    )


def run_knowledge_sync(environment: str, mode: KnowledgeSyncMode) -> KnowledgeSyncResult:
    context = _cloud_context(environment)
    return sync_knowledge(
        GcloudKnowledgeClient(context),
        bucket_name=context.bucket_name,
        mode=mode,
    )


def render_knowledge_result(result: BaseModel) -> str:
    values = result.model_dump()
    lines: list[str] = []
    for key, value in values.items():
        if isinstance(value, bool):
            lines.append(f"{key}={str(value).lower()}")
        elif isinstance(value, list):
            lines.append(f"{key}={','.join(str(item) for item in value) if value else 'none'}")
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"
