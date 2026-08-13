"""FastAPI surface for persistent, bounded investigations."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from opspilot import __version__
from opspilot.audit import InvestigationAudit, audit_hash, extract_trace_id, new_trace_id
from opspilot.catalog import ServiceCatalog, load_service_catalog
from opspilot.domain import INCIDENT_ID_PATTERN, IncidentReport, OutputLanguage, RequestedDepth
from opspilot.remediation.auth import GoogleIdTokenVerifier, TokenVerifier, bearer_token
from opspilot.remediation.errors import RemediationError
from opspilot.reporting import render_markdown
from opspilot.service import (
    CloudTasksPublisher,
    IncidentRecord,
    IncidentSeed,
    IncidentState,
    InvestigationCoordinator,
    InvestigationExecutor,
    InvestigationRecord,
    InvestigationStore,
    InvestigationTaskPublisher,
    LiveInvestigationExecutor,
    new_incident_id,
)

LOGGER = logging.getLogger(__name__)


def _verified_caller(
    app: FastAPI,
    authorization: str | None,
    *,
    audience: str,
    allowed_email: str | None = None,
    source: str,
) -> str:
    principal = app.state.token_verifier.verify(bearer_token(authorization), audience=audience)
    if allowed_email is not None and (not allowed_email or principal.email != allowed_email):
        raise HTTPException(status_code=403, detail=f"{source} caller is not allowed")
    actor_hash = audit_hash(f"{source}_actor", principal.subject)
    LOGGER.info(
        "%s",
        json.dumps(
            {
                "actor_hash": actor_hash,
                "event": "opspilot_internal_caller",
                "source": source,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
    )
    return actor_hash


class StartInvestigationRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2_000)
    incident_id: str | None = Field(default=None, pattern=INCIDENT_ID_PATTERN)
    mode: RequestedDepth = RequestedDepth.STANDARD


class StartInvestigationResponse(BaseModel):
    investigation_id: str
    correlation_id: str
    trace_id: str
    incident_id: str
    status: str


class RuntimeInvestigationRequest(StartInvestigationRequest):
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{16}$")
    correlation_id: str = Field(pattern=r"^COR-[A-F0-9]{16}$")
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    actor_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    session_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    query_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_language: OutputLanguage = OutputLanguage.EN


class PubSubMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    data: str
    message_id: str = Field(alias="messageId", min_length=1, max_length=256)


class PubSubEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: PubSubMessage
    subscription: str | None = None


class AlertIngestResponse(BaseModel):
    incident_id: str
    state: IncidentState
    created_or_updated: bool
    investigation_started: bool = False


class ValueChange(BaseModel):
    before: Any
    after: Any
    changed: bool


class ReportComparison(BaseModel):
    incident_id: str
    from_version: int
    to_version: int
    status: ValueChange
    severity: ValueChange
    top_hypothesis: ValueChange
    evidence_ids: ValueChange
    data_gaps: ValueChange
    recommendations: ValueChange


def _coordinator(request: Request) -> InvestigationCoordinator:
    return cast(InvestigationCoordinator, request.app.state.coordinator)


def _parse_datetime(value: object, fallback: datetime) -> datetime:
    if not isinstance(value, str):
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else fallback


def _nested(mapping: dict[str, Any], *path: str) -> object:
    current: object = mapping
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _incident_seed(payload: dict[str, Any], catalog: ServiceCatalog) -> IncidentSeed:
    incident = payload.get("incident")
    if not isinstance(incident, dict):
        raise ValueError("Monitoring payload has no incident object")
    resource_labels = _nested(incident, "resource", "labels")
    service = None
    if isinstance(resource_labels, dict):
        service = resource_labels.get("service_name") or resource_labels.get("service")
    if not isinstance(service, str):
        resource_name = incident.get("resource_name")
        if isinstance(resource_name, str):
            service = next((name for name in catalog.services if name in resource_name), None)
    if service not in catalog.services:
        raise ValueError("Monitoring incident service is not allowlisted")
    raw_state = str(incident.get("state", "OPEN")).upper()
    if raw_state in {"OPEN", "INCIDENT_OPEN", "FIRING"}:
        state = IncidentState.OPEN
    elif raw_state in {"CLOSED", "INCIDENT_CLOSED", "RESOLVED"}:
        state = IncidentState.CLOSED
    else:
        raise ValueError("Monitoring incident state is unsupported")
    external_key = str(
        incident.get("incident_id")
        or incident.get("name")
        or incident.get("url")
        or incident.get("resource_name")
        or ""
    )
    if not external_key:
        raise ValueError("Monitoring incident has no stable deduplication key")
    now = datetime.now(UTC)
    opened_at = _parse_datetime(incident.get("started_at") or incident.get("startedAt"), now)
    closed_at = (
        _parse_datetime(incident.get("ended_at") or incident.get("endedAt"), now)
        if state is IncidentState.CLOSED
        else None
    )
    return IncidentSeed(
        incident_id=new_incident_id(now),
        services=[service],
        state=state,
        opened_at=opened_at,
        closed_at=closed_at,
        alert_key_hash=f"sha256:{hashlib.sha256(external_key.encode()).hexdigest()}",
        assumptions=["Incident scope was derived from an allowlisted Monitoring alert."],
    )


def compare_reports(before: IncidentReport, after: IncidentReport) -> ReportComparison:
    def change(left: Any, right: Any) -> ValueChange:
        return ValueChange(before=left, after=right, changed=left != right)

    def top(report: IncidentReport) -> dict[str, Any] | None:
        if not report.hypotheses:
            return None
        hypothesis = sorted(report.hypotheses, key=lambda item: (item.rank, item.hypothesis_id))[0]
        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "claim": hypothesis.claim,
            "status": hypothesis.status.value,
            "evidence_support_score": hypothesis.evidence_support_score,
        }

    def recommendations(report: IncidentReport) -> list[dict[str, str]]:
        return sorted(
            [
                {"action_id": item.action_id, "title": item.title, "risk_level": item.risk_level}
                for item in report.recommended_actions
            ],
            key=lambda item: item["action_id"],
        )

    return ReportComparison(
        incident_id=before.incident_id,
        from_version=before.report_version,
        to_version=after.report_version,
        status=change(before.status.value, after.status.value),
        severity=change(before.severity, after.severity),
        top_hypothesis=change(top(before), top(after)),
        evidence_ids=change(
            sorted(item.evidence_id for item in before.evidence),
            sorted(item.evidence_id for item in after.evidence),
        ),
        data_gaps=change(sorted(before.data_gaps), sorted(after.data_gaps)),
        recommendations=change(recommendations(before), recommendations(after)),
    )


def _production_adapters() -> tuple[InvestigationStore | None, InvestigationTaskPublisher | None]:
    project_id = os.getenv("OPSPILOT_INVESTIGATION_PROJECT_ID", "").strip()
    if not project_id:
        return None, None
    from opspilot.investigation_firestore import FirestoreInvestigationStore

    store: InvestigationStore = FirestoreInvestigationStore(
        project_id=project_id,
        database_id=os.getenv("OPSPILOT_INVESTIGATION_DATABASE_ID", "opspilot-dev"),
    )
    queue = os.getenv("OPSPILOT_INVESTIGATION_TASK_QUEUE", "").strip()
    if not queue:
        return store, None
    publisher: InvestigationTaskPublisher = CloudTasksPublisher(
        queue_name=queue,
        worker_url=os.environ["OPSPILOT_INVESTIGATION_WORKER_URL"],
        service_account_email=os.environ["OPSPILOT_INVESTIGATION_TASK_SERVICE_ACCOUNT"],
        audience=os.environ["OPSPILOT_INVESTIGATION_WORKER_AUDIENCE"],
    )
    return store, publisher


def create_app(
    executor: InvestigationExecutor | None = None,
    *,
    store: InvestigationStore | None = None,
    task_publisher: InvestigationTaskPublisher | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    catalog = load_service_catalog()
    if store is None and task_publisher is None:
        store, task_publisher = _production_adapters()
    project_id = os.getenv("OPSPILOT_INVESTIGATION_PROJECT_ID", "").strip()
    if executor is None and project_id:
        executor = LiveInvestigationExecutor(
            project_id=project_id,
            catalog=catalog,
            region=os.getenv("OPSPILOT_INVESTIGATION_REGION", "asia-northeast3"),
        )
    coordinator = InvestigationCoordinator(
        catalog,
        executor=executor,
        store=store,
        task_publisher=task_publisher,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await coordinator.close()

    app = FastAPI(title="OpsPilot MVP", version=__version__, lifespan=lifespan)
    app.state.coordinator = coordinator
    app.state.token_verifier = token_verifier or GoogleIdTokenVerifier()

    @app.exception_handler(RemediationError)
    async def authentication_error_handler(_: Request, error: RemediationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.safe_message}},
        )

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    async def ready() -> dict[str, str | int]:
        return {"status": "ready", "allowlisted_services": len(catalog.services)}

    @app.post(
        "/api/v1/investigations",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=StartInvestigationResponse,
    )
    async def start_investigation(
        payload: StartInvestigationRequest,
        request: Request,
        authorization: str | None = Header(default=None),
        cloud_trace_context: str | None = Header(default=None, alias="X-Cloud-Trace-Context"),
    ) -> StartInvestigationResponse:
        trace_id = extract_trace_id(cloud_trace_context) or new_trace_id()
        actor_hash: str | None = None
        audience = os.getenv("OPSPILOT_INVESTIGATION_AUDIENCE", "").strip()
        if audience:
            actor_hash = _verified_caller(
                app,
                authorization,
                audience=audience,
                source="direct_api",
            )
        try:
            record = await _coordinator(request).submit(
                payload.query,
                payload.incident_id,
                payload.mode,
                trace_id=trace_id,
                audit=InvestigationAudit(
                    source="direct_api",
                    actor_hash=actor_hash,
                    query_hash=audit_hash("direct_api_query", payload.query),
                    trace_id=trace_id,
                ),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return StartInvestigationResponse(
            investigation_id=record.investigation_id,
            correlation_id=record.correlation_id,
            trace_id=record.trace_id,
            incident_id=record.incident_id,
            status=record.status.value,
        )

    @app.post("/internal/v1/investigations/{investigation_id}/execute")
    async def execute_task(
        investigation_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> InvestigationRecord:
        audience = os.getenv("OPSPILOT_INVESTIGATION_AUDIENCE", "").strip()
        if audience:
            _verified_caller(
                app,
                authorization,
                audience=audience,
                allowed_email=os.getenv("OPSPILOT_INVESTIGATION_TASK_SERVICE_ACCOUNT", "").strip(),
                source="task",
            )
        try:
            record = await _coordinator(request).process_task(investigation_id)
        except Exception as error:
            raise HTTPException(
                status_code=503, detail="investigation task should be retried"
            ) from error
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record

    @app.post("/internal/v1/runtime/investigations", response_class=PlainTextResponse)
    async def runtime_investigation(
        payload: RuntimeInvestigationRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> PlainTextResponse:
        """Bridge one Enterprise turn to the same queued, persisted execution path."""

        coordinator_value = _coordinator(request)
        if payload.query_hash != audit_hash("enterprise_query", payload.query):
            raise HTTPException(status_code=422, detail="runtime query hash does not match")
        audience = os.getenv("OPSPILOT_INVESTIGATION_AUDIENCE", "").strip()
        if audience:
            _verified_caller(
                app,
                authorization,
                audience=audience,
                allowed_email=os.getenv(
                    "OPSPILOT_INVESTIGATION_RUNTIME_SERVICE_ACCOUNT", ""
                ).strip(),
                source="runtime",
            )
        try:
            submitted = await coordinator_value.submit(
                payload.query,
                payload.incident_id,
                payload.mode,
                correlation_id=payload.correlation_id,
                trace_id=payload.trace_id,
                audit=InvestigationAudit(
                    source="enterprise",
                    actor_hash=payload.actor_hash,
                    session_hash=payload.session_hash,
                    query_hash=payload.query_hash,
                    run_id=payload.run_id,
                    trace_id=payload.trace_id,
                ),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        deadline = asyncio.get_running_loop().time() + 12
        while asyncio.get_running_loop().time() < deadline:
            record = await coordinator_value.store.get_record(submitted.investigation_id)
            if record is None:
                raise HTTPException(status_code=503, detail="investigation state is unavailable")
            if record.status.value == "COMPLETE":
                report = await coordinator_value.store.get_report(record.incident_id)
                if report is None:
                    raise HTTPException(status_code=503, detail="persisted report is unavailable")
                return PlainTextResponse(
                    render_markdown(report, language=payload.output_language),
                    media_type="text/markdown",
                )
            if record.status.value == "FAILED":
                raise HTTPException(status_code=503, detail="investigation failed safely")
            await asyncio.sleep(0.25)
        raise HTTPException(status_code=504, detail="investigation did not finish in time")

    @app.get("/api/v1/investigations/{investigation_id}", response_model=InvestigationRecord)
    async def investigation_status(investigation_id: str, request: Request) -> InvestigationRecord:
        record = await _coordinator(request).store.get_record(investigation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record

    @app.get("/api/v1/incidents/{incident_id}", response_model=IncidentRecord)
    async def incident(incident_id: str, request: Request) -> IncidentRecord:
        value = await _coordinator(request).store.get_incident(incident_id)
        if value is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return value

    @app.get("/api/v1/incidents/{incident_id}/reports", response_model=list[IncidentReport])
    async def reports(incident_id: str, request: Request) -> list[IncidentReport]:
        if await _coordinator(request).store.get_incident(incident_id) is None:
            raise HTTPException(status_code=404, detail="incident not found")
        return await _coordinator(request).store.list_reports(incident_id)

    @app.get("/api/v1/incidents/{incident_id}/reports/latest", response_model=IncidentReport)
    async def latest_report(
        incident_id: str,
        request: Request,
        accept: str | None = Header(default=None),
    ) -> IncidentReport | PlainTextResponse:
        report = await _coordinator(request).store.get_report(incident_id)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        if accept and "text/markdown" in accept:
            return PlainTextResponse(render_markdown(report), media_type="text/markdown")
        return report

    @app.get(
        "/api/v1/incidents/{incident_id}/reports/compare",
        response_model=ReportComparison,
    )
    async def compare(
        incident_id: str,
        request: Request,
        from_version: int = Query(ge=1),
        to_version: int = Query(ge=1),
    ) -> ReportComparison:
        before = await _coordinator(request).store.get_report(incident_id, from_version)
        after = await _coordinator(request).store.get_report(incident_id, to_version)
        if before is None or after is None:
            raise HTTPException(status_code=404, detail="report version not found")
        return compare_reports(before, after)

    @app.get("/api/v1/incidents/{incident_id}/reports/{version}", response_model=IncidentReport)
    async def report_version(incident_id: str, version: int, request: Request) -> IncidentReport:
        report = await _coordinator(request).store.get_report(incident_id, version)
        if report is None:
            raise HTTPException(status_code=404, detail="report not found")
        return report

    @app.post(
        "/api/v1/incidents/{incident_id}/replays",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=StartInvestigationResponse,
    )
    async def replay(incident_id: str, request: Request) -> StartInvestigationResponse:
        try:
            record = await _coordinator(request).replay(incident_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return StartInvestigationResponse(
            investigation_id=record.investigation_id,
            correlation_id=record.correlation_id,
            trace_id=record.trace_id,
            incident_id=record.incident_id,
            status=record.status.value,
        )

    @app.post("/internal/v1/alerts/monitoring", response_model=AlertIngestResponse)
    async def monitoring_alert(
        envelope: PubSubEnvelope,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> AlertIngestResponse:
        audience = os.getenv("OPSPILOT_INVESTIGATION_AUDIENCE", "").strip()
        if audience:
            _verified_caller(
                app,
                authorization,
                audience=audience,
                allowed_email=os.getenv("OPSPILOT_INVESTIGATION_ALERT_SERVICE_ACCOUNT", "").strip(),
                source="alert",
            )
        try:
            decoded = base64.b64decode(envelope.message.data, validate=True)
            payload = json.loads(decoded)
            if not isinstance(payload, dict):
                raise ValueError("Monitoring payload must be an object")
            seed = _incident_seed(cast(dict[str, Any], payload), catalog)
            message_key = (
                f"sha256:{hashlib.sha256(envelope.message.message_id.encode()).hexdigest()}"
            )
            incident_value, changed = await _coordinator(request).store.ingest_alert(
                seed, message_key=message_key
            )
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return AlertIngestResponse(
            incident_id=incident_value.incident_id,
            state=incident_value.state,
            created_or_updated=changed,
        )

    return app
