"""In-process investigation state and orchestration for R0."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from opspilot.catalog import ServiceCatalog
from opspilot.domain import IncidentReport, InvestigationRequest, RequestedDepth
from opspilot.parser import parse_investigation_request
from opspilot.workflow import run_fixture_investigation


class InvestigationStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class InvestigationRecord(BaseModel):
    investigation_id: str
    correlation_id: str
    incident_id: str | None = None
    status: InvestigationStatus
    current_stage: str
    completed_collectors: list[str] = Field(default_factory=list)
    partial_failures: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    safe_error: str | None = None
    execution_mode: str
    scenario_id: str


class InvestigationExecution(BaseModel):
    report: IncidentReport
    completed_collectors: list[str] = Field(default_factory=list)


class InvestigationExecutor(Protocol):
    execution_mode: str
    scenario_id: str

    def validate(self, request: InvestigationRequest) -> None: ...

    async def execute(
        self, request: InvestigationRequest, *, correlation_id: str
    ) -> InvestigationExecution: ...


class FixtureInvestigationExecutor:
    """Honest local API boundary for the single executable fixture scenario."""

    execution_mode = "fixture"
    scenario_id = "SCN-001"
    incident_id = "INC-2026-0001"
    supported_services: Sequence[str] = ("payment-service",)

    def validate(self, request: InvestigationRequest) -> None:
        if request.services != list(self.supported_services):
            raise ValueError(
                "the local investigation API only supports payment-service with SCN-001"
            )
        if request.incident_id not in {None, self.incident_id}:
            raise ValueError("the requested incident is not available in the local fixture API")

    async def execute(
        self, request: InvestigationRequest, *, correlation_id: str
    ) -> InvestigationExecution:
        report = await run_fixture_investigation(
            self.scenario_id,
            correlation_id=correlation_id,
            assumptions=request.assumptions,
        )
        return InvestigationExecution(
            report=report,
            completed_collectors=["LOG", "METRIC", "CHANGE", "KNOWLEDGE"],
        )


class InMemoryInvestigationStore:
    def __init__(self) -> None:
        self._records: dict[str, InvestigationRecord] = {}
        self._reports: dict[str, IncidentReport] = {}
        self._lock = asyncio.Lock()

    async def put_record(self, record: InvestigationRecord) -> None:
        async with self._lock:
            self._records[record.investigation_id] = record.model_copy(deep=True)

    async def get_record(self, investigation_id: str) -> InvestigationRecord | None:
        async with self._lock:
            record = self._records.get(investigation_id)
            return record.model_copy(deep=True) if record else None

    async def put_report(self, report: IncidentReport) -> None:
        async with self._lock:
            self._reports[report.incident_id] = report.model_copy(deep=True)

    async def get_report(self, incident_id: str) -> IncidentReport | None:
        async with self._lock:
            report = self._reports.get(incident_id)
            return report.model_copy(deep=True) if report else None


class InvestigationCoordinator:
    def __init__(
        self,
        catalog: ServiceCatalog,
        executor: InvestigationExecutor | None = None,
    ) -> None:
        self.catalog = catalog
        self.executor = executor or FixtureInvestigationExecutor()
        self.store = InMemoryInvestigationStore()
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit(
        self, query: str, incident_id: str | None, mode: RequestedDepth
    ) -> InvestigationRecord:
        request = parse_investigation_request(
            query, catalog=self.catalog, incident_id=incident_id, mode=mode
        )
        self.executor.validate(request)
        investigation_id = f"INV-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:12].upper()}"
        correlation_id = f"COR-{uuid4().hex[:16].upper()}"
        record = InvestigationRecord(
            investigation_id=investigation_id,
            correlation_id=correlation_id,
            incident_id=request.incident_id,
            status=InvestigationStatus.QUEUED,
            current_stage="QUEUED",
            execution_mode=self.executor.execution_mode,
            scenario_id=self.executor.scenario_id,
        )
        await self.store.put_record(record)
        task = asyncio.create_task(self._run(record, request))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    async def _run(self, record: InvestigationRecord, request: InvestigationRequest) -> None:
        running = record.model_copy(
            update={
                "status": InvestigationStatus.RUNNING,
                "current_stage": "EVIDENCE_COLLECTION",
                "started_at": datetime.now(UTC),
            }
        )
        await self.store.put_record(running)
        try:
            execution = await self.executor.execute(
                request,
                correlation_id=record.correlation_id,
            )
            report = execution.report
            await self.store.put_report(report)
            complete = running.model_copy(
                update={
                    "incident_id": report.incident_id,
                    "status": InvestigationStatus.COMPLETE,
                    "current_stage": "COMPLETE",
                    "completed_collectors": execution.completed_collectors,
                    "partial_failures": [error.safe_message for error in report.tool_errors],
                    "finished_at": datetime.now(UTC),
                }
            )
            await self.store.put_record(complete)
        except Exception:
            failed = running.model_copy(
                update={
                    "status": InvestigationStatus.FAILED,
                    "current_stage": "FAILED",
                    "finished_at": datetime.now(UTC),
                    "safe_error": "The local fixture investigation failed.",
                }
            )
            await self.store.put_record(failed)

    async def close(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
