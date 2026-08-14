from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from opspilot.audit import InvestigationAudit, audit_hash
from opspilot.catalog import load_service_catalog
from opspilot.domain import Environment, InvestigationRequest, RequestedDepth
from opspilot.evidence import FixtureEvidenceClient
from opspilot.parser import parse_investigation_request
from opspilot.service import (
    ConversationContext,
    FixtureInvestigationExecutor,
    InMemoryInvestigationStore,
    InvestigationCoordinator,
    InvestigationExecution,
    LiveInvestigationExecutor,
)


@pytest.mark.asyncio
async def test_conversation_context_is_session_isolated_and_expires_after_ttl() -> None:
    store = InMemoryInvestigationStore()
    active = ConversationContext(
        session_hash="a" * 64,
        incident_id="INC-2026-0001",
        environment=Environment.STAGING,
        services=["order-service"],
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    expired = ConversationContext(
        session_hash="b" * 64,
        incident_id="INC-2026-0002",
        services=["payment-service"],
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    await store.put_context(active)
    await store.put_context(expired)

    assert await store.get_context("a" * 64) == active
    assert await store.get_context("b" * 64) is None
    assert await store.get_context("c" * 64) is None
    assert "query" not in active.model_dump_json().lower()
    assert "user" not in active.model_dump_json().lower()


class RecordingPublisher:
    def __init__(self) -> None:
        self.ids: list[str] = []

    async def publish(self, investigation_id: str) -> None:
        if investigation_id not in self.ids:
            self.ids.append(investigation_id)


class CountingExecutor(FixtureInvestigationExecutor):
    def __init__(self) -> None:
        super().__init__(("inventory-service", "order-service", "payment-service"))
        self.calls = 0

    async def execute(
        self,
        request: InvestigationRequest,
        *,
        correlation_id: str,
        trace_id: str | None = None,
        investigation_id: str | None = None,
        run_id: str | None = None,
    ) -> InvestigationExecution:
        self.calls += 1
        await asyncio.sleep(0.01)
        return await super().execute(
            request,
            correlation_id=correlation_id,
            trace_id=trace_id,
            investigation_id=investigation_id,
            run_id=run_id,
        )


class FailFirstCompleteStore(InMemoryInvestigationStore):
    def __init__(self) -> None:
        super().__init__()
        self.failures = 1

    async def complete(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if self.failures:
            self.failures -= 1
            raise RuntimeError("synthetic persistence outage")
        return await super().complete(*args, **kwargs)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cloud_task_duplicate_delivery_executes_once() -> None:
    publisher = RecordingPublisher()
    executor = CountingExecutor()
    coordinator = InvestigationCoordinator(
        load_service_catalog(), executor=executor, task_publisher=publisher
    )
    record = await coordinator.submit(
        "payment-service 최근 30분 오류 분석", None, RequestedDepth.STANDARD
    )
    assert publisher.ids == [record.investigation_id]

    results = await asyncio.gather(
        *(coordinator.process_task(record.investigation_id) for _ in range(20))
    )

    assert executor.calls == 1
    assert all(item is not None for item in results)
    reports = await coordinator.store.list_reports(record.incident_id)
    assert [item.report_version for item in reports] == [1]


@pytest.mark.asyncio
async def test_concurrent_replays_allocate_monotonic_report_versions() -> None:
    publisher = RecordingPublisher()
    coordinator = InvestigationCoordinator(
        load_service_catalog(), executor=CountingExecutor(), task_publisher=publisher
    )
    original = await coordinator.submit(
        "order-service 지난 15분 지연 분석", None, RequestedDepth.STANDARD
    )
    await coordinator.process_task(original.investigation_id)
    replays = await asyncio.gather(*(coordinator.replay(original.incident_id) for _ in range(4)))
    await asyncio.gather(*(coordinator.process_task(item.investigation_id) for item in replays))

    reports = await coordinator.store.list_reports(original.incident_id)
    assert [item.report_version for item in reports] == [1, 2, 3, 4, 5]
    assert len({item.report_id for item in reports}) == 5


@pytest.mark.asyncio
async def test_report_storage_failure_requeues_task_for_retry() -> None:
    publisher = RecordingPublisher()
    store = FailFirstCompleteStore()
    executor = CountingExecutor()
    coordinator = InvestigationCoordinator(
        load_service_catalog(),
        executor=executor,
        store=store,
        task_publisher=publisher,
    )
    record = await coordinator.submit(
        "inventory-service last 20 minutes errors", None, RequestedDepth.STANDARD
    )

    with pytest.raises(RuntimeError, match="synthetic persistence outage"):
        await coordinator.process_task(record.investigation_id)
    queued = await store.get_record(record.investigation_id)
    assert queued is not None and queued.status.value == "QUEUED"

    complete = await coordinator.process_task(record.investigation_id)
    assert complete is not None and complete.status.value == "COMPLETE"
    assert complete.task_attempts == 2
    assert executor.calls == 2


@pytest.mark.asyncio
async def test_live_executor_collects_each_service_and_keeps_evidence_ids_unique() -> None:
    catalog = load_service_catalog()
    executor = LiveInvestigationExecutor(project_id="server-owned-project", catalog=catalog)
    executor.client = FixtureEvidenceClient("SCN-001")  # type: ignore[assignment]
    request = parse_investigation_request(
        "order-service payment-service inventory-service 최근 30분 오류 분석",
        catalog=catalog,
    ).model_copy(update={"incident_id": "INC-2026-AAAAAAAAAAAAAAAA"})

    execution = await executor.execute(request, correlation_id="COR-LIVE-TEST")

    assert execution.report.affected_services == [
        "inventory-service",
        "order-service",
        "payment-service",
    ]
    evidence_ids = [item.evidence_id for item in execution.report.evidence]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert execution.report.audit["model_calls"] == 0
    assert execution.report.audit["logical_tool_calls"] == 12
    api_calls = execution.report.audit["api_calls"]
    assert isinstance(api_calls, int)
    assert api_calls <= 20
    assert set(execution.completed_collectors) == {"CHANGE", "KNOWLEDGE", "LOG", "METRIC"}


@pytest.mark.asyncio
async def test_enterprise_run_id_reaches_every_live_tool_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="opspilot.evidence")
    catalog = load_service_catalog()
    executor = LiveInvestigationExecutor(project_id="server-owned-project", catalog=catalog)
    executor.client = FixtureEvidenceClient("SCN-001")  # type: ignore[assignment]
    request = parse_investigation_request(
        "dev payment-service recent 15 minutes errors", catalog=catalog
    ).model_copy(update={"incident_id": "INC-2026-BBBBBBBBBBBBBBBB"})

    await executor.execute(
        request,
        correlation_id="COR-0123456789ABCDEF",
        trace_id="0123456789abcdef0123456789abcdef",
        investigation_id="INV-RUN-0123456789ABCDEF",
        run_id="RUN-0123456789ABCDEF",
    )

    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "opspilot.evidence"
    ]
    assert len(events) == 4
    assert {event["run_id"] for event in events} == {"RUN-0123456789ABCDEF"}
    assert {event["trace_id"] for event in events} == {"0123456789abcdef0123456789abcdef"}


@pytest.mark.asyncio
async def test_concurrent_runtime_submissions_create_one_named_incident() -> None:
    publisher = RecordingPublisher()
    store = InMemoryInvestigationStore()
    coordinator = InvestigationCoordinator(
        load_service_catalog(),
        executor=CountingExecutor(),
        store=store,
        task_publisher=publisher,
    )
    query = "dev payment-service last 10 minutes errors INC-2026-CCCCCCCCCCCCCCCC"
    trace_id = "abcdef0123456789abcdef0123456789"
    audit = InvestigationAudit(
        source="enterprise",
        query_hash=audit_hash("enterprise_query", query),
        run_id="RUN-ABCDEF0123456789",
        trace_id=trace_id,
    )

    records = await asyncio.gather(
        *(
            coordinator.submit(
                query,
                None,
                RequestedDepth.STANDARD,
                correlation_id="COR-ABCDEF0123456789",
                trace_id=trace_id,
                audit=audit,
            )
            for _ in range(20)
        )
    )

    assert {record.investigation_id for record in records} == {"INV-RUN-ABCDEF0123456789"}
    assert {record.incident_id for record in records} == {"INC-2026-CCCCCCCCCCCCCCCC"}
    assert publisher.ids == ["INV-RUN-ABCDEF0123456789"]


@pytest.mark.asyncio
async def test_retry_after_commit_response_loss_does_not_requeue_completed_record() -> None:
    publisher = RecordingPublisher()
    store = InMemoryInvestigationStore()
    coordinator = InvestigationCoordinator(
        load_service_catalog(),
        executor=CountingExecutor(),
        store=store,
        task_publisher=publisher,
    )
    record = await coordinator.submit(
        "payment-service 최근 30분 오류 분석", None, RequestedDepth.STANDARD
    )
    completed = await coordinator.process_task(record.investigation_id)
    assert completed is not None

    await store.retry(completed, safe_error="simulated lost commit response")

    persisted = await store.get_record(record.investigation_id)
    assert persisted is not None and persisted.status.value == "COMPLETE"


@pytest.mark.asyncio
async def test_runtime_run_id_is_idempotent_and_persists_only_redacted_query() -> None:
    publisher = RecordingPublisher()
    store = InMemoryInvestigationStore()
    coordinator = InvestigationCoordinator(
        load_service_catalog(),
        executor=CountingExecutor(),
        store=store,
        task_publisher=publisher,
    )
    query = (
        "payment-service last 10 minutes errors for operator@example.invalid token=supersecret123"
    )
    trace_id = "0123456789abcdef0123456789abcdef"
    audit = InvestigationAudit(
        source="enterprise",
        actor_hash=audit_hash("enterprise_actor", "private-user"),
        session_hash=audit_hash("enterprise_session", "private-session"),
        query_hash=audit_hash("enterprise_query", query),
        run_id="RUN-0123456789ABCDEF",
        trace_id=trace_id,
    )

    records = await asyncio.gather(
        *(
            coordinator.submit(
                query,
                None,
                RequestedDepth.STANDARD,
                correlation_id="COR-0123456789ABCDEF",
                trace_id=trace_id,
                audit=audit,
            )
            for _ in range(20)
        )
    )

    assert {item.investigation_id for item in records} == {"INV-RUN-0123456789ABCDEF"}
    assert publisher.ids == ["INV-RUN-0123456789ABCDEF"]
    request = await store.get_request("INV-RUN-0123456789ABCDEF")
    assert request is not None
    serialized = request.model_dump_json()
    assert "operator@example.invalid" not in serialized
    assert "supersecret123" not in serialized
    assert "[REDACTED_EMAIL]" in request.user_query
    assert "[REDACTED_TOKEN]" in request.user_query

    await coordinator.process_task("INV-RUN-0123456789ABCDEF")
    report = await store.get_report(records[0].incident_id)
    assert report is not None
    assert report.correlation_id == "COR-0123456789ABCDEF"
    assert report.audit["trace_id"] == trace_id


def test_legacy_investigation_record_loads_without_new_audit_fields() -> None:
    from opspilot.service import InvestigationRecord

    record = InvestigationRecord.model_validate(
        {
            "investigation_id": "INV-LEGACY",
            "correlation_id": "COR-LEGACY",
            "incident_id": "INC-2026-0001",
            "status": "QUEUED",
            "current_stage": "QUEUED",
            "execution_mode": "fixture",
            "scenario_id": "SCN-001",
        }
    )
    assert record.audit is None
    assert len(record.trace_id) == 32
