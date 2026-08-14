"""Persistent, task-driven investigation orchestration."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import quote
from uuid import uuid4

from google.auth.transport.requests import AuthorizedSession
from pydantic import BaseModel, Field

from opspilot.audit import (
    InvestigationAudit,
    ToolAuditContext,
    audit_hash,
    new_correlation_id,
    new_trace_id,
)
from opspilot.catalog import ServiceCatalog
from opspilot.domain import (
    Environment,
    EvidenceItem,
    IncidentReport,
    IncidentTimelineEvent,
    InvestigationRequest,
    OutputLanguage,
    ReportStatus,
    RequestedDepth,
    SourceType,
)
from opspilot.evidence import (
    EvidenceCollectionRequest,
    LiveEvidenceClient,
    UrllibJsonTransport,
    WorkloadAdcTokenProvider,
    collect_evidence,
)
from opspilot.parser import parse_investigation_request
from opspilot.redaction import redact_text
from opspilot.remediation.google import _authorized_session
from opspilot.report_policy import add_prod_sim_rollback_request, apply_live_report_policy
from opspilot.workflow import run_fixture_investigation


class InvestigationStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class IncidentState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class InvestigationRecord(BaseModel):
    investigation_id: str
    correlation_id: str
    trace_id: str = Field(default_factory=new_trace_id, pattern=r"^[0-9a-f]{32}$")
    incident_id: str
    status: InvestigationStatus
    current_stage: str
    completed_collectors: list[str] = Field(default_factory=list)
    partial_failures: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    lease_expires_at: datetime | None = None
    task_attempts: int = Field(default=0, ge=0)
    safe_error: str | None = None
    execution_mode: str
    scenario_id: str
    report_version: int | None = Field(default=None, ge=1)
    audit: InvestigationAudit | None = None


class IncidentRecord(BaseModel):
    incident_id: str
    services: list[str]
    state: IncidentState = IncidentState.OPEN
    source: str = "user"
    opened_at: datetime
    closed_at: datetime | None = None
    latest_report_version: int = Field(default=0, ge=0)
    latest_investigation_id: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class IncidentSeed(BaseModel):
    incident_id: str
    services: list[str]
    state: IncidentState
    opened_at: datetime
    closed_at: datetime | None = None
    source: str = "monitoring"
    alert_key_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    assumptions: list[str] = Field(default_factory=list)


class InvestigationExecution(BaseModel):
    report: IncidentReport
    completed_collectors: list[str] = Field(default_factory=list)


class AgentTurnIntent(StrEnum):
    INVESTIGATE = "INVESTIGATE"
    REFINE_INVESTIGATION = "REFINE_INVESTIGATION"
    EXPLAIN_REPORT = "EXPLAIN_REPORT"
    COMPARE_REPORT_VERSIONS = "COMPARE_REPORT_VERSIONS"
    SHOW_STATUS = "SHOW_STATUS"
    CREATE_REMEDIATION_REQUEST = "CREATE_REMEDIATION_REQUEST"
    SHOW_CAPABILITIES = "SHOW_CAPABILITIES"
    REJECTED = "REJECTED"


class ConversationContext(BaseModel):
    session_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    incident_id: str
    environment: Environment = Environment.DEV
    services: list[str] = Field(default_factory=list)
    window_minutes: int = Field(default=30, ge=1, le=120)
    requested_depth: RequestedDepth = RequestedDepth.STANDARD
    report_version: int | None = Field(default=None, ge=1)
    focus_hypothesis_id: str | None = Field(default=None, pattern=r"^H-\d{2}$")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(hours=24))


class InvestigationExecutor(Protocol):
    execution_mode: str
    scenario_id: str

    def validate(self, request: InvestigationRequest) -> None: ...

    async def execute(
        self,
        request: InvestigationRequest,
        *,
        correlation_id: str,
        trace_id: str | None = None,
        investigation_id: str | None = None,
        run_id: str | None = None,
    ) -> InvestigationExecution: ...


class InvestigationTaskPublisher(Protocol):
    async def publish(self, investigation_id: str) -> None: ...


class InvestigationStore(Protocol):
    async def create_investigation(
        self, record: InvestigationRecord, request: InvestigationRequest
    ) -> bool: ...

    async def get_record(self, investigation_id: str) -> InvestigationRecord | None: ...

    async def get_request(self, investigation_id: str) -> InvestigationRequest | None: ...

    async def claim(
        self, investigation_id: str, *, now: datetime
    ) -> tuple[InvestigationRecord, InvestigationRequest] | None: ...

    async def complete(
        self, record: InvestigationRecord, execution: InvestigationExecution, *, now: datetime
    ) -> tuple[InvestigationRecord, IncidentReport]: ...

    async def fail(
        self, record: InvestigationRecord, *, now: datetime, safe_error: str
    ) -> None: ...

    async def retry(self, record: InvestigationRecord, *, safe_error: str) -> None: ...

    async def get_incident(self, incident_id: str) -> IncidentRecord | None: ...

    async def list_reports(self, incident_id: str) -> list[IncidentReport]: ...

    async def get_report(
        self, incident_id: str, version: int | None = None
    ) -> IncidentReport | None: ...

    async def ingest_alert(
        self, seed: IncidentSeed, *, message_key: str
    ) -> tuple[IncidentRecord, bool]: ...

    async def get_context(self, session_hash: str) -> ConversationContext | None: ...

    async def put_context(self, context: ConversationContext) -> None: ...


class FixtureInvestigationExecutor:
    """Deterministic executor used by local development and contract tests."""

    execution_mode = "fixture"
    scenario_id = "SCN-001"

    def __init__(self, supported_services: Sequence[str] | None = None) -> None:
        self.supported_services = set(supported_services or ("payment-service",))

    def validate(self, request: InvestigationRequest) -> None:
        unsupported = sorted(set(request.services) - self.supported_services)
        if unsupported:
            raise ValueError(
                f"services are not executable by this investigation backend: {unsupported}"
            )

    async def execute(
        self,
        request: InvestigationRequest,
        *,
        correlation_id: str,
        trace_id: str | None = None,
        investigation_id: str | None = None,
        run_id: str | None = None,
    ) -> InvestigationExecution:
        del investigation_id, run_id
        effective_trace = trace_id or new_trace_id()
        report = await run_fixture_investigation(
            self.scenario_id,
            correlation_id=correlation_id,
            trace_id=effective_trace,
            assumptions=request.assumptions,
        )
        report = report.model_copy(
            update={
                "incident_id": request.incident_id,
                "environment": request.environment,
                "requested_start_time": request.start_time,
                "requested_end_time": request.end_time,
                "title": (
                    f"{request.services[0]} Incident Investigation"
                    if len(request.services) == 1
                    else "Multi-Service Incident Investigation"
                ),
                "affected_services": request.services,
                "assumptions": request.assumptions,
                "audit": {**report.audit, "trace_id": effective_trace},
            },
            deep=True,
        )
        return InvestigationExecution(
            report=report,
            completed_collectors=["LOG", "METRIC", "CHANGE", "KNOWLEDGE"],
        )


class LiveInvestigationExecutor:
    """Bounded production evidence executor; server configuration owns every cloud target."""

    execution_mode = "live"
    scenario_id = "SCN-001"

    def __init__(
        self,
        *,
        project_id: str,
        catalog: ServiceCatalog,
        region: str = "asia-northeast3",
    ) -> None:
        self.catalog = catalog
        self.client = LiveEvidenceClient(
            project_id,
            catalog=catalog,
            token_provider=WorkloadAdcTokenProvider(),
            transport=UrllibJsonTransport(),
            region=region,
            request_timeout_seconds=3.0,
        )

    def validate(self, request: InvestigationRequest) -> None:
        if request.requested_actions:
            raise ValueError("live investigation execution is read-only")
        if not request.services or any(
            service not in self.catalog.services for service in request.services
        ):
            raise ValueError("live investigation service scope is not allowlisted")

    async def execute(
        self,
        request: InvestigationRequest,
        *,
        correlation_id: str,
        trace_id: str | None = None,
        investigation_id: str | None = None,
        run_id: str | None = None,
    ) -> InvestigationExecution:
        effective_trace = trace_id or new_trace_id()
        collections = await asyncio.gather(
            *(
                collect_evidence(
                    self.client,
                    EvidenceCollectionRequest(
                        scenario_id=self.scenario_id,
                        environment=request.environment,
                        start_time=request.start_time,
                        end_time=request.end_time,
                        services=[service],
                        symptoms=request.symptoms,
                        requested_depth=request.requested_depth,
                        focus_hypothesis_id=request.focus_hypothesis_id,
                    ),
                    tool_timeout_seconds=5.0,
                    collection_deadline_seconds=12.0,
                    audit_context=ToolAuditContext(
                        trace_id=effective_trace,
                        correlation_id=correlation_id,
                        investigation_id=investigation_id,
                        run_id=run_id,
                    ),
                )
                for service in request.services
            )
        )
        prefixes = {
            SourceType.LOG: "LOG",
            SourceType.METRIC: "MET",
            SourceType.CHANGE: "CHG",
            SourceType.KNOWLEDGE: "KNW",
            SourceType.INCIDENT: "INC",
            SourceType.ACTION: "ACT",
        }
        counters: dict[SourceType, int] = {}
        evidence: list[EvidenceItem] = []
        for collection in collections:
            for item in collection.evidence:
                counters[item.source_type] = counters.get(item.source_type, 0) + 1
                evidence.append(
                    item.model_copy(
                        update={
                            "evidence_id": (
                                f"EV-{prefixes[item.source_type]}-{counters[item.source_type]:04d}"
                            )
                        },
                        deep=True,
                    )
                )
        logical_tool_calls = sum(collection.budget.logical_tool_calls for collection in collections)
        api_calls = sum(collection.budget.api_calls for collection in collections)
        if logical_tool_calls > 20 or api_calls > 20:
            raise RuntimeError("multi-service evidence collection exceeded its fixed call budget")
        now = datetime.now(UTC)
        operational_evidence = [
            item
            for item in evidence
            if item.source_type not in {SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}
            or (
                (item.observed_at or item.period_start) is not None
                and request.start_time
                <= (item.observed_at or item.period_start or request.start_time)
                <= request.end_time
            )
        ]
        timeline = [
            IncidentTimelineEvent(
                timestamp=item.observed_at or item.period_start or now,
                event_type=item.source_type.value,
                title=item.title,
                description=item.summary,
                service=item.service,
                evidence_ids=[item.evidence_id],
            )
            for item in operational_evidence
            if item.source_type in {SourceType.LOG, SourceType.METRIC, SourceType.CHANGE}
            and (item.observed_at is not None or item.period_start is not None)
        ]
        timeline.sort(key=lambda event: event.timestamp)
        tool_errors = [error for collection in collections for error in collection.tool_errors]
        data_gaps = sorted({gap for collection in collections for gap in collection.data_gaps})
        completed_collectors = sorted(
            {
                source
                for collection in collections
                for source, succeeded in collection.source_status.items()
                if succeeded
            }
        )
        report = IncidentReport(
            report_id="RPT-PENDING",
            report_version=1,
            incident_id=request.incident_id or new_incident_id(now),
            generated_at=now,
            correlation_id=correlation_id,
            environment=request.environment,
            requested_start_time=request.start_time,
            requested_end_time=request.end_time,
            title=(
                f"{request.services[0]} Incident Investigation"
                if len(request.services) == 1
                else "Multi-Service Incident Investigation"
            ),
            severity="UNCLASSIFIED",
            severity_rationale="Severity is not inferred beyond collected bounded evidence.",
            status=ReportStatus.INCONCLUSIVE,
            impact_summary="Impact requires evidence-backed operator review.",
            executive_summary=(
                "Bounded evidence was collected from the requested allowlisted services. "
                "No model-only root cause is asserted by the production API executor."
            ),
            affected_services=request.services,
            timeline=timeline,
            evidence=operational_evidence,
            data_gaps=data_gaps,
            assumptions=request.assumptions,
            tool_errors=tool_errors,
            audit={
                "execution_mode": "live-api",
                "model_calls": 0,
                "unauthorized_action_count": 0,
                "trace_id": effective_trace,
                "logical_tool_calls": logical_tool_calls,
                "api_calls": api_calls,
            },
        )
        direct_signal = any(
            item.source_type is SourceType.LOG
            or (
                item.source_type is SourceType.METRIC
                and "missing_points" not in item.quality_flags
                and item.value not in {None, 0, "0"}
            )
            for item in operational_evidence
        )
        deterministic_report = apply_live_report_policy(report)
        if deterministic_report.hypotheses:
            deterministic_report = add_prod_sim_rollback_request(deterministic_report)
            return InvestigationExecution(
                report=deterministic_report,
                completed_collectors=completed_collectors,
            )
        if direct_signal:
            from opspilot.agent.contracts import AgentEvidenceContext, ModelBackend
            from opspilot.agent.runner import run_agent_context

            agent_result = await run_agent_context(
                AgentEvidenceContext(
                    scenario_id=self.scenario_id,
                    incident_id=request.incident_id or new_incident_id(now),
                    generated_at=now,
                    correlation_id=correlation_id,
                    trace_id=effective_trace,
                    output_language=request.output_language,
                    evidence=operational_evidence,
                    tool_errors=tool_errors,
                    data_gaps=data_gaps,
                    assumptions=request.assumptions,
                ),
                model_backend=ModelBackend.VERTEX,
                complete=not tool_errors,
                run_id=run_id,
            )
            if agent_result.succeeded and agent_result.report is not None:
                graph_report = agent_result.report
                report = graph_report.model_copy(
                    update={
                        "environment": request.environment,
                        "requested_start_time": request.start_time,
                        "requested_end_time": request.end_time,
                        "title": (
                            f"{request.services[0]} Incident Investigation"
                            if len(request.services) == 1
                            else "Multi-Service Incident Investigation"
                        ),
                        "affected_services": request.services,
                        "timeline": timeline,
                        "evidence": operational_evidence,
                        "audit": {
                            **graph_report.audit,
                            "trace_id": effective_trace,
                            "logical_tool_calls": logical_tool_calls,
                            "api_calls": api_calls,
                            "model_calls": agent_result.budget.model_calls,
                        },
                    },
                    deep=True,
                )
                report = apply_live_report_policy(report)
                report = add_prod_sim_rollback_request(report)
                return InvestigationExecution(
                    report=report,
                    completed_collectors=completed_collectors,
                )
        report = apply_live_report_policy(report)
        if not direct_signal and not report.hypotheses:
            report = report.model_copy(
                update={
                    "impact_summary": "No meaningful incident impact was established.",
                    "executive_summary": (
                        "No meaningful incident evidence was found in the bounded window. "
                        "Source delay and data gaps are listed below."
                    ),
                },
                deep=True,
            )
        report = add_prod_sim_rollback_request(report)
        return InvestigationExecution(
            report=report,
            completed_collectors=completed_collectors,
        )


class InMemoryInvestigationStore:
    def __init__(self) -> None:
        self._records: dict[str, InvestigationRecord] = {}
        self._requests: dict[str, InvestigationRequest] = {}
        self._incidents: dict[str, IncidentRecord] = {}
        self._reports: dict[str, dict[int, IncidentReport]] = {}
        self._alert_messages: set[str] = set()
        self._alert_incidents: dict[str, str] = {}
        self._contexts: dict[str, ConversationContext] = {}
        self._lock = asyncio.Lock()

    async def create_investigation(
        self, record: InvestigationRecord, request: InvestigationRequest
    ) -> bool:
        async with self._lock:
            if record.investigation_id in self._records:
                return False
            self._records[record.investigation_id] = record.model_copy(deep=True)
            self._requests[record.investigation_id] = request.model_copy(deep=True)
            incident = self._incidents.get(record.incident_id)
            if incident is None:
                incident = IncidentRecord(
                    incident_id=record.incident_id,
                    services=request.services,
                    opened_at=record.created_at,
                    latest_investigation_id=record.investigation_id,
                    assumptions=request.assumptions,
                )
            else:
                incident = incident.model_copy(
                    update={"latest_investigation_id": record.investigation_id}, deep=True
                )
            self._incidents[record.incident_id] = incident
            return True

    async def put_record(self, record: InvestigationRecord) -> None:
        async with self._lock:
            self._records[record.investigation_id] = record.model_copy(deep=True)

    async def get_record(self, investigation_id: str) -> InvestigationRecord | None:
        async with self._lock:
            record = self._records.get(investigation_id)
            return record.model_copy(deep=True) if record else None

    async def get_request(self, investigation_id: str) -> InvestigationRequest | None:
        async with self._lock:
            request = self._requests.get(investigation_id)
            return request.model_copy(deep=True) if request else None

    async def claim(
        self, investigation_id: str, *, now: datetime
    ) -> tuple[InvestigationRecord, InvestigationRequest] | None:
        async with self._lock:
            record = self._records.get(investigation_id)
            request = self._requests.get(investigation_id)
            if record is None or request is None:
                return None
            lease_active = record.lease_expires_at is not None and record.lease_expires_at > now
            if record.status is InvestigationStatus.RUNNING and lease_active:
                return None
            if record.status not in {InvestigationStatus.QUEUED, InvestigationStatus.RUNNING}:
                return None
            claimed = record.model_copy(
                update={
                    "status": InvestigationStatus.RUNNING,
                    "current_stage": "EVIDENCE_COLLECTION",
                    "started_at": record.started_at or now,
                    "lease_expires_at": now + timedelta(minutes=5),
                    "task_attempts": record.task_attempts + 1,
                }
            )
            self._records[investigation_id] = claimed
            return claimed.model_copy(deep=True), request.model_copy(deep=True)

    async def complete(
        self, record: InvestigationRecord, execution: InvestigationExecution, *, now: datetime
    ) -> tuple[InvestigationRecord, IncidentReport]:
        async with self._lock:
            incident = self._incidents[record.incident_id]
            version = incident.latest_report_version + 1
            report = execution.report.model_copy(
                update={
                    "incident_id": record.incident_id,
                    "report_id": f"RPT-{record.incident_id.removeprefix('INC-')}-{version:04d}",
                    "report_version": version,
                },
                deep=True,
            )
            self._reports.setdefault(record.incident_id, {})[version] = report
            completed = record.model_copy(
                update={
                    "status": InvestigationStatus.COMPLETE,
                    "current_stage": "COMPLETE",
                    "completed_collectors": execution.completed_collectors,
                    "partial_failures": [error.safe_message for error in report.tool_errors],
                    "finished_at": now,
                    "lease_expires_at": None,
                    "report_version": version,
                }
            )
            self._records[record.investigation_id] = completed
            self._incidents[record.incident_id] = incident.model_copy(
                update={
                    "latest_report_version": version,
                    "latest_investigation_id": record.investigation_id,
                    "services": report.affected_services,
                }
            )
            return completed.model_copy(deep=True), report.model_copy(deep=True)

    async def fail(self, record: InvestigationRecord, *, now: datetime, safe_error: str) -> None:
        failed = record.model_copy(
            update={
                "status": InvestigationStatus.FAILED,
                "current_stage": "FAILED",
                "finished_at": now,
                "lease_expires_at": None,
                "safe_error": safe_error,
            }
        )
        await self.put_record(failed)

    async def retry(self, record: InvestigationRecord, *, safe_error: str) -> None:
        async with self._lock:
            current = self._records.get(record.investigation_id)
            if current is not None and current.status is InvestigationStatus.RUNNING:
                self._records[record.investigation_id] = current.model_copy(
                    update={
                        "status": InvestigationStatus.QUEUED,
                        "current_stage": "QUEUED",
                        "lease_expires_at": None,
                        "safe_error": safe_error,
                    }
                )

    async def get_incident(self, incident_id: str) -> IncidentRecord | None:
        async with self._lock:
            incident = self._incidents.get(incident_id)
            return incident.model_copy(deep=True) if incident else None

    async def list_reports(self, incident_id: str) -> list[IncidentReport]:
        async with self._lock:
            reports = self._reports.get(incident_id, {})
            return [reports[key].model_copy(deep=True) for key in sorted(reports)]

    async def get_report(
        self, incident_id: str, version: int | None = None
    ) -> IncidentReport | None:
        async with self._lock:
            reports = self._reports.get(incident_id, {})
            selected = version if version is not None else max(reports, default=0)
            report = reports.get(selected)
            return report.model_copy(deep=True) if report else None

    async def ingest_alert(
        self, seed: IncidentSeed, *, message_key: str
    ) -> tuple[IncidentRecord, bool]:
        async with self._lock:
            if message_key in self._alert_messages:
                incident_id = self._alert_incidents[seed.alert_key_hash]
                return self._incidents[incident_id].model_copy(deep=True), False
            self._alert_messages.add(message_key)
            incident_id = self._alert_incidents.get(seed.alert_key_hash, seed.incident_id)
            current = self._incidents.get(incident_id)
            if current is None:
                current = IncidentRecord(
                    incident_id=incident_id,
                    services=seed.services,
                    state=seed.state,
                    source=seed.source,
                    opened_at=seed.opened_at,
                    closed_at=seed.closed_at,
                    assumptions=seed.assumptions,
                )
            elif seed.state is IncidentState.CLOSED:
                current = current.model_copy(
                    update={"state": IncidentState.CLOSED, "closed_at": seed.closed_at}
                )
            self._incidents[incident_id] = current
            self._alert_incidents[seed.alert_key_hash] = incident_id
            return current.model_copy(deep=True), True

    async def get_context(self, session_hash: str) -> ConversationContext | None:
        async with self._lock:
            context = self._contexts.get(session_hash)
            if context is None or context.expires_at <= datetime.now(UTC):
                self._contexts.pop(session_hash, None)
                return None
            return context.model_copy(deep=True)

    async def put_context(self, context: ConversationContext) -> None:
        async with self._lock:
            self._contexts[context.session_hash] = context.model_copy(deep=True)


class CloudTasksPublisher:
    """Dependency-free Cloud Tasks REST publisher with deterministic task names."""

    def __init__(
        self,
        *,
        queue_name: str,
        worker_url: str,
        service_account_email: str,
        audience: str,
        session: AuthorizedSession | None = None,
    ) -> None:
        self.queue_name = queue_name.rstrip("/")
        self.worker_url = worker_url.rstrip("/")
        self.service_account_email = service_account_email
        self.audience = audience
        self.session = session or _authorized_session()

    async def publish(self, investigation_id: str) -> None:
        task_id = hashlib.sha256(investigation_id.encode()).hexdigest()[:32]
        payload = base64.b64encode(
            json.dumps({"investigation_id": investigation_id}).encode()
        ).decode()
        body = {
            "task": {
                "name": f"{self.queue_name}/tasks/{task_id}",
                "httpRequest": {
                    "httpMethod": "POST",
                    "url": (
                        f"{self.worker_url}/internal/v1/investigations/"
                        f"{quote(investigation_id)}/execute"
                    ),
                    "headers": {"Content-Type": "application/json"},
                    "body": payload,
                    "oidcToken": {
                        "serviceAccountEmail": self.service_account_email,
                        "audience": self.audience,
                    },
                },
            }
        }
        request_body: dict[str, Any] = body
        response = await asyncio.to_thread(
            self.session.post,
            f"https://cloudtasks.googleapis.com/v2/{self.queue_name}/tasks",
            json=request_body,
            timeout=10,
        )
        if response.status_code not in {200, 201, 409}:
            raise RuntimeError("investigation task could not be queued")


def new_incident_id(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return f"INC-{current:%Y}-{secrets.token_hex(8).upper()}"


class InvestigationCoordinator:
    def __init__(
        self,
        catalog: ServiceCatalog,
        executor: InvestigationExecutor | None = None,
        *,
        store: InvestigationStore | None = None,
        task_publisher: InvestigationTaskPublisher | None = None,
    ) -> None:
        self.catalog = catalog
        self.executor = executor or FixtureInvestigationExecutor(tuple(catalog.services))
        self.store = store or InMemoryInvestigationStore()
        self.task_publisher = task_publisher
        self._tasks: set[asyncio.Task[InvestigationRecord | None]] = set()

    async def submit(
        self,
        query: str,
        incident_id: str | None,
        mode: RequestedDepth,
        *,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        audit: InvestigationAudit | None = None,
        output_language: OutputLanguage = OutputLanguage.EN,
    ) -> InvestigationRecord:
        request = parse_investigation_request(
            query,
            catalog=self.catalog,
            incident_id=incident_id,
            mode=mode,
            output_language=output_language,
        )
        if request.requested_actions:
            raise ValueError("write actions are outside the read-only investigation API")
        effective_incident = request.incident_id
        assigned_incident = effective_incident or new_incident_id()
        safe_query = redact_text(query)
        request = request.model_copy(
            update={"incident_id": assigned_incident, "user_query": safe_query}
        )
        self.executor.validate(request)
        effective_trace = trace_id or new_trace_id()
        effective_correlation = correlation_id or new_correlation_id()
        effective_audit = audit or InvestigationAudit(
            source="direct_api",
            query_hash=audit_hash("direct_api_query", query),
            trace_id=effective_trace,
        )
        if effective_audit.trace_id != effective_trace:
            raise ValueError("audit trace ID does not match the investigation trace ID")
        investigation_id = (
            f"INV-RUN-{effective_audit.run_id.removeprefix('RUN-')}"
            if effective_audit.run_id is not None
            else f"INV-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:12].upper()}"
        )
        record = InvestigationRecord(
            investigation_id=investigation_id,
            correlation_id=effective_correlation,
            trace_id=effective_trace,
            incident_id=assigned_incident,
            status=InvestigationStatus.QUEUED,
            current_stage="QUEUED",
            execution_mode=self.executor.execution_mode,
            scenario_id=self.executor.scenario_id,
            audit=effective_audit,
        )
        created = await self.store.create_investigation(record, request)
        stored = await self.store.get_record(investigation_id)
        if stored is not None:
            record = stored
        if self.task_publisher is not None:
            await self.task_publisher.publish(record.investigation_id)
        elif self.task_publisher is None and created:
            task = asyncio.create_task(self.process_task(record.investigation_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return record

    async def replay(self, incident_id: str) -> InvestigationRecord:
        incident = await self.store.get_incident(incident_id)
        if incident is None or incident.latest_investigation_id is None:
            raise ValueError("incident has no persisted investigation scope")
        request = await self.store.get_request(incident.latest_investigation_id)
        if request is None:
            raise ValueError("incident investigation scope is unavailable")
        trace_id = new_trace_id()
        return await self.submit(
            request.user_query,
            incident_id,
            request.requested_depth,
            trace_id=trace_id,
            output_language=request.output_language,
            audit=InvestigationAudit(
                source="replay",
                query_hash=audit_hash("replay_query", request.user_query),
                trace_id=trace_id,
            ),
        )

    async def process_task(self, investigation_id: str) -> InvestigationRecord | None:
        claim = await self.store.claim(investigation_id, now=datetime.now(UTC))
        if claim is None:
            return await self.store.get_record(investigation_id)
        record, request = claim
        try:
            execution = await self.executor.execute(
                request,
                correlation_id=record.correlation_id,
                trace_id=record.trace_id,
                investigation_id=record.investigation_id,
                run_id=record.audit.run_id if record.audit is not None else None,
            )
        except Exception:
            await self.store.fail(
                record,
                now=datetime.now(UTC),
                safe_error="The bounded investigation failed.",
            )
            return await self.store.get_record(investigation_id)
        try:
            completed, _ = await self.store.complete(record, execution, now=datetime.now(UTC))
        except Exception:
            await self.store.retry(record, safe_error="Report persistence will be retried.")
            raise
        return completed

    async def close(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
