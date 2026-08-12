from __future__ import annotations

import hashlib
import tarfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from opspilot.agent.runtime import (
    RUNTIME_DISPLAY_NAME,
    RUNTIME_PROBE_GATE,
    RuntimeInvocationResult,
    RuntimeProbeBlocker,
    RuntimeProbeFailure,
    create_runtime_root_agent,
    package_runtime,
    process_runtime_input,
    run_runtime_probe,
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
    assert "rejection_code: `unsupported_service`" in result.output_markdown
    assert "evidence_api_calls: `0`" in result.output_markdown
    assert "model_calls: `0`" in result.output_markdown


async def test_M7_fixture_runtime_preserves_existing_two_model_node_graph() -> None:
    result = await smoke_runtime()

    assert result.accepted is True
    assert result.succeeded is True
    assert result.model_calls == 2
    assert result.citation_coverage == 1.0
    assert result.unauthorized_action_count == 0
    assert "EV-" in result.output_markdown
    assert "citation_coverage: `1.00`" in result.output_markdown
    assert "unauthorized_action_count: `0`" in result.output_markdown


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


class FakeProbeClient:
    def __init__(self, *, runtimes: int = 1, failure: RuntimeProbeBlocker | None = None) -> None:
        self.runtimes = runtimes
        self.failure = failure
        self.queries = 0

    async def list_runtimes(self) -> list[Mapping[str, Any]]:
        if self.failure:
            raise RuntimeProbeFailure(self.failure)
        return [
            {"name": f"hidden-runtime-{index}", "displayName": RUNTIME_DISPLAY_NAME}
            for index in range(self.runtimes)
        ]

    async def query(self, _runtime_name: str) -> Mapping[str, Any]:
        self.queries += 1
        return {
            "output": (
                "## Runtime acceptance audit\n"
                "- rejection_code: `unsupported_service`\n"
                "- evidence_api_calls: `0`\n"
                "- model_calls: `0`\n"
            )
        }


async def test_M7_runtime_probe_is_default_off_and_executes_no_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(RUNTIME_PROBE_GATE, raising=False)
    client = FakeProbeClient()

    result = await run_runtime_probe(client=client)

    assert result.succeeded is False
    assert result.blocker_code == "gate_disabled"
    assert result.executed_query_count == 0
    assert client.queries == 0


async def test_M7_runtime_probe_sends_one_fixed_request_and_returns_only_safe_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(RUNTIME_PROBE_GATE, "true")
    client = FakeProbeClient()

    result = await run_runtime_probe(client=client)

    assert result.succeeded is True
    assert result.runtime_match_count == 1
    assert result.executed_query_count == 1
    assert result.safe_rejection_observed is True
    assert result.rejection_code == "unsupported_service"
    assert client.queries == 1
    assert "hidden-runtime" not in result.model_dump_json()


@pytest.mark.parametrize(
    "failure",
    ["unauthorized", "forbidden", "not_found", "upstream_error", "invalid_response"],
)
async def test_M7_runtime_probe_normalizes_failures_without_raw_response(
    monkeypatch: pytest.MonkeyPatch, failure: RuntimeProbeBlocker
) -> None:
    monkeypatch.setenv(RUNTIME_PROBE_GATE, "true")

    result = await run_runtime_probe(client=FakeProbeClient(failure=failure))

    assert result.succeeded is False
    assert result.blocker_code == failure
    assert result.executed_query_count == 0
