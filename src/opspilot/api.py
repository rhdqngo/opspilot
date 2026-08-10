"""FastAPI surface for the local R0 investigation workflow."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from opspilot import __version__
from opspilot.catalog import load_service_catalog
from opspilot.domain import IncidentReport, RequestedDepth
from opspilot.reporting import render_markdown
from opspilot.service import InvestigationCoordinator, InvestigationRecord


class StartInvestigationRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2_000)
    incident_id: str | None = Field(default=None, pattern=r"^INC-\d{4}-\d{4}$")
    mode: RequestedDepth = RequestedDepth.STANDARD


class StartInvestigationResponse(BaseModel):
    investigation_id: str
    correlation_id: str
    status: str


def _coordinator(request: Request) -> InvestigationCoordinator:
    return cast(InvestigationCoordinator, request.app.state.coordinator)


def create_app() -> FastAPI:
    catalog = load_service_catalog()
    coordinator = InvestigationCoordinator(catalog)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await coordinator.close()

    app = FastAPI(title="OpsPilot R0", version=__version__, lifespan=lifespan)
    app.state.coordinator = coordinator

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
        payload: StartInvestigationRequest, request: Request
    ) -> StartInvestigationResponse:
        try:
            record = await _coordinator(request).submit(
                payload.query, payload.incident_id, payload.mode
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return StartInvestigationResponse(
            investigation_id=record.investigation_id,
            correlation_id=record.correlation_id,
            status=record.status.value,
        )

    @app.get("/api/v1/investigations/{investigation_id}", response_model=InvestigationRecord)
    async def investigation_status(investigation_id: str, request: Request) -> InvestigationRecord:
        record = await _coordinator(request).store.get_record(investigation_id)
        if record is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return record

    @app.get(
        "/api/v1/incidents/{incident_id}/reports/latest",
        response_model=IncidentReport,
    )
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

    return app
