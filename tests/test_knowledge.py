from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from opspilot.knowledge import (
    MAX_CHUNK_BYTES,
    KnowledgeImportOutcome,
    KnowledgeIndexStatus,
    SearchKnowledgeInput,
    build_agent_search_request,
    build_search_filter,
    catalog_jsonl,
    load_corpus,
    load_knowledge_document,
    normalize_search_response,
    run_local_smoke,
    sync_knowledge,
    validate_knowledge,
)


class FakeKnowledgeCloud:
    def __init__(self, snapshot: dict[str, str] | None = None, *, import_ok: bool = True) -> None:
        self.snapshot = snapshot or {}
        self.import_ok = import_ok
        self.uploads: dict[str, str] = {}

    def read_snapshot(self) -> dict[str, str]:
        return dict(self.snapshot)

    def upload_text(self, object_name: str, content: str) -> None:
        self.uploads[object_name] = content

    def import_documents(self, manifest_object: str) -> str:
        assert manifest_object == "manifests/import.jsonl"
        return "operations/synthetic"

    def wait_for_operation(self, operation_name: str) -> KnowledgeImportOutcome:
        assert operation_name == "operations/synthetic"
        return KnowledgeImportOutcome(
            success_count=13 if self.import_ok else 12,
            failure_count=0 if self.import_ok else 1,
            total_count=13,
            completed=True,
        )

    def read_index_status(self, expected_document_ids: Sequence[str]) -> KnowledgeIndexStatus:
        return KnowledgeIndexStatus(
            document_count=len(expected_document_ids),
            indexed_count=len(expected_document_ids),
            error_count=0,
            exact_document_set=True,
        )


def test_corpus_has_deterministic_catalog_and_ten_queries() -> None:
    result = validate_knowledge()
    documents = load_corpus()
    first = catalog_jsonl(documents)
    second = catalog_jsonl(load_corpus())

    assert result.valid
    assert result.document_count == 13
    assert result.query_count == 10
    assert first == second
    assert "gs://" not in first


def test_corpus_rejects_naive_frontmatter_datetime(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text(
        """---
document_id: RB-BAD-001
document_type: runbook
service: payment-service
version: '1.0'
owner: opspilot
updated_at: '2026-01-01T00:00:00'
review_due_at: '2027-01-01T00:00:00Z'
canonical_uri: opspilot://knowledge/RB-BAD-001
tags: [bad]
---
# Bad
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_knowledge_document(path, tmp_path)


def test_local_smoke_finds_all_documents_and_flags_untrusted_content() -> None:
    result = run_local_smoke()

    assert result.passed
    assert result.query_count == 10
    assert result.passed_count == 10
    assert result.untrusted_content_flagged
    assert not result.untrusted_instruction_executed


def test_search_filter_is_built_only_from_allowlisted_fields() -> None:
    request = SearchKnowledgeInput(
        query="database timeout", service="payment-service", document_types=["runbook"]
    )

    assert (
        build_search_filter(request)
        == 'service: ANY("payment-service") AND document_type: ANY("runbook")'
    )
    body = build_agent_search_request(request)
    assert body["query"] == "database timeout"
    assert body["pageSize"] == 6
    assert "database timeout" not in str(body["filter"])
    with pytest.raises(ValidationError):
        SearchKnowledgeInput(query="valid query", service='payment-service") OR true')


def test_search_normalizer_bounds_content_and_uses_logical_uri() -> None:
    request = SearchKnowledgeInput(query="database timeout", top_k=2)
    payload = {
        "results": [
            {
                "chunk": {
                    "content": "x" * (MAX_CHUNK_BYTES + 100),
                    "relevanceScore": 0.5,
                    "documentMetadata": {
                        "structData": {
                            "document_id": "RB-PAY-001",
                            "title": "Payment pool",
                            "document_type": "runbook",
                            "service": "payment-service",
                            "canonical_uri": "opspilot://knowledge/RB-PAY-001",
                            "section": "Symptoms",
                        }
                    },
                }
            }
        ]
    }

    hits = normalize_search_response(payload, request)

    assert len(hits) == 1
    assert len(hits[0].chunk_text.encode()) == MAX_CHUNK_BYTES
    assert hits[0].uri == "opspilot://knowledge/RB-PAY-001"


def test_sync_is_idempotent_and_updates_snapshot_only_after_full_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    desired = {item.metadata.document_id: item.content_sha256 for item in load_corpus()}
    no_op = sync_knowledge(FakeKnowledgeCloud(desired), bucket_name="synthetic-bucket", mode="plan")
    assert no_op.no_op

    monkeypatch.setenv("OPSPILOT_KNOWLEDGE_APPLY_ENABLED", "true")
    failed = FakeKnowledgeCloud(import_ok=False)
    with pytest.raises(RuntimeError, match="did not complete"):
        sync_knowledge(failed, bucket_name="synthetic-bucket", mode="apply")
    assert "snapshots/current.json" not in failed.uploads

    successful = FakeKnowledgeCloud()
    result = sync_knowledge(successful, bucket_name="synthetic-bucket", mode="apply")
    assert result.import_success_count == 13
    assert result.snapshot_updated
    assert len(successful.uploads) == 15
