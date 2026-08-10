"""Conservative local request parsing for the R0 fixture workflow."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from opspilot.catalog import ServiceCatalog, validate_request_scope
from opspilot.domain import (
    Environment,
    InvestigationRequest,
    RequestedDepth,
    Symptom,
)

SERVICE_TOKEN = re.compile(r"\b[a-z][a-z0-9-]*-service\b")


def parse_investigation_request(
    query: str,
    *,
    catalog: ServiceCatalog,
    incident_id: str | None = None,
    mode: RequestedDepth = RequestedDepth.STANDARD,
    now: datetime | None = None,
) -> InvestigationRequest:
    end = now or datetime.now(UTC)
    mentioned = sorted(set(SERVICE_TOKEN.findall(query.lower())))
    unknown = sorted(set(mentioned) - set(catalog.services))
    if unknown:
        raise ValueError(f"services are not allowlisted: {unknown}")
    assumptions = ["No explicit time range was parsed; using the previous 30 minutes."]
    if mentioned:
        services = mentioned
    else:
        services = sorted(catalog.services)
        assumptions.append("No service was specified; using the configured service allowlist.")
    lowered = query.lower()
    symptoms: list[Symptom] = []
    if any(term in lowered for term in ("error", "오류", "5xx", "실패")):
        symptoms.append(Symptom.ERROR_RATE)
    if any(term in lowered for term in ("timeout", "타임아웃", "지연")):
        symptoms.append(Symptom.TIMEOUT)
    if not symptoms:
        symptoms.append(Symptom.UNKNOWN)
    request = InvestigationRequest(
        incident_id=incident_id,
        user_query=query,
        services=services,
        environment=Environment.DEV,
        start_time=end - timedelta(minutes=30),
        end_time=end,
        symptoms=symptoms,
        requested_depth=mode,
        assumptions=assumptions,
    )
    return validate_request_scope(request, catalog)
