from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from opspilot.agent.runtime import (
    RuntimeInvocationResult,
    create_runtime_root_agent,
    package_runtime,
    process_runtime_input,
    smoke_runtime,
    validate_runtime,
    validate_runtime_input,
)
from opspilot.catalog import load_service_catalog


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("order-service 최근 상태를 분석해줘", "unsupported_service"),
        ("payment-service 최근 60분 상태를 분석해줘", "unsupported_window"),
        ("payment-service 지난 7일 상태를 분석해줘", "unsupported_window"),
        ("payment-service를 재시작해", "action_request_rejected"),
        ("payment-service에 명령을 전달해줘", "unsupported_intent"),
        ("x", "invalid_length"),
    ],
)
def test_M7_runtime_rejects_out_of_scope_input_before_work(text: str, code: str) -> None:
    decision = validate_runtime_input(text)

    assert decision.accepted is False
    assert decision.rejection_code == code


def test_M7_runtime_defaults_to_fixed_recent_window_without_copying_input() -> None:
    decision = validate_runtime_input("payment-service 상태를 근거와 함께 분석해줘")

    assert decision.accepted is True
    assert decision.service == "payment-service"
    assert decision.window_minutes == 30
    assert len(decision.assumptions) == 1


async def test_M7_rejection_makes_zero_evidence_and_model_calls() -> None:
    calls = 0

    async def forbidden_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("out-of-scope input reached the investigation handler")

    result = await process_runtime_input(
        "inventory-service 상태를 분석해줘", handler=forbidden_handler
    )

    assert result.accepted is False
    assert result.model_calls == 0
    assert result.evidence_api_calls == 0
    assert calls == 0


async def test_M7_fixture_runtime_preserves_existing_two_model_node_graph() -> None:
    result = await smoke_runtime()

    assert result.accepted is True
    assert result.succeeded is True
    assert result.model_calls == 2
    assert result.citation_coverage == 1.0
    assert result.unauthorized_action_count == 0
    assert "EV-" in result.output_markdown


async def test_M7_public_callback_skips_the_upper_routing_model() -> None:
    calls = 0

    async def handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            model_calls=2,
            citation_coverage=1.0,
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


def test_M7_runtime_validation_and_catalog_work_outside_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    catalog = load_service_catalog()
    result = validate_runtime()

    assert "payment-service" in catalog.services
    assert result.valid is True
    assert result.upper_routing_model_calls == 0
    assert result.message_content_capture_enabled is False


def test_M7_runtime_package_is_deterministic_and_allowlisted() -> None:
    first = package_runtime(Path(".tmp/test-m7-runtime-a"))
    second = package_runtime(Path(".tmp/test-m7-runtime-b"))
    first_path = Path(".tmp/test-m7-runtime-a/opspilot-agent-runtime.tar.gz")
    second_path = Path(".tmp/test-m7-runtime-b/opspilot-agent-runtime.tar.gz")

    assert first.sha256 == second.sha256
    assert hashlib.sha256(first_path.read_bytes()).hexdigest() == first.sha256
    with tarfile.open(first_path, "r:gz") as archive:
        names = archive.getnames()
        requirements = archive.extractfile("requirements.txt")
        assert requirements is not None
        requirement_text = requirements.read().decode()
    assert "opspilot/agent/runtime_agent.py" in names
    assert "opspilot/resources/services.yaml" in names
    assert "google-adk==2.5.0" in requirement_text
    assert all(not name.startswith(("tests/", "docs/", "infra/", ".git", ".env")) for name in names)
    assert all(not name.startswith("scenarios/") for name in names)
    assert first_path.read_bytes() == second_path.read_bytes()


def test_M7_runtime_package_cannot_escape_tmp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"under \.tmp"):
        package_runtime(tmp_path)
