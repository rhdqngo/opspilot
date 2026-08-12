from __future__ import annotations

from collections import Counter
from typing import cast

import pytest
from google.adk.agents.context import Context

from opspilot.agent.contracts import (
    AgentBackend,
    HypothesisDraft,
    ModelBackend,
    ModelEvidence,
    ReviewInput,
)
from opspilot.agent.models import (
    MAX_MODEL_INPUT_BYTES,
    MODEL_DEADLINE_SECONDS,
    MODEL_NODE_TIMEOUT_SECONDS,
)
from opspilot.agent.runner import run_agent_eval, run_agent_investigation
from opspilot.agent.workflow import (
    canonicalize_verified_root_cause,
    create_root_agent,
    evidence_reviewer,
    graph_node_names,
)
from opspilot.domain import EvidenceDirection, ReportStatus, SourceType
from opspilot.evaluation import load_evaluation_suite
from opspilot.fixtures import load_scenario_fixture

EXPECTED_TRAJECTORY = [
    "prepare_bounded_evidence",
    "rca_analyst",
    "prepare_review",
    "evidence_reviewer",
    "verify_and_score",
    "report_composer",
    "finalize_report",
]


def test_agent_graph_keeps_only_two_bounded_tool_free_model_nodes() -> None:
    workflow = create_root_agent(use_fake_model=True)

    assert MODEL_NODE_TIMEOUT_SECONDS == 30.0
    assert MODEL_DEADLINE_SECONDS == 75
    assert graph_node_names(workflow) == ("__START__", *EXPECTED_TRAJECTORY)
    assert workflow.timeout == MODEL_DEADLINE_SECONDS
    assert workflow.max_concurrency == 1
    assert workflow.graph is not None
    model_nodes = [node for node in workflow.graph.nodes if hasattr(node, "tools")]
    assert len(model_nodes) == 2
    assert all(node.tools == [] for node in model_nodes)
    assert all(node.timeout == MODEL_NODE_TIMEOUT_SECONDS for node in model_nodes)


@pytest.mark.asyncio
async def test_fixture_agent_returns_canonical_grounded_report() -> None:
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.FAKE,
    )

    assert result.succeeded
    assert result.trajectory == EXPECTED_TRAJECTORY
    assert result.budget.model_calls == 2
    assert result.budget.attempted_model_calls == 2
    assert result.budget.successful_model_calls == 2
    assert result.budget.max_request_input_bytes <= MAX_MODEL_INPUT_BYTES
    assert result.report is not None
    assert result.report.audit["root_cause_code"] == "PAYMENT_DB_POOL_EXHAUSTION"
    assert "model_root_cause_code" not in result.report.audit
    assert "canonical_root_cause_code" not in result.report.audit
    assert result.report.audit["citation_coverage"] == 1.0
    assert result.report.audit["unauthorized_action_count"] == 0
    assert result.report.audit["run_id"] == result.run_id
    assert all(action.requires_approval for action in result.report.recommended_actions)
    assert all(event.event_type != SourceType.KNOWLEDGE.value for event in result.report.timeline)
    assert any(item.source_type == SourceType.KNOWLEDGE for item in result.report.evidence)


@pytest.mark.asyncio
async def test_fixture_evaluation_passes_all_seven_cases_with_fourteen_calls() -> None:
    result = await run_agent_eval()

    assert result.passed
    assert result.executed_case_count == 7
    assert result.passed_case_count == 7
    assert result.model_calls == 14
    assert result.suite == "core"
    assert result.suite_version == "core-v1"
    assert result.gate_failures == []


@pytest.mark.asyncio
async def test_portfolio_evaluation_passes_all_forty_versioned_cases() -> None:
    result = await run_agent_eval(suite="portfolio")

    assert result.passed
    assert result.executed_case_count == 40
    assert result.passed_case_count == 40
    assert result.model_calls == 80
    assert result.suite_version == "portfolio-v1"
    assert result.metrics.rca_top1_accuracy == 1.0
    assert result.metrics.rca_top3_accuracy == 1.0
    assert result.metrics.required_tool_recall == 1.0
    assert result.metrics.citation_coverage == 1.0
    assert result.metrics.evidence_id_validity == 1.0
    assert result.metrics.unauthorized_action_count == 0
    assert result.metrics.prompt_injection_success_count == 0
    assert result.duration_percentiles.p95_ms <= 45_000
    assert result.gate_failures == []


def test_portfolio_suite_keeps_the_reviewed_category_distribution() -> None:
    suite = load_evaluation_suite("portfolio")

    assert suite.suite_version == "portfolio-v1"
    assert Counter(case.category.value for case in suite.cases) == {
        "single_cause": 14,
        "multi_cause": 6,
        "no_incident": 4,
        "insufficient_data": 4,
        "prompt_injection": 4,
        "dependency_failure": 4,
        "replay_action_safety": 4,
    }


@pytest.mark.asyncio
async def test_partial_evidence_is_preserved_without_failing_the_run() -> None:
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.FAKE,
        fail_sources=frozenset({SourceType.METRIC}),
    )

    assert result.succeeded
    assert result.status.value == "partial"
    assert result.report is not None
    assert result.report.tool_errors
    assert result.report.data_gaps
    assert result.collection_trajectory == [
        "query_logs",
        "query_metric_series",
        "list_cloud_run_revisions",
        "search_knowledge",
    ]
    assert result.source_error_codes == {"METRIC": "FIXTURE_METRIC_UNAVAILABLE"}


@pytest.mark.asyncio
async def test_insufficient_and_prompt_injection_cases_create_no_actions() -> None:
    insufficient = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-006",
        model_backend=ModelBackend.FAKE,
    )
    malicious = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-007",
        model_backend=ModelBackend.FAKE,
    )

    assert insufficient.report is not None
    assert insufficient.report.status == ReportStatus.INCONCLUSIVE
    assert insufficient.report.hypotheses == []
    assert insufficient.report.recommended_actions == []
    assert malicious.report is not None
    assert malicious.report.audit["root_cause_code"] == "RUNBOOK_PROMPT_INJECTION"
    assert malicious.report.recommended_actions == []


def _review_context() -> Context:
    return cast(Context, object())


def test_reviewer_rejects_forged_missing_and_direction_mismatched_citations() -> None:
    evidence = [
        ModelEvidence(
            evidence_id="EV-LOG-0001",
            source_type="LOG",
            title="safe log",
            service="payment-service",
            summary="bounded error signature",
            direction=EvidenceDirection.SUPPORTS.value,
            source_uri="opspilot://evidence/log/1",
        ),
        ModelEvidence(
            evidence_id="EV-MET-0001",
            source_type="METRIC",
            title="safe metric",
            service="payment-service",
            summary="bounded contradiction",
            direction=EvidenceDirection.CONTRADICTS.value,
            source_uri="opspilot://evidence/metric/1",
        ),
    ]

    valid = HypothesisDraft(
        draft_id="D-01",
        root_cause_code="PAYMENT_DB_POOL_EXHAUSTION",
        claim="Database pool exhaustion",
        mechanism="Pool acquisition failures align with the incident.",
        affected_services=["payment-service"],
        supporting_evidence_ids=["EV-LOG-0001"],
        contradicting_evidence_ids=["EV-MET-0001"],
    )
    forged = valid.model_copy(
        update={"draft_id": "D-02", "supporting_evidence_ids": ["EV-LOG-9999"]}
    )
    mismatched = valid.model_copy(
        update={"draft_id": "D-03", "supporting_evidence_ids": ["EV-MET-0001"]}
    )
    reviews = evidence_reviewer(
        _review_context(), ReviewInput(evidence=evidence, drafts=[valid, forged, mismatched])
    )

    assert [review.decision for review in reviews.reviews] == ["ACCEPT", "REJECT", "REJECT"]


def test_verified_evidence_not_model_label_determines_product_taxonomy() -> None:
    fixture = load_scenario_fixture("SCN-001")
    resolved = canonicalize_verified_root_cause(
        "ARBITRARY_MODEL_LABEL",
        supporting_evidence=fixture.evidence,
        affected_services=[fixture.primary_service],
    )
    wrong_service = canonicalize_verified_root_cause(
        "ARBITRARY_MODEL_LABEL",
        supporting_evidence=fixture.evidence,
        affected_services=["inventory-service"],
    )
    contradiction_only = canonicalize_verified_root_cause(
        "ARBITRARY_MODEL_LABEL",
        supporting_evidence=[
            item.model_copy(update={"direction": EvidenceDirection.CONTRADICTS})
            for item in fixture.evidence
        ],
        affected_services=[fixture.primary_service],
    )

    assert resolved.canonical_root_cause_code == "PAYMENT_DB_POOL_EXHAUSTION"
    assert wrong_service.canonical_root_cause_code == "ARBITRARY_MODEL_LABEL"
    assert contradiction_only.canonical_root_cause_code == "ARBITRARY_MODEL_LABEL"
