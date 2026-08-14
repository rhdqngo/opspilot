from __future__ import annotations

from datetime import UTC, datetime

import pytest

from opspilot.domain import (
    Environment,
    EvidenceDirection,
    EvidenceItem,
    IncidentReport,
    OutputLanguage,
    ReportStatus,
    SourceType,
)
from opspilot.report_policy import add_prod_sim_rollback_request, apply_live_report_policy
from opspilot.reporting import render_markdown
from opspilot.workflow import run_fixture_investigation


def _live_inconclusive_report(*, include_metric: bool = True) -> IncidentReport:
    evidence = [
        EvidenceItem(
            evidence_id="EV-LOG-0001",
            source_type=SourceType.LOG,
            title="Cloud Run log signature",
            service="payment-service",
            summary="Synthetic payment pool acquisition failed.",
            value=6,
            direction=EvidenceDirection.UNKNOWN,
            quality_flags=["live_read_only", "redacted"],
        ),
        EvidenceItem(
            evidence_id="EV-KNW-0001",
            source_type=SourceType.KNOWLEDGE,
            title="Payment connection pool runbook",
            service="payment-service",
            summary="Review the bounded pool evidence.",
            direction=EvidenceDirection.UNKNOWN,
        ),
    ]
    if include_metric:
        evidence.append(
            EvidenceItem(
                evidence_id="EV-MET-0001",
                source_type=SourceType.METRIC,
                title="Cloud Run error_ratio",
                service="payment-service",
                summary="Observed bounded error-ratio points.",
                value=0.0,
                direction=EvidenceDirection.UNKNOWN,
                quality_flags=["live_read_only"],
            )
        )
    return IncidentReport(
        report_id="RPT-LIVE-001",
        report_version=1,
        incident_id="INC-2026-0001",
        generated_at=datetime.now(UTC),
        correlation_id="COR-LIVE",
        title="Bounded Multi-Service Investigation",
        severity="UNCLASSIFIED",
        severity_rationale="Evidence review is pending.",
        status=ReportStatus.INCONCLUSIVE,
        impact_summary="Impact review is pending.",
        executive_summary="No root cause is asserted.",
        affected_services=["payment-service"],
        evidence=evidence,
        audit={"execution_mode": "live-api", "model_calls": 0},
    )


def test_live_policy_identifies_only_direct_log_metric_conjunction() -> None:
    identified = apply_live_report_policy(_live_inconclusive_report())
    insufficient = apply_live_report_policy(_live_inconclusive_report(include_metric=False))

    assert identified.status is ReportStatus.IDENTIFIED
    assert [item.hypothesis_id for item in identified.hypotheses] == ["H-01", "H-02"]
    assert [item.category for item in identified.recommended_actions] == [
        "CONTAINMENT",
        "MITIGATION",
        "ROOT_FIX",
    ]
    evidence_ids = {item.evidence_id for item in identified.evidence}
    assert all(
        set(action.supporting_evidence_ids).issubset(evidence_ids)
        for action in identified.recommended_actions
    )
    assert identified.audit["model_calls"] == 0
    assert insufficient.status is ReportStatus.INCONCLUSIVE
    assert insufficient.hypotheses == []
    assert insufficient.recommended_actions == []


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
async def test_SCN_001_adds_safe_alternative_and_classified_grounded_actions() -> None:
    report = await run_fixture_investigation("SCN-001")
    assert [item.hypothesis_id for item in report.hypotheses] == ["H-01", "H-02"]
    assert report.hypotheses[0].evidence_support_score == 100
    assert report.hypotheses[1].evidence_support_score == 0
    assert report.hypotheses[1].status.value == "INSUFFICIENT_EVIDENCE"
    assert report.hypotheses[1].missing_evidence
    assert report.hypotheses[1].next_checks

    assert [item.category for item in report.recommended_actions] == [
        "CONTAINMENT",
        "MITIGATION",
        "ROOT_FIX",
    ]
    evidence_ids = {item.evidence_id for item in report.evidence}
    assert all(item.requires_approval for item in report.recommended_actions)
    assert all(
        item.supporting_evidence_ids and set(item.supporting_evidence_ids) <= evidence_ids
        for item in report.recommended_actions
    )
    markdown = render_markdown(report)
    assert report.hypotheses[1].missing_evidence[0] in markdown
    assert report.hypotheses[1].next_checks[0] in markdown
    assert "### Immediate containment" in markdown
    assert "### Bounded mitigation" in markdown
    assert "### Root fix or prevention" in markdown


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
    markdown = render_markdown(report)
    assert "## Root-cause hypotheses\n\n- None verified with the available evidence." in markdown
    knowledge_ids = {
        item.evidence_id for item in report.evidence if item.source_type == SourceType.KNOWLEDGE
    }
    assert knowledge_ids
    assert knowledge_ids.isdisjoint(
        evidence_id for event in report.timeline for evidence_id in event.evidence_ids
    )
    assert "Additional evidence is summarized by type: KNOWLEDGE: 1" in markdown
    assert "Ask a follow-up question to inspect omitted evidence." in markdown


@pytest.mark.asyncio
async def test_FR_023_markdown_contains_every_material_evidence_id() -> None:
    report = await run_fixture_investigation("SCN-001")
    markdown = render_markdown(report)
    for evidence_id in report.hypotheses[0].supporting_evidence_ids:
        assert evidence_id in markdown


@pytest.mark.asyncio
async def test_korean_markdown_localizes_structure_and_preserves_evidence_titles() -> None:
    report = await run_fixture_investigation(
        "SCN-001",
        fail_sources=frozenset({SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}),
    )

    markdown = render_markdown(report, language=OutputLanguage.KO)

    assert "## 요약" in markdown
    assert "## 타임라인" in markdown
    assert "## 근본 원인 가설" in markdown
    assert "- 사용 가능한 증거로 검증된 가설이 없습니다." in markdown
    assert "## 권장 조치" in markdown
    assert "- 사용 가능한 증거로 권장할 조치가 없습니다." in markdown
    assert "## 데이터 공백" in markdown
    assert "## 가정" in markdown
    assert "## 출처" in markdown
    assert "추가 증거 유형별 요약: KNOWLEDGE: 1" in markdown
    assert "생략된 증거는 후속 질문으로 확인할 수 있습니다." in markdown


@pytest.mark.asyncio
async def test_korean_markdown_localizes_canonical_hypotheses_actions_and_assumptions() -> None:
    report = await run_fixture_investigation(
        "SCN-001", assumptions=["No environment was specified; using dev."]
    )

    markdown = render_markdown(report, language=OutputLanguage.KO)

    assert "DB 연결 풀 구성이 축소되었습니다" in markdown
    assert "외부 결제 제공자 timeout 가능성은 확인되지 않았습니다" in markdown
    assert "### 즉시 조치" in markdown
    assert "### 완화 조치" in markdown
    assert "### 근본 개선" in markdown
    assert "환경이 지정되지 않아 DEV를 사용합니다." in markdown
    assert "No environment was specified" not in markdown


@pytest.mark.asyncio
async def test_only_prod_sim_payment_report_exposes_a_rollback_approval_request() -> None:
    report = await run_fixture_investigation("SCN-001")
    prod_sim = report.model_copy(update={"environment": Environment.PROD_SIM})
    candidate = add_prod_sim_rollback_request(prod_sim)

    rollback = [
        action
        for action in candidate.recommended_actions
        if action.category == "ROLLBACK_CLOUD_RUN"
    ]
    assert len(rollback) == 1
    assert rollback[0].requires_approval is True
    assert rollback[0].remediation_action_type == "ROLLBACK_CLOUD_RUN"
    assert add_prod_sim_rollback_request(report).recommended_actions == report.recommended_actions
