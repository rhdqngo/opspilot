from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types
from vertexai import agent_engines

from opspilot.agent.runtime import (
    RUNTIME_SOURCE_ALLOWLIST,
    RuntimeInvocationResult,
    create_runtime_root_agent,
    package_runtime,
    process_runtime_input,
    validate_runtime_input,
)
from opspilot.agent.runtime_agent import OpsPilotRuntimeApp, root_agent


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("order-service 최근 상태를 분석해줘", "unsupported_service"),
        ("payment-service 최근 60분 상태를 분석해줘", "unsupported_window"),
        ("payment-service를 재시작해", "action_request_rejected"),
        ("payment-service 명령을 전달해줘", "unsupported_intent"),
        ("x", "invalid_length"),
    ],
)
def test_runtime_rejects_out_of_scope_input(text: str, code: str) -> None:
    decision = validate_runtime_input(text)

    assert not decision.accepted
    assert decision.rejection_code == code


def test_runtime_accepts_only_payment_recent_thirty_minutes() -> None:
    explicit = validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    defaulted = validate_runtime_input("payment-service 상태를 근거와 함께 분석해줘")

    assert explicit.accepted and explicit.window_minutes == 30
    assert defaulted.accepted and defaulted.assumptions


@pytest.mark.asyncio
async def test_rejection_stops_before_evidence_or_model_handler() -> None:
    calls = 0

    async def forbidden_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("out-of-scope input reached the investigation handler")

    result = await process_runtime_input(
        "inventory-service 상태를 분석해줘", handler=forbidden_handler
    )

    assert not result.accepted
    assert result.rejection_code == "unsupported_service"
    assert calls == 0
    assert "Runtime acceptance audit" not in result.output_markdown


@pytest.mark.asyncio
async def test_public_callback_uses_deterministic_router_without_upper_model() -> None:
    calls = 0

    async def handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
        )

    runner = InMemoryRunner(node=create_runtime_root_agent(handler=handler), app_name="test")
    await runner.session_service.create_session(
        app_name="test", user_id="ignored-user", session_id="session"
    )
    outputs: list[str] = []
    async for event in runner.run_async(
        user_id="ignored-user",
        session_id="session",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="payment-service 최근 30분 상태를 분석해줘")],
        ),
    ):
        if event.content:
            outputs.extend(part.text or "" for part in event.content.parts or [])

    assert calls == 1
    assert "# Safe report" in "".join(outputs)


def test_runtime_package_is_deterministic_and_production_only() -> None:
    first = package_runtime(Path(".tmp/test-lean-runtime-a"))
    second = package_runtime(Path(".tmp/test-lean-runtime-b"))
    first_path = Path(".tmp/test-lean-runtime-a/opspilot-agent-runtime.tar.gz")
    second_path = Path(".tmp/test-lean-runtime-b/opspilot-agent-runtime.tar.gz")

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
        for token in ("cli.py", "demo", "fixtures", "terraform", "tests", "docs", "diagnostic")
    )


def test_packaged_entrypoint_is_narrow_adk_app() -> None:
    assert isinstance(root_agent, agent_engines.AdkApp)
    assert isinstance(root_agent, OpsPilotRuntimeApp)
    assert root_agent.register_operations() == {"async_stream": ["streaming_agent_run_with_events"]}
    assert callable(root_agent.streaming_agent_run_with_events)


def test_runtime_package_cannot_escape_tmp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"under \.tmp"):
        package_runtime(tmp_path)
