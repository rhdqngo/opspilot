from __future__ import annotations

import asyncio

import pytest

from opspilot.catalog import load_service_catalog
from opspilot.domain import InvestigationRequest, RequestedDepth
from opspilot.evidence import FixtureEvidenceClient
from opspilot.parser import parse_investigation_request
from opspilot.service import (
    FixtureInvestigationExecutor,
    InMemoryInvestigationStore,
    InvestigationCoordinator,
    InvestigationExecution,
    LiveInvestigationExecutor,
)


class RecordingPublisher:
    def __init__(self) -> None:
        self.ids: list[str] = []

    async def publish(self, investigation_id: str) -> None:
        self.ids.append(investigation_id)


class CountingExecutor(FixtureInvestigationExecutor):
    def __init__(self) -> None:
        super().__init__(("inventory-service", "order-service", "payment-service"))
        self.calls = 0

    async def execute(
        self, request: InvestigationRequest, *, correlation_id: str
    ) -> InvestigationExecution:
        self.calls += 1
        await asyncio.sleep(0.01)
        return await super().execute(request, correlation_id=correlation_id)


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
        "order-service payment-service 최근 30분 오류 분석", catalog=catalog
    ).model_copy(update={"incident_id": "INC-2026-AAAAAAAAAAAAAAAA"})

    execution = await executor.execute(request, correlation_id="COR-LIVE-TEST")

    assert execution.report.affected_services == ["order-service", "payment-service"]
    evidence_ids = [item.evidence_id for item in execution.report.evidence]
    assert len(evidence_ids) == len(set(evidence_ids))
    assert execution.report.audit["model_calls"] == 0
    assert set(execution.completed_collectors) == {"CHANGE", "KNOWLEDGE", "LOG", "METRIC"}


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
