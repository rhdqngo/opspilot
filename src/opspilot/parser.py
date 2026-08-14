"""Deterministic natural-language intake for catalog-bounded investigations."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from opspilot.catalog import ServiceCatalog, validate_request_scope
from opspilot.domain import (
    Environment,
    InvestigationRequest,
    OutputLanguage,
    RequestedDepth,
    Symptom,
)

KST = ZoneInfo("Asia/Seoul")
SERVICE_TOKEN = re.compile(r"(?<![a-z0-9-])[a-z][a-z0-9-]*-service(?![a-z0-9-])", re.I)
MINUTE_WINDOW = re.compile(
    r"(?:(?:last|past|previous|recent|최근|지난)\s*)?(\d{1,3})\s*(?:minutes?|mins?|min|분)\b",
    re.I,
)
HOUR_WINDOW = re.compile(
    r"(?:(?:last|past|previous|recent|최근|지난)\s*)?(\d{1,2})\s*(?:hours?|hrs?|hr|시간)\b",
    re.I,
)
ISO_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?",
    re.I,
)
CLOCK_RANGE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})\s*(?:-|~|부터)\s*(\d{1,2}):(\d{2})(?!\d)")
CLOCK_SINCE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})\s*(?:부터|since)\b", re.I)
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
    "확장",
)
INCIDENT_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])INC-\d{4}-(?:\d{4}|[A-F0-9]{16})(?![A-Za-z0-9-])", re.I
)
HYPOTHESIS_TOKEN = re.compile(r"(?<![A-Za-z0-9-])H-\d{2}(?![A-Za-z0-9-])", re.I)
ENVIRONMENT_TOKENS = {
    Environment.DEV: re.compile(r"(?i)(?<![A-Za-z0-9-])(?:dev|development)(?![A-Za-z0-9-])|개발"),
    Environment.STAGING: re.compile(
        r"(?i)(?<![A-Za-z0-9-])(?:stage|staging)(?![A-Za-z0-9-])|"
        r"(?<![A-Za-z0-9-])qa(?![A-Za-z0-9-@])|스테이징"
    ),
    Environment.PROD_SIM: re.compile(
        r"(?i)(?<![A-Za-z0-9-])(?:prod-sim|demo)(?![A-Za-z0-9-])|운영\s*모사|시뮬레이션"
    ),
}
REAL_PRODUCTION = re.compile(
    r"(?i)(?<![A-Za-z0-9-])(?:prod|production)(?![-A-Za-z0-9])|(?<!모사)운영(?!\s*모사)"
)
DEPTH_TOKENS = {
    RequestedDepth.QUICK: re.compile(r"(?i)\bquick\b|간단|빠르게"),
    RequestedDepth.DEEP: re.compile(r"(?i)\bdeep\b|심층|깊게"),
}


class RequestValidationError(ValueError):
    """A safe, classifiable intake failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _parse_iso(value: str, assumptions: list[str]) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
        assumptions.append("A timezone-free timestamp was interpreted as Asia/Seoul.")
    return parsed.astimezone(UTC)


def _time_range(
    query: str, *, now: datetime, maximum: int, assumptions: list[str]
) -> tuple[datetime, datetime]:
    minute_values = {int(value) for value in MINUTE_WINDOW.findall(query)}
    minute_values.update(int(value) * 60 for value in HOUR_WINDOW.findall(query))
    iso_values = ISO_TIMESTAMP.findall(query)
    clock_range = CLOCK_RANGE.search(query)
    clock_since = CLOCK_SINCE.search(query)
    explicit_kinds = sum(
        bool(value) for value in (minute_values, iso_values, clock_range, clock_since)
    )
    if len(minute_values) > 1 or explicit_kinds > 1:
        raise RequestValidationError("ambiguous_time", "multiple time windows were provided")
    if minute_values:
        minutes = minute_values.pop()
        if not 1 <= minutes <= min(maximum, 120):
            raise RequestValidationError(
                "unsupported_window", "relative time window must be between 1 and 120 minutes"
            )
        return now - timedelta(minutes=minutes), now
    if iso_values:
        if len(iso_values) > 2:
            raise RequestValidationError("ambiguous_time", "multiple time windows were provided")
        start = _parse_iso(iso_values[0], assumptions)
        end = _parse_iso(iso_values[1], assumptions) if len(iso_values) == 2 else now
        if end <= start or end - start > timedelta(minutes=min(maximum, 120)):
            raise RequestValidationError(
                "unsupported_window", "absolute time window must be between 1 and 120 minutes"
            )
        return start, end
    local_now = now.astimezone(KST)
    if clock_range:
        start = local_now.replace(
            hour=int(clock_range.group(1)),
            minute=int(clock_range.group(2)),
            second=0,
            microsecond=0,
        )
        end = local_now.replace(
            hour=int(clock_range.group(3)),
            minute=int(clock_range.group(4)),
            second=0,
            microsecond=0,
        )
        assumptions.append("Timezone-free clock times were interpreted as Asia/Seoul.")
        if end <= start or end - start > timedelta(minutes=min(maximum, 120)):
            raise RequestValidationError(
                "unsupported_window", "clock time window must be between 1 and 120 minutes"
            )
        return start.astimezone(UTC), end.astimezone(UTC)
    if clock_since:
        start = local_now.replace(
            hour=int(clock_since.group(1)),
            minute=int(clock_since.group(2)),
            second=0,
            microsecond=0,
        )
        assumptions.append("A timezone-free clock time was interpreted as Asia/Seoul.")
        if now - start.astimezone(UTC) <= timedelta(0) or now - start.astimezone(UTC) > timedelta(
            minutes=min(maximum, 120)
        ):
            raise RequestValidationError(
                "unsupported_window", "clock time window must be between 1 and 120 minutes"
            )
        return start.astimezone(UTC), now
    assumptions.append("No explicit time range was parsed; using the previous 30 minutes.")
    return now - timedelta(minutes=30), now


def _symptoms(lowered: str) -> list[Symptom]:
    rules = (
        (Symptom.ERROR_RATE, ("error", "오류", "5xx", "실패")),
        (Symptom.TIMEOUT, ("timeout", "타임아웃", "시간 초과")),
        (Symptom.LATENCY, ("latency", "slow", "지연", "느림")),
        (Symptom.AVAILABILITY, ("unavailable", "availability", "가용성", "접속 불가")),
        (Symptom.RESOURCE_EXHAUSTION, ("exhaust", "capacity", "pool", "포화", "자원")),
        (Symptom.DATA_INCONSISTENCY, ("inconsistent", "mismatch", "불일치", "정합성")),
    )
    found = [symptom for symptom, terms in rules if any(term in lowered for term in terms)]
    return found or [Symptom.UNKNOWN]


def parse_investigation_request(
    query: str,
    *,
    catalog: ServiceCatalog,
    incident_id: str | None = None,
    mode: RequestedDepth = RequestedDepth.STANDARD,
    output_language: OutputLanguage = OutputLanguage.EN,
    now: datetime | None = None,
    focus_hypothesis_id: str | None = None,
) -> InvestigationRequest:
    end = now or datetime.now(UTC)
    lowered = query.casefold()
    if REAL_PRODUCTION.search(query):
        raise RequestValidationError(
            "real_production_unsupported",
            "real production is not supported; use the explicit prod-sim environment",
        )

    explicit_tokens = sorted(set(token.casefold() for token in SERVICE_TOKEN.findall(query)))
    unknown = sorted(set(explicit_tokens) - set(catalog.services))
    if unknown:
        raise RequestValidationError(
            "unsupported_service", f"services are not allowlisted: {unknown}"
        )
    mentioned = sorted(set(explicit_tokens) | set(catalog.resolve_services(query)))

    parsed_incidents = INCIDENT_TOKEN.findall(query)
    if len(parsed_incidents) > 1:
        raise RequestValidationError("multiple_incident_ids", "multiple incident IDs were provided")
    parsed_incident = parsed_incidents[0].upper() if parsed_incidents else None
    supplied_incident = incident_id.upper() if incident_id is not None else None
    if (
        parsed_incident is not None
        and supplied_incident is not None
        and parsed_incident != supplied_incident
    ):
        raise RequestValidationError(
            "incident_conflict", "incident ID in the query conflicts with the request field"
        )
    parsed_hypotheses = {value.upper() for value in HYPOTHESIS_TOKEN.findall(query)}
    if len(parsed_hypotheses) > 1:
        raise RequestValidationError(
            "ambiguous_hypothesis", "multiple hypothesis IDs were provided"
        )
    parsed_focus = next(iter(parsed_hypotheses), None)
    if (
        focus_hypothesis_id is not None
        and parsed_focus is not None
        and focus_hypothesis_id.upper() != parsed_focus
    ):
        raise RequestValidationError(
            "hypothesis_conflict", "hypothesis ID conflicts with the request field"
        )

    environments = {
        environment for environment, pattern in ENVIRONMENT_TOKENS.items() if pattern.search(query)
    }
    if len(environments) > 1:
        raise RequestValidationError("ambiguous_environment", "multiple environments were provided")
    assumptions: list[str] = []
    environment = environments.pop() if environments else Environment.DEV
    if not environments and not any(
        pattern.search(query) for pattern in ENVIRONMENT_TOKENS.values()
    ):
        assumptions.append("No environment was specified; using dev.")

    start, finish = _time_range(
        query, now=end, maximum=catalog.max_query_window_minutes, assumptions=assumptions
    )
    services = mentioned or sorted(catalog.services)
    if not mentioned:
        assumptions.append("No service was specified; using the configured service allowlist.")

    depth_matches = {depth for depth, pattern in DEPTH_TOKENS.items() if pattern.search(query)}
    if len(depth_matches) > 1:
        raise RequestValidationError(
            "ambiguous_depth", "multiple investigation depths were provided"
        )
    parsed_mode = next(iter(depth_matches), mode)
    if mode is not RequestedDepth.STANDARD and depth_matches and parsed_mode is not mode:
        raise RequestValidationError(
            "depth_conflict", "investigation depth conflicts with the request field"
        )

    request = InvestigationRequest(
        incident_id=supplied_incident or parsed_incident,
        user_query=query,
        services=services,
        environment=environment,
        start_time=start,
        end_time=finish,
        symptoms=_symptoms(lowered),
        requested_depth=parsed_mode,
        output_language=output_language,
        assumptions=assumptions,
        requested_actions=sorted({term for term in ACTION_TERMS if term in lowered}),
        focus_hypothesis_id=(focus_hypothesis_id or parsed_focus),
    )
    return validate_request_scope(request, catalog)
