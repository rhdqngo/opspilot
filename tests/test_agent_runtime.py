from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from google.adk.agents import InvocationContext
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from vertexai import agent_engines

import opspilot.agent.runtime as runtime_module
from opspilot.agent.contracts import (
    AgentEvidenceContext,
    HypothesisDraft,
    HypothesisDraftBatch,
)
from opspilot.agent.runtime import (
    RUNTIME_FAILURE_TEXT,
    RUNTIME_PROGRESS_TEXT,
    RUNTIME_SOURCE_ALLOWLIST,
    RuntimeInvocationResult,
    create_runtime_root_agent,
    package_runtime,
    process_runtime_input,
    validate_runtime_input,
)
from opspilot.agent.runtime_agent import (
    OpsPilotRuntimeApp,
    create_ephemeral_session_service,
    create_runtime_app,
    root_agent,
)
from opspilot.agent.workflow import build_runtime_rca_input
from opspilot.domain import EvidenceDirection, EvidenceItem, OutputLanguage, SourceType
from opspilot.evidence import (
    CollectionBudgetUsage,
    EvidenceBackend,
    EvidenceCollectionResult,
)


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


def test_runtime_language_detection_prefers_korean_when_hangul_is_present() -> None:
    korean = validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    mixed = validate_runtime_input("payment-service recent 30 minutes status를 analyze 해줘")
    english = validate_runtime_input("payment-service recent 30 minutes status analyze")
    rejected_korean = validate_runtime_input("가")
    rejected_english = validate_runtime_input("")

    assert korean.output_language == OutputLanguage.KO
    assert mixed.output_language == OutputLanguage.KO
    assert english.output_language == OutputLanguage.EN
    assert rejected_korean.output_language == OutputLanguage.KO
    assert rejected_english.output_language == OutputLanguage.EN


def test_runtime_rca_input_and_language_validation_use_requested_language() -> None:
    context = AgentEvidenceContext(
        scenario_id="SCN-001",
        incident_id="INC-2026-0001",
        generated_at=datetime(2026, 8, 12, tzinfo=UTC),
        correlation_id="COR-LOCALIZED",
    )
    korean_drafts = HypothesisDraftBatch(
        drafts=[
            HypothesisDraft(
                draft_id="D-01",
                root_cause_code="PAYMENT_REVISION_REGRESSION",
                claim="결제 리비전에서 오류가 발생했습니다.",
                mechanism="변경 시점과 오류 시점이 일치합니다.",
                next_checks=["이전 설정과 비교합니다."],
            )
        ]
    )
    english_drafts = HypothesisDraftBatch(
        drafts=[
            HypothesisDraft(
                draft_id="D-01",
                root_cause_code="PAYMENT_REVISION_REGRESSION",
                claim="The payment revision introduced errors.",
                mechanism="The change and error times align.",
                next_checks=["Compare the previous configuration."],
            )
        ]
    )

    payload = build_runtime_rca_input(context, output_language=OutputLanguage.KO)

    assert payload.output_language == OutputLanguage.KO
    assert runtime_module._drafts_match_output_language(korean_drafts, OutputLanguage.KO)
    assert not runtime_module._drafts_match_output_language(english_drafts, OutputLanguage.KO)
    assert runtime_module._drafts_match_output_language(english_drafts, OutputLanguage.EN)
    assert not runtime_module._drafts_match_output_language(korean_drafts, OutputLanguage.EN)


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


def _live_collection(
    evidence: list[EvidenceItem],
    *,
    complete: bool = True,
    data_gaps: list[str] | None = None,
) -> EvidenceCollectionResult:
    return EvidenceCollectionResult(
        backend=EvidenceBackend.LIVE,
        scenario_id="SCN-001",
        complete=complete,
        source_status={source.value: True for source in SourceType},
        evidence=evidence,
        data_gaps=data_gaps or [],
        budget=CollectionBudgetUsage(
            logical_tool_calls=4,
            api_calls=4,
            result_count=len(evidence),
            response_bytes=0,
            duration_ms=1,
        ),
    )


def _runtime_evidence(
    evidence_id: str,
    source_type: SourceType,
    title: str,
    *,
    direction: EvidenceDirection = EvidenceDirection.UNKNOWN,
    quality_flags: list[str] | None = None,
) -> EvidenceItem:
    now = datetime(2026, 8, 12, 0, 0, tzinfo=UTC)
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type=source_type,
        title=title,
        service="payment-service",
        environment="dev",
        observed_at=now,
        period_start=now - timedelta(minutes=30),
        period_end=now,
        summary=f"bounded {title}",
        direction=direction,
        source_uri=f"opspilot://evidence/{evidence_id.lower()}",
        quality_flags=quality_flags or [],
    )


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
async def test_korean_rejection_uses_korean_fixed_copy_without_handler() -> None:
    calls = 0

    async def forbidden_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("rejected Korean input reached the handler")

    result = await process_runtime_input(
        "inventory-service 최근 30분 상태를 분석해줘",
        handler=forbidden_handler,
    )

    assert calls == 0
    assert result.output_markdown == runtime_module.RUNTIME_COPY[OutputLanguage.KO].rejection


@pytest.mark.asyncio
async def test_runtime_agent_streams_progress_then_report_without_upper_model() -> None:
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
    events = [
        event
        async for event in runner.run_async(
            user_id="ignored-user",
            session_id="session",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="payment-service 최근 30분 상태를 분석해줘")],
            ),
        )
    ]

    assert calls == 1
    assert len(events) == 2
    assert events[0].partial is True
    assert events[0].turn_complete is False
    assert events[0].content is not None
    assert events[0].content.parts is not None
    korean_progress = runtime_module.RUNTIME_COPY[OutputLanguage.KO].progress
    assert events[0].content.parts[0].text == korean_progress
    assert korean_progress.endswith("\u2026\n\n")
    assert f"{korean_progress}# Safe report\n".endswith("\u2026\n\n# Safe report\n")
    assert events[1].partial is False
    assert events[1].turn_complete is True
    assert events[1].content is not None
    assert events[1].content.parts is not None
    assert events[1].content.parts[0].text == "# Safe report\n"


@pytest.mark.asyncio
async def test_live_zero_point_request_skips_model_and_returns_inconclusive_report(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    metric_gaps = [
        "Cloud Run error_ratio returned no bounded points in the requested window.",
        "Cloud Run latency_p95 returned no bounded points in the requested window.",
    ]
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-MET-0001",
                SourceType.METRIC,
                "Cloud Run error_ratio",
                quality_flags=["missing_points"],
            ),
            _runtime_evidence(
                "EV-MET-0002",
                SourceType.METRIC,
                "Cloud Run latency_p95",
                quality_flags=["missing_points"],
            ),
            _runtime_evidence("EV-CHG-0001", SourceType.CHANGE, "Cloud Run revision observed"),
            _runtime_evidence("EV-KNW-0001", SourceType.KNOWLEDGE, "Payment DB pool runbook"),
        ],
        complete=False,
        data_gaps=metric_gaps,
    )
    model_calls = 0

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def forbidden_rca(
        _context: object, _output_language: OutputLanguage
    ) -> HypothesisDraftBatch:
        nonlocal model_calls
        model_calls += 1
        raise AssertionError("zero-point evidence must not reach the model")

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", forbidden_rca)
    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service recent 30 minutes status analyze")
    )

    assert model_calls == 0
    assert result.succeeded is True
    assert result.summary is not None
    assert result.summary.run_id == result.run_id
    assert result.summary.outcome == "inconclusive"
    assert result.summary.reasoning_outcome == "skipped"
    assert "# [UNCLASSIFIED] Inconclusive Investigation" in result.output_markdown
    assert "- None verified with the available evidence." in result.output_markdown
    assert "- No action is recommended with the available evidence." in result.output_markdown
    assert all(gap in result.output_markdown for gap in metric_gaps)
    timeline, sources = result.output_markdown.split("## Sources", maxsplit=1)
    assert "Payment DB pool runbook" not in timeline
    assert "Payment DB pool runbook" in sources
    assert "`EV-MET-0001` - Cloud Run error_ratio" in sources
    assert '"stage":"reasoning_skipped"' in caplog.text


@pytest.mark.asyncio
async def test_live_korean_zero_point_request_localizes_copy_and_preserves_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-MET-0001",
                SourceType.METRIC,
                "Cloud Run error_ratio",
                quality_flags=["missing_points"],
            ),
            _runtime_evidence(
                "EV-MET-0002",
                SourceType.METRIC,
                "Cloud Run latency_p95",
                quality_flags=["missing_points"],
            ),
            _runtime_evidence("EV-CHG-0001", SourceType.CHANGE, "Cloud Run revision observed"),
            _runtime_evidence("EV-KNW-0001", SourceType.KNOWLEDGE, "Payment DB pool runbook"),
        ],
        complete=False,
        data_gaps=["untrusted English presentation gap"],
    )
    model_calls = 0

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def forbidden_rca(
        _context: object, _output_language: OutputLanguage
    ) -> HypothesisDraftBatch:
        nonlocal model_calls
        model_calls += 1
        raise AssertionError("zero-point Korean evidence reached the model")

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", forbidden_rca)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    )

    assert model_calls == 0
    assert "# [UNCLASSIFIED] 판단 불가 조사: Payment Service 상태" in result.output_markdown
    assert "## 요약" in result.output_markdown
    assert "## 근본 원인 가설" in result.output_markdown
    assert "- 사용 가능한 증거로 검증된 가설이 없습니다." in result.output_markdown
    assert "- 사용 가능한 증거로 권장할 조치가 없습니다." in result.output_markdown
    assert (
        "Cloud Run error_ratio가 요청 구간 내 데이터 포인트를 반환하지 않았습니다."
        in result.output_markdown
    )
    assert (
        "Cloud Run latency_p95가 요청 구간 내 데이터 포인트를 반환하지 않았습니다."
        in result.output_markdown
    )
    assert "untrusted English presentation gap" not in result.output_markdown
    timeline, sources = result.output_markdown.split("## 출처", maxsplit=1)
    assert "Payment DB pool runbook" not in timeline
    assert "`EV-KNW-0001` - Payment DB pool runbook" in sources
    assert "`EV-MET-0001` - Cloud Run error_ratio" in sources


@pytest.mark.asyncio
async def test_korean_missing_window_assumption_and_configuration_error_are_localized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = validate_runtime_input("payment-service 상태를 근거와 함께 분석해줘")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    result = await runtime_module.run_live_runtime_investigation(decision)

    assert decision.assumptions == [
        "시간 범위가 지정되지 않아 최근 30분의 고정 구간을 사용했습니다."
    ]
    assert result.output_markdown == (
        runtime_module.RUNTIME_COPY[OutputLanguage.KO].configuration_unavailable
    )


@pytest.mark.asyncio
async def test_live_korean_source_failure_uses_structured_localized_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _live_collection([], complete=False).model_copy(
        update={
            "source_status": {
                SourceType.LOG.value: False,
                SourceType.METRIC.value: True,
                SourceType.CHANGE.value: True,
                SourceType.KNOWLEDGE.value: True,
            },
            "data_gaps": ["LOG evidence was unavailable."],
        }
    )

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    )

    assert "LOG 증거를 사용할 수 없습니다." in result.output_markdown
    assert "LOG evidence was unavailable." not in result.output_markdown


@pytest.mark.asyncio
async def test_live_two_source_signal_calls_one_rca_and_verifies_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-LOG-0001",
                SourceType.LOG,
                "Payment errors",
                direction=EvidenceDirection.SUPPORTS,
                quality_flags=["direct_error_signature_match"],
            ),
            _runtime_evidence(
                "EV-CHG-0001",
                SourceType.CHANGE,
                "Payment revision",
                direction=EvidenceDirection.SUPPORTS,
                quality_flags=["change_temporal_proximity"],
            ),
        ]
    )
    model_calls = 0

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def fake_rca(_context: object, output_language: OutputLanguage) -> HypothesisDraftBatch:
        nonlocal model_calls
        model_calls += 1
        assert output_language == OutputLanguage.EN
        return HypothesisDraftBatch(
            drafts=[
                HypothesisDraft(
                    draft_id="D-01",
                    root_cause_code="PAYMENT_REVISION_REGRESSION",
                    claim="The payment revision introduced the observed errors.",
                    mechanism="The bounded change and error signature align in time.",
                    affected_services=["payment-service"],
                    supporting_evidence_ids=["EV-LOG-0001", "EV-CHG-0001"],
                    next_checks=["Compare the previous revision configuration."],
                )
            ]
        )

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", fake_rca)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service recent 30 minutes status analyze")
    )

    assert model_calls == 1
    assert result.succeeded is True
    assert "The payment revision introduced the observed errors." in result.output_markdown
    assert "EV-LOG-0001, EV-CHG-0001" in result.output_markdown
    assert "## Recommended actions\n\n- No action is recommended" in result.output_markdown


@pytest.mark.asyncio
async def test_live_korean_signal_calls_one_rca_and_keeps_citations_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-LOG-0001",
                SourceType.LOG,
                "Payment errors",
                direction=EvidenceDirection.SUPPORTS,
                quality_flags=["direct_error_signature_match"],
            ),
            _runtime_evidence(
                "EV-CHG-0001",
                SourceType.CHANGE,
                "Payment revision",
                direction=EvidenceDirection.SUPPORTS,
                quality_flags=["change_temporal_proximity"],
            ),
        ]
    )
    model_calls = 0

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def fake_rca(_context: object, output_language: OutputLanguage) -> HypothesisDraftBatch:
        nonlocal model_calls
        model_calls += 1
        assert output_language == OutputLanguage.KO
        return HypothesisDraftBatch(
            drafts=[
                HypothesisDraft(
                    draft_id="D-01",
                    root_cause_code="PAYMENT_REVISION_REGRESSION",
                    claim="결제 리비전이 관측된 오류를 유발했습니다.",
                    mechanism="제한된 변경 증거와 오류 신호의 시점이 일치합니다.",
                    affected_services=["payment-service"],
                    supporting_evidence_ids=["EV-LOG-0001", "EV-CHG-0001"],
                    next_checks=["이전 리비전의 설정과 비교합니다."],
                )
            ]
        )

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", fake_rca)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    )

    assert model_calls == 1
    assert "# [UNCLASSIFIED] Payment Service 조사" in result.output_markdown
    assert "결제 리비전이 관측된 오류를 유발했습니다." in result.output_markdown
    assert "EV-LOG-0001, EV-CHG-0001" in result.output_markdown
    assert "`EV-LOG-0001` - Payment errors" in result.output_markdown
    assert "## 권장 조치\n\n- 사용 가능한 증거로 권장할 조치가 없습니다." in (
        result.output_markdown
    )


@pytest.mark.asyncio
async def test_live_korean_signal_rejects_english_rca_prose_and_degrades_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-LOG-0001",
                SourceType.LOG,
                "Payment errors",
                direction=EvidenceDirection.SUPPORTS,
            ),
            _runtime_evidence(
                "EV-CHG-0001",
                SourceType.CHANGE,
                "Payment revision",
                direction=EvidenceDirection.SUPPORTS,
            ),
        ]
    )

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def wrong_language_rca(
        _context: object, output_language: OutputLanguage
    ) -> HypothesisDraftBatch:
        assert output_language == OutputLanguage.KO
        return HypothesisDraftBatch(
            drafts=[
                HypothesisDraft(
                    draft_id="D-01",
                    root_cause_code="PAYMENT_REVISION_REGRESSION",
                    claim="The payment revision introduced the errors.",
                    mechanism="The change and error signature align in time.",
                    supporting_evidence_ids=["EV-LOG-0001", "EV-CHG-0001"],
                )
            ]
        )

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", wrong_language_rca)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    )

    assert result.succeeded is True
    assert "# [UNCLASSIFIED] 판단 불가 조사" in result.output_markdown
    assert "제한된 RCA 추론 단계를 사용할 수 없습니다." in result.output_markdown
    assert "The payment revision introduced" not in result.output_markdown
    assert "`EV-LOG-0001` - Payment errors" in result.output_markdown


@pytest.mark.asyncio
async def test_live_korean_rca_timeout_uses_localized_inconclusive_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-LOG-0001",
                SourceType.LOG,
                "Payment errors",
                direction=EvidenceDirection.SUPPORTS,
            ),
            _runtime_evidence(
                "EV-CHG-0001",
                SourceType.CHANGE,
                "Payment revision",
                direction=EvidenceDirection.SUPPORTS,
            ),
        ]
    )

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def blocked_rca(
        _context: object, output_language: OutputLanguage
    ) -> HypothesisDraftBatch:
        assert output_language == OutputLanguage.KO
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", blocked_rca)
    monkeypatch.setattr(runtime_module, "RUNTIME_RCA_TIMEOUT_SECONDS", 0.01)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service 최근 30분 상태를 근거와 함께 분석해줘")
    )

    assert result.succeeded is True
    assert "제한된 RCA 추론 단계를 사용할 수 없습니다." in result.output_markdown
    assert "The bounded RCA reasoning step" not in result.output_markdown


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "exception", "invalid_output"])
async def test_live_rca_failure_degrades_to_evidence_backed_inconclusive(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    collection = _live_collection(
        [
            _runtime_evidence(
                "EV-LOG-0001",
                SourceType.LOG,
                "Payment errors",
                direction=EvidenceDirection.SUPPORTS,
            ),
            _runtime_evidence(
                "EV-CHG-0001",
                SourceType.CHANGE,
                "Payment revision",
                direction=EvidenceDirection.SUPPORTS,
            ),
        ]
    )

    async def fake_collect(*_args: object, **_kwargs: object) -> EvidenceCollectionResult:
        return collection

    async def failing_rca(
        _context: object, _output_language: OutputLanguage
    ) -> HypothesisDraftBatch:
        if failure == "timeout":
            await asyncio.Event().wait()
        if failure == "invalid_output":
            raise ValueError("private malformed model output")
        raise RuntimeError("private model failure")

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "bounded-project")
    monkeypatch.setattr(runtime_module, "collect_evidence", fake_collect)
    monkeypatch.setattr(runtime_module, "run_runtime_rca", failing_rca)
    if failure == "timeout":
        monkeypatch.setattr(runtime_module, "RUNTIME_RCA_TIMEOUT_SECONDS", 0.01)

    result = await runtime_module.run_live_runtime_investigation(
        validate_runtime_input("payment-service recent 30 minutes status analyze")
    )

    assert result.succeeded is True
    assert "# [UNCLASSIFIED] Inconclusive Investigation" in result.output_markdown
    assert "The bounded RCA reasoning step was unavailable." in result.output_markdown
    assert "`EV-LOG-0001` - Payment errors" in result.output_markdown
    assert "private" not in result.output_markdown


@pytest.mark.asyncio
async def test_enterprise_stream_emits_progress_before_blocked_handler_finishes() -> None:
    handler_started = asyncio.Event()
    release_handler = asyncio.Event()

    async def blocked_handler(_decision: object) -> RuntimeInvocationResult:
        handler_started.set()
        await release_handler.wait()
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
        )

    app = _local_runtime_app(blocked_handler)
    request_json = json.dumps(
        {
            "message": {
                "role": "user",
                "parts": [{"text": "payment-service recent 30 minutes status analyze"}],
            },
            "userId": "private-enterprise-user",
            "sessionId": "enterprise-session",
        }
    )
    stream = app.streaming_agent_run_with_events(request_json)

    progress_chunk = await asyncio.wait_for(anext(stream), timeout=5)
    progress = _single_converted_event(progress_chunk)
    final_task = asyncio.create_task(anext(stream))
    await asyncio.wait_for(handler_started.wait(), timeout=1)

    assert progress["partial"] is True
    assert progress["turn_complete"] is False
    assert progress["content"]["parts"][0]["text"] == RUNTIME_PROGRESS_TEXT
    assert not final_task.done()

    release_handler.set()
    final = _single_converted_event(await asyncio.wait_for(final_task, timeout=1))
    assert final["partial"] is False
    assert final["turn_complete"] is True
    assert final["content"]["parts"][0]["text"] == "# Safe report\n"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_enterprise_session_id_uses_ephemeral_service_and_emits_report() -> None:
    calls = 0

    async def handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        return RuntimeInvocationResult(
            accepted=True,
            succeeded=True,
            output_markdown="# Safe report\n",
        )

    app = _local_runtime_app(handler)
    request_text = "payment-service recent 30 minutes status analyze"
    request_json = json.dumps(
        {
            "message": {"role": "user", "parts": [{"text": request_text}]},
            "userId": "private-enterprise-user",
            "sessionId": "enterprise-session",
        }
    )
    events = [event async for event in app.streaming_agent_run_with_events(request_json)]
    serialized = json.dumps(events)

    assert calls == 1
    assert len(events) == 2
    assert _single_converted_event(events[0])["partial"] is True
    assert _single_converted_event(events[1])["turn_complete"] is True
    assert "# Safe report" in serialized
    assert "private-enterprise-user" not in serialized
    assert request_text not in serialized


@pytest.mark.asyncio
async def test_enterprise_session_id_rejection_stops_before_handler() -> None:
    calls = 0

    async def forbidden_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("out-of-scope input reached the investigation handler")

    app = _local_runtime_app(forbidden_handler)
    request_text = "inventory-service recent 30 minutes status analyze"
    request_json = json.dumps(
        {
            "message": {"role": "user", "parts": [{"text": request_text}]},
            "userId": "private-enterprise-user",
            "sessionId": "enterprise-session",
        }
    )
    events = [event async for event in app.streaming_agent_run_with_events(request_json)]
    serialized = json.dumps(events)

    assert calls == 0
    assert len(events) == 1
    rejection = _single_converted_event(events[0])
    assert rejection["partial"] is False
    assert rejection["turn_complete"] is True
    assert RUNTIME_PROGRESS_TEXT not in serialized
    assert "only supports a read-only investigation of payment-service" in serialized
    assert "private-enterprise-user" not in serialized
    assert request_text not in serialized


@pytest.mark.asyncio
async def test_runtime_exception_emits_fixed_safe_final_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing_handler(_decision: object) -> RuntimeInvocationResult:
        raise RuntimeError("private-enterprise-user secret prompt")

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    app = _local_runtime_app(failing_handler)
    request_json = json.dumps(
        {
            "message": {
                "role": "user",
                "parts": [{"text": "payment-service recent 30 minutes status analyze"}],
            },
            "userId": "private-enterprise-user",
            "sessionId": "enterprise-session",
        }
    )

    chunks = [chunk async for chunk in app.streaming_agent_run_with_events(request_json)]
    serialized = json.dumps(chunks)

    assert len(chunks) == 2
    final = _single_converted_event(chunks[1])
    assert final["content"]["parts"][0]["text"] == RUNTIME_FAILURE_TEXT
    assert final["turn_complete"] is True
    assert "private-enterprise-user" not in serialized
    assert "secret prompt" not in serialized
    assert '"stage":"final_emitted"' in caplog.text
    assert "private-enterprise-user" not in caplog.text
    assert "secret prompt" not in caplog.text


@pytest.mark.asyncio
async def test_runtime_deadline_emits_fixed_safe_final_event(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def blocked_handler(_decision: object) -> RuntimeInvocationResult:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(runtime_module, "RUNTIME_DEADLINE_SECONDS", 0.01)
    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
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
    assert events[-1].content is not None
    assert events[-1].content.parts is not None
    assert events[-1].content.parts[0].text == RUNTIME_FAILURE_TEXT
    assert events[-1].turn_complete is True
    assert '"stage":"timeout"' in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ["exception", "timeout"])
async def test_korean_runtime_failure_and_deadline_use_localized_safe_final(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    async def handler(_decision: object) -> RuntimeInvocationResult:
        if failure_mode == "timeout":
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        raise RuntimeError("private Korean failure")

    if failure_mode == "timeout":
        monkeypatch.setattr(runtime_module, "RUNTIME_DEADLINE_SECONDS", 0.01)
    app = _local_runtime_app(handler)
    request_json = json.dumps(
        {
            "message": {
                "role": "user",
                "parts": [{"text": "payment-service 최근 30분 상태를 근거와 함께 분석해줘"}],
            },
            "userId": "private-korean-user",
            "sessionId": "private-korean-session",
        }
    )

    chunks = [chunk async for chunk in app.streaming_agent_run_with_events(request_json)]
    progress = _single_converted_event(chunks[0])
    final = _single_converted_event(chunks[1])
    serialized = json.dumps(chunks, ensure_ascii=False)

    assert progress["content"]["parts"][0]["text"] == (
        runtime_module.RUNTIME_COPY[OutputLanguage.KO].progress
    )
    assert final["content"]["parts"][0]["text"] == (
        "제한된 범위의 조사를 안전하게 완료하지 못했습니다."
    )
    assert "private-korean" not in serialized


@pytest.mark.asyncio
async def test_live_runtime_async_work_is_cancelled_by_stream_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = asyncio.Event()

    async def cancellable_live_investigation(
        _decision: object,
    ) -> RuntimeInvocationResult:
        try:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")
        finally:
            cancelled.set()

    monkeypatch.setattr(
        runtime_module,
        "_run_live_runtime_investigation_async",
        cancellable_live_investigation,
    )
    monkeypatch.setattr(runtime_module, "RUNTIME_DEADLINE_SECONDS", 0.01)
    runner = InMemoryRunner(
        node=create_runtime_root_agent(handler=runtime_module.run_live_runtime_investigation),
        app_name="test",
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
    assert events[-1].content is not None
    assert events[-1].content.parts is not None
    assert events[-1].content.parts[0].text == RUNTIME_FAILURE_TEXT
    assert events[-1].turn_complete is True
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_runtime_cancellation_is_logged_and_propagated_after_progress(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler_started = asyncio.Event()

    async def blocked_handler(_decision: object) -> RuntimeInvocationResult:
        handler_started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    runner = InMemoryRunner(
        node=create_runtime_root_agent(handler=blocked_handler), app_name="test"
    )
    await runner.session_service.create_session(
        app_name="test", user_id="private-user", session_id="private-session"
    )
    stream = runner.run_async(
        user_id="private-user",
        session_id="private-session",
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="payment-service recent 30 minutes status analyze")],
        ),
    )

    progress = await anext(stream)
    final_task = asyncio.create_task(anext(stream))
    await asyncio.wait_for(handler_started.wait(), timeout=1)
    final_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await final_task
    await stream.aclose()

    assert progress.partial is True
    assert '"stage":"cancelled"' in caplog.text
    assert "private-user" not in caplog.text
    assert "private-session" not in caplog.text


@pytest.mark.asyncio
async def test_runtime_generator_exit_is_logged_before_handler_starts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0

    async def forbidden_handler(_decision: object) -> RuntimeInvocationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("closed stream reached the handler")

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    agent = create_runtime_root_agent(handler=forbidden_handler)
    session_service = create_ephemeral_session_service()
    session = await session_service.create_session(
        app_name="test",
        user_id="private-generator-user",
        session_id="private-generator-session",
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

    progress = await anext(stream)
    await stream.aclose()

    assert progress.partial is True
    assert calls == 0
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
        )

    caplog.set_level(logging.INFO, logger="opspilot.agent.runtime")
    app = _local_runtime_app(handler)

    async def collect(user_id: str, session_id: str) -> list[dict[str, Any]]:
        request_json = json.dumps(
            {
                "message": {
                    "role": "user",
                    "parts": [{"text": "payment-service recent 30 minutes status analyze"}],
                },
                "userId": user_id,
                "sessionId": session_id,
            }
        )
        return [chunk async for chunk in app.streaming_agent_run_with_events(request_json)]

    results = await asyncio.gather(
        *(collect(f"private-user-{index}", f"private-session-{index}") for index in range(20))
    )
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
    assert len(accepted_logs) == 20
    assert len(summary_logs) == 20
    assert len({item["run_id"] for item in accepted_logs}) == 20
    assert all(set(item) == {"event", "run_id", "stage", "elapsed_ms"} for item in accepted_logs)
    assert all(item["outcome"] == "complete" for item in summary_logs)
    assert "private-user" not in serialized
    assert "private-session" not in serialized
    assert "private-user" not in caplog.text
    assert "private-session" not in caplog.text


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
    assert isinstance(create_ephemeral_session_service(), InMemorySessionService)
    assert root_agent.register_operations() == {"async_stream": ["streaming_agent_run_with_events"]}
    assert callable(root_agent.streaming_agent_run_with_events)


def test_runtime_package_cannot_escape_tmp() -> None:
    with pytest.raises(ValueError, match=r"under \.tmp"):
        package_runtime(Path("outside-runtime-package"))
