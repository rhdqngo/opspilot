from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from opspilot.domain import (
    EvidenceDirection,
    EvidenceItem,
    IncidentReport,
    InvestigationRequest,
    SourceType,
    ToolMeta,
    ToolResult,
)
from opspilot.scoring import calculate_evidence_support_score, status_for_score


def test_FR_002_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        InvestigationRequest(
            user_query="analyze payment-service errors",
            services=["payment-service"],
            start_time=datetime(2026, 8, 10, 4, 0),
            end_time=datetime(2026, 8, 10, 4, 30),
        )


def test_FR_003_rejects_time_window_over_two_hours() -> None:
    start = datetime(2026, 8, 10, 4, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="cannot exceed 2 hours"):
        InvestigationRequest(
            user_query="analyze payment-service errors",
            services=["payment-service"],
            start_time=start,
            end_time=start + timedelta(hours=3),
        )


def test_NFR_020_tool_result_requires_consistent_error_shape() -> None:
    now = datetime.now(UTC)
    meta = ToolMeta(
        tool_name="fixture_log",
        request_id="TOOL-1",
        started_at=now,
        finished_at=now,
        duration_ms=0,
        source_project="synthetic-fixture",
    )
    with pytest.raises(ValidationError, match="requires data"):
        ToolResult[list[str]](ok=True, meta=meta)


def test_NFR_019_support_score_is_deterministic() -> None:
    item = EvidenceItem(
        evidence_id="EV-LOG-0001",
        source_type=SourceType.LOG,
        title="signature",
        summary="fixture",
        direction=EvidenceDirection.SUPPORTS,
        quality_flags=["direct_error_signature_match", "metric_log_agreement"],
    )
    score = calculate_evidence_support_score([item], contradictions=1, missing_required=1)
    assert score == 20
    assert status_for_score(score, has_minimum_evidence=True).value == "INSUFFICIENT_EVIDENCE"


def test_FR_010_report_rejects_forged_evidence_reference() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="unknown evidence references"):
        IncidentReport.model_validate(
            {
                "report_id": "RPT-1",
                "report_version": 1,
                "incident_id": "INC-2026-0001",
                "generated_at": now,
                "correlation_id": "COR-1",
                "title": "fixture",
                "severity": "UNCLASSIFIED",
                "severity_rationale": "fixture",
                "status": "INCONCLUSIVE",
                "impact_summary": "fixture",
                "executive_summary": "fixture",
                "timeline": [
                    {
                        "timestamp": now,
                        "event_type": "LOG",
                        "title": "forged",
                        "description": "fixture",
                        "evidence_ids": ["EV-LOG-9999"],
                    }
                ],
            }
        )
