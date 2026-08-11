from __future__ import annotations

import json
from typing import cast

import pytest
from google.adk.agents.context import Context
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from opspilot.agent.contracts import (
    AgentBackend,
    AgentErrorCategory,
    HypothesisDraft,
    HypothesisDraftBatch,
    HypothesisReview,
    HypothesisReviewBatch,
    ModelBackend,
)
from opspilot.agent.models import (
    MAX_MODEL_INPUT_BYTES,
    MODEL_DEADLINE_SECONDS,
    MODEL_NODE_TIMEOUT_SECONDS,
)
from opspilot.agent.runner import (
    render_agent_result,
    run_agent_eval,
    run_agent_investigation,
)
from opspilot.agent.workflow import (
    _safe_action,
    create_root_agent,
    graph_node_names,
    validate_model_request,
    verify_and_score,
)
from opspilot.domain import ReportStatus, SourceType
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


def test_M6_graph_is_bounded_and_contains_no_tools() -> None:
    workflow = create_root_agent(use_fake_model=True)

    assert graph_node_names(workflow) == ("__START__", *EXPECTED_TRAJECTORY)
    assert workflow.timeout == MODEL_DEADLINE_SECONDS
    assert workflow.max_concurrency == 1
    assert workflow.graph is not None
    model_nodes = [node for node in workflow.graph.nodes if hasattr(node, "tools")]
    assert len(model_nodes) == 3
    assert all(node.tools == [] for node in model_nodes)
    assert all(node.timeout == MODEL_NODE_TIMEOUT_SECONDS for node in model_nodes)


@pytest.mark.asyncio
async def test_M6_fake_agent_runs_three_model_nodes_and_keeps_citations_grounded() -> None:
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.FAKE,
    )

    assert result.succeeded
    assert result.trajectory == EXPECTED_TRAJECTORY
    assert result.budget.model_calls == 3
    assert result.budget.input_bytes <= MAX_MODEL_INPUT_BYTES
    assert result.report is not None
    assert result.report.audit["root_cause_code"] == "PAYMENT_DB_POOL_EXHAUSTION"
    assert result.report.audit["citation_coverage"] == 1.0
    assert result.report.audit["unauthorized_action_count"] == 0
    assert all(action.requires_approval for action in result.report.recommended_actions)
    assert all(
        item.source_uri is None or item.source_uri.startswith("opspilot://")
        for item in result.report.evidence
    )


@pytest.mark.asyncio
async def test_M6_offline_eval_passes_all_seven_fixtures() -> None:
    result = await run_agent_eval(model_backend=ModelBackend.FAKE)

    assert result.passed
    assert result.executed_case_count == 7
    assert result.passed_case_count == 7
    assert result.model_calls == 21


@pytest.mark.asyncio
async def test_M6_inconclusive_and_prompt_injection_cases_do_not_create_actions() -> None:
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


@pytest.mark.asyncio
async def test_M6_partial_evidence_produces_a_partial_report() -> None:
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.FAKE,
        fail_sources=frozenset({SourceType.METRIC}),
    )

    assert result.succeeded
    assert result.status.value == "partial"
    assert result.report is not None
    assert result.report.tool_errors[0].code == "FIXTURE_METRIC_UNAVAILABLE"
    assert "METRIC evidence was unavailable." in result.report.data_gaps


@pytest.mark.asyncio
async def test_M6_vertex_backend_is_fail_closed_without_live_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPSPILOT_LIVE_MODEL_ENABLED", raising=False)
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.VERTEX,
    )

    assert not result.succeeded
    assert result.budget.model_calls == 0
    assert result.errors[0].category == AgentErrorCategory.VALIDATION
    assert result.errors[0].code == "AGENT_GATE_DISABLED"
    assert "project" not in result.errors[0].safe_message.casefold()


def test_M6_model_request_rejects_cloud_identifiers_and_oversized_input() -> None:
    cloud_request = LlmRequest(
        contents=[types.Content(parts=[types.Part(text="projects/example/locations/global")])]
    )
    with pytest.raises(ValueError, match="prohibited cloud identifier"):
        validate_model_request(cast(Context, object()), cloud_request)

    oversized = LlmRequest(
        contents=[types.Content(parts=[types.Part(text="x" * (MAX_MODEL_INPUT_BYTES + 1))])]
    )
    with pytest.raises(ValueError, match="fixed byte budget"):
        validate_model_request(cast(Context, object()), oversized)


def test_M6_deterministic_verifier_rejects_forged_evidence() -> None:
    fixture = load_scenario_fixture("SCN-001")

    class StubContext:
        state: dict[str, object]

        def __init__(self) -> None:
            self.state = {
                "agent_context": {
                    "scenario_id": fixture.scenario_id,
                    "incident_id": fixture.incident_id,
                    "generated_at": fixture.evidence[0].observed_at,
                    "correlation_id": "COR-REDACTED000001",
                    "evidence": [item.model_dump(mode="json") for item in fixture.evidence],
                },
                "hypothesis_drafts": HypothesisDraftBatch(
                    drafts=[
                        HypothesisDraft(
                            draft_id="D-01",
                            root_cause_code="FORGED_CAUSE",
                            claim="A forged cause was supplied",
                            mechanism="The citation does not exist in trusted evidence.",
                            affected_services=[fixture.primary_service],
                            supporting_evidence_ids=["EV-LOG-9999"],
                        )
                    ]
                ).model_dump(mode="json"),
            }

    output = verify_and_score(
        cast(Context, StubContext()),
        HypothesisReviewBatch(
            reviews=[
                HypothesisReview(
                    draft_id="D-01",
                    decision="ACCEPT",
                    rationale="The untrusted draft requested acceptance.",
                )
            ]
        ),
    )

    assert output["verified_hypotheses"] == []


def test_M6_unsafe_recommendations_are_filtered() -> None:
    from opspilot.agent.contracts import RecommendationDraft

    draft = RecommendationDraft(
        category="MITIGATION",
        title="Run a command",
        description="Use gcloud to update the service.",
        target_service="payment",
        expected_effect="Change production state.",
        supporting_evidence_ids=["EV-LOG-0001"],
    )
    assert not _safe_action(
        draft,
        known_evidence={"EV-LOG-0001"},
        known_services={"payment"},
    )


@pytest.mark.asyncio
async def test_M6_public_json_does_not_expose_cloud_or_transport_inputs() -> None:
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.FAKE,
    )
    output = render_agent_result(result, "json")
    parsed = json.loads(output)

    assert parsed["succeeded"] is True
    lowered = output.casefold()
    for prohibited in (
        "authorization",
        "bearer ",
        "googleapis.com",
        "run.app",
        "projects/",
        "logging filter",
    ):
        assert prohibited not in lowered
