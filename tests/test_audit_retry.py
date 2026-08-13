from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from opspilot.audit import ToolAuditContext, ToolCallAuditEvent, log_tool_call
from opspilot.domain import SourceType, ToolErrorCategory
from opspilot.evidence import (
    EvidenceCollectionRequest,
    FixtureEvidenceClient,
    LiveEvidenceFailure,
    UrllibJsonTransport,
    collect_evidence,
)
from opspilot.retry import RetryPolicy, run_with_retry


def test_retry_policy_uses_bounded_exponential_full_jitter() -> None:
    calls = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("transient")
        return "ok"

    result = run_with_retry(
        operation,
        should_retry=lambda error: isinstance(error, TimeoutError),
        policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0.1,
            max_delay_seconds=1,
            deadline_seconds=5,
        ),
        sleeper=delays.append,
        random_source=lambda: 1.0,
        monotonic=lambda: 0.0,
    )

    assert result == "ok"
    assert calls == 3
    assert delays == [0.1, 0.2]


def test_retry_policy_stops_on_nonretryable_error_and_deadline() -> None:
    calls = 0

    def invalid() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("invalid")

    with pytest.raises(ValueError, match="invalid"):
        run_with_retry(
            invalid,
            should_retry=lambda error: isinstance(error, TimeoutError),
            policy=RetryPolicy(),
            sleeper=lambda _: None,
        )
    assert calls == 1

    deadline_calls = 0

    def timeout() -> None:
        nonlocal deadline_calls
        deadline_calls += 1
        raise TimeoutError("late")

    with pytest.raises(TimeoutError, match="late"):
        run_with_retry(
            timeout,
            should_retry=lambda error: isinstance(error, TimeoutError),
            policy=RetryPolicy(base_delay_seconds=0.1, deadline_seconds=0.05),
            sleeper=lambda _: None,
            random_source=lambda: 1.0,
            monotonic=lambda: 0.0,
        )
    assert deadline_calls == 1


@pytest.mark.asyncio
async def test_evidence_transport_retries_only_retryable_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def transient(*_: object, **__: object) -> tuple[dict[str, Any], int]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise LiveEvidenceFailure(
                "EVIDENCE_UPSTREAM",
                ToolErrorCategory.UPSTREAM,
                retryable=True,
                safe_message="Evidence source is temporarily unavailable.",
            )
        return {"entries": []}, 2

    monkeypatch.setattr(UrllibJsonTransport, "_request_sync", staticmethod(transient))
    transport = UrllibJsonTransport(
        sleeper=lambda _: None,
        random_source=lambda: 0.0,
    )
    payload, api_calls = await transport.request(
        "GET",
        "https://sensitive.invalid",
        token="secret-token",
        quota_project="secret-project",
    )
    assert payload == {"entries": []}
    assert api_calls == 2
    assert calls == 3

    calls = 0

    def forbidden(*_: object, **__: object) -> tuple[dict[str, Any], int]:
        nonlocal calls
        calls += 1
        raise LiveEvidenceFailure(
            "EVIDENCE_FORBIDDEN",
            ToolErrorCategory.AUTH,
            retryable=False,
            safe_message="Evidence access was denied.",
        )

    monkeypatch.setattr(UrllibJsonTransport, "_request_sync", staticmethod(forbidden))
    with pytest.raises(LiveEvidenceFailure) as failure:
        await transport.request(
            "GET",
            "https://sensitive.invalid",
            token="secret-token",
            quota_project="secret-project",
        )
    assert failure.value.code == "EVIDENCE_FORBIDDEN"
    assert calls == 1


@pytest.mark.asyncio
async def test_tool_call_logs_have_fixed_safe_schema_for_success_and_partial(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="opspilot.evidence")
    end = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    await collect_evidence(
        FixtureEvidenceClient("SCN-001", fail_sources=frozenset({SourceType.METRIC})),
        EvidenceCollectionRequest(
            scenario_id="SCN-001",
            start_time=end - timedelta(minutes=15),
            end_time=end,
            services=["payment-service"],
        ),
        audit_context=ToolAuditContext(
            trace_id="0123456789abcdef0123456789abcdef",
            correlation_id="COR-0123456789ABCDEF",
            investigation_id="INV-RUN-0123456789ABCDEF",
            run_id="RUN-0123456789ABCDEF",
        ),
    )

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "opspilot.evidence"
    ]
    assert len(events) == 4
    expected_fields = {
        "event",
        "trace_id",
        "correlation_id",
        "investigation_id",
        "run_id",
        "tool_call_id",
        "tool_name",
        "environment",
        "service_count",
        "window_seconds",
        "started_at",
        "finished_at",
        "duration_ms",
        "status",
        "api_call_count",
        "result_count",
        "result_bytes",
        "truncated",
        "cache_hit",
        "error_code",
        "error_category",
        "retryable",
    }
    assert all(set(event) == expected_fields for event in events)
    assert {event["status"] for event in events} == {"OK", "ERROR"}
    serialized = json.dumps(events)
    for forbidden in (
        "secret-token",
        "private-user",
        "private-session",
        "https://",
        "secret-project",
    ):
        assert forbidden not in serialized


def test_tool_call_uses_json_stdout_on_cloud_run(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("K_SERVICE", "opspilot-investigation")
    now = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    event = ToolCallAuditEvent(
        trace_id="0123456789abcdef0123456789abcdef",
        correlation_id="COR-0123456789ABCDEF",
        investigation_id="INV-RUN-0123456789ABCDEF",
        run_id="RUN-0123456789ABCDEF",
        tool_call_id="TOOL-1",
        tool_name="logging.query",
        environment="DEV",
        service_count=1,
        window_seconds=900,
        started_at=now,
        finished_at=now,
        duration_ms=0,
        status="OK",
        api_call_count=1,
        result_count=1,
        result_bytes=10,
        truncated=False,
        cache_hit=False,
    )

    log_tool_call(logging.getLogger("opspilot.test"), event)

    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "opspilot_tool_call"
    assert payload["tool_name"] == "logging.query"
