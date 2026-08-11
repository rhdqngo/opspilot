"""Bounded fixture and live evidence collection for the M5 read-only tool layer."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from time import perf_counter
from typing import Any, Literal, Protocol, Self
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, model_validator

from opspilot.catalog import ServiceCatalog, load_service_catalog
from opspilot.domain import (
    EvidenceDirection,
    EvidenceItem,
    SourceType,
    ToolError,
    ToolErrorCategory,
    ToolMeta,
    ToolResult,
)
from opspilot.fixtures import load_scenario_fixture
from opspilot.knowledge import (
    KnowledgeHit,
    SearchKnowledgeInput,
    build_agent_search_request,
    normalize_search_response,
)
from opspilot.redaction import redact_text

MAX_ERROR_BODY_BYTES = 16 * 1024
MAX_LOG_BYTES = 30 * 1024
MAX_LOG_ENTRIES = 100
MAX_METRIC_POINTS = 600
MAX_TOOL_CALLS = 8
MAX_API_CALLS = 10
COLLECTION_DEADLINE_SECONDS = 45.0
TOOL_TIMEOUT_SECONDS = 10.0
LIVE_METRIC_TYPES = {
    "request_count": "run.googleapis.com/request_count",
    "error_ratio": "run.googleapis.com/request_count",
    "latency_p95": "run.googleapis.com/request_latencies",
    "instance_count": "run.googleapis.com/container/instance_count",
}
FIXTURE_ONLY_METRICS = frozenset({"db_pool_waiters"})
QUERY_TERM_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SCENARIO_RUN_PATTERN = re.compile(r"^RUN-SCN-001-[A-Z0-9]{12}$")
CONTROL_OR_ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
DIGEST_PATTERN = re.compile(r"@(?P<digest>sha256:[0-9a-f]{64})$")


class EvidenceBackend(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"


class MetricReducer(StrEnum):
    MEAN = "mean"
    SUM = "sum"
    MAX = "max"
    P95 = "p95"
    RATIO = "ratio"


class QueryLogsInput(BaseModel):
    service: str
    environment: Literal["dev"] = "dev"
    start_time: datetime
    end_time: datetime
    severity_at_least: Literal["DEFAULT", "INFO", "WARNING", "ERROR", "CRITICAL"] = "ERROR"
    trace_id: str | None = None
    scenario_run_id: str | None = None
    query_terms: list[str] = Field(default_factory=list, max_length=5)
    max_entries: int = Field(default=100, ge=1, le=100)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        _validate_time_window(self.start_time, self.end_time)
        if self.trace_id is not None and not TRACE_ID_PATTERN.fullmatch(self.trace_id):
            raise ValueError("trace_id must be a lowercase 32-character hex value")
        if self.scenario_run_id is not None and not SCENARIO_RUN_PATTERN.fullmatch(
            self.scenario_run_id
        ):
            raise ValueError("scenario_run_id is invalid")
        if any(not QUERY_TERM_PATTERN.fullmatch(term) for term in self.query_terms):
            raise ValueError("query terms must be safe literal tokens")
        if len(self.query_terms) != len(set(self.query_terms)):
            raise ValueError("query terms must be unique")
        return self


class LogSample(BaseModel):
    timestamp: datetime
    severity: str
    service: str
    revision: str | None = None
    trace_present: bool = False
    message_redacted: str
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    labels: dict[str, str] = Field(default_factory=dict)


class LogSignature(BaseModel):
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_message: str
    count: int = Field(ge=1)
    first_seen: datetime
    last_seen: datetime
    representative_samples: list[LogSample] = Field(default_factory=list, max_length=3)


class QueryLogsData(BaseModel):
    signatures: list[LogSignature] = Field(default_factory=list)
    total_matching_entries: int | None = Field(default=None, ge=0)


class QueryMetricSeriesInput(BaseModel):
    service: str
    metric_key: str
    start_time: datetime
    end_time: datetime
    alignment_period_seconds: int = Field(default=60, ge=60, le=900)
    reducer: MetricReducer

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        _validate_time_window(self.start_time, self.end_time)
        return self


class MetricPoint(BaseModel):
    timestamp: datetime
    value: float


class MetricSeries(BaseModel):
    metric_key: str
    unit: str
    alignment_period_seconds: int
    points: list[MetricPoint] = Field(default_factory=list, max_length=MAX_METRIC_POINTS)
    sample_count: int = Field(ge=0)
    missing_ratio: float = Field(ge=0.0, le=1.0)
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None
    p95_value: float | None = None


class ListRevisionsInput(BaseModel):
    service: str
    start_time: datetime
    end_time: datetime
    max_revisions: int = Field(default=20, ge=1, le=20)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        _validate_time_window(self.start_time, self.end_time)
        return self


class RevisionSummary(BaseModel):
    revision_name: str = Field(pattern=r"^revision-[0-9a-f]{12}$")
    created_at: datetime
    image_digest: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    traffic_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    env_keys_changed: list[str] = Field(default_factory=list)
    within_window: bool = False


class CollectionBudgetUsage(BaseModel):
    logical_tool_calls: int = Field(ge=0, le=MAX_TOOL_CALLS)
    api_calls: int = Field(ge=0, le=MAX_API_CALLS)
    result_count: int = Field(ge=0)
    response_bytes: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    truncated_sources: list[str] = Field(default_factory=list)


class EvidenceCollectionResult(BaseModel):
    backend: EvidenceBackend
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    complete: bool
    source_status: dict[str, bool] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_errors: list[ToolError] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    budget: CollectionBudgetUsage

    @property
    def succeeded(self) -> bool:
        return bool(self.evidence)


class EvidenceCollectionRequest(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    environment: Literal["dev"] = "dev"
    start_time: datetime
    end_time: datetime
    services: list[str] = Field(default_factory=lambda: ["payment-service"], min_length=1)
    scenario_run_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        _validate_time_window(self.start_time, self.end_time)
        if self.scenario_run_id is not None and not SCENARIO_RUN_PATTERN.fullmatch(
            self.scenario_run_id
        ):
            raise ValueError("scenario_run_id is invalid")
        if len(self.services) != len(set(self.services)):
            raise ValueError("services must be unique")
        return self


class EvidenceClient(Protocol):
    backend: EvidenceBackend

    async def collect_source(
        self, source: SourceType, request: EvidenceCollectionRequest
    ) -> ToolResult[list[EvidenceItem]]: ...


class TokenProvider(Protocol):
    async def get_token(self) -> str: ...


class JsonTransport(Protocol):
    async def request(
        self,
        method: Literal["GET", "POST"],
        url: str,
        *,
        token: str,
        quota_project: str,
        body: Mapping[str, Any] | None = None,
        timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
    ) -> tuple[dict[str, Any], int]: ...


class LiveEvidenceFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        category: ToolErrorCategory,
        *,
        retryable: bool,
        safe_message: str,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.category = category
        self.retryable = retryable
        self.safe_message = safe_message


def _validate_time_window(start_time: datetime, end_time: datetime) -> None:
    if start_time.tzinfo is None or end_time.tzinfo is None:
        raise ValueError("evidence time range must be timezone-aware")
    if start_time.utcoffset() != timedelta(0) or end_time.utcoffset() != timedelta(0):
        raise ValueError("evidence time range must use UTC")
    if end_time <= start_time:
        raise ValueError("evidence end_time must be after start_time")
    if end_time - start_time > timedelta(hours=2):
        raise ValueError("evidence time range cannot exceed 2 hours")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _safe_text(value: object, *, max_lines: int = 20) -> str:
    sanitized = CONTROL_OR_ANSI_PATTERN.sub("", str(value))
    bounded = "\n".join(sanitized.splitlines()[:max_lines])
    return redact_text(bounded)


def _fingerprint(value: str) -> str:
    normalized = re.sub(r"\b\d+\b", "#", value.casefold())
    return hashlib.sha256(normalized.encode()).hexdigest()


def _logical_record_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:12]}"


def _validate_service_metric(
    catalog: ServiceCatalog, service: str, metric_key: str | None = None
) -> None:
    definition = catalog.services.get(service)
    if definition is None:
        raise ValueError("service is not allowlisted")
    if metric_key is not None and metric_key not in definition.metrics:
        raise ValueError("metric key is not allowlisted for the service")


def build_logging_filter(request: QueryLogsInput, catalog: ServiceCatalog) -> str:
    _validate_service_metric(catalog, request.service)
    clauses = [
        'resource.type="cloud_run_revision"',
        f'resource.labels.service_name="opspilot-dev-{request.service.removesuffix("-service")}"',
        f'timestamp>="{_iso(request.start_time)}"',
        f'timestamp<="{_iso(request.end_time)}"',
        f"severity>={request.severity_at_least}",
    ]
    if request.trace_id is not None:
        clauses.append(f'trace:"/traces/{request.trace_id}"')
    if request.scenario_run_id is not None:
        clauses.append(f'jsonPayload.scenario_run_id="{request.scenario_run_id}"')
    clauses.extend(f'jsonPayload.message:"{term}"' for term in request.query_terms)
    return " AND ".join(clauses)


def build_monitoring_filter(request: QueryMetricSeriesInput, catalog: ServiceCatalog) -> str:
    _validate_service_metric(catalog, request.service, request.metric_key)
    metric_type = LIVE_METRIC_TYPES.get(request.metric_key)
    if metric_type is None:
        if request.metric_key in FIXTURE_ONLY_METRICS:
            raise ValueError("metric is fixture-only")
        raise ValueError("metric key has no live mapping")
    service_name = f"opspilot-dev-{request.service.removesuffix('-service')}"
    return (
        f'metric.type="{metric_type}" AND '
        'resource.type="cloud_run_revision" AND '
        f'resource.labels.service_name="{service_name}"'
    )


def _tool_meta(
    name: str,
    started_at: datetime,
    started_clock: float,
    *,
    location: str | None = None,
    api_calls: int = 0,
    result_count: int = 0,
    response_bytes: int = 0,
    truncated: bool = False,
    warnings: Sequence[str] = (),
) -> ToolMeta:
    return ToolMeta(
        tool_name=name,
        request_id=f"TOOL-{name.upper().replace('_', '-')}",
        started_at=started_at,
        finished_at=datetime.now(UTC),
        duration_ms=max(0, round((perf_counter() - started_clock) * 1_000)),
        source_project="current-default",
        source_location=location,
        truncated=truncated,
        api_call_count=api_calls,
        result_count=result_count,
        response_bytes=response_bytes,
        warnings=list(warnings),
    )


def _tool_failure(
    name: str,
    started_at: datetime,
    started_clock: float,
    failure: LiveEvidenceFailure,
    *,
    location: str | None = None,
    api_calls: int = 0,
) -> ToolResult[Any]:
    return ToolResult[Any](
        ok=False,
        error=ToolError(
            code=failure.code,
            category=failure.category,
            retryable=failure.retryable,
            safe_message=failure.safe_message,
        ),
        meta=_tool_meta(
            name,
            started_at,
            started_clock,
            location=location,
            api_calls=api_calls,
        ),
    )


class UrllibJsonTransport:
    async def request(
        self,
        method: Literal["GET", "POST"],
        url: str,
        *,
        token: str,
        quota_project: str,
        body: Mapping[str, Any] | None = None,
        timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
    ) -> tuple[dict[str, Any], int]:
        return await asyncio.to_thread(
            self._request_sync,
            method,
            url,
            token,
            quota_project,
            body,
            timeout_seconds,
        )

    @staticmethod
    def _request_sync(
        method: Literal["GET", "POST"],
        url: str,
        token: str,
        quota_project: str,
        body: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], int]:
        encoded = json.dumps(body).encode() if body is not None else None
        request = Request(
            url,
            data=encoded,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": quota_project,
            },
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            exc.read(MAX_ERROR_BODY_BYTES + 1)[:MAX_ERROR_BODY_BYTES]
            raise _http_failure(exc.code) from None
        except (URLError, TimeoutError):
            raise LiveEvidenceFailure(
                "EVIDENCE_TRANSPORT_ERROR",
                ToolErrorCategory.TIMEOUT,
                retryable=True,
                safe_message="The evidence API request did not complete.",
            ) from None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            raise LiveEvidenceFailure(
                "EVIDENCE_INVALID_RESPONSE",
                ToolErrorCategory.UPSTREAM,
                retryable=False,
                safe_message="The evidence API returned an invalid response.",
            ) from None
        if not isinstance(payload, dict):
            raise LiveEvidenceFailure(
                "EVIDENCE_INVALID_RESPONSE",
                ToolErrorCategory.UPSTREAM,
                retryable=False,
                safe_message="The evidence API returned an invalid response.",
            )
        return payload, len(raw)


def _http_failure(status: int) -> LiveEvidenceFailure:
    if status == 401:
        return LiveEvidenceFailure(
            "EVIDENCE_UNAUTHORIZED",
            ToolErrorCategory.AUTH,
            retryable=False,
            safe_message="Evidence credentials are invalid or expired.",
        )
    if status == 403:
        return LiveEvidenceFailure(
            "EVIDENCE_FORBIDDEN",
            ToolErrorCategory.AUTH,
            retryable=False,
            safe_message="The investigator lacks a required read permission.",
        )
    if status == 404:
        return LiveEvidenceFailure(
            "EVIDENCE_NOT_FOUND",
            ToolErrorCategory.NOT_FOUND,
            retryable=False,
            safe_message="The requested evidence source was not found.",
        )
    if status == 429:
        return LiveEvidenceFailure(
            "EVIDENCE_RATE_LIMITED",
            ToolErrorCategory.QUOTA,
            retryable=True,
            safe_message="The evidence API rate limit was reached.",
        )
    return LiveEvidenceFailure(
        "EVIDENCE_UPSTREAM_ERROR",
        ToolErrorCategory.UPSTREAM,
        retryable=status >= 500,
        safe_message="The evidence API returned an upstream error.",
    )


class GcloudImpersonationTokenProvider:
    def __init__(self, project_id: str, environment: str) -> None:
        self._project_id = project_id
        self._environment = environment

    async def get_token(self) -> str:
        executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
        service_account = (
            f"opspilot-{self._environment}-agent@{self._project_id}.iam.gserviceaccount.com"
        )
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [
                    executable,
                    "auth",
                    "print-access-token",
                    f"--impersonate-service-account={service_account}",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is None or completed.returncode != 0 or not completed.stdout.strip():
            raise LiveEvidenceFailure(
                "EVIDENCE_IMPERSONATION_FAILED",
                ToolErrorCategory.AUTH,
                retryable=False,
                safe_message="The investigator identity could not be impersonated.",
            )
        return completed.stdout.strip()


class FixtureEvidenceClient:
    backend = EvidenceBackend.FIXTURE

    def __init__(
        self,
        scenario_id: str,
        *,
        fail_sources: frozenset[SourceType] = frozenset(),
    ) -> None:
        self._fixture = load_scenario_fixture(scenario_id)
        self._fail_sources = fail_sources

    async def collect_source(
        self, source: SourceType, request: EvidenceCollectionRequest
    ) -> ToolResult[list[EvidenceItem]]:
        del request
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        await asyncio.sleep(0)
        if source in self._fail_sources:
            failure = LiveEvidenceFailure(
                f"FIXTURE_{source.value}_UNAVAILABLE",
                ToolErrorCategory.UPSTREAM,
                retryable=True,
                safe_message=f"{source.value.lower()} evidence is temporarily unavailable",
            )
            return _tool_failure(
                f"fixture_{source.value.lower()}", started_at, started_clock, failure
            )
        items = [
            item.model_copy(update={"summary": redact_text(item.summary)})
            for item in self._fixture.evidence
            if item.source_type == source
        ]
        return ToolResult[list[EvidenceItem]](
            ok=True,
            data=items,
            meta=_tool_meta(
                f"fixture_{source.value.lower()}",
                started_at,
                started_clock,
                result_count=len(items),
            ),
        )


class LiveEvidenceClient:
    backend = EvidenceBackend.LIVE

    def __init__(
        self,
        project_id: str,
        *,
        catalog: ServiceCatalog,
        token_provider: TokenProvider,
        transport: JsonTransport,
        region: str = "asia-northeast3",
    ) -> None:
        self._project_id = project_id
        self._catalog = catalog
        self._token_provider = token_provider
        self._transport = transport
        self._region = region

    async def collect_source(
        self, source: SourceType, request: EvidenceCollectionRequest
    ) -> ToolResult[list[EvidenceItem]]:
        service = request.services[0]
        if source == SourceType.LOG:
            log_result = await self.query_logs(
                QueryLogsInput(
                    service=service,
                    start_time=request.start_time,
                    end_time=request.end_time,
                    scenario_run_id=request.scenario_run_id,
                )
            )
            return _normalize_log_result(log_result, request.environment)
        if source == SourceType.METRIC:
            metric_requests = [
                QueryMetricSeriesInput(
                    service=service,
                    metric_key="error_ratio",
                    start_time=request.start_time,
                    end_time=request.end_time,
                    reducer=MetricReducer.RATIO,
                ),
                QueryMetricSeriesInput(
                    service=service,
                    metric_key="latency_p95",
                    start_time=request.start_time,
                    end_time=request.end_time,
                    reducer=MetricReducer.P95,
                ),
            ]
            metric_results = await asyncio.gather(
                *(self.query_metric_series(item) for item in metric_requests)
            )
            return _normalize_metric_results(metric_results, service, request.environment)
        if source == SourceType.CHANGE:
            revision_result = await self.list_revisions(
                ListRevisionsInput(
                    service=service,
                    start_time=request.start_time,
                    end_time=request.end_time,
                )
            )
            return _normalize_revision_result(revision_result, service, request.environment)
        if source == SourceType.KNOWLEDGE:
            knowledge_result = await self.search_knowledge(
                SearchKnowledgeInput(
                    query="payment database pool acquisition timeout",
                    service=service,
                    document_types=["runbook", "prior_rca"],
                    top_k=6,
                )
            )
            return _normalize_knowledge_result(knowledge_result, request.environment)
        raise ValueError("source is not available in the M5 evidence layer")

    async def query_logs(self, request: QueryLogsInput) -> ToolResult[QueryLogsData]:
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        api_calls = 0
        try:
            filter_text = build_logging_filter(request, self._catalog)
            token = await self._token_provider.get_token()
            payload, response_bytes = await self._transport.request(
                "POST",
                "https://logging.googleapis.com/v2/entries:list",
                token=token,
                quota_project=self._project_id,
                body={
                    "resourceNames": [f"projects/{self._project_id}"],
                    "filter": filter_text,
                    "orderBy": "timestamp desc",
                    "pageSize": request.max_entries,
                },
            )
            api_calls = 1
            data = normalize_log_response(payload, request)
            truncated = (
                "nextPageToken" in payload or len(payload.get("entries", [])) > MAX_LOG_ENTRIES
            )
            return ToolResult[QueryLogsData](
                ok=True,
                data=data,
                meta=_tool_meta(
                    "query_logs",
                    started_at,
                    started_clock,
                    location=self._region,
                    api_calls=1,
                    result_count=len(data.signatures),
                    response_bytes=response_bytes,
                    truncated=truncated,
                ),
            )
        except LiveEvidenceFailure as failure:
            return _tool_failure(
                "query_logs",
                started_at,
                started_clock,
                failure,
                location=self._region,
                api_calls=api_calls,
            )

    async def query_metric_series(
        self, request: QueryMetricSeriesInput
    ) -> ToolResult[MetricSeries]:
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        api_calls = 0
        try:
            filter_text = build_monitoring_filter(request, self._catalog)
            token = await self._token_provider.get_token()
            params = urlencode(
                {
                    "filter": filter_text,
                    "interval.startTime": _iso(request.start_time),
                    "interval.endTime": _iso(request.end_time),
                    "aggregation.alignmentPeriod": f"{request.alignment_period_seconds}s",
                    "aggregation.perSeriesAligner": _aligner(request),
                    "view": "FULL",
                    "pageSize": MAX_METRIC_POINTS,
                }
            )
            if request.reducer == MetricReducer.P95:
                params += "&" + urlencode({"aggregation.crossSeriesReducer": "REDUCE_MAX"})
            payload, response_bytes = await self._transport.request(
                "GET",
                "https://monitoring.googleapis.com/v3/projects/"
                f"{quote(self._project_id, safe='')}/timeSeries?{params}",
                token=token,
                quota_project=self._project_id,
            )
            api_calls = 1
            data = normalize_metric_response(payload, request)
            return ToolResult[MetricSeries](
                ok=True,
                data=data,
                meta=_tool_meta(
                    "query_metric_series",
                    started_at,
                    started_clock,
                    location=self._region,
                    api_calls=1,
                    result_count=data.sample_count,
                    response_bytes=response_bytes,
                    truncated="nextPageToken" in payload,
                ),
            )
        except ValueError as exc:
            failure = LiveEvidenceFailure(
                "METRIC_UNAVAILABLE",
                ToolErrorCategory.PARTIAL,
                retryable=False,
                safe_message=str(exc),
            )
            return _tool_failure(
                "query_metric_series", started_at, started_clock, failure, location=self._region
            )
        except LiveEvidenceFailure as failure:
            return _tool_failure(
                "query_metric_series",
                started_at,
                started_clock,
                failure,
                location=self._region,
                api_calls=api_calls,
            )

    async def list_revisions(
        self, request: ListRevisionsInput
    ) -> ToolResult[list[RevisionSummary]]:
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        api_calls = 0
        try:
            _validate_service_metric(self._catalog, request.service)
            token = await self._token_provider.get_token()
            service_id = f"opspilot-dev-{request.service.removesuffix('-service')}"
            parent = (
                f"projects/{quote(self._project_id, safe='')}/locations/"
                f"{quote(self._region, safe='')}"
            )
            service_payload, service_bytes = await self._transport.request(
                "GET",
                f"https://run.googleapis.com/v2/{parent}/services/{quote(service_id, safe='')}",
                token=token,
                quota_project=self._project_id,
            )
            api_calls = 1
            params = urlencode({"pageSize": request.max_revisions})
            revision_payload, revision_bytes = await self._transport.request(
                "GET",
                "https://run.googleapis.com/v2/"
                f"{parent}/services/{quote(service_id, safe='')}/revisions?{params}",
                token=token,
                quota_project=self._project_id,
            )
            api_calls = 2
            revisions = normalize_revision_response(service_payload, revision_payload, request)
            return ToolResult[list[RevisionSummary]](
                ok=True,
                data=revisions,
                meta=_tool_meta(
                    "list_cloud_run_revisions",
                    started_at,
                    started_clock,
                    location=self._region,
                    api_calls=2,
                    result_count=len(revisions),
                    response_bytes=service_bytes + revision_bytes,
                    truncated="nextPageToken" in revision_payload,
                ),
            )
        except LiveEvidenceFailure as failure:
            return _tool_failure(
                "list_cloud_run_revisions",
                started_at,
                started_clock,
                failure,
                location=self._region,
                api_calls=api_calls,
            )

    async def search_knowledge(
        self, request: SearchKnowledgeInput
    ) -> ToolResult[list[KnowledgeHit]]:
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        api_calls = 0
        try:
            token = await self._token_provider.get_token()
            serving_config = (
                f"projects/{quote(self._project_id, safe='')}/locations/global/collections/"
                "default_collection/engines/opspilot-dev-knowledge/servingConfigs/default_search"
            )
            payload, response_bytes = await self._transport.request(
                "POST",
                f"https://discoveryengine.googleapis.com/v1/{serving_config}:search",
                token=token,
                quota_project=self._project_id,
                body=build_agent_search_request(request),
            )
            api_calls = 1
            hits = normalize_search_response(payload, request)
            return ToolResult[list[KnowledgeHit]](
                ok=True,
                data=hits,
                meta=_tool_meta(
                    "search_knowledge",
                    started_at,
                    started_clock,
                    location="global",
                    api_calls=1,
                    result_count=len(hits),
                    response_bytes=response_bytes,
                ),
            )
        except LiveEvidenceFailure as failure:
            return _tool_failure(
                "search_knowledge",
                started_at,
                started_clock,
                failure,
                location="global",
                api_calls=api_calls,
            )


def normalize_log_response(payload: Mapping[str, Any], request: QueryLogsInput) -> QueryLogsData:
    raw_entries = payload.get("entries")
    entries = raw_entries if isinstance(raw_entries, list) else []
    grouped: dict[str, list[LogSample]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    used_bytes = 0
    for raw_entry in entries[:MAX_LOG_ENTRIES]:
        if not isinstance(raw_entry, dict):
            continue
        timestamp = _parse_time(raw_entry.get("timestamp"))
        if timestamp is None:
            continue
        json_payload = raw_entry.get("jsonPayload")
        structured = json_payload if isinstance(json_payload, dict) else {}
        raw_message = structured.get("message", raw_entry.get("textPayload", ""))
        message = _safe_text(raw_message)
        remaining = MAX_LOG_BYTES - used_bytes
        if remaining <= 0:
            break
        encoded = message.encode("utf-8")[:remaining]
        while encoded:
            try:
                message = encoded.decode("utf-8")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        used_bytes += len(message.encode("utf-8"))
        fingerprint = _fingerprint(message)
        resource = raw_entry.get("resource")
        resource_map = resource if isinstance(resource, dict) else {}
        raw_resource_labels = resource_map.get("labels")
        resource_labels = raw_resource_labels if isinstance(raw_resource_labels, dict) else {}
        labels = {
            key: _safe_text(structured[key], max_lines=1)[:128]
            for key in ("event_type", "error_code", "scenario_id")
            if isinstance(structured.get(key), (str, int))
        }
        revision_value = resource_labels.get("revision_name")
        revision = (
            _logical_record_id("revision", str(revision_value))
            if isinstance(revision_value, str) and revision_value
            else None
        )
        sample = LogSample(
            timestamp=timestamp,
            severity=str(raw_entry.get("severity", "DEFAULT")),
            service=request.service,
            revision=revision,
            trace_present=bool(raw_entry.get("trace")),
            message_redacted=message,
            fingerprint=fingerprint,
            labels=labels,
        )
        counts[fingerprint] += 1
        if len(grouped[fingerprint]) < 3:
            grouped[fingerprint].append(sample)
    signatures = []
    for fingerprint, samples in grouped.items():
        ordered = sorted(samples, key=lambda item: item.timestamp)
        signatures.append(
            LogSignature(
                fingerprint=fingerprint,
                normalized_message=ordered[0].message_redacted,
                count=counts[fingerprint],
                first_seen=ordered[0].timestamp,
                last_seen=ordered[-1].timestamp,
                representative_samples=ordered,
            )
        )
    signatures.sort(key=lambda item: item.last_seen, reverse=True)
    return QueryLogsData(signatures=signatures, total_matching_entries=len(entries))


def _aligner(request: QueryMetricSeriesInput) -> str:
    return {
        MetricReducer.MEAN: "ALIGN_MEAN",
        MetricReducer.SUM: "ALIGN_SUM",
        MetricReducer.MAX: "ALIGN_MAX",
        MetricReducer.P95: "ALIGN_PERCENTILE_95",
        MetricReducer.RATIO: "ALIGN_SUM",
    }[request.reducer]


def _point_value(point: Mapping[str, Any]) -> float | None:
    raw_value = point.get("value")
    value = raw_value if isinstance(raw_value, dict) else {}
    for key in ("doubleValue", "int64Value"):
        raw = value.get(key)
        if isinstance(raw, (int, float, str)):
            try:
                return float(raw)
            except ValueError:
                return None
    return None


def normalize_metric_response(
    payload: Mapping[str, Any], request: QueryMetricSeriesInput
) -> MetricSeries:
    raw_series = payload.get("timeSeries")
    series = raw_series if isinstance(raw_series, list) else []
    values_by_time: dict[datetime, list[tuple[float, bool]]] = defaultdict(list)
    for raw_item in series:
        if not isinstance(raw_item, dict):
            continue
        metric = raw_item.get("metric")
        metric_map = metric if isinstance(metric, dict) else {}
        raw_labels = metric_map.get("labels")
        labels = raw_labels if isinstance(raw_labels, dict) else {}
        is_error = labels.get("response_code_class") == "5xx"
        raw_points = raw_item.get("points")
        points = raw_points if isinstance(raw_points, list) else []
        for raw_point in points:
            if not isinstance(raw_point, dict):
                continue
            interval = raw_point.get("interval")
            interval_map = interval if isinstance(interval, dict) else {}
            timestamp = _parse_time(interval_map.get("endTime"))
            value = _point_value(raw_point)
            if timestamp is not None and value is not None:
                values_by_time[timestamp].append((value, is_error))
    output_points: list[MetricPoint] = []
    for timestamp, values in sorted(values_by_time.items()):
        if request.metric_key == "error_ratio":
            total = sum(value for value, _ in values)
            errors = sum(value for value, is_error in values if is_error)
            output = errors / total * 100.0 if total > 0 else 0.0
        elif request.reducer == MetricReducer.MAX:
            output = max(value for value, _ in values)
        elif request.reducer == MetricReducer.MEAN:
            output = sum(value for value, _ in values) / len(values)
        else:
            output = sum(value for value, _ in values)
        output_points.append(MetricPoint(timestamp=timestamp, value=output))
        if len(output_points) >= MAX_METRIC_POINTS:
            break
    scalars = [point.value for point in output_points]
    ordered = sorted(scalars)
    p95 = ordered[max(0, int((len(ordered) - 1) * 0.95))] if ordered else None
    unit = (
        "percent"
        if request.metric_key == "error_ratio"
        else "ms"
        if request.metric_key == "latency_p95"
        else "count"
    )
    return MetricSeries(
        metric_key=request.metric_key,
        unit=unit,
        alignment_period_seconds=request.alignment_period_seconds,
        points=output_points,
        sample_count=len(output_points),
        missing_ratio=0.0 if output_points else 1.0,
        min_value=min(scalars) if scalars else None,
        max_value=max(scalars) if scalars else None,
        mean_value=sum(scalars) / len(scalars) if scalars else None,
        p95_value=p95,
    )


def normalize_revision_response(
    service_payload: Mapping[str, Any],
    revision_payload: Mapping[str, Any],
    request: ListRevisionsInput,
) -> list[RevisionSummary]:
    traffic_by_revision: dict[str, float] = {}
    raw_traffic = service_payload.get("trafficStatuses", service_payload.get("traffic", []))
    traffic = raw_traffic if isinstance(raw_traffic, list) else []
    for item in traffic:
        if isinstance(item, dict) and isinstance(item.get("revision"), str):
            percent = item.get("percent")
            if isinstance(percent, (int, float)):
                traffic_by_revision[str(item["revision"])] = float(percent)
    raw_revisions = revision_payload.get("revisions")
    revisions = raw_revisions if isinstance(raw_revisions, list) else []
    records: list[tuple[dict[str, Any], dict[str, str], str, datetime]] = []
    for raw_revision in revisions[: request.max_revisions]:
        if not isinstance(raw_revision, dict):
            continue
        created_at = _parse_time(raw_revision.get("createTime"))
        raw_name = raw_revision.get("name")
        if created_at is None or not isinstance(raw_name, str):
            continue
        raw_containers = raw_revision.get("containers")
        containers = raw_containers if isinstance(raw_containers, list) else []
        first = containers[0] if containers and isinstance(containers[0], dict) else {}
        image = first.get("image")
        digest_match = DIGEST_PATTERN.search(str(image)) if image else None
        raw_env = first.get("env")
        env = raw_env if isinstance(raw_env, list) else []
        env_pairs = sorted(
            (str(item.get("name", "")), str(item.get("value", "")))
            for item in env
            if isinstance(item, dict) and item.get("name")
        )
        config_material = json.dumps(
            {"image": str(image), "env": env_pairs}, sort_keys=True, separators=(",", ":")
        )
        name_hash = hashlib.sha256(raw_name.encode()).hexdigest()
        records.append(
            (
                {
                    "revision_name": f"revision-{name_hash[:12]}",
                    "created_at": created_at,
                    "image_digest": digest_match.group("digest") if digest_match else None,
                    "traffic_percent": traffic_by_revision.get(raw_name),
                    "config_hash": hashlib.sha256(config_material.encode()).hexdigest(),
                    "within_window": request.start_time <= created_at <= request.end_time,
                },
                dict(env_pairs),
                raw_name,
                created_at,
            )
        )
    records.sort(key=lambda item: item[3], reverse=True)
    summaries: list[RevisionSummary] = []
    for index, (values, current_env, _raw_name, _created_at) in enumerate(records):
        previous_env = records[index + 1][1] if index + 1 < len(records) else current_env
        changed_keys = sorted(
            key
            for key in set(current_env) | set(previous_env)
            if current_env.get(key) != previous_env.get(key)
        )
        summaries.append(RevisionSummary(**values, env_keys_changed=changed_keys))
    return summaries


def _normalize_log_result(
    result: ToolResult[QueryLogsData], environment: str
) -> ToolResult[list[EvidenceItem]]:
    if not result.ok or result.data is None:
        return ToolResult[list[EvidenceItem]](ok=False, error=result.error, meta=result.meta)
    evidence = [
        EvidenceItem(
            evidence_id=f"EV-LOG-{index:04d}",
            source_type=SourceType.LOG,
            title="Cloud Run log signature",
            service=sample.service,
            environment=environment,
            observed_at=signature.last_seen,
            summary=signature.normalized_message,
            value=signature.count,
            unit="occurrences",
            direction=EvidenceDirection.UNKNOWN,
            source_uri=f"opspilot://evidence/log/{index:04d}",
            source_record_id=f"log-{signature.fingerprint[:12]}",
            raw_excerpt_hash=f"sha256:{signature.fingerprint}",
            quality_flags=["live_read_only", "redacted"],
        )
        for index, signature in enumerate(result.data.signatures, start=1)
        for sample in signature.representative_samples[:1]
    ]
    return ToolResult[list[EvidenceItem]](ok=True, data=evidence, meta=result.meta)


def _normalize_metric_results(
    results: Sequence[ToolResult[MetricSeries]], service: str, environment: str
) -> ToolResult[list[EvidenceItem]]:
    successful = [result for result in results if result.ok and result.data is not None]
    api_calls = sum(result.meta.api_call_count for result in results)
    response_bytes = sum(result.meta.response_bytes for result in results)
    started_at = min(result.meta.started_at for result in results)
    finished_at = max(result.meta.finished_at for result in results)
    evidence: list[EvidenceItem] = []
    for index, result in enumerate(successful, start=1):
        series = result.data
        if series is None:
            continue
        evidence.append(
            EvidenceItem(
                evidence_id=f"EV-MET-{index:04d}",
                source_type=SourceType.METRIC,
                title=f"Cloud Run {series.metric_key}",
                service=service,
                environment=environment,
                period_start=series.points[0].timestamp if series.points else None,
                period_end=series.points[-1].timestamp if series.points else None,
                summary=(f"Observed {series.sample_count} bounded points for {series.metric_key}."),
                value=series.p95_value if series.metric_key == "latency_p95" else series.max_value,
                unit=series.unit,
                direction=EvidenceDirection.UNKNOWN,
                source_uri=f"opspilot://evidence/metric/{index:04d}",
                source_record_id=f"metric-{series.metric_key}",
                quality_flags=["live_read_only"] if series.points else ["missing_points"],
            )
        )
    meta = ToolMeta(
        tool_name="query_metric_series",
        request_id="TOOL-QUERY-METRIC-SERIES",
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=max(0, round((finished_at - started_at).total_seconds() * 1_000)),
        source_project="current-default",
        source_location=results[0].meta.source_location,
        truncated=any(result.meta.truncated for result in results),
        api_call_count=api_calls,
        result_count=len(evidence),
        response_bytes=response_bytes,
    )
    if not successful:
        first_error = next((result.error for result in results if result.error is not None), None)
        return ToolResult[list[EvidenceItem]](ok=False, error=first_error, meta=meta)
    if len(successful) != len(results):
        meta.warnings.append("One metric series was unavailable.")
    return ToolResult[list[EvidenceItem]](ok=True, data=evidence, meta=meta)


def _normalize_revision_result(
    result: ToolResult[list[RevisionSummary]], service: str, environment: str
) -> ToolResult[list[EvidenceItem]]:
    if not result.ok or result.data is None:
        return ToolResult[list[EvidenceItem]](ok=False, error=result.error, meta=result.meta)
    evidence = [
        EvidenceItem(
            evidence_id=f"EV-CHG-{index:04d}",
            source_type=SourceType.CHANGE,
            title="Cloud Run revision observed",
            service=service,
            environment=environment,
            observed_at=revision.created_at,
            summary=(
                "A bounded Cloud Run revision snapshot was observed; no causal change is inferred."
            ),
            value=revision.image_digest,
            direction=EvidenceDirection.NEUTRAL,
            source_uri=f"opspilot://evidence/change/{index:04d}",
            source_record_id=revision.revision_name,
            raw_excerpt_hash=f"sha256:{revision.config_hash}",
            quality_flags=[
                "temporal_only" if revision.within_window else "outside_investigation_window",
                "env_values_withheld",
            ],
        )
        for index, revision in enumerate(result.data, start=1)
    ]
    return ToolResult[list[EvidenceItem]](ok=True, data=evidence, meta=result.meta)


def _normalize_knowledge_result(
    result: ToolResult[list[KnowledgeHit]], environment: str
) -> ToolResult[list[EvidenceItem]]:
    if not result.ok or result.data is None:
        return ToolResult[list[EvidenceItem]](ok=False, error=result.error, meta=result.meta)
    evidence = [
        EvidenceItem(
            evidence_id=f"EV-KNW-{index:04d}",
            source_type=SourceType.KNOWLEDGE,
            title=hit.title,
            service=hit.service,
            environment=environment,
            observed_at=hit.updated_at,
            summary=_safe_text(hit.chunk_text),
            direction=EvidenceDirection.UNKNOWN,
            source_uri=hit.uri,
            source_record_id=hit.document_id,
            raw_excerpt_hash=f"sha256:{hashlib.sha256(hit.chunk_text.encode()).hexdigest()}",
            retrieval_score=(
                hit.relevance_score
                if hit.relevance_score is not None and 0.0 <= hit.relevance_score <= 1.0
                else None
            ),
            quality_flags=[
                *hit.safety_flags,
                *([hit.staleness_warning] if hit.staleness_warning else []),
            ],
        )
        for index, hit in enumerate(result.data, start=1)
    ]
    return ToolResult[list[EvidenceItem]](ok=True, data=evidence, meta=result.meta)


async def collect_evidence(
    client: EvidenceClient,
    request: EvidenceCollectionRequest,
) -> EvidenceCollectionResult:
    started_clock = perf_counter()
    sources = (SourceType.LOG, SourceType.METRIC, SourceType.CHANGE, SourceType.KNOWLEDGE)
    semaphore = asyncio.Semaphore(4)

    async def bounded(source: SourceType) -> ToolResult[list[EvidenceItem]]:
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    client.collect_source(source, request), timeout=TOOL_TIMEOUT_SECONDS
                )
            except TimeoutError:
                now = datetime.now(UTC)
                return ToolResult[list[EvidenceItem]](
                    ok=False,
                    error=ToolError(
                        code="EVIDENCE_TOOL_TIMEOUT",
                        category=ToolErrorCategory.TIMEOUT,
                        retryable=True,
                        safe_message="An evidence source exceeded its time limit.",
                    ),
                    meta=ToolMeta(
                        tool_name=f"collect_{source.value.lower()}",
                        request_id=f"TOOL-{source.value}",
                        started_at=now,
                        finished_at=now,
                        duration_ms=round(TOOL_TIMEOUT_SECONDS * 1_000),
                        source_project="current-default",
                    ),
                )

    results = await asyncio.wait_for(
        asyncio.gather(*(bounded(source) for source in sources)),
        timeout=COLLECTION_DEADLINE_SECONDS,
    )
    api_calls = sum(result.meta.api_call_count for result in results)
    if len(results) > MAX_TOOL_CALLS or api_calls > MAX_API_CALLS:
        raise RuntimeError("evidence collection exceeded its fixed call budget")
    evidence = sorted(
        [item for result in results if result.data for item in result.data],
        key=lambda item: item.observed_at or item.period_start or datetime.min.replace(tzinfo=UTC),
    )
    errors = [result.error for result in results if result.error is not None]
    source_status = {
        source.value: result.ok for source, result in zip(sources, results, strict=True)
    }
    gaps = [
        f"{source.value} evidence was unavailable."
        for source, result in zip(sources, results, strict=True)
        if not result.ok
    ]
    return EvidenceCollectionResult(
        backend=client.backend,
        scenario_id=request.scenario_id,
        complete=all(source_status.values()),
        source_status=source_status,
        evidence=evidence,
        tool_errors=errors,
        data_gaps=gaps,
        budget=CollectionBudgetUsage(
            logical_tool_calls=len(results),
            api_calls=api_calls,
            result_count=len(evidence),
            response_bytes=sum(result.meta.response_bytes for result in results),
            duration_ms=max(0, round((perf_counter() - started_clock) * 1_000)),
            truncated_sources=[
                source.value
                for source, result in zip(sources, results, strict=True)
                if result.meta.truncated
            ],
        ),
    )


def _gcloud_value(arguments: Sequence[str]) -> str:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


async def run_evidence_smoke(
    *,
    backend: EvidenceBackend,
    scenario_id: str,
    environment: str,
    now: datetime | None = None,
) -> EvidenceCollectionResult:
    if environment != "dev":
        raise ValueError("evidence environment must be dev")
    end_time = now or datetime.now(UTC)
    scenario_run_id = os.environ.get("OPSPILOT_SCENARIO_RUN_ID")
    request = EvidenceCollectionRequest(
        scenario_id=scenario_id,
        environment="dev",
        start_time=end_time - timedelta(minutes=30),
        end_time=end_time,
        services=["payment-service"],
        scenario_run_id=scenario_run_id,
    )
    if backend == EvidenceBackend.FIXTURE:
        return await collect_evidence(FixtureEvidenceClient(scenario_id), request)
    if os.environ.get("OPSPILOT_LIVE_EVIDENCE_ENABLED") != "true":
        raise RuntimeError("live evidence gate is disabled")
    if not scenario_run_id:
        raise RuntimeError("live evidence requires process-scoped scenario correlation")
    project_id = _gcloud_value(("config", "get-value", "project"))
    if not project_id:
        raise RuntimeError("default Google Cloud project is unavailable")
    catalog = load_service_catalog()
    client = LiveEvidenceClient(
        project_id,
        catalog=catalog,
        token_provider=GcloudImpersonationTokenProvider(project_id, environment),
        transport=UrllibJsonTransport(),
    )
    return await collect_evidence(client, request)


def render_evidence_summary(result: EvidenceCollectionResult) -> str:
    lines = [
        f"backend: {result.backend.value}",
        f"scenario_id: {result.scenario_id}",
        f"complete: {'pass' if result.complete else 'partial'}",
    ]
    lines.extend(
        f"source_{name.lower()}: {'pass' if ready else 'fail'}"
        for name, ready in sorted(result.source_status.items())
    )
    lines.extend(
        [
            f"logical_tool_calls: {result.budget.logical_tool_calls}",
            f"api_calls: {result.budget.api_calls}",
            f"evidence_count: {len(result.evidence)}",
            f"tool_error_count: {len(result.tool_errors)}",
            f"data_gap_count: {len(result.data_gaps)}",
            "evidence_ids: " + ",".join(item.evidence_id for item in result.evidence),
        ]
    )
    return "\n".join(lines) + "\n"
