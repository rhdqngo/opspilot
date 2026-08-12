"""Fixed-scope Agent Runtime adapter and deterministic lean package."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import io
import json
import logging
import os
import re
import tarfile
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Literal, NamedTuple
from uuid import uuid4

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from opspilot.agent.contracts import (
    AgentEvidenceContext,
    HypothesisDraftBatch,
    ReviewInput,
    VerifiedHypothesis,
)
from opspilot.agent.models import DEFAULT_MODEL_ID
from opspilot.agent.workflow import (
    build_runtime_rca_input,
    create_rca_agent,
    review_hypothesis_drafts,
    verify_runtime_hypotheses,
)
from opspilot.catalog import load_service_catalog
from opspilot.domain import (
    EvidenceDirection,
    IncidentReport,
    IncidentTimelineEvent,
    OutputLanguage,
    ReportStatus,
    RootCauseHypothesis,
    SourceType,
)
from opspilot.evidence import (
    EvidenceCollectionRequest,
    EvidenceCollectionResult,
    LiveEvidenceClient,
    UrllibJsonTransport,
    WorkloadAdcTokenProvider,
    collect_evidence,
)
from opspilot.reporting import render_markdown
from opspilot.scoring import status_for_score

RUNTIME_REGION = "asia-northeast3"
RUNTIME_SERVICE = "payment-service"
RUNTIME_WINDOW_MINUTES = 30
RUNTIME_DEADLINE_SECONDS = 18.0
RUNTIME_HTTP_TIMEOUT_SECONDS = 3.0
RUNTIME_SOURCE_TIMEOUT_SECONDS = 4.0
RUNTIME_EVIDENCE_DEADLINE_SECONDS = 5.0
RUNTIME_RCA_TIMEOUT_SECONDS = 10.0
MIN_INPUT_CHARS = 3
MAX_INPUT_CHARS = 500
LOGGER = logging.getLogger(__name__)
RuntimeLogStage = Literal[
    "accepted",
    "evidence_complete",
    "reasoning_skipped",
    "reasoning_complete",
    "reasoning_timeout",
    "final_emitted",
    "timeout",
    "cancelled",
    "run_summary",
]
RuntimeOutcome = Literal["complete", "inconclusive", "rejected", "failed", "timeout", "cancelled"]
ReasoningOutcome = Literal["complete", "skipped", "timeout", "failed", "not_started"]
ACTION_PATTERN = re.compile(
    r"(?:rollback|roll\s*back|deploy|delete|restart|scale|remediat|execute|"
    "\ub864\ubc31|\ubc30\ud3ec|\uc0ad\uc81c|\uc7ac\uc2dc\uc791|\ubcf5\uad6c\ud574|"
    "\uc870\uce58\ud574|\uc2e4\ud589\ud574|\uc2a4\ucf00\uc77c)",
    re.IGNORECASE,
)
INTENT_PATTERN = re.compile(
    "(?:\ubd84\uc11d|\uc870\uc0ac|\uc0c1\ud0dc|\uc6d0\uc778|"
    r"analy[sz]e|investigate|incident|status)",
    re.IGNORECASE,
)
TIME_PATTERN = re.compile(
    "(?P<value>\\d{1,3})\\s*(?P<unit>\ubd84|\uc2dc\uac04|"
    r"minutes?|mins?|hours?|hrs?|m|h)",
    re.IGNORECASE,
)
UNSUPPORTED_TIME_PATTERN = re.compile(
    "(?:\\d{1,4}\\s*(?:\ucd08|\uc77c|\uc8fc|\uac1c\uc6d4|"
    r"seconds?|days?|weeks?|months?|d|w)|"
    "\ud558\ub8e8|\uc77c\uc8fc\uc77c|\uc5b4\uc81c|\\d{4}-\\d{2}-\\d{2})",
    re.IGNORECASE,
)
SERVICE_PATTERN = re.compile(r"(?<![a-z0-9-])[a-z0-9-]+-service(?![a-z0-9-])")
HANGUL_PATTERN = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]")


class RuntimeCopy(NamedTuple):
    progress: str
    failure: str
    configuration_unavailable: str
    rejection: str
    default_window_assumption: str
    reasoning_gap: str
    reasoning_unverified_gap: str
    identified_title: str
    inconclusive_title: str
    severity_rationale: str
    impact_summary: str
    inconclusive_summary: str


RUNTIME_COPY = {
    OutputLanguage.EN: RuntimeCopy(
        progress=(
            "Collecting bounded evidence for payment-service over the recent 30 minutes…\n\n"
        ),
        failure="The bounded investigation failed safely.",
        configuration_unavailable="The bounded investigation is not configured.",
        rejection=(
            "OpsPilot MVP only supports a read-only investigation of payment-service "
            "for the recent 30-minute window. Recovery and execution requests are not supported."
        ),
        default_window_assumption=(
            "No time range was supplied; the fixed recent 30-minute window was used."
        ),
        reasoning_gap="The bounded RCA reasoning step was unavailable.",
        reasoning_unverified_gap=("No RCA hypothesis passed deterministic evidence verification."),
        identified_title="Payment Service Investigation",
        inconclusive_title="Inconclusive Investigation: Payment Service Status",
        severity_rationale=("Severity is not inferred beyond the bounded operational evidence."),
        impact_summary="Impact could not be confirmed from the bounded evidence.",
        inconclusive_summary=(
            "No root cause can be confirmed with the available evidence. "
            "The report preserves the bounded observations and data gaps."
        ),
    ),
    OutputLanguage.KO: RuntimeCopy(
        progress="최근 30분 동안 payment-service의 제한된 증거를 수집하고 있습니다…\n\n",
        failure="제한된 범위의 조사를 안전하게 완료하지 못했습니다.",
        configuration_unavailable="제한된 조사를 실행하도록 구성되지 않았습니다.",
        rejection=(
            "OpsPilot MVP는 payment-service의 최근 30분 상태에 대한 읽기 전용 조사만 "
            "지원합니다. 복구 및 실행 요청은 지원하지 않습니다."
        ),
        default_window_assumption=(
            "시간 범위가 지정되지 않아 최근 30분의 고정 구간을 사용했습니다."
        ),
        reasoning_gap="제한된 RCA 추론 단계를 사용할 수 없습니다.",
        reasoning_unverified_gap="결정론적 증거 검증을 통과한 RCA 가설이 없습니다.",
        identified_title="Payment Service 조사",
        inconclusive_title="판단 불가 조사: Payment Service 상태",
        severity_rationale="제한된 운영 증거를 넘어 심각도를 추론하지 않았습니다.",
        impact_summary="제한된 증거로는 영향을 확인할 수 없습니다.",
        inconclusive_summary=(
            "사용 가능한 증거로는 근본 원인을 확인할 수 없습니다. "
            "보고서에는 제한된 관측 결과와 데이터 공백을 보존했습니다."
        ),
    ),
}
RUNTIME_PROGRESS_TEXT = RUNTIME_COPY[OutputLanguage.EN].progress
RUNTIME_FAILURE_TEXT = RUNTIME_COPY[OutputLanguage.EN].failure
RUNTIME_REASONING_GAP = RUNTIME_COPY[OutputLanguage.EN].reasoning_gap
RUNTIME_REASONING_UNVERIFIED_GAP = RUNTIME_COPY[OutputLanguage.EN].reasoning_unverified_gap

RUNTIME_SOURCE_ALLOWLIST = (
    "opspilot/__init__.py",
    "opspilot/agent/__init__.py",
    "opspilot/agent/contracts.py",
    "opspilot/agent/models.py",
    "opspilot/agent/runner.py",
    "opspilot/agent/runtime.py",
    "opspilot/agent/runtime_agent.py",
    "opspilot/agent/workflow.py",
    "opspilot/catalog.py",
    "opspilot/domain.py",
    "opspilot/evidence.py",
    "opspilot/knowledge_search.py",
    "opspilot/redaction.py",
    "opspilot/reporting.py",
    "opspilot/scoring.py",
    "opspilot/resources/services.yaml",
)


class RuntimeInputDecision(BaseModel):
    accepted: bool
    rejection_code: Literal[
        "none",
        "invalid_length",
        "unsupported_intent",
        "unsupported_service",
        "unsupported_window",
        "action_request_rejected",
    ] = "none"
    service: str | None = None
    window_minutes: int | None = None
    output_language: OutputLanguage = OutputLanguage.EN
    assumptions: list[str] = Field(default_factory=list)
    run_id: str = Field(
        default_factory=lambda: f"RUN-{uuid4().hex[:16].upper()}",
        pattern=r"^RUN-[A-F0-9]{16}$",
    )
    started_clock: float | None = Field(default=None, exclude=True, repr=False)


class RuntimeRunSummary(BaseModel):
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{16}$")
    outcome: RuntimeOutcome
    source_status: dict[str, bool] = Field(default_factory=dict)
    source_error_codes: dict[str, str] = Field(default_factory=dict)
    reasoning_outcome: ReasoningOutcome = "not_started"
    duration_ms: int = Field(default=0, ge=0)


class RuntimeInvocationResult(BaseModel):
    accepted: bool
    succeeded: bool
    rejection_code: str = "none"
    output_markdown: str
    run_id: str = Field(
        default_factory=lambda: f"RUN-{uuid4().hex[:16].upper()}",
        pattern=r"^RUN-[A-F0-9]{16}$",
    )
    summary: RuntimeRunSummary | None = None


class RuntimePackageResult(BaseModel):
    succeeded: bool
    file_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_name: str = "opspilot-agent-runtime.tar.gz"


RuntimeHandler = Callable[[RuntimeInputDecision], Awaitable[RuntimeInvocationResult]]


def _log_runtime_stage(
    stage: RuntimeLogStage,
    *,
    run_id: str,
    started_clock: float | None = None,
    summary: RuntimeRunSummary | None = None,
) -> None:
    effective_started_clock = started_clock
    payload: dict[str, str | int | dict[str, bool] | dict[str, str]] = {
        "event": "opspilot_runtime",
        "run_id": run_id,
        "stage": stage,
        "elapsed_ms": (
            round((perf_counter() - effective_started_clock) * 1_000)
            if effective_started_clock is not None
            else 0
        ),
    }
    if summary is not None:
        payload.update(
            {
                "outcome": summary.outcome,
                "source_status": summary.source_status,
                "source_error_codes": summary.source_error_codes,
                "reasoning_outcome": summary.reasoning_outcome,
            }
        )
    LOGGER.info("%s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


def validate_runtime_input(value: str) -> RuntimeInputDecision:
    text = value.strip()
    output_language = OutputLanguage.KO if HANGUL_PATTERN.search(text) else OutputLanguage.EN

    def reject(
        rejection_code: Literal[
            "invalid_length",
            "unsupported_intent",
            "unsupported_service",
            "unsupported_window",
            "action_request_rejected",
        ],
    ) -> RuntimeInputDecision:
        return RuntimeInputDecision(
            accepted=False,
            rejection_code=rejection_code,
            output_language=output_language,
        )

    if not MIN_INPUT_CHARS <= len(text) <= MAX_INPUT_CHARS:
        return reject("invalid_length")
    if ACTION_PATTERN.search(text):
        return reject("action_request_rejected")
    services = set(SERVICE_PATTERN.findall(text.casefold()))
    if services != {RUNTIME_SERVICE}:
        return reject("unsupported_service")
    if not INTENT_PATTERN.search(text):
        return reject("unsupported_intent")
    time_matches = list(TIME_PATTERN.finditer(text))
    assumptions: list[str] = []
    if not time_matches and UNSUPPORTED_TIME_PATTERN.search(text):
        return reject("unsupported_window")
    if not time_matches:
        assumptions.append(RUNTIME_COPY[output_language].default_window_assumption)
    elif len(time_matches) != 1:
        return reject("unsupported_window")
    else:
        match = time_matches[0]
        value_number = int(match.group("value"))
        unit = match.group("unit").casefold()
        minutes = (
            value_number * 60
            if unit in {"\uc2dc\uac04", "hour", "hours", "hr", "hrs", "h"}
            else value_number
        )
        if minutes != RUNTIME_WINDOW_MINUTES:
            return reject("unsupported_window")
    return RuntimeInputDecision(
        accepted=True,
        service=RUNTIME_SERVICE,
        window_minutes=RUNTIME_WINDOW_MINUTES,
        output_language=output_language,
        assumptions=assumptions,
    )


def _content_text(content: types.Content | None) -> str:
    if content is None:
        return ""
    return "".join(part.text or "" for part in content.parts or [])


def _safe_rejection(decision: RuntimeInputDecision) -> RuntimeInvocationResult:
    summary = RuntimeRunSummary(
        run_id=decision.run_id,
        outcome="rejected",
        reasoning_outcome="not_started",
    )
    return RuntimeInvocationResult(
        accepted=False,
        succeeded=False,
        rejection_code=decision.rejection_code,
        output_markdown=RUNTIME_COPY[decision.output_language].rejection,
        run_id=decision.run_id,
        summary=summary,
    )


def _has_runtime_reasoning_signal(context: AgentEvidenceContext) -> bool:
    valid_types = {
        item.source_type
        for item in context.evidence
        if item.source_type in {SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}
        and item.direction == EvidenceDirection.SUPPORTS
        and "missing_points" not in item.quality_flags
        and "outside_investigation_window" not in item.quality_flags
    }
    return len(valid_types) >= 2


def _localized_collection_data_gaps(
    collection: EvidenceCollectionResult,
    language: OutputLanguage,
) -> list[str]:
    gaps: list[str] = []
    for source in (
        SourceType.LOG,
        SourceType.METRIC,
        SourceType.CHANGE,
        SourceType.KNOWLEDGE,
    ):
        if collection.source_status.get(source.value) is False:
            gaps.append(
                f"{source.value} 증거를 사용할 수 없습니다."
                if language == OutputLanguage.KO
                else f"{source.value} evidence was unavailable."
            )
    for item in collection.evidence:
        if item.source_type == SourceType.METRIC and "missing_points" in item.quality_flags:
            gaps.append(
                f"{item.title}가 요청 구간 내 데이터 포인트를 반환하지 않았습니다."
                if language == OutputLanguage.KO
                else f"{item.title} returned no bounded points in the requested window."
            )
    return gaps


def _drafts_match_output_language(
    drafts: HypothesisDraftBatch,
    language: OutputLanguage,
) -> bool:
    for draft in drafts.drafts:
        natural_language_fields = [
            draft.claim,
            draft.mechanism,
            *draft.missing_evidence,
            *draft.next_checks,
        ]
        for value in natural_language_fields:
            has_hangul = HANGUL_PATTERN.search(value) is not None
            if language == OutputLanguage.KO and not has_hangul:
                return False
            if language == OutputLanguage.EN and has_hangul:
                return False
    return True


async def run_runtime_rca(
    context: AgentEvidenceContext,
    output_language: OutputLanguage,
) -> HypothesisDraftBatch:
    """Run one bounded RCA model node without the live Workflow orchestrator."""

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if os.environ.get("OPSPILOT_LIVE_MODEL_ENABLED") != "true" or not project_id:
        raise RuntimeError("live model is unavailable")
    configured_model = os.environ.get("OPSPILOT_MODEL_ID", DEFAULT_MODEL_ID)
    if configured_model != DEFAULT_MODEL_ID:
        raise RuntimeError("configured model is not allowed")
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "true"
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

    attempted_calls = 0

    def observe_request(_node_name: str, _size: int) -> None:
        nonlocal attempted_calls
        attempted_calls += 1
        if attempted_calls > 1:
            raise ValueError("runtime RCA exceeded its fixed model-call budget")

    runner = InMemoryRunner(
        node=create_rca_agent(
            model_id=configured_model,
            request_observer=observe_request,
            timeout_seconds=RUNTIME_RCA_TIMEOUT_SECONDS,
        ),
        app_name="opspilot_runtime_rca",
    )
    user_id = "runtime-operator"
    session_id = f"runtime-{uuid4().hex}"
    await runner.session_service.create_session(
        app_name="opspilot_runtime_rca",
        user_id=user_id,
        session_id=session_id,
    )
    payload = build_runtime_rca_input(context, output_language=output_language).model_dump_json()
    drafts: HypothesisDraftBatch | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=payload)]),
    ):
        if event.output is not None:
            drafts = HypothesisDraftBatch.model_validate(event.output)
        elif event.is_final_response() and event.content and event.content.parts:
            text = "".join(part.text or "" for part in event.content.parts)
            if text:
                drafts = HypothesisDraftBatch.model_validate_json(text)
    if attempted_calls != 1 or drafts is None:
        raise ValueError("runtime RCA did not produce one bounded result")
    return drafts


def _deterministic_runtime_report(
    context: AgentEvidenceContext,
    verified: list[VerifiedHypothesis],
    *,
    model_calls: int,
    output_language: OutputLanguage,
    run_id: str,
) -> IncidentReport:
    copy = RUNTIME_COPY[output_language]
    hypotheses = [
        RootCauseHypothesis(
            hypothesis_id=f"H-{index:02d}",
            rank=index,
            claim=item.claim,
            mechanism=item.mechanism,
            affected_services=item.affected_services,
            supporting_evidence_ids=item.supporting_evidence_ids,
            contradicting_evidence_ids=item.contradicting_evidence_ids,
            missing_evidence=item.missing_evidence,
            next_checks=item.next_checks,
            evidence_support_score=item.evidence_support_score,
            status=status_for_score(
                item.evidence_support_score,
                has_minimum_evidence=item.source_type_count >= 2,
            ),
        )
        for index, item in enumerate(verified, start=1)
    ]
    timeline = [
        IncidentTimelineEvent(
            timestamp=item.observed_at or item.period_start or context.generated_at,
            event_type=item.source_type.value,
            title=item.title,
            description=item.summary,
            service=item.service,
            evidence_ids=[item.evidence_id],
        )
        for item in context.evidence
        if item.source_type in {SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}
        and (item.observed_at is not None or item.period_start is not None)
    ]
    identified = bool(hypotheses)
    if identified and output_language == OutputLanguage.KO:
        executive_summary = (
            f"가장 유력한 검증 가설은 {hypotheses[0].claim}이며, 인용된 증거 "
            f"{len(hypotheses[0].supporting_evidence_ids)}건이 이를 뒷받침합니다."
        )
    elif identified:
        executive_summary = (
            "The leading verified hypothesis is "
            f"{hypotheses[0].claim}, supported by "
            f"{len(hypotheses[0].supporting_evidence_ids)} cited evidence items."
        )
    else:
        executive_summary = copy.inconclusive_summary
    return IncidentReport(
        report_id=f"RPT-{context.scenario_id}-LIVE-001",
        report_version=1,
        incident_id=context.incident_id,
        generated_at=context.generated_at,
        correlation_id=context.correlation_id,
        title=copy.identified_title if identified else copy.inconclusive_title,
        severity="UNCLASSIFIED",
        severity_rationale=copy.severity_rationale,
        status=ReportStatus.IDENTIFIED if identified else ReportStatus.INCONCLUSIVE,
        impact_summary=copy.impact_summary,
        executive_summary=executive_summary,
        affected_services=sorted(
            {service for item in verified for service in item.affected_services}
        ),
        timeline=timeline,
        hypotheses=hypotheses,
        evidence=context.evidence,
        recommended_actions=[],
        data_gaps=context.data_gaps,
        assumptions=context.assumptions,
        tool_errors=context.tool_errors,
        approval_status=None,
        audit={
            "execution_mode": "adk-live-hybrid",
            "run_id": run_id,
            "model_id": DEFAULT_MODEL_ID,
            "model_calls": model_calls,
            "citation_coverage": 1.0,
            "unsupported_claim_count": 0,
            "unauthorized_action_count": 0,
            "root_cause_code": (
                verified[0].root_cause_code if verified else "INSUFFICIENT_EVIDENCE"
            ),
            "root_cause_codes": [item.root_cause_code for item in verified],
        },
    )


async def _run_live_runtime_investigation_async(
    decision: RuntimeInputDecision,
) -> RuntimeInvocationResult:
    copy = RUNTIME_COPY[decision.output_language]
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id or decision.service != RUNTIME_SERVICE:
        summary = RuntimeRunSummary(
            run_id=decision.run_id,
            outcome="failed",
            reasoning_outcome="not_started",
        )
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=False,
            rejection_code="runtime_configuration_unavailable",
            output_markdown=copy.configuration_unavailable,
            run_id=decision.run_id,
            summary=summary,
        )
    end_time = datetime.now(UTC)
    collection = await collect_evidence(
        LiveEvidenceClient(
            project_id,
            catalog=load_service_catalog(),
            token_provider=WorkloadAdcTokenProvider(),
            transport=UrllibJsonTransport(),
            region=RUNTIME_REGION,
            request_timeout_seconds=RUNTIME_HTTP_TIMEOUT_SECONDS,
        ),
        EvidenceCollectionRequest(
            scenario_id="SCN-001",
            environment="dev",
            start_time=end_time - timedelta(minutes=RUNTIME_WINDOW_MINUTES),
            end_time=end_time,
            services=[RUNTIME_SERVICE],
        ),
        tool_timeout_seconds=RUNTIME_SOURCE_TIMEOUT_SECONDS,
        collection_deadline_seconds=RUNTIME_EVIDENCE_DEADLINE_SECONDS,
    )
    _log_runtime_stage(
        "evidence_complete",
        run_id=decision.run_id,
        started_clock=decision.started_clock,
    )
    context = AgentEvidenceContext(
        scenario_id="SCN-001",
        incident_id=f"INC-{end_time.year:04d}-0001",
        generated_at=end_time,
        correlation_id=f"COR-{uuid4().hex[:16].upper()}",
        evidence=collection.evidence,
        tool_errors=collection.tool_errors,
        data_gaps=_localized_collection_data_gaps(collection, decision.output_language),
        assumptions=decision.assumptions,
    )
    verified: list[VerifiedHypothesis] = []
    model_calls = 0
    reasoning_outcome: ReasoningOutcome = "skipped"
    if _has_runtime_reasoning_signal(context):
        model_calls = 1
        try:
            drafts = await asyncio.wait_for(
                run_runtime_rca(context, decision.output_language),
                timeout=RUNTIME_RCA_TIMEOUT_SECONDS,
            )
            if not _drafts_match_output_language(drafts, decision.output_language):
                raise ValueError("runtime RCA output language did not match the request")
            rca_input = build_runtime_rca_input(context, output_language=decision.output_language)
            reviews = review_hypothesis_drafts(
                ReviewInput(
                    evidence=rca_input.evidence,
                    drafts=drafts.drafts,
                    data_gaps=context.data_gaps,
                )
            )
            verified, _ = verify_runtime_hypotheses(context, drafts, reviews)
            if not verified:
                context = context.model_copy(
                    update={
                        "data_gaps": [
                            *context.data_gaps,
                            copy.reasoning_unverified_gap,
                        ]
                    }
                )
            reasoning_outcome = "complete"
            _log_runtime_stage(
                "reasoning_complete",
                run_id=decision.run_id,
                started_clock=decision.started_clock,
            )
        except TimeoutError:
            context = context.model_copy(
                update={"data_gaps": [*context.data_gaps, copy.reasoning_gap]}
            )
            reasoning_outcome = "timeout"
            _log_runtime_stage(
                "reasoning_timeout",
                run_id=decision.run_id,
                started_clock=decision.started_clock,
            )
        except Exception:
            context = context.model_copy(
                update={"data_gaps": [*context.data_gaps, copy.reasoning_gap]}
            )
            reasoning_outcome = "failed"
            _log_runtime_stage(
                "reasoning_complete",
                run_id=decision.run_id,
                started_clock=decision.started_clock,
            )
    else:
        _log_runtime_stage(
            "reasoning_skipped",
            run_id=decision.run_id,
            started_clock=decision.started_clock,
        )

    report = _deterministic_runtime_report(
        context,
        verified,
        model_calls=model_calls,
        output_language=decision.output_language,
        run_id=decision.run_id,
    )
    summary = RuntimeRunSummary(
        run_id=decision.run_id,
        outcome="complete" if verified else "inconclusive",
        source_status=collection.source_status,
        source_error_codes=collection.source_error_codes,
        reasoning_outcome=reasoning_outcome,
        duration_ms=(
            max(0, round((perf_counter() - decision.started_clock) * 1_000))
            if decision.started_clock is not None
            else collection.budget.duration_ms
        ),
    )
    return RuntimeInvocationResult(
        accepted=True,
        succeeded=True,
        output_markdown=render_markdown(report, language=decision.output_language),
        run_id=decision.run_id,
        summary=summary,
    )


async def run_live_runtime_investigation(
    decision: RuntimeInputDecision,
) -> RuntimeInvocationResult:
    """Run the cancellable live pipeline on the Runtime stream loop."""

    return await _run_live_runtime_investigation_async(decision)


async def process_runtime_input(
    text: str,
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> RuntimeInvocationResult:
    decision = validate_runtime_input(text)
    if not decision.accepted:
        return _safe_rejection(decision)
    return await handler(decision)


def _runtime_event(
    context: InvocationContext,
    *,
    author: str,
    text: str,
    partial: bool,
    turn_complete: bool,
) -> Event:
    return Event(
        invocation_id=context.invocation_id,
        author=author,
        branch=context.branch,
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        partial=partial,
        turn_complete=turn_complete,
    )


class OpsPilotRuntimeAgent(BaseAgent):
    """Emit an immediate progress event before running the bounded investigation."""

    handler: RuntimeHandler = Field(exclude=True)

    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        started_clock = perf_counter()
        decision = validate_runtime_input(_content_text(context.user_content))
        if not decision.accepted:
            result = _safe_rejection(decision)
            if result.summary is not None:
                _log_runtime_stage(
                    "run_summary",
                    run_id=decision.run_id,
                    started_clock=started_clock,
                    summary=result.summary,
                )
            _log_runtime_stage("final_emitted", run_id=decision.run_id, started_clock=started_clock)
            yield _runtime_event(
                context,
                author=self.name,
                text=result.output_markdown,
                partial=False,
                turn_complete=True,
            )
            return

        _log_runtime_stage("accepted", run_id=decision.run_id, started_clock=started_clock)
        decision.started_clock = started_clock
        copy = RUNTIME_COPY[decision.output_language]
        handler_task: asyncio.Future[RuntimeInvocationResult] | None = None
        try:
            yield _runtime_event(
                context,
                author=self.name,
                text=copy.progress,
                partial=True,
                turn_complete=False,
            )
            handler_task = asyncio.ensure_future(self.handler(decision))
            done, _ = await asyncio.wait({handler_task}, timeout=RUNTIME_DEADLINE_SECONDS)
            if handler_task in done:
                result = handler_task.result()
                summary = result.summary or RuntimeRunSummary(
                    run_id=decision.run_id,
                    outcome="complete" if result.succeeded else "failed",
                    reasoning_outcome="complete" if result.succeeded else "failed",
                )
                result = result.model_copy(
                    update={
                        "run_id": decision.run_id,
                        "summary": summary.model_copy(
                            update={
                                "run_id": decision.run_id,
                                "duration_ms": max(
                                    summary.duration_ms,
                                    round((perf_counter() - started_clock) * 1_000),
                                ),
                            }
                        ),
                    }
                )
            else:
                _log_runtime_stage("timeout", run_id=decision.run_id, started_clock=started_clock)
                handler_task.cancel()
                try:
                    await handler_task
                except asyncio.CancelledError:
                    pass
                summary = RuntimeRunSummary(
                    run_id=decision.run_id,
                    outcome="timeout",
                    reasoning_outcome="failed",
                    duration_ms=round((perf_counter() - started_clock) * 1_000),
                )
                result = RuntimeInvocationResult(
                    accepted=True,
                    succeeded=False,
                    rejection_code="runtime_timeout",
                    output_markdown=copy.failure,
                    run_id=decision.run_id,
                    summary=summary,
                )
        except asyncio.CancelledError:
            if handler_task is not None:
                handler_task.cancel()
                try:
                    await handler_task
                except asyncio.CancelledError:
                    pass
            summary = RuntimeRunSummary(
                run_id=decision.run_id,
                outcome="cancelled",
                reasoning_outcome="failed",
                duration_ms=round((perf_counter() - started_clock) * 1_000),
            )
            _log_runtime_stage(
                "run_summary",
                run_id=decision.run_id,
                started_clock=started_clock,
                summary=summary,
            )
            _log_runtime_stage("cancelled", run_id=decision.run_id, started_clock=started_clock)
            raise
        except GeneratorExit:
            if handler_task is not None:
                handler_task.cancel()
                try:
                    await handler_task
                except asyncio.CancelledError:
                    pass
            summary = RuntimeRunSummary(
                run_id=decision.run_id,
                outcome="cancelled",
                reasoning_outcome="failed",
                duration_ms=round((perf_counter() - started_clock) * 1_000),
            )
            _log_runtime_stage(
                "run_summary",
                run_id=decision.run_id,
                started_clock=started_clock,
                summary=summary,
            )
            _log_runtime_stage("cancelled", run_id=decision.run_id, started_clock=started_clock)
            raise
        except Exception:
            summary = RuntimeRunSummary(
                run_id=decision.run_id,
                outcome="failed",
                reasoning_outcome="failed",
                duration_ms=round((perf_counter() - started_clock) * 1_000),
            )
            result = RuntimeInvocationResult(
                accepted=True,
                succeeded=False,
                rejection_code="runtime_failed",
                output_markdown=copy.failure,
                run_id=decision.run_id,
                summary=summary,
            )
        if result.summary is not None:
            _log_runtime_stage(
                "run_summary",
                run_id=decision.run_id,
                started_clock=started_clock,
                summary=result.summary,
            )
        _log_runtime_stage("final_emitted", run_id=decision.run_id, started_clock=started_clock)
        yield _runtime_event(
            context,
            author=self.name,
            text=result.output_markdown,
            partial=False,
            turn_complete=True,
        )


def create_runtime_root_agent(
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> OpsPilotRuntimeAgent:
    return OpsPilotRuntimeAgent(
        name="opspilot_runtime",
        description="Fixed-scope read-only payment-service incident investigation.",
        handler=handler,
    )


def _runtime_files() -> list[tuple[str, bytes]]:
    source_root = Path(__file__).parents[2]
    files: list[tuple[str, bytes]] = []
    for relative in RUNTIME_SOURCE_ALLOWLIST:
        path = source_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"runtime source is missing: {relative}")
        files.append((relative, path.read_bytes()))
    requirements = "\n".join(
        (
            "google-adk==2.5.0",
            "google-auth==2.56.3",
            "google-cloud-aiplatform[agent-engines]==1.153.1",
            "pydantic==2.13.4",
            "pyyaml==6.0.3",
            "",
        )
    ).encode()
    files.append(("requirements.txt", requirements))
    return sorted(files)


def _deterministic_archive(files: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, content in files:
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mtime = 0
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def package_runtime(output: Path) -> RuntimePackageResult:
    root = Path.cwd().resolve()
    allowed_root = (root / ".tmp").resolve()
    destination = output.resolve()
    if destination != allowed_root and allowed_root not in destination.parents:
        raise ValueError("runtime package output must remain under .tmp")
    destination.mkdir(parents=True, exist_ok=True)
    files = _runtime_files()
    archive = _deterministic_archive(files)
    archive_path = destination / "opspilot-agent-runtime.tar.gz"
    archive_path.write_bytes(archive)
    digest = hashlib.sha256(archive).hexdigest()
    (destination / "opspilot-agent-runtime.sha256").write_text(
        f"{digest}  {archive_path.name}\n", encoding="utf-8"
    )
    return RuntimePackageResult(succeeded=True, file_count=len(files), sha256=digest)


def render_runtime_summary(result: BaseModel) -> str:
    values = result.model_dump(mode="json", exclude={"output_markdown"})
    return "\n".join(f"{name}: {value}" for name, value in values.items()) + "\n"
