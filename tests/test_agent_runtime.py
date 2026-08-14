from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tarfile
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest
from google.adk.agents import InvocationContext
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.oauth2 import id_token
from vertexai import agent_engines

import opspilot.agent.runtime as runtime_module
from opspilot.agent.runtime import (
    RUNTIME_FAILURE_TEXT,
    RUNTIME_SOURCE_ALLOWLIST,
    RuntimeInvocationResult,
    create_runtime_root_agent,
    package_runtime,
    process_runtime_input,
    run_live_runtime_investigation,
    validate_runtime_api_input,
)
from opspilot.agent.runtime_agent import (
    OpsPilotRuntimeApp,
    _normalize_agent_engine_project,
    create_ephemeral_session_service,
    create_runtime_app,
    root_agent,
)
from opspilot.audit import audit_hash
from opspilot.domain import OutputLanguage


def _single_converted_event(chunk: dict[str, Any]) -> dict[str, Any]:
    events = chunk["events"]
    assert isinstance(events, list) and len(events) == 1
    event = events[0]
    assert isinstance(event, dict)
    return event


def _local_runtime_app(handler: Any) -> OpsPilotRuntimeApp:
    app = create_runtime_app(handler=handler)
    app._tmpl_attrs["project"] = None
    app._tmpl_attrs["location"] = None
    return app


def _request_json(
    text: str, *, user: str = "private-user", session: str = "private-session"
) -> str:
    return json.dumps(
        {
            "message": {"role": "user", "parts": [{"text": text}]},
            "userId": user,
            "sessionId": session,
        }
    )


def test_agent_engine_normalizes_numeric_project_without_project_iam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MetadataResponse:
        def __enter__(self) -> MetadataResponse:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b"safe-project-id"

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "123456789012")
    monkeypatch.setattr(
        "opspilot.agent.runtime_agent.urlopen",
        lambda *_args, **_kwargs: MetadataResponse(),
    )

    _normalize_agent_engine_project()

    assert os.environ["GOOGLE_CLOUD_PROJECT"] == "safe-project-id"


def test_enterprise_adapter_defers_scope_and_intent_to_the_api() -> None:
    explicit = validate_runtime_api_input(
        "order-service inventory-service 최근 120분 오류를 분석해줘"
    )
    defaulted = validate_runtime_api_input("상태를 근거와 함께 분석해줘")

    assert explicit.accepted is True
    assert explicit.services == []
    assert explicit.window_minutes is None
    assert defaulted.accepted is True
    assert defaulted.services == []
    assert defaulted.window_minutes is None


def test_enterprise_adapter_only_rejects_transport_invalid_input() -> None:
    text = "x"
    decision = validate_runtime_api_input(text)

    assert decision.accepted is False
    assert decision.rejection_code == "invalid_length"

    assert validate_runtime_api_input("shipping-service 최근 30분 상태를 분석해줘").accepted
    assert validate_runtime_api_input("payment-service 최근 121분 상태를 분석해줘").accepted
    assert validate_runtime_api_input("payment-service를 재시작해").accepted


def test_runtime_language_detection_prefers_korean_when_hangul_is_present() -> None:
    korean = validate_runtime_api_input("payment-service 최근 30분 상태를 분석해줘")
    mixed = validate_runtime_api_input("payment-service recent 30 minutes status를 analyze 해줘")
    english = validate_runtime_api_input("payment-service recent 30 minutes status analyze")
    rejected_korean = validate_runtime_api_input("가")
    rejected_english = validate_runtime_api_input("")

    assert korean.output_language == OutputLanguage.KO
    assert mixed.output_language == OutputLanguage.KO
    assert english.output_language == OutputLanguage.EN
    assert rejected_korean.output_language == OutputLanguage.KO
    assert rejected_english.output_language == OutputLanguage.EN


@pytest.mark.asyncio
async def test_rejection_stops_before_handler() -> None:
    calls = 0

    async def forbidden_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("rejected input reached the handler")

    result = await process_runtime_input("x", handler=forbidden_handler)

    assert result.accepted is False
    assert result.rejection_code == "invalid_length"
    assert calls == 0


@pytest.mark.asyncio
async def test_runtime_requires_the_persistent_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPSPILOT_INVESTIGATION_API_URL", raising=False)
    decision = validate_runtime_api_input("payment-service 최근 30분 상태를 분석해줘")

    result = await run_live_runtime_investigation(decision)

    assert result.accepted is True
    assert result.succeeded is False
    assert result.rejection_code == "runtime_configuration_unavailable"
    assert (
        result.output_markdown
        == runtime_module.RUNTIME_COPY[OutputLanguage.KO].configuration_unavailable
    )


@pytest.mark.asyncio
async def test_runtime_calls_the_internal_api_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object] | None, float, str | None, str | None]] = []
    monkeypatch.setenv("OPSPILOT_INVESTIGATION_API_URL", "https://investigation.example")
    monkeypatch.setenv("OPSPILOT_INVESTIGATION_API_AUDIENCE", "https://audience.example")
    monkeypatch.setattr(id_token, "fetch_id_token", lambda *_: "token")

    def fake_request(
        url: str,
        *,
        token: str,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        accept: str = "application/json",
        timeout_seconds: float = 5,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[int, bytes]:
        del token, method, accept
        calls.append((url, payload, timeout_seconds, trace_id, idempotency_key))
        return 200, json.dumps(
            {
                "intent": "INVESTIGATE",
                "outcome": "complete",
                "accepted": True,
                "started_investigation": True,
                "markdown": "# Persisted report\n",
                "progress_markdown": "Collecting evidence…\n\n",
            }
        ).encode()

    monkeypatch.setattr(runtime_module, "_api_request", fake_request)
    decision = validate_runtime_api_input(
        "order-service inventory-service recent 15 minutes status analyze"
    )

    result = await run_live_runtime_investigation(decision)

    assert result.succeeded is True
    assert result.output_markdown == "# Persisted report\n"
    assert calls == [
        (
            "https://investigation.example/internal/v2/runtime/turns",
            {
                "query": "order-service inventory-service recent 15 minutes status analyze",
                "mode": "STANDARD",
                "run_id": decision.run_id,
                "correlation_id": decision.correlation_id,
                "trace_id": decision.trace_id,
                "actor_hash": None,
                "session_hash": None,
                "query_hash": decision.query_hash,
                "output_language": "en",
            },
            runtime_module.RUNTIME_API_TIMEOUT_SECONDS,
            decision.trace_id,
            decision.run_id,
        )
    ]


def test_runtime_reuses_identity_token_within_its_safe_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fetch(*_: object) -> str:
        nonlocal calls
        calls += 1
        return "synthetic-token"

    runtime_module._ID_TOKEN_CACHE.clear()
    monkeypatch.setattr(id_token, "fetch_id_token", fetch)

    first = runtime_module._fetch_cached_id_token("https://cache-audience.invalid")
    second = runtime_module._fetch_cached_id_token("https://cache-audience.invalid")

    assert first == second == "synthetic-token"
    assert calls == 1
    runtime_module._ID_TOKEN_CACHE.clear()


def test_runtime_write_retries_only_with_an_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unavailable(*_: object, **__: object) -> None:
        nonlocal calls
        calls += 1
        raise URLError("unavailable")

    monkeypatch.setattr(runtime_module, "urlopen", unavailable)
    status, _ = runtime_module._api_request(
        "https://sensitive.invalid",
        token="secret-token",
        method="POST",
        payload={"safe": True},
        timeout_seconds=1,
    )
    assert status == 0
    assert calls == 1

    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return b"ok"

    calls = 0

    def eventually_available(*_: object, **__: object) -> Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise URLError("unavailable")
        return Response()

    monkeypatch.setattr(runtime_module, "urlopen", eventually_available)
    status, body = runtime_module._api_request(
        "https://sensitive.invalid",
        token="secret-token",
        method="POST",
        payload={"safe": True},
        timeout_seconds=1,
        idempotency_key="RUN-0123456789ABCDEF",
    )
    assert (status, body) == (200, b"ok")
    assert calls == 3


@pytest.mark.asyncio
async def test_runtime_agent_streams_dynamic_progress_then_report() -> None:
    calls = 0

    async def handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
            started_investigation=True,
            progress_markdown="최근 15분 동안 order-service의 증거를 수집하고 있습니다…\n\n",
        )

    runner = InMemoryRunner(node=create_runtime_root_agent(handler=handler), app_name="test")
    await runner.session_service.create_session(
        app_name="test", user_id="ignored-user", session_id="session"
    )
    events = [
        event
        async for event in runner.run_async(
            user_id="ignored-user",
            session_id="session",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="order-service 최근 15분 상태를 분석해줘")],
            ),
        )
    ]

    assert calls == 1
    assert len(events) == 2
    assert events[0].partial is True and events[0].turn_complete is False
    assert events[0].content is not None and events[0].content.parts is not None
    progress = events[0].content.parts[0].text or ""
    assert "order-service" in progress and "15분" in progress
    assert progress.endswith("…\n\n")
    assert events[1].turn_complete is True
    assert events[1].content is not None and events[1].content.parts is not None
    assert events[1].content.parts[0].text == "# Safe report\n"


@pytest.mark.asyncio
async def test_runtime_buffers_progress_until_handler_completes() -> None:
    release = asyncio.Event()
    started = asyncio.Event()

    async def delayed_handler(_decision: object) -> RuntimeInvocationResult:
        started.set()
        await release.wait()
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Delayed safe report\n",
            started_investigation=True,
            progress_markdown="Collecting bounded evidence…\n\n",
        )

    agent = create_runtime_root_agent(handler=delayed_handler)
    session_service = create_ephemeral_session_service()
    session = await session_service.create_session(
        app_name="test", user_id="ignored-user", session_id="session"
    )
    context = InvocationContext(
        session_service=session_service,
        invocation_id="buffered-invocation",
        agent=agent,
        user_content=types.Content(
            role="user",
            parts=[types.Part(text="payment-service recent 30 minutes status analyze")],
        ),
        session=session,
    )
    stream = agent._run_async_impl(context)
    first_event = asyncio.create_task(anext(stream))

    await started.wait()
    await asyncio.sleep(0)
    assert first_event.done() is False

    release.set()
    progress = await first_event
    final = await anext(stream)

    assert progress.partial is True and progress.turn_complete is False
    assert final.partial is False and final.turn_complete is True
    assert final.content is not None and final.content.parts is not None
    assert final.content.parts[0].text == "# Delayed safe report\n"


@pytest.mark.asyncio
async def test_enterprise_session_uses_ephemeral_state_and_hides_identifiers() -> None:
    decisions: list[Any] = []

    async def handler(decision: object) -> RuntimeInvocationResult:
        decisions.append(decision)
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
            started_investigation=True,
            progress_markdown="Collecting bounded evidence…\n\n",
        )

    app = _local_runtime_app(handler)
    request_text = "payment-service recent 30 minutes status analyze"
    events = [
        event
        async for event in app.streaming_agent_run_with_events(
            _request_json(request_text, user="private-enterprise-user")
        )
    ]
    serialized = json.dumps(events)

    assert len(events) == 2
    assert _single_converted_event(events[0])["partial"] is True
    assert _single_converted_event(events[1])["turn_complete"] is True
    assert "private-enterprise-user" not in serialized
    assert request_text not in serialized
    decision = decisions[0]
    assert decision.actor_hash == audit_hash("enterprise_actor", "private-enterprise-user")
    assert decision.session_hash == audit_hash("enterprise_session", "private-session")


@pytest.mark.asyncio
async def test_enterprise_follow_up_reuses_external_session_hash() -> None:
    decisions: list[Any] = []

    async def handler(decision: object) -> RuntimeInvocationResult:
        decisions.append(decision)
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
            started_investigation=True,
            progress_markdown="Collecting bounded evidence...\n",
        )

    app = _local_runtime_app(handler)
    for query in (
        "payment-service recent 30 minutes status analyze",
        "Summarize that report",
    ):
        _ = [
            event
            async for event in app.streaming_agent_run_with_events(
                _request_json(query, session="stable-enterprise-chat")
            )
        ]

    assert len(decisions) == 2
    assert decisions[0].session_hash == decisions[1].session_hash
    assert decisions[0].session_hash == audit_hash("enterprise_session", "stable-enterprise-chat")


@pytest.mark.asyncio
async def test_runtime_exception_emits_fixed_safe_final_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing_handler(_decision: object) -> RuntimeInvocationResult:
        raise RuntimeError("private-enterprise-user secret prompt")

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    app = _local_runtime_app(failing_handler)
    chunks = [
        chunk
        async for chunk in app.streaming_agent_run_with_events(
            _request_json("payment-service recent 30 minutes status analyze")
        )
    ]
    serialized = json.dumps(chunks)

    assert len(chunks) == 2
    assert _single_converted_event(chunks[1])["content"]["parts"][0]["text"] == RUNTIME_FAILURE_TEXT
    assert "private-user" not in serialized
    assert "secret prompt" not in serialized
    assert '"stage":"final_emitted"' in caplog.text


@pytest.mark.asyncio
async def test_runtime_deadline_cancels_handler_and_emits_safe_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = asyncio.Event()

    async def blocked_handler(_decision: object) -> RuntimeInvocationResult:
        try:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        finally:
            cancelled.set()

    monkeypatch.setattr(runtime_module, "RUNTIME_DEADLINE_SECONDS", 0.01)
    runner = InMemoryRunner(
        node=create_runtime_root_agent(handler=blocked_handler), app_name="test"
    )
    await runner.session_service.create_session(
        app_name="test", user_id="ignored-user", session_id="session"
    )
    events = [
        event
        async for event in runner.run_async(
            user_id="ignored-user",
            session_id="session",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="payment-service recent 30 minutes status analyze")],
            ),
        )
    ]

    assert len(events) == 2
    assert events[-1].content is not None and events[-1].content.parts is not None
    assert events[-1].content.parts[0].text == RUNTIME_FAILURE_TEXT
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_runtime_generator_exit_cancels_started_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0
    cancelled = asyncio.Event()

    async def started_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        try:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        finally:
            cancelled.set()

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    agent = create_runtime_root_agent(handler=started_handler)
    session_service = create_ephemeral_session_service()
    session = await session_service.create_session(
        app_name="test", user_id="private-generator-user", session_id="private-session"
    )
    context = InvocationContext(
        session_service=session_service,
        invocation_id="private-generator-invocation",
        agent=agent,
        user_content=types.Content(
            role="user",
            parts=[types.Part(text="payment-service recent 30 minutes status analyze")],
        ),
        session=session,
    )
    stream = agent._run_async_impl(context)

    first_event = asyncio.create_task(anext(stream))
    while calls == 0:
        await asyncio.sleep(0)
    first_event.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_event

    assert calls == 1
    assert cancelled.is_set()
    assert '"stage":"handler_started"' in caplog.text
    assert '"stage":"cancelled"' in caplog.text
    assert "private-generator" not in caplog.text


@pytest.mark.asyncio
async def test_concurrent_enterprise_requests_keep_events_and_logs_private(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0

    async def handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
            started_investigation=True,
            progress_markdown="Collecting bounded evidence…\n\n",
        )

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    app = _local_runtime_app(handler)

    async def collect(index: int) -> list[dict[str, Any]]:
        return [
            chunk
            async for chunk in app.streaming_agent_run_with_events(
                _request_json(
                    "payment-service recent 30 minutes status analyze",
                    user=f"private-user-{index}",
                    session=f"private-session-{index}",
                )
            )
        ]

    results = await asyncio.gather(*(collect(index) for index in range(20)))
    accepted_logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "opspilot.agent.runtime"
        and json.loads(record.message).get("stage") == "accepted"
    ]
    summary_logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "opspilot.agent.runtime"
        and json.loads(record.message).get("stage") == "run_summary"
    ]
    serialized = json.dumps(results)

    assert calls == 20
    assert all(len(events) == 2 for events in results)
    assert len(accepted_logs) == 20 and len(summary_logs) == 20
    assert len({item["run_id"] for item in accepted_logs}) == 20
    assert all(
        set(item)
        == {
            "event",
            "run_id",
            "correlation_id",
            "trace_id",
            "stage",
            "elapsed_ms",
        }
        for item in accepted_logs
    )
    assert all(item["outcome"] == "complete" for item in summary_logs)
    assert "private-user" not in serialized
    assert "private-session" not in caplog.text


def test_runtime_package_is_deterministic_and_thin() -> None:
    first = package_runtime(Path(".tmp/test-runtime-a"))
    second = package_runtime(Path(".tmp/test-runtime-b"))
    first_path = Path(".tmp/test-runtime-a/opspilot-agent-runtime.tar.gz")
    second_path = Path(".tmp/test-runtime-b/opspilot-agent-runtime.tar.gz")

    assert first.sha256 == second.sha256
    assert hashlib.sha256(first_path.read_bytes()).hexdigest() == first.sha256
    assert first_path.read_bytes() == second_path.read_bytes()
    with tarfile.open(first_path, "r:gz") as archive:
        names = archive.getnames()
        requirements = archive.extractfile("requirements.txt")
        assert requirements is not None
        requirement_text = requirements.read().decode()
    assert set(names) == {*RUNTIME_SOURCE_ALLOWLIST, "requirements.txt"}
    assert "google-adk==2.5.0" in requirement_text
    assert "google-cloud-aiplatform[agent-engines]==1.153.1" in requirement_text
    assert not any(
        token in name
        for name in names
        for token in (
            "contracts.py",
            "models.py",
            "runner.py",
            "workflow.py",
            "evidence.py",
            "knowledge_search.py",
            "redaction.py",
            "reporting.py",
            "scoring.py",
        )
    )


def test_packaged_entrypoint_is_narrow_adk_app() -> None:
    assert isinstance(root_agent, agent_engines.AdkApp)
    assert isinstance(root_agent, OpsPilotRuntimeApp)
    assert isinstance(create_ephemeral_session_service(), InMemorySessionService)
    assert root_agent.register_operations() == {"async_stream": ["streaming_agent_run_with_events"]}
    assert root_agent._telemetry_enabled() is False
    assert callable(root_agent.streaming_agent_run_with_events)


def test_runtime_package_cannot_escape_tmp() -> None:
    with pytest.raises(ValueError, match=r"under \.tmp"):
        package_runtime(Path("outside-runtime-package"))
