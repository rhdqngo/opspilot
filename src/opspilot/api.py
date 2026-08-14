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
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from opspilot import __version__
from opspilot.audit import InvestigationAudit, audit_hash, extract_trace_id, new_trace_id
from opspilot.catalog import ServiceCatalog, load_service_catalog
from opspilot.conversation import (
    capabilities_markdown,
    classify_turn,
    classify_validation_error,
    compare_reports_markdown,
    contextualize_query,
    explain_report_markdown,
    incident_id_from_query,
    incident_ids_from_query,
    rejection_markdown,
)
from opspilot.domain import INCIDENT_ID_PATTERN, IncidentReport, OutputLanguage, RequestedDepth
from opspilot.remediation.auth import GoogleIdTokenVerifier, TokenVerifier, bearer_token
from opspilot.remediation.bridge import (
    HttpRemediationRequestGateway,
    RemediationRequestGateway,
)
from opspilot.remediation.errors import RemediationError
from opspilot.reporting import render_markdown
from opspilot.service import (
    AgentTurnIntent,
    CloudTasksPublisher,
    ConversationContext,
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


class RuntimeTurnResponse(BaseModel):
    intent: AgentTurnIntent
    outcome: str
    accepted: bool
    started_investigation: bool = False
    markdown: str
    progress_markdown: str | None = None
    investigation_id: str | None = None
    incident_id: str | None = None
    report_version: int | None = None
    remediation_id: str | None = None


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
    remediation_gateway: RemediationRequestGateway | None = None,
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
    remediation_url = os.getenv("OPSPILOT_REMEDIATION_CONTROL_URL", "").strip()
    remediation_audience = os.getenv("OPSPILOT_REMEDIATION_CONTROL_AUDIENCE", "").strip()
    if remediation_gateway is None and remediation_url and remediation_audience:
        remediation_gateway = HttpRemediationRequestGateway(
            base_url=remediation_url,
            audience=remediation_audience,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await coordinator.close()

    app = FastAPI(title="OpsPilot MVP", version=__version__, lifespan=lifespan)
    app.state.coordinator = coordinator
    app.state.catalog = catalog
    app.state.remediation_gateway = remediation_gateway
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

    @app.post("/internal/v2/runtime/turns", response_model=RuntimeTurnResponse)
    async def runtime_turn(
        payload: RuntimeInvestigationRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> RuntimeTurnResponse:
        """Resolve an Enterprise turn using bounded durable conversation context."""

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

        query_incident_ids = incident_ids_from_query(payload.query)
        if len(query_incident_ids) > 1 or (
            payload.incident_id is not None
            and query_incident_ids
            and payload.incident_id.upper() != query_incident_ids[0]
        ):
            return RuntimeTurnResponse(
                intent=AgentTurnIntent.REJECTED,
                outcome="rejected",
                accepted=False,
                markdown=rejection_markdown("multiple_incidents", payload.output_language),
            )

        intent = classify_turn(payload.query)
        context = (
            await coordinator_value.store.get_context(payload.session_hash)
            if payload.session_hash is not None
            else None
        )
        if intent is AgentTurnIntent.SHOW_CAPABILITIES:
            return RuntimeTurnResponse(
                intent=intent,
                outcome="complete",
                accepted=True,
                markdown=capabilities_markdown(payload.output_language),
            )

        context_incident_id = context.incident_id if context is not None else None
        incident_id = incident_id_from_query(payload.query) or context_incident_id
        if intent in {
            AgentTurnIntent.EXPLAIN_REPORT,
            AgentTurnIntent.COMPARE_REPORT_VERSIONS,
            AgentTurnIntent.SHOW_STATUS,
        }:
            if incident_id is None:
                return RuntimeTurnResponse(
                    intent=AgentTurnIntent.REJECTED,
                    outcome="rejected",
                    accepted=False,
                    markdown=rejection_markdown("missing_context", payload.output_language),
                )
            reports = await coordinator_value.store.list_reports(incident_id)
            if not reports:
                return RuntimeTurnResponse(
                    intent=AgentTurnIntent.REJECTED,
                    outcome="rejected",
                    accepted=False,
                    markdown=rejection_markdown("missing_context", payload.output_language),
                    incident_id=incident_id,
                )
            latest = reports[-1]
            if intent is AgentTurnIntent.COMPARE_REPORT_VERSIONS:
                markdown = compare_reports_markdown(reports, language=payload.output_language)
            elif intent is AgentTurnIntent.SHOW_STATUS:
                markdown = (
                    f"조사 상태: `{latest.status.value}`, 보고서 버전: `{latest.report_version}`\n"
                    if payload.output_language is OutputLanguage.KO
                    else (
                        f"Investigation status: `{latest.status.value}`, "
                        f"report version: `{latest.report_version}`\n"
                    )
                )
            else:
                markdown = explain_report_markdown(
                    latest, query=payload.query, language=payload.output_language
                )
            return RuntimeTurnResponse(
                intent=intent,
                outcome="complete",
                accepted=True,
                markdown=markdown,
                incident_id=incident_id,
                report_version=latest.report_version,
            )

        if intent is AgentTurnIntent.CREATE_REMEDIATION_REQUEST:
            eligible = (
                context is not None
                and context.environment.value == "prod-sim"
                and context.services == ["payment-service"]
                and payload.actor_hash is not None
            )
            if eligible and incident_id is not None:
                report = await coordinator_value.store.get_report(incident_id)
                gateway = cast(
                    RemediationRequestGateway | None,
                    request.app.state.remediation_gateway,
                )
                if report is not None and gateway is not None:
                    try:
                        reference = await gateway.request(
                            incident_id=incident_id,
                            report=report,
                            actor_hash=cast(str, payload.actor_hash),
                            idempotency_key=payload.run_id,
                        )
                    except ValueError:
                        pass
                    else:
                        markdown = (
                            "복구 승인 요청을 만들었습니다. 별도 M8 승인 경로에서 검토해야 하며 "
                            "아직 실행되지 않았습니다.\n\n"
                            f"- 상태: `{reference.status}`\n"
                            f"- remediation ID: `{reference.remediation_id}`\n"
                            f"- 만료 시각: `{reference.expires_at}`\n"
                            if payload.output_language is OutputLanguage.KO
                            else (
                                "A remediation approval request was created. It must be reviewed "
                                "in the separate M8 control path and has not been executed.\n\n"
                                f"- Status: `{reference.status}`\n"
                                f"- Remediation ID: `{reference.remediation_id}`\n"
                                f"- Expires at: `{reference.expires_at}`\n"
                            )
                        )
                        return RuntimeTurnResponse(
                            intent=intent,
                            outcome="complete",
                            accepted=True,
                            markdown=markdown,
                            incident_id=incident_id,
                            report_version=report.report_version,
                            remediation_id=reference.remediation_id,
                        )
            return RuntimeTurnResponse(
                intent=AgentTurnIntent.REJECTED,
                outcome="rejected",
                accepted=False,
                markdown=rejection_markdown(
                    "write_unsupported" if "restart" in payload.query.lower() else "m8_ineligible",
                    payload.output_language,
                ),
                incident_id=incident_id if eligible else None,
            )

        if intent is AgentTurnIntent.REFINE_INVESTIGATION and context is None:
            return RuntimeTurnResponse(
                intent=AgentTurnIntent.REJECTED,
                outcome="rejected",
                accepted=False,
                markdown=rejection_markdown("missing_context", payload.output_language),
            )

        effective_query = (
            contextualize_query(payload.query, context=context, catalog=app.state.catalog)
            if intent is AgentTurnIntent.REFINE_INVESTIGATION and context is not None
            else payload.query
        )
        try:
            submitted = await coordinator_value.submit(
                effective_query,
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
                output_language=payload.output_language,
            )
        except ValueError as error:
            return RuntimeTurnResponse(
                intent=AgentTurnIntent.REJECTED,
                outcome="rejected",
                accepted=False,
                markdown=rejection_markdown(
                    classify_validation_error(str(error)), payload.output_language
                ),
            )
        stored_request = await coordinator_value.store.get_request(submitted.investigation_id)
        if stored_request is None:
            raise HTTPException(status_code=503, detail="investigation scope is unavailable")
        minutes = round((stored_request.end_time - stored_request.start_time).total_seconds() / 60)
        if payload.output_language is OutputLanguage.KO:
            progress_markdown = (
                f"{stored_request.environment.value} 환경에서 "
                f"{', '.join(stored_request.services)}의 최근 {minutes}분 증거를 "
                "수집하고 있습니다…\n\n"
            )
        else:
            progress_markdown = (
                f"Collecting bounded evidence for {', '.join(stored_request.services)} in "
                f"{stored_request.environment.value} over {minutes} minutes…\n\n"
            )
        deadline = asyncio.get_running_loop().time() + 30
        while asyncio.get_running_loop().time() < deadline:
            record = await coordinator_value.store.get_record(submitted.investigation_id)
            if record is None:
                raise HTTPException(status_code=503, detail="investigation state is unavailable")
            if record.status.value == "COMPLETE":
                report = await coordinator_value.store.get_report(record.incident_id)
                if report is None:
                    raise HTTPException(status_code=503, detail="persisted report is unavailable")
                if payload.session_hash is not None:
                    await coordinator_value.store.put_context(
                        ConversationContext(
                            session_hash=payload.session_hash,
                            incident_id=record.incident_id,
                            environment=stored_request.environment,
                            services=stored_request.services,
                            window_minutes=minutes,
                            requested_depth=stored_request.requested_depth,
                            report_version=report.report_version,
                            focus_hypothesis_id=stored_request.focus_hypothesis_id,
                            updated_at=datetime.now(UTC),
                            expires_at=datetime.now(UTC) + timedelta(hours=24),
                        )
                    )
                return RuntimeTurnResponse(
                    intent=intent,
                    outcome="complete",
                    accepted=True,
                    started_investigation=True,
                    markdown=render_markdown(report, language=payload.output_language),
                    progress_markdown=progress_markdown,
                    investigation_id=record.investigation_id,
                    incident_id=record.incident_id,
                    report_version=report.report_version,
                )
            if record.status.value == "FAILED":
                raise HTTPException(status_code=503, detail="investigation failed safely")
            await asyncio.sleep(0.25)
        raise HTTPException(status_code=504, detail="investigation did not finish in time")

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
                output_language=payload.output_language,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        deadline = asyncio.get_running_loop().time() + 30
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
