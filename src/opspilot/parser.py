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
INCIDENT_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])INC-\d{4}-(?:\d{4}|[A-F0-9]{16})(?![A-Za-z0-9-])", re.I
)
ENVIRONMENT_TOKENS = {
    Environment.DEV: re.compile(r"(?i)(?<![A-Za-z0-9-])(?:dev|development)(?![A-Za-z0-9-])|개발"),
    Environment.STAGING: re.compile(r"(?i)(?<![A-Za-z0-9-])(?:stage|staging|qa)(?![A-Za-z0-9-])"),
    Environment.PROD_SIM: re.compile(
        r"(?i)(?<![A-Za-z0-9-])(?:prod|production|prod-sim)(?![A-Za-z0-9-])|운영"
    ),
}


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

    parsed_incidents = INCIDENT_TOKEN.findall(query)
    if len(parsed_incidents) > 1:
        raise ValueError("multiple incident IDs were provided")
    parsed_incident = parsed_incidents[0].upper() if parsed_incidents else None
    if incident_id is not None:
        incident_id = incident_id.upper()
    if parsed_incident is not None and incident_id is not None and parsed_incident != incident_id:
        raise ValueError("incident ID in the query conflicts with the request field")
    effective_incident = incident_id or parsed_incident

    mentioned_environments = {
        environment for environment, pattern in ENVIRONMENT_TOKENS.items() if pattern.search(query)
    }
    if len(mentioned_environments) > 1:
        raise ValueError("multiple environments were provided")
    if mentioned_environments and mentioned_environments != {Environment.DEV}:
        raise ValueError("environment is outside the current DEV-only scope")

    assumptions: list[str] = []
    if not mentioned_environments:
        assumptions.append("No environment was specified; using dev.")
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
        incident_id=effective_incident,
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
