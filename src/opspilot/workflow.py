"""Model-free, fixture-backed evidence workflow used by R0."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from opspilot.domain import (
    EvidenceDirection,
    IncidentReport,
    IncidentTimelineEvent,
    RecommendedAction,
    ReportStatus,
    RootCauseHypothesis,
    SourceType,
)
from opspilot.evidence import (
    EvidenceCollectionRequest,
    FixtureEvidenceClient,
    collect_evidence,
)
from opspilot.fixtures import load_scenario_fixture
from opspilot.scoring import calculate_evidence_support_score, status_for_score


async def run_fixture_investigation(
    scenario_id: str,
    *,
    correlation_id: str | None = None,
    fail_sources: frozenset[SourceType] = frozenset(),
    assumptions: list[str] | None = None,
) -> IncidentReport:
    fixture = load_scenario_fixture(scenario_id)
    end_time = datetime.now(UTC)
    collection = await collect_evidence(
        FixtureEvidenceClient(scenario_id, fail_sources=fail_sources),
        EvidenceCollectionRequest(
            scenario_id=scenario_id,
            start_time=end_time - timedelta(minutes=30),
            end_time=end_time,
            services=[fixture.primary_service],
        ),
    )
    evidence = collection.evidence
    tool_errors = collection.tool_errors
    collected_sources = {item.source_type for item in evidence}
    required_sources = set(fixture.required_evidence_types)
    missing_sources = sorted(source.value for source in required_sources - collected_sources)
    supporting = [item for item in evidence if item.direction == EvidenceDirection.SUPPORTS]
    contradicting = [item for item in evidence if item.direction == EvidenceDirection.CONTRADICTS]
    score = calculate_evidence_support_score(
        supporting,
        contradictions=len(contradicting),
        missing_required=len(missing_sources),
    )
    has_minimum = len(required_sources & collected_sources) >= fixture.minimum_evidence_count
    hypothesis_status = status_for_score(score, has_minimum_evidence=has_minimum)
    hypotheses: list[RootCauseHypothesis] = []
    actions: list[RecommendedAction] = []
    should_identify = (
        fixture.expected_report_status == ReportStatus.IDENTIFIED and has_minimum and score >= 25
    )
    if should_identify:
        hypotheses.append(
            RootCauseHypothesis(
                hypothesis_id="H-01",
                rank=1,
                claim=fixture.expected_root_cause,
                mechanism=fixture.mechanism,
                affected_services=[fixture.primary_service],
                supporting_evidence_ids=[item.evidence_id for item in supporting],
                contradicting_evidence_ids=[item.evidence_id for item in contradicting],
                missing_evidence=[f"Missing {source} evidence" for source in missing_sources],
                next_checks=fixture.next_checks,
                evidence_support_score=score,
                status=hypothesis_status,
            )
        )
        if score >= 45 and fixture.action is not None:
            action = fixture.action
            actions.append(
                RecommendedAction(
                    action_id="ACT-01",
                    category=action.category,
                    title=action.title,
                    description=action.description,
                    target_service=action.target_service or fixture.primary_service,
                    risk_level=action.risk_level,
                    requires_approval=action.requires_approval,
                    prerequisites=action.prerequisites,
                    expected_effect=action.expected_effect,
                    rollback_method=action.rollback_method,
                    verification_steps=action.verification_steps,
                    supporting_evidence_ids=[item.evidence_id for item in supporting],
                )
            )
    timeline = [
        IncidentTimelineEvent(
            timestamp=item.observed_at or item.period_start or datetime.now(UTC),
            event_type=item.source_type.value,
            title=item.title,
            description=item.summary,
            service=item.service,
            evidence_ids=[item.evidence_id],
        )
        for item in evidence
        if item.source_type in {SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}
        and (item.observed_at is not None or item.period_start is not None)
    ]
    is_identified = bool(hypotheses) and score >= 45
    return IncidentReport(
        report_id=f"RPT-{fixture.scenario_id}-001",
        report_version=1,
        incident_id=fixture.incident_id,
        generated_at=datetime.now(UTC),
        correlation_id=correlation_id or f"COR-{uuid4().hex[:16].upper()}",
        title=fixture.title,
        severity="SEV-2" if is_identified else "UNCLASSIFIED",
        severity_rationale=(
            f"Synthetic evidence supports {fixture.root_cause_code}."
            if is_identified
            else "The available fixture evidence is insufficient to assign severity."
        ),
        status=ReportStatus.IDENTIFIED if is_identified else ReportStatus.INCONCLUSIVE,
        impact_summary=(fixture.impact_summary if is_identified else "Impact is inconclusive."),
        executive_summary=(
            f"The leading hypothesis is {fixture.expected_root_cause}, supported by "
            f"{len(supporting)} evidence items with an evidence support score of {score}/100."
            if is_identified
            else "No root cause can be confirmed with the available evidence."
        ),
        affected_services=[fixture.primary_service] if is_identified else [],
        timeline=timeline,
        hypotheses=hypotheses,
        evidence=evidence,
        recommended_actions=actions,
        data_gaps=[f"{source} evidence was unavailable." for source in missing_sources],
        assumptions=list(assumptions or []),
        tool_errors=tool_errors,
        approval_status=None,
        audit={
            "execution_mode": "fixture",
            "tool_calls": collection.budget.logical_tool_calls,
            "citation_coverage": 1.0,
            "unauthorized_action_count": 0,
            "scenario_id": scenario_id,
            "root_cause_code": fixture.root_cause_code,
            "expected_tools": fixture.expected_tools_any_order,
            "forbidden_tools": fixture.forbidden_tools,
        },
    )
