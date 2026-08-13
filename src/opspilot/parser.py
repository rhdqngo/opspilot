"""Conservative natural-language parsing for bounded live investigations."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from opspilot.catalog import ServiceCatalog, validate_request_scope
from opspilot.domain import Environment, InvestigationRequest, RequestedDepth, Symptom

SERVICE_TOKEN = re.compile(r"(?<![a-z0-9-])[a-z][a-z0-9-]*-service(?![a-z0-9-])")
MINUTE_WINDOW = re.compile(
    r"(?:(?:last|past|previous|최근|지난)\s*)?(\d{1,3})\s*(?:minutes?|mins?|min|분)\b",
    re.IGNORECASE,
)
HOUR_WINDOW = re.compile(
    r"(?:(?:last|past|previous|최근|지난)\s*)?(\d{1,2})\s*(?:hours?|hrs?|hr|시간)\b",
    re.IGNORECASE,
)
ACTION_TERMS = (
    "rollback",
    "roll back",
    "restart",
    "deploy",
    "delete",
    "scale",
    "롤백",
    "재시작",
    "배포",
    "삭제",
    "스케일",
)


def _window_minutes(query: str, maximum: int) -> int | None:
    values = {int(value) for value in MINUTE_WINDOW.findall(query)}
    values.update(int(value) * 60 for value in HOUR_WINDOW.findall(query))
    if len(values) > 1:
        raise ValueError("multiple relative time windows were provided")
    if not values:
        return None
    minutes = values.pop()
    if not 1 <= minutes <= min(maximum, 120):
        raise ValueError("relative time window must be between 1 and 120 minutes")
    return minutes


def parse_investigation_request(
    query: str,
    *,
    catalog: ServiceCatalog,
    incident_id: str | None = None,
    mode: RequestedDepth = RequestedDepth.STANDARD,
    now: datetime | None = None,
) -> InvestigationRequest:
    end = now or datetime.now(UTC)
    lowered = query.lower()
    mentioned = sorted(set(SERVICE_TOKEN.findall(lowered)))
    unknown = sorted(set(mentioned) - set(catalog.services))
    if unknown:
        raise ValueError(f"services are not allowlisted: {unknown}")

    assumptions: list[str] = []
    window_minutes = _window_minutes(query, catalog.max_query_window_minutes)
    if window_minutes is None:
        window_minutes = 30
        assumptions.append("No explicit time range was parsed; using the previous 30 minutes.")
    if mentioned:
        services = mentioned
    else:
        services = sorted(catalog.services)
        assumptions.append("No service was specified; using the configured service allowlist.")

    symptoms: list[Symptom] = []
    if any(term in lowered for term in ("error", "오류", "5xx", "실패")):
        symptoms.append(Symptom.ERROR_RATE)
    if any(term in lowered for term in ("timeout", "타임아웃", "시간 초과")):
        symptoms.append(Symptom.TIMEOUT)
    if any(term in lowered for term in ("latency", "slow", "지연", "느림")):
        symptoms.append(Symptom.LATENCY)
    if not symptoms:
        symptoms.append(Symptom.UNKNOWN)

    request = InvestigationRequest(
        incident_id=incident_id,
        user_query=query,
        services=services,
        environment=Environment.DEV,
        start_time=end - timedelta(minutes=window_minutes),
        end_time=end,
        symptoms=symptoms,
        requested_depth=mode,
        assumptions=assumptions,
        requested_actions=sorted({term for term in ACTION_TERMS if term in lowered}),
    )
    return validate_request_scope(request, catalog)
