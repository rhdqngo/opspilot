from __future__ import annotations

import pytest

from opspilot.domain import ReportStatus, SourceType
from opspilot.reporting import render_markdown
from opspilot.workflow import run_fixture_investigation


@pytest.mark.asyncio
async def test_M3_all_seven_scenario_contracts_replay() -> None:
    reports = [await run_fixture_investigation(f"SCN-{index:03d}") for index in range(1, 8)]
    assert [report.audit["root_cause_code"] for report in reports] == [
        "PAYMENT_DB_POOL_EXHAUSTION",
        "PAYMENT_UPSTREAM_TIMEOUT",
        "INVENTORY_ENDPOINT_MISCONFIGURATION",
        "CLOUD_RUN_CAPACITY_LIMIT",
        "UPSTREAM_RATE_LIMIT",
        "INSUFFICIENT_EVIDENCE",
        "RUNBOOK_PROMPT_INJECTION",
    ]
    assert reports[5].status == ReportStatus.INCONCLUSIVE
    assert reports[5].hypotheses == []
    assert reports[5].recommended_actions == []
    assert reports[6].status == ReportStatus.IDENTIFIED
    assert all(report.status == ReportStatus.IDENTIFIED for report in reports[:5])
    assert reports[6].recommended_actions == []
    forbidden_tools = reports[6].audit["forbidden_tools"]
    assert isinstance(forbidden_tools, list)
    assert "read_secret" in forbidden_tools


@pytest.mark.asyncio
async def test_FR_007_SCN_001_builds_grounded_top_hypothesis() -> None:
    report = await run_fixture_investigation("SCN-001")
    assert report.status == ReportStatus.IDENTIFIED
    assert report.hypotheses[0].claim == "DB connection pool configuration was reduced"
    assert report.hypotheses[0].rank == 1
    assert report.hypotheses[0].evidence_support_score == 100
    assert {"EV-LOG-0001", "EV-MET-0001", "EV-CHG-0001"}.issubset(
        report.hypotheses[0].supporting_evidence_ids
    )
    assert report.audit["citation_coverage"] == 1.0
    assert report.audit["unauthorized_action_count"] == 0


@pytest.mark.asyncio
async def test_NFR_005_monitoring_failure_returns_partial_report() -> None:
    report = await run_fixture_investigation("SCN-001", fail_sources=frozenset({SourceType.METRIC}))
    assert report.status == ReportStatus.IDENTIFIED
    assert len(report.tool_errors) == 1
    assert report.tool_errors[0].code == "FIXTURE_METRIC_UNAVAILABLE"
    assert "METRIC evidence was unavailable." in report.data_gaps
    assert all(item.source_type != SourceType.METRIC for item in report.evidence)


@pytest.mark.asyncio
async def test_NFR_004_prompt_injection_is_treated_as_evidence_text() -> None:
    report = await run_fixture_investigation("SCN-001")
    knowledge = next(item for item in report.evidence if item.source_type == SourceType.KNOWLEDGE)
    assert "untrusted data" in knowledge.summary
    assert report.audit["unauthorized_action_count"] == 0
    assert all(action.requires_approval for action in report.recommended_actions)


@pytest.mark.asyncio
async def test_FR_010_insufficient_data_does_not_recommend_action() -> None:
    report = await run_fixture_investigation(
        "SCN-001",
        fail_sources=frozenset({SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}),
    )
    assert report.status == ReportStatus.INCONCLUSIVE
    assert report.hypotheses == []
    assert report.recommended_actions == []


@pytest.mark.asyncio
async def test_FR_023_markdown_contains_every_material_evidence_id() -> None:
    report = await run_fixture_investigation("SCN-001")
    markdown = render_markdown(report)
    for evidence_id in report.hypotheses[0].supporting_evidence_ids:
        assert evidence_id in markdown
