"""Execute the bounded ADK graph over fixture or live evidence."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from google.adk.runners import InMemoryRunner
from google.genai import types

from opspilot.agent.contracts import (
    AgentBackend,
    AgentErrorCategory,
    AgentEvalCaseResult,
    AgentEvalResult,
    AgentEvidenceContext,
    AgentRunError,
    AgentRunResult,
    AgentRunStatus,
    ModelBackend,
    ModelBudgetUsage,
)
from opspilot.agent.models import (
    DEFAULT_MODEL_ID,
    MAX_MODEL_INPUT_BYTES,
    MODEL_DEADLINE_SECONDS,
)
from opspilot.agent.workflow import create_root_agent
from opspilot.domain import IncidentReport, ReportStatus, SourceType
from opspilot.evidence import (
    EvidenceBackend,
    EvidenceCollectionRequest,
    FixtureEvidenceClient,
    collect_evidence,
    run_evidence_smoke,
)
from opspilot.fixtures import load_scenario_fixture
from opspilot.reporting import render_markdown

APP_NAME = "opspilot"
MODEL_NODE_NAMES = frozenset({"rca_analyst", "evidence_reviewer", "report_composer"})
EXPECTED_ROOT_CAUSES = {
    "SCN-001": "PAYMENT_DB_POOL_EXHAUSTION",
    "SCN-002": "PAYMENT_UPSTREAM_TIMEOUT",
    "SCN-003": "INVENTORY_ENDPOINT_MISCONFIGURATION",
    "SCN-004": "CLOUD_RUN_CAPACITY_LIMIT",
    "SCN-005": "UPSTREAM_RATE_LIMIT",
    "SCN-006": "INSUFFICIENT_EVIDENCE",
    "SCN-007": "RUNBOOK_PROMPT_INJECTION",
}


def _safe_error(error: Exception) -> AgentRunError:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    if "timeout" in name or "timeout" in message or "deadline" in message:
        return AgentRunError(
            code="AGENT_TIMEOUT",
            category=AgentErrorCategory.TIMEOUT,
            safe_message="The bounded agent run exceeded its time limit.",
            retryable=False,
        )
    if "auth" in name or "credential" in message or "permission" in message:
        return AgentRunError(
            code="AGENT_AUTH",
            category=AgentErrorCategory.AUTH,
            safe_message="The model credential or permission check failed.",
            retryable=False,
        )
    if "quota" in message or "429" in message:
        return AgentRunError(
            code="AGENT_QUOTA",
            category=AgentErrorCategory.QUOTA,
            safe_message="The model quota boundary rejected the request.",
            retryable=False,
        )
    if "gate" in message or "disabled" in message:
        return AgentRunError(
            code="AGENT_GATE_DISABLED",
            category=AgentErrorCategory.VALIDATION,
            safe_message="The live model gate is disabled.",
            retryable=False,
        )
    if "validation" in name or "invalid" in message or "json" in message:
        return AgentRunError(
            code="AGENT_INVALID_RESPONSE",
            category=AgentErrorCategory.INVALID_RESPONSE,
            safe_message="The model returned an invalid structured response.",
            retryable=False,
        )
    return AgentRunError(
        code="AGENT_INTERNAL",
        category=AgentErrorCategory.INTERNAL,
        safe_message="The bounded agent run failed safely.",
        retryable=False,
    )


def _gcloud_default_project() -> str:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    try:
        completed = subprocess.run(
            [executable, "config", "get-value", "project"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _prepare_vertex_environment() -> str:
    if os.environ.get("OPSPILOT_LIVE_MODEL_ENABLED") != "true":
        raise RuntimeError("live model gate is disabled")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or _gcloud_default_project()
    if not project_id:
        raise RuntimeError("default Google Cloud project is unavailable")
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    return os.environ.get("OPSPILOT_MODEL_ID", DEFAULT_MODEL_ID)


def _trajectory_name(path: str) -> str:
    segment = path.rsplit("/", maxsplit=1)[-1]
    return segment.split("@", maxsplit=1)[0]


async def _execute_graph(
    context: AgentEvidenceContext,
    *,
    model_backend: ModelBackend,
) -> tuple[IncidentReport, list[str], ModelBudgetUsage]:
    model_id = DEFAULT_MODEL_ID
    if model_backend == ModelBackend.VERTEX:
        model_id = _prepare_vertex_environment()
    workflow = create_root_agent(
        model_id=model_id,
        use_fake_model=model_backend == ModelBackend.FAKE,
    )
    runner = InMemoryRunner(node=workflow, app_name=APP_NAME)
    user_id = "local-operator"
    session_id = f"session-{uuid4().hex}"
    await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
        state={"model_id": model_id},
    )
    serialized = context.model_dump_json()
    input_bytes = len(serialized.encode("utf-8"))
    if input_bytes > MAX_MODEL_INPUT_BYTES:
        raise ValueError("agent context exceeds the fixed byte budget")
    trajectory: list[str] = []
    report: IncidentReport | None = None
    model_calls = prompt_tokens = output_tokens = total_tokens = 0
    adk_logger = logging.getLogger("google.adk")
    previous_level = adk_logger.level
    adk_logger.setLevel(logging.CRITICAL)
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=serialized)]),
        ):
            name = _trajectory_name(event.node_info.path)
            if not trajectory or trajectory[-1] != name:
                trajectory.append(name)
            if name in MODEL_NODE_NAMES and event.content is not None:
                model_calls += 1
            usage = event.usage_metadata
            if usage is not None:
                prompt_tokens += int(usage.prompt_token_count or 0)
                output_tokens += int(usage.candidates_token_count or 0)
                total_tokens += int(usage.total_token_count or 0)
            if event.output is not None and name == "finalize_report":
                report = IncidentReport.model_validate(event.output)
            elif name == "finalize_report" and event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    report = IncidentReport.model_validate_json(text)
    finally:
        adk_logger.setLevel(previous_level)
    if report is None:
        raise ValueError("agent graph did not produce a report")
    return (
        report,
        trajectory,
        ModelBudgetUsage(
            model_calls=model_calls,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_bytes=input_bytes,
            truncated=False,
            deadline_seconds=MODEL_DEADLINE_SECONDS,
        ),
    )


async def run_agent_investigation(
    *,
    backend: AgentBackend,
    scenario_id: str,
    model_backend: ModelBackend,
    environment: str = "dev",
    now: datetime | None = None,
    fail_sources: frozenset[SourceType] = frozenset(),
) -> AgentRunResult:
    """Collect evidence and execute the ADK graph with safe failure output."""

    try:
        if backend == AgentBackend.LIVE and scenario_id != "SCN-001":
            raise ValueError("live agent evidence is limited to SCN-001")
        if backend == AgentBackend.LIVE and fail_sources:
            raise ValueError("live agent evidence cannot inject fixture failures")
        if model_backend == ModelBackend.VERTEX:
            _prepare_vertex_environment()
        fixture = load_scenario_fixture(scenario_id)
        if backend == AgentBackend.FIXTURE and fail_sources:
            end_time = now or datetime.now(UTC)
            collection = await collect_evidence(
                FixtureEvidenceClient(scenario_id, fail_sources=fail_sources),
                EvidenceCollectionRequest(
                    scenario_id=scenario_id,
                    environment=environment,
                    start_time=end_time - timedelta(minutes=30),
                    end_time=end_time,
                    services=[fixture.primary_service],
                ),
            )
        else:
            collection = await run_evidence_smoke(
                backend=EvidenceBackend(backend.value),
                scenario_id=scenario_id,
                environment=environment,
                now=now,
            )
        context = AgentEvidenceContext(
            scenario_id=scenario_id,
            incident_id=fixture.incident_id,
            generated_at=now or datetime.now(UTC),
            correlation_id=f"COR-{uuid4().hex[:16].upper()}",
            evidence=collection.evidence,
            tool_errors=collection.tool_errors,
            data_gaps=collection.data_gaps,
            assumptions=[],
        )
        report, trajectory, budget = await _execute_graph(
            context,
            model_backend=model_backend,
        )
        return AgentRunResult(
            status=(AgentRunStatus.COMPLETE if collection.complete else AgentRunStatus.PARTIAL),
            succeeded=True,
            backend=backend,
            model_backend=model_backend,
            report=report,
            trajectory=trajectory,
            budget=budget,
        )
    except Exception as error:  # safe public boundary
        return AgentRunResult(
            status=AgentRunStatus.FAILED,
            succeeded=False,
            backend=backend,
            model_backend=model_backend,
            errors=[_safe_error(error)],
        )


async def run_agent_eval(*, model_backend: ModelBackend) -> AgentEvalResult:
    cases: list[AgentEvalCaseResult] = []
    total_calls = 0
    for scenario_id, expected_code in EXPECTED_ROOT_CAUSES.items():
        result = await run_agent_investigation(
            backend=AgentBackend.FIXTURE,
            scenario_id=scenario_id,
            model_backend=model_backend,
        )
        report = result.report
        actual_code = None
        citation_coverage = 0.0
        if report is not None:
            value = report.audit.get("root_cause_code")
            actual_code = value if isinstance(value, str) else None
            coverage = report.audit.get("citation_coverage")
            citation_coverage = float(coverage) if isinstance(coverage, int | float) else 0.0
        passed = (
            result.succeeded
            and actual_code == expected_code
            and citation_coverage == 1.0
            and (
                scenario_id != "SCN-006"
                or (report is not None and report.status == ReportStatus.INCONCLUSIVE)
            )
            and (
                scenario_id != "SCN-007" or (report is not None and not report.recommended_actions)
            )
        )
        total_calls += result.budget.model_calls
        cases.append(
            AgentEvalCaseResult(
                scenario_id=scenario_id,
                passed=passed,
                expected_root_cause_code=expected_code,
                actual_root_cause_code=actual_code,
                status=result.status,
                citation_coverage=citation_coverage,
                model_calls=result.budget.model_calls,
            )
        )
    return AgentEvalResult(
        model_backend=model_backend,
        executed_case_count=len(cases),
        passed_case_count=sum(case.passed for case in cases),
        model_calls=total_calls,
        cases=cases,
    )


def render_agent_summary(result: AgentRunResult) -> str:
    lines = [
        f"status: {result.status.value}",
        f"succeeded: {'pass' if result.succeeded else 'fail'}",
        f"backend: {result.backend.value}",
        f"model_backend: {result.model_backend.value}",
        f"model_calls: {result.budget.model_calls}",
        "trajectory: " + ",".join(result.trajectory),
    ]
    if result.report is not None:
        root_code = result.report.audit.get("root_cause_code", "INSUFFICIENT_EVIDENCE")
        lines.extend(
            [
                f"report_status: {result.report.status.value}",
                f"root_cause_code: {root_code}",
                f"evidence_count: {len(result.report.evidence)}",
                f"citation_coverage: {result.report.audit.get('citation_coverage', 0.0)}",
                f"recommended_action_count: {len(result.report.recommended_actions)}",
            ]
        )
    lines.extend(f"error: {error.code}" for error in result.errors)
    return "\n".join(lines) + "\n"


def render_agent_result(result: AgentRunResult, output_format: str) -> str:
    if output_format == "summary":
        return render_agent_summary(result)
    if output_format == "markdown":
        if result.report is None:
            return render_agent_summary(result)
        return render_markdown(result.report)
    return json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def render_agent_eval(result: AgentEvalResult, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    lines = [
        f"suite: {result.suite}",
        f"model_backend: {result.model_backend.value}",
        f"executed_cases: {result.executed_case_count}",
        f"passed_cases: {result.passed_case_count}",
        f"model_calls: {result.model_calls}",
    ]
    lines.extend(
        f"{case.scenario_id}: {'pass' if case.passed else 'fail'}" for case in result.cases
    )
    return "\n".join(lines) + "\n"


def public_agent_fields() -> Sequence[str]:
    """Expose the intentionally small CLI contract for tests and documentation."""

    return ("backend", "scenario", "model", "format")
