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
from pathlib import Path
from time import perf_counter
from typing import Literal, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import uuid4

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as AuthRequest
from google.genai import types
from google.oauth2 import id_token
from pydantic import BaseModel, Field

from opspilot.catalog import load_service_catalog
from opspilot.domain import OutputLanguage
from opspilot.parser import parse_investigation_request

RUNTIME_DEADLINE_SECONDS = 18.0
MIN_INPUT_CHARS = 3
MAX_INPUT_CHARS = 500
LOGGER = logging.getLogger(__name__)
RuntimeLogStage = Literal[
    "accepted",
    "final_emitted",
    "timeout",
    "cancelled",
    "run_summary",
]
RuntimeOutcome = Literal["complete", "rejected", "failed", "timeout", "cancelled"]
HANGUL_PATTERN = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]")


class RuntimeCopy(NamedTuple):
    progress: str
    failure: str
    configuration_unavailable: str
    rejection: str


RUNTIME_COPY = {
    OutputLanguage.EN: RuntimeCopy(
        progress=(
            "Collecting bounded evidence for {services} over the recent {minutes} minutes…\n\n"
        ),
        failure="The bounded investigation failed safely.",
        configuration_unavailable="The bounded investigation is not configured.",
        rejection=(
            "OpsPilot MVP supports read-only investigations of the configured service catalog "
            "over 1-120 minutes. Recovery and execution requests are not supported."
        ),
    ),
    OutputLanguage.KO: RuntimeCopy(
        progress="최근 {minutes}분 동안 {services}의 제한된 증거를 수집하고 있습니다…\n\n",
        failure="제한된 범위의 조사를 안전하게 완료하지 못했습니다.",
        configuration_unavailable="제한된 조사를 실행하도록 구성되지 않았습니다.",
        rejection=(
            "OpsPilot MVP는 구성된 서비스 카탈로그의 최근 1~120분 상태에 대한 "
            "읽기 전용 조사만 지원합니다. 복구 및 실행 요청은 지원하지 않습니다."
        ),
    ),
}
RUNTIME_FAILURE_TEXT = RUNTIME_COPY[OutputLanguage.EN].failure

RUNTIME_SOURCE_ALLOWLIST = (
    "opspilot/__init__.py",
    "opspilot/agent/__init__.py",
    "opspilot/agent/runtime.py",
    "opspilot/agent/runtime_agent.py",
    "opspilot/catalog.py",
    "opspilot/domain.py",
    "opspilot/parser.py",
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
    services: list[str] = Field(default_factory=list)
    window_minutes: int | None = None
    user_query: str = Field(default="", exclude=True)
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
    payload: dict[str, str | int] = {
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
        payload["outcome"] = summary.outcome
    LOGGER.info("%s", json.dumps(payload, separators=(",", ":"), sort_keys=True))


def validate_runtime_api_input(value: str) -> RuntimeInputDecision:
    """Validate the shared bounded scope used by the Enterprise API adapter."""

    text = value.strip()
    output_language = OutputLanguage.KO if HANGUL_PATTERN.search(text) else OutputLanguage.EN
    if not MIN_INPUT_CHARS <= len(text) <= MAX_INPUT_CHARS:
        return RuntimeInputDecision(
            accepted=False,
            rejection_code="invalid_length",
            output_language=output_language,
        )
    try:
        request = parse_investigation_request(text, catalog=load_service_catalog())
    except ValueError as error:
        code = "unsupported_window" if "time window" in str(error) else "unsupported_service"
        return RuntimeInputDecision(
            accepted=False,
            rejection_code=code,
            output_language=output_language,
        )
    if request.requested_actions:
        return RuntimeInputDecision(
            accepted=False,
            rejection_code="action_request_rejected",
            output_language=output_language,
        )
    return RuntimeInputDecision(
        accepted=True,
        service=request.services[0] if len(request.services) == 1 else None,
        services=request.services,
        window_minutes=round((request.end_time - request.start_time).total_seconds() / 60),
        user_query=text,
        output_language=output_language,
        assumptions=request.assumptions,
    )


def _content_text(content: types.Content | None) -> str:
    if content is None:
        return ""
    return "".join(part.text or "" for part in content.parts or [])


def _safe_rejection(decision: RuntimeInputDecision) -> RuntimeInvocationResult:
    summary = RuntimeRunSummary(
        run_id=decision.run_id,
        outcome="rejected",
    )
    return RuntimeInvocationResult(
        accepted=False,
        succeeded=False,
        rejection_code=decision.rejection_code,
        output_markdown=RUNTIME_COPY[decision.output_language].rejection,
        run_id=decision.run_id,
        summary=summary,
    )


async def run_live_runtime_investigation(
    decision: RuntimeInputDecision,
) -> RuntimeInvocationResult:
    """Call the bounded persistent-investigation API once."""

    api_url = os.getenv("OPSPILOT_INVESTIGATION_API_URL", "").strip().rstrip("/")
    if not api_url:
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=False,
            rejection_code="runtime_configuration_unavailable",
            output_markdown=RUNTIME_COPY[decision.output_language].configuration_unavailable,
            run_id=decision.run_id,
            summary=RuntimeRunSummary(run_id=decision.run_id, outcome="failed"),
        )
    return await _run_api_runtime_investigation(decision, api_url=api_url)


def _api_request(
    url: str,
    *,
    token: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    accept: str = "application/json",
    timeout_seconds: float = 5,
) -> tuple[int, bytes]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = UrlRequest(
        url,
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read()
    except HTTPError as error:
        body = error.read()
        status = error.code
        error.close()
        return status, body
    except (URLError, OSError):
        return 0, b""


async def _run_api_runtime_investigation(
    decision: RuntimeInputDecision, *, api_url: str
) -> RuntimeInvocationResult:
    """Thin Enterprise adapter: enqueue, poll, and return the persisted report."""

    audience = os.getenv("OPSPILOT_INVESTIGATION_API_AUDIENCE", api_url).strip()
    try:
        token = await asyncio.to_thread(id_token.fetch_id_token, AuthRequest(), audience)
        status, markdown = await asyncio.to_thread(
            _api_request,
            f"{api_url}/internal/v1/runtime/investigations",
            token=token,
            method="POST",
            payload={"query": decision.user_query, "mode": "STANDARD"},
            accept="text/markdown",
            timeout_seconds=14,
        )
        if status != 200:
            raise RuntimeError("investigation API did not return a persisted report")
        summary = RuntimeRunSummary(
            run_id=decision.run_id,
            outcome="complete",
        )
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown=markdown.decode("utf-8"),
            run_id=decision.run_id,
            summary=summary,
        )
    except (
        GoogleAuthError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        RuntimeError,
        TimeoutError,
    ):
        summary = RuntimeRunSummary(
            run_id=decision.run_id,
            outcome="failed",
        )
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=False,
            rejection_code="runtime_failed",
            output_markdown=RUNTIME_COPY[decision.output_language].failure,
            run_id=decision.run_id,
            summary=summary,
        )


async def process_runtime_input(
    text: str,
    *,
    handler: RuntimeHandler = run_live_runtime_investigation,
) -> RuntimeInvocationResult:
    decision = validate_runtime_api_input(text)
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
        input_text = _content_text(context.user_content)
        decision = validate_runtime_api_input(input_text)
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
        progress = copy.progress.format(
            services=", ".join(decision.services),
            minutes=decision.window_minutes,
        )
        handler_task: asyncio.Future[RuntimeInvocationResult] | None = None
        try:
            yield _runtime_event(
                context,
                author=self.name,
                text=progress,
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
        description="Catalog-bounded read-only persistent incident investigation.",
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
