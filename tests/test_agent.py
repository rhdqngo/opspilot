from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

import pytest
from google.adk.agents.context import Context
from google.adk.models.llm_request import LlmRequest
from google.genai import types

from opspilot.access_check import AccessCheckResult, CommandResult
from opspilot.agent.contracts import (
    AgentBackend,
    AgentErrorCategory,
    HypothesisDraft,
    HypothesisDraftBatch,
    HypothesisReview,
    HypothesisReviewBatch,
    ModelBackend,
)
from opspilot.agent.diagnostics import render_agent_diagnostic, run_agent_diagnostic
from opspilot.agent.models import (
    MAX_MODEL_INPUT_BYTES,
    MODEL_DEADLINE_SECONDS,
    MODEL_NODE_TIMEOUT_SECONDS,
)
from opspilot.agent.runner import (
    _safe_error,
    render_agent_acceptance,
    render_agent_result,
    run_agent_acceptance,
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
    assert result.budget.attempted_model_calls == 3
    assert result.budget.successful_model_calls == 3
    assert result.budget.request_input_bytes > 0
    assert result.budget.max_request_input_bytes <= MAX_MODEL_INPUT_BYTES
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
async def test_M6_core_acceptance_is_fixed_to_three_cases_and_nine_calls() -> None:
    result = await run_agent_acceptance(model_backend=ModelBackend.FAKE)

    assert result.passed
    assert [case.scenario_id for case in result.cases] == ["SCN-001", "SCN-006", "SCN-007"]
    assert result.executed_case_count == 3
    assert result.passed_case_count == 3
    assert result.attempted_model_calls == 9
    assert result.successful_model_calls == 9
    assert all(case.budget.attempted_model_calls == 3 for case in result.cases)
    assert "attempted_model_calls: 9" in render_agent_acceptance(result, "summary")


@pytest.mark.asyncio
async def test_M6_core_acceptance_stops_after_first_failed_case_without_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPSPILOT_LIVE_MODEL_ENABLED", raising=False)

    result = await run_agent_acceptance(model_backend=ModelBackend.VERTEX)

    assert not result.passed
    assert result.executed_case_count == 1
    assert result.attempted_model_calls == 0
    assert result.cases[0].errors[0].code == "AGENT_GATE_DISABLED"
    assert "SCN-001_error: AGENT_GATE_DISABLED" in render_agent_acceptance(result, "summary")


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


@pytest.mark.asyncio
async def test_M6_vertex_backend_rejects_unapproved_model_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPSPILOT_LIVE_MODEL_ENABLED", "true")
    monkeypatch.setenv("OPSPILOT_MODEL_ID", "gemini-unapproved")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "secret-project")

    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.VERTEX,
    )

    assert not result.succeeded
    assert result.budget.attempted_model_calls == 0
    assert result.errors[0].code == "AGENT_MODEL_NOT_ALLOWED"
    assert "secret-project" not in render_agent_result(result, "json")


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


def test_M6_vertex_errors_are_classified_without_raw_details() -> None:
    class VertexFailure(RuntimeError):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    expected = {
        401: "AGENT_AUTH",
        403: "AGENT_AUTH",
        404: "AGENT_MODEL_NOT_FOUND",
        429: "AGENT_QUOTA",
        500: "AGENT_UPSTREAM",
        503: "AGENT_UPSTREAM",
    }
    for status, code in expected.items():
        error = _safe_error(VertexFailure(status, "projects/secret token raw upstream detail"))
        assert error.code == code
        serialized = error.model_dump_json().casefold()
        assert "projects/" not in serialized
        assert "token" not in serialized

    safety = _safe_error(RuntimeError("response blocked by safety filters"))
    assert safety.code == "AGENT_SAFETY_BLOCKED"


def test_M6_diagnostic_is_zero_generation_and_redacted() -> None:
    access = AccessCheckResult(
        account_alias_match=True,
        user_credentials=True,
        application_default_credentials=True,
        default_project_configured=True,
        project_active=True,
        project_confirmed=True,
        billing_enabled=True,
        billing_currency_krw_confirmed=True,
    )

    def access_checker(**_kwargs: object) -> AccessCheckResult:
        return access

    def runner(arguments: Sequence[str]) -> CommandResult:
        if arguments[:3] == ("config", "get-value", "project"):
            return CommandResult(0, "secret-project")
        if arguments[:3] == ("auth", "print-access-token"):
            return CommandResult(0, "secret-token")
        if arguments[:3] == ("services", "list", "--enabled"):
            return CommandResult(0, "aiplatform.googleapis.com")
        return CommandResult(1, "")

    def requester(
        token: str, url: str, body: dict[str, object] | None, quota_project: str
    ) -> dict[str, object]:
        assert token == "secret-token"
        assert "secret-project" in url
        assert quota_project == "secret-project"
        assert body is not None
        return {"permissions": ["aiplatform.endpoints.predict", "serviceusage.services.use"]}

    result = run_agent_diagnostic(
        account_alias="Edu_687",
        access_checker=access_checker,
        runner=runner,
        requester=requester,
    )

    assert result.model_ready
    assert result.generate_content_calls == 0
    output = result.model_dump_json() + render_agent_diagnostic(result)
    assert "secret-project" not in output
    assert "secret-token" not in output
    assert "googleapis.com" not in output


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
