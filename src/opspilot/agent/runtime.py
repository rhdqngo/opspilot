"""MVP-only Agent Runtime adapter, validation, and deterministic source package."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import re
import tarfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from pydantic import BaseModel, Field

from opspilot.agent.contracts import AgentBackend, AgentEvidenceContext, ModelBackend
from opspilot.agent.models import DEFAULT_MODEL_ID
from opspilot.agent.runner import run_agent_context, run_agent_investigation
from opspilot.catalog import load_service_catalog
from opspilot.evidence import (
    EvidenceCollectionRequest,
    LiveEvidenceClient,
    UrllibJsonTransport,
    WorkloadAdcTokenProvider,
    collect_evidence,
)
from opspilot.reporting import render_markdown

RUNTIME_REGION = "asia-northeast3"
RUNTIME_SERVICE = "payment-service"
RUNTIME_WINDOW_MINUTES = 30
RUNTIME_DISPLAY_NAME = "OpsPilot Incident Commander"
MIN_INPUT_CHARS = 3
MAX_INPUT_CHARS = 500
ACTION_PATTERN = re.compile(
    r"(?:rollback|roll\s*back|deploy|delete|restart|scale|remediat|execute|"
    "\ub864\ubc31|\ubc30\ud3ec|\uc0ad\uc81c|\uc7ac\uc2dc\uc791|\ubcf5\uad6c\ud574|"
    "\uc870\uce58\ud574|\uc2e4\ud589\ud574|\uc2a4\ucf00\uc77c)",
    re.IGNORECASE,
)
INTENT_PATTERN = re.compile(
    "(?:\ubd84\uc11d|\uc870\uc0ac|\uc0c1\ud0dc|\uc6d0\uc778|"
    r"analy[sz]e|investigate|incident|status)",
    re.I,
)
TIME_PATTERN = re.compile(
    "(?P<value>\\d{1,3})\\s*(?P<unit>\ubd84|\uc2dc\uac04|"
    r"minutes?|mins?|hours?|hrs?|m|h)",
    re.I,
)
UNSUPPORTED_TIME_PATTERN = re.compile(
    "(?:\\d{1,4}\\s*(?:\ucd08|\uc77c|\uc8fc|\uac1c\uc6d4|"
    r"seconds?|days?|weeks?|months?|d|w)|"
    "\ud558\ub8e8|\uc77c\uc8fc\uc77c|\uc5b4\uc81c|\\d{4}-\\d{2}-\\d{2})",
    re.I,
)
SERVICE_PATTERN = re.compile(r"(?<![a-z0-9-])[a-z0-9-]+-service(?![a-z0-9-])")


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
    assumptions: list[str] = Field(default_factory=list)


class RuntimeInvocationResult(BaseModel):
    accepted: bool
    succeeded: bool
    rejection_code: str = "none"
    report_status: str | None = None
    evidence_api_calls: int = Field(default=0, ge=0, le=10)
    model_calls: int = Field(default=0, ge=0, le=2)
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    unauthorized_action_count: int = Field(default=0, ge=0)
    output_markdown: str


class RuntimeValidationResult(BaseModel):
    valid: bool
    python_version: str = "3.12"
    entrypoint_ready: bool
    catalog_ready: bool
    fixed_service: str = RUNTIME_SERVICE
    fixed_window_minutes: int = RUNTIME_WINDOW_MINUTES
    fixed_region: str = RUNTIME_REGION
    upper_routing_model_calls: int = 0
    model_call_limit: int = 2
    telemetry_enabled: bool = True
    message_content_capture_enabled: bool = False


class RuntimePackageResult(BaseModel):
    succeeded: bool
    file_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_name: str = "opspilot-agent-runtime.tar.gz"


RuntimeHandler = Callable[[RuntimeInputDecision], Awaitable[RuntimeInvocationResult]]


def _audit_number(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def validate_runtime_input(value: str) -> RuntimeInputDecision:
    text = value.strip()
    if not MIN_INPUT_CHARS <= len(text) <= MAX_INPUT_CHARS:
        return RuntimeInputDecision(accepted=False, rejection_code="invalid_length")
    if ACTION_PATTERN.search(text):
        return RuntimeInputDecision(accepted=False, rejection_code="action_request_rejected")
    services = set(SERVICE_PATTERN.findall(text.casefold()))
    if services != {RUNTIME_SERVICE}:
        return RuntimeInputDecision(accepted=False, rejection_code="unsupported_service")
    if not INTENT_PATTERN.search(text):
        return RuntimeInputDecision(accepted=False, rejection_code="unsupported_intent")
    time_matches = list(TIME_PATTERN.finditer(text))
    assumptions: list[str] = []
    if not time_matches and UNSUPPORTED_TIME_PATTERN.search(text):
        return RuntimeInputDecision(accepted=False, rejection_code="unsupported_window")
    if not time_matches:
        assumptions.append(
            "No time range was supplied; the fixed recent 30-minute window was used."
        )
    elif len(time_matches) != 1:
        return RuntimeInputDecision(accepted=False, rejection_code="unsupported_window")
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
            return RuntimeInputDecision(accepted=False, rejection_code="unsupported_window")
    return RuntimeInputDecision(
        accepted=True,
        service=RUNTIME_SERVICE,
        window_minutes=RUNTIME_WINDOW_MINUTES,
        assumptions=assumptions,
    )


def _content_text(content: types.Content | None) -> str:
    if content is None:
        return ""
    return "".join(part.text or "" for part in content.parts or [])


def _safe_rejection(decision: RuntimeInputDecision) -> RuntimeInvocationResult:
    return RuntimeInvocationResult(
        accepted=False,
        succeeded=False,
        rejection_code=decision.rejection_code,
        output_markdown=(
            "OpsPilot MVP only supports a read-only investigation of payment-service "
            "for the recent 30-minute window. Recovery and execution requests are not supported."
        ),
    )


async def run_fixture_runtime_investigation(
    _decision: RuntimeInputDecision,
) -> RuntimeInvocationResult:
    result = await run_agent_investigation(
        backend=AgentBackend.FIXTURE,
        scenario_id="SCN-001",
        model_backend=ModelBackend.FAKE,
    )
    report = result.report
    if report is None:
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=False,
            rejection_code="runtime_failed",
            model_calls=result.budget.model_calls,
            output_markdown="The bounded investigation failed safely.",
        )
    return RuntimeInvocationResult(
        accepted=True,
        succeeded=result.succeeded,
        report_status=report.status.value,
        model_calls=result.budget.model_calls,
        citation_coverage=_audit_number(report.audit.get("citation_coverage", 0.0)),
        unauthorized_action_count=int(
            _audit_number(report.audit.get("unauthorized_action_count", 0))
        ),
        output_markdown=render_markdown(report),
    )


async def run_live_runtime_investigation(
    decision: RuntimeInputDecision,
) -> RuntimeInvocationResult:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project_id or decision.service != RUNTIME_SERVICE:
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=False,
            rejection_code="runtime_configuration_unavailable",
            output_markdown="The bounded investigation is not configured.",
        )
    end_time = datetime.now(UTC)
    catalog = load_service_catalog()
    collection = await collect_evidence(
        LiveEvidenceClient(
            project_id,
            catalog=catalog,
            token_provider=WorkloadAdcTokenProvider(),
            transport=UrllibJsonTransport(),
            region=RUNTIME_REGION,
        ),
        EvidenceCollectionRequest(
            scenario_id="SCN-001",
            environment="dev",
            start_time=end_time - timedelta(minutes=RUNTIME_WINDOW_MINUTES),
            end_time=end_time,
            services=[RUNTIME_SERVICE],
        ),
    )
    context = AgentEvidenceContext(
        scenario_id="SCN-001",
        incident_id=f"INC-{end_time.year:04d}-0001",
        generated_at=end_time,
        correlation_id=f"COR-{uuid4().hex[:16].upper()}",
        evidence=collection.evidence,
        tool_errors=collection.tool_errors,
        data_gaps=collection.data_gaps,
        assumptions=decision.assumptions,
    )
    result = await run_agent_context(
        context,
        model_backend=ModelBackend.VERTEX,
        complete=collection.complete,
    )
    report = result.report
    if report is None:
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=False,
            rejection_code="runtime_failed",
            evidence_api_calls=collection.budget.api_calls,
            model_calls=result.budget.model_calls,
            output_markdown="The bounded investigation failed safely.",
        )
    return RuntimeInvocationResult(
        accepted=True,
        succeeded=result.succeeded,
        report_status=report.status.value,
        evidence_api_calls=collection.budget.api_calls,
        model_calls=result.budget.model_calls,
        citation_coverage=_audit_number(report.audit.get("citation_coverage", 0.0)),
        unauthorized_action_count=int(
            _audit_number(report.audit.get("unauthorized_action_count", 0))
        ),
        output_markdown=render_markdown(report),
    )


async def process_runtime_input(
    text: str,
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> RuntimeInvocationResult:
    decision = validate_runtime_input(text)
    if not decision.accepted:
        return _safe_rejection(decision)
    return await handler(decision)


def create_runtime_root_agent(
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> LlmAgent:
    async def validate_and_run(callback_context: CallbackContext) -> types.Content:
        result = await process_runtime_input(
            _content_text(callback_context.user_content),
            handler=handler,
        )
        return types.Content(role="model", parts=[types.Part(text=result.output_markdown)])

    return LlmAgent(
        name="opspilot_runtime",
        model=DEFAULT_MODEL_ID,
        description="Fixed-scope read-only payment-service incident investigation.",
        instruction="This routing model is never called; the deterministic callback handles input.",
        tools=[],
        before_agent_callback=validate_and_run,
    )


def validate_runtime() -> RuntimeValidationResult:
    catalog_ready = RUNTIME_SERVICE in load_service_catalog().services
    return RuntimeValidationResult(
        valid=catalog_ready,
        entrypoint_ready=True,
        catalog_ready=catalog_ready,
    )


async def smoke_runtime() -> RuntimeInvocationResult:
    return await process_runtime_input(
        "payment-service 최근 30분 상태를 근거와 함께 분석해줘",
        handler=run_fixture_runtime_investigation,
    )


def _runtime_files() -> list[tuple[str, bytes]]:
    package_root = Path(__file__).parents[1]
    files: list[tuple[str, bytes]] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".yaml"}:
            continue
        relative = path.relative_to(package_root.parent).as_posix()
        files.append((relative, path.read_bytes()))
    requirements = "\n".join(
        (
            "google-adk==2.5.0",
            "google-auth==2.56.3",
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
