"""Minimal structured stdout logging for Cloud Run correlation."""

from __future__ import annotations

import json
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from opspilot.demo.config import DemoSettings

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
TRACE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


def normalize_request_id(value: str | None) -> str:
    if value is None:
        return f"req_{uuid4().hex[:20]}"
    if not REQUEST_ID_PATTERN.fullmatch(value):
        raise ValueError("invalid X-Request-ID")
    return value


def extract_trace_id(trace_context: str | None) -> str | None:
    if not trace_context:
        return None
    trace_id = trace_context.split("/", maxsplit=1)[0]
    return trace_id.lower() if TRACE_ID_PATTERN.fullmatch(trace_id) else None


def emit_request_log(
    settings: DemoSettings,
    *,
    request_id: str,
    trace_id: str | None,
    method: str,
    path: str,
    status_code: int,
    latency_ms: int,
) -> None:
    payload: dict[str, str | int] = {
        "severity": "ERROR" if status_code >= 500 else "INFO",
        "message": "demo service request completed",
        "service": f"{settings.service.value}-service",
        "environment": settings.environment,
        "revision": settings.revision,
        "request_id": request_id,
        "trace_id": trace_id or "",
        "event_type": "http_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    if trace_id and settings.project_id:
        payload["logging.googleapis.com/trace"] = (
            f"projects/{settings.project_id}/traces/{trace_id}"
        )
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True), flush=True)


def emit_scenario_log(
    settings: DemoSettings,
    *,
    request_id: str,
    trace_id: str | None,
    scenario_id: str,
    scenario_run_id: str,
    scenario_step: int,
) -> None:
    payload: dict[str, str | int] = {
        "severity": "ERROR",
        "message": "synthetic payment pool acquisition timed out",
        "service": f"{settings.service.value}-service",
        "environment": settings.environment,
        "revision": settings.revision,
        "request_id": request_id,
        "trace_id": trace_id or "",
        "event_type": "database_timeout",
        "error_code": "DB_POOL_TIMEOUT",
        "latency_ms": 250,
        "scenario_id": scenario_id,
        "scenario_run_id": scenario_run_id,
        "scenario_step": scenario_step,
    }
    if trace_id and settings.project_id:
        payload["logging.googleapis.com/trace"] = (
            f"projects/{settings.project_id}/traces/{trace_id}"
        )
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True), flush=True)


def install_request_logging(app: FastAPI, settings: DemoSettings) -> None:
    @app.middleware("http")
    async def request_logging(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = perf_counter()
        status_code = 500
        response: Response
        try:
            request_id = normalize_request_id(request.headers.get("X-Request-ID"))
        except ValueError:
            request_id = f"req_{uuid4().hex[:20]}"
            response = JSONResponse(
                status_code=400,
                content={"detail": "invalid X-Request-ID", "request_id": request_id},
            )
            response.headers["X-Request-ID"] = request_id
            status_code = response.status_code
            emit_request_log(
                settings,
                request_id=request_id,
                trace_id=None,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                latency_ms=max(0, round((perf_counter() - started) * 1_000)),
            )
            return response

        request.state.request_id = request_id
        trace_context = request.headers.get("X-Cloud-Trace-Context")
        request.state.trace_context = trace_context
        trace_id = extract_trace_id(trace_context)
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            emit_request_log(
                settings,
                request_id=request_id,
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                latency_ms=max(0, round((perf_counter() - started) * 1_000)),
            )
