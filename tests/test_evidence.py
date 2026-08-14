from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from email.message import Message
from io import BytesIO
from typing import Any, cast
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

import opspilot.evidence as evidence_module
from opspilot.catalog import load_service_catalog
from opspilot.domain import RequestedDepth, SourceType, ToolErrorCategory
from opspilot.evidence import (
    EvidenceBackend,
    EvidenceCollectionRequest,
    FixtureEvidenceClient,
    ListRevisionsInput,
    LiveEvidenceClient,
    MetricReducer,
    QueryLogsInput,
    QueryMetricSeriesInput,
    build_logging_filter,
    build_monitoring_filter,
    collect_evidence,
    normalize_log_response,
    normalize_metric_response,
    normalize_revision_response,
    render_evidence_summary,
    run_evidence_smoke,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("depth", "expected_calls", "expected_sources"),
    [
        (RequestedDepth.QUICK, 2, {"LOG", "METRIC"}),
        (RequestedDepth.STANDARD, 4, {"LOG", "METRIC", "CHANGE", "KNOWLEDGE"}),
        (RequestedDepth.DEEP, 4, {"LOG", "METRIC", "CHANGE", "KNOWLEDGE"}),
    ],
)
async def test_investigation_depth_owns_a_fixed_evidence_plan(
    depth: RequestedDepth,
    expected_calls: int,
    expected_sources: set[str],
) -> None:
    end = datetime(2026, 8, 11, 6, 30, tzinfo=UTC)
    result = await collect_evidence(
        FixtureEvidenceClient("SCN-001"),
        EvidenceCollectionRequest(
            scenario_id="SCN-001",
            start_time=end - timedelta(minutes=15),
            end_time=end,
            services=["payment-service"],
            requested_depth=depth,
        ),
    )

    assert result.budget.logical_tool_calls == expected_calls
    assert set(result.source_status) == expected_sources


def _window() -> tuple[datetime, datetime]:
    end = datetime(2026, 8, 11, 6, 30, tzinfo=UTC)
    return end - timedelta(minutes=30), end


def test_M5_inputs_require_bounded_utc_and_safe_literal_terms() -> None:
    start, end = _window()
    with pytest.raises(ValidationError, match="timezone-aware"):
        QueryLogsInput(
            service="payment-service",
            start_time=start.replace(tzinfo=None),
            end_time=end,
        )
    with pytest.raises(ValidationError, match="cannot exceed 2 hours"):
        QueryMetricSeriesInput(
            service="payment-service",
            metric_key="request_count",
            start_time=end - timedelta(hours=3),
            end_time=end,
            reducer=MetricReducer.SUM,
        )
    with pytest.raises(ValidationError, match="safe literal"):
        QueryLogsInput(
            service="payment-service",
            start_time=start,
            end_time=end,
            query_terms=['severity>=DEFAULT OR textPayload:"secret"'],
        )
    with pytest.raises(ValidationError, match="scenario_run_id"):
        EvidenceCollectionRequest(
            scenario_id="SCN-001",
            start_time=start,
            end_time=end,
            scenario_run_id="raw-filter-fragment",
        )


def test_M5_server_side_builders_use_only_allowlisted_scope() -> None:
    start, end = _window()
    catalog = load_service_catalog()
    log_filter = build_logging_filter(
        QueryLogsInput(
            service="payment-service",
            start_time=start,
            end_time=end,
            query_terms=["DB_POOL_TIMEOUT"],
        ),
        catalog,
    )
    assert 'resource.type="cloud_run_revision"' in log_filter
    assert 'resource.labels.service_name="opspilot-dev-payment"' in log_filter
    assert "DB_POOL_TIMEOUT" in log_filter
    assert "project" not in log_filter

    metric_filter = build_monitoring_filter(
        QueryMetricSeriesInput(
            service="payment-service",
            metric_key="error_ratio",
            start_time=start,
            end_time=end,
            reducer=MetricReducer.RATIO,
        ),
        catalog,
    )
    assert 'metric.type="run.googleapis.com/request_count"' in metric_filter
    assert 'resource.labels.service_name="opspilot-dev-payment"' in metric_filter

    with pytest.raises(ValueError, match="not allowlisted"):
        build_monitoring_filter(
            QueryMetricSeriesInput(
                service="unknown-service",
                metric_key="request_count",
                start_time=start,
                end_time=end,
                reducer=MetricReducer.SUM,
            ),
            catalog,
        )
    with pytest.raises(ValueError, match="fixture-only"):
        build_monitoring_filter(
            QueryMetricSeriesInput(
                service="payment-service",
                metric_key="db_pool_waiters",
                start_time=start,
                end_time=end,
                reducer=MetricReducer.MAX,
            ),
            catalog,
        )


def test_M5_log_normalization_masks_sensitive_and_control_content() -> None:
    start, end = _window()
    request = QueryLogsInput(service="payment-service", start_time=start, end_time=end)
    payload = {
        "entries": [
            {
                "timestamp": "2026-08-11T06:15:00Z",
                "severity": "ERROR",
                "trace": "projects/hidden/traces/0123456789abcdef0123456789abcdef",
                "resource": {"labels": {"revision_name": "secret-revision-name"}},
                "jsonPayload": {
                    "message": (
                        "\u001b[31mDB_POOL_TIMEOUT user=demo@example.test "
                        "token=secret-token-12345678 4111 1111 1111 1111"
                    ),
                    "event_type": "database_timeout",
                    "error_code": "DB_POOL_TIMEOUT",
                    "request_id": "req_secret",
                },
            }
        ]
    }
    result = normalize_log_response(payload, request)

    assert result.total_matching_entries == 1
    sample = result.signatures[0].representative_samples[0]
    assert sample.trace_present is True
    assert sample.revision is not None and sample.revision.startswith("revision-")
    assert sample.labels == {
        "event_type": "database_timeout",
        "error_code": "DB_POOL_TIMEOUT",
    }
    serialized = json.dumps(result.model_dump(mode="json"))
    assert "demo@example.test" not in serialized
    assert "secret-token" not in serialized
    assert "4111 1111 1111 1111" not in serialized
    assert "secret-revision-name" not in serialized
    assert "req_secret" not in serialized
    assert "\u001b" not in serialized


def test_M5_metric_normalization_computes_error_ratio_and_missing_points() -> None:
    start, end = _window()
    request = QueryMetricSeriesInput(
        service="payment-service",
        metric_key="error_ratio",
        start_time=start,
        end_time=end,
        reducer=MetricReducer.RATIO,
    )
    payload = {
        "timeSeries": [
            {
                "metric": {"labels": {"response_code_class": "2xx"}},
                "points": [
                    {"interval": {"endTime": "2026-08-11T06:20:00Z"}, "value": {"int64Value": "4"}}
                ],
            },
            {
                "metric": {"labels": {"response_code_class": "5xx"}},
                "points": [
                    {"interval": {"endTime": "2026-08-11T06:20:00Z"}, "value": {"int64Value": "6"}}
                ],
            },
        ]
    }
    result = normalize_metric_response(payload, request)

    assert result.unit == "percent"
    assert result.sample_count == 1
    assert result.points[0].value == 60.0
    assert result.max_value == 60.0
    assert normalize_metric_response({}, request).missing_ratio == 1.0


def test_M5_revision_normalization_never_returns_env_values_or_resource_names() -> None:
    start, end = _window()
    request = ListRevisionsInput(
        service="payment-service",
        start_time=start,
        end_time=end,
    )
    service_payload = {
        "trafficStatuses": [
            {"revision": "projects/hidden/revisions/secret-revision", "percent": 100}
        ]
    }
    revision_payload = {
        "revisions": [
            {
                "name": "projects/hidden/revisions/secret-revision",
                "createTime": "2026-08-11T06:10:00Z",
                "containers": [
                    {
                        "image": "registry.invalid/demo@sha256:" + "a" * 64,
                        "env": [
                            {"name": "DB_POOL_SIZE", "value": "secret-value"},
                            {"name": "MODE", "value": "dev"},
                        ],
                    }
                ],
            },
            {
                "name": "projects/hidden/revisions/older-revision",
                "createTime": "2026-08-11T06:05:00Z",
                "containers": [
                    {
                        "image": "registry.invalid/demo@sha256:" + "a" * 64,
                        "env": [
                            {"name": "DB_POOL_SIZE", "value": "previous-value"},
                            {"name": "MODE", "value": "dev"},
                        ],
                    }
                ],
            },
        ]
    }
    summaries = normalize_revision_response(service_payload, revision_payload, request)

    assert len(summaries) == 2
    assert summaries[0].revision_name.startswith("revision-")
    assert summaries[0].image_digest == "sha256:" + "a" * 64
    assert summaries[0].env_keys_changed == ["DB_POOL_SIZE"]
    assert summaries[0].within_window is True
    serialized = json.dumps([item.model_dump(mode="json") for item in summaries])
    assert "secret-value" not in serialized
    assert "projects/hidden" not in serialized
    assert "secret-revision" not in serialized


@pytest.mark.parametrize(
    ("status", "category", "retryable"),
    [
        (401, ToolErrorCategory.AUTH, False),
        (403, ToolErrorCategory.AUTH, False),
        (404, ToolErrorCategory.NOT_FOUND, False),
        (429, ToolErrorCategory.QUOTA, True),
        (500, ToolErrorCategory.UPSTREAM, True),
    ],
)
def test_M5_http_failures_are_safely_classified(
    status: int, category: ToolErrorCategory, retryable: bool
) -> None:
    failure = evidence_module._http_failure(status)
    assert failure.category == category
    assert failure.retryable is retryable
    assert "http" not in failure.safe_message.casefold()


def test_M5_transport_discards_malformed_and_sensitive_error_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not-json"

    monkeypatch.setattr(evidence_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    with pytest.raises(evidence_module.LiveEvidenceFailure) as malformed:
        evidence_module.UrllibJsonTransport._request_sync(
            "GET", "https://example.invalid", "secret-token", "secret-project", None, 1.0
        )
    assert malformed.value.code == "EVIDENCE_INVALID_RESPONSE"
    assert "secret" not in malformed.value.safe_message

    def raise_http(*_args: object, **_kwargs: object) -> None:
        headers = Message()
        raise HTTPError(
            "https://secret-project.invalid",
            403,
            "token=secret-token",
            headers,
            BytesIO(b'project="secret-project" token="secret-token"'),
        )

    monkeypatch.setattr(evidence_module, "urlopen", raise_http)
    with pytest.raises(evidence_module.LiveEvidenceFailure) as forbidden:
        evidence_module.UrllibJsonTransport._request_sync(
            "GET", "https://example.invalid", "secret-token", "secret-project", None, 1.0
        )
    assert forbidden.value.code == "EVIDENCE_FORBIDDEN"
    serialized = forbidden.value.safe_message + str(forbidden.value.args)
    assert "secret-project" not in serialized
    assert "secret-token" not in serialized


def test_M5_transport_converts_timeout_without_raw_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise TimeoutError("https://secret-project.invalid token=secret-token")

    monkeypatch.setattr(evidence_module, "urlopen", raise_timeout)
    with pytest.raises(evidence_module.LiveEvidenceFailure) as timeout:
        evidence_module.UrllibJsonTransport._request_sync(
            "GET", "https://example.invalid", "secret-token", "secret-project", None, 1.0
        )
    assert timeout.value.code == "EVIDENCE_TRANSPORT_ERROR"
    assert timeout.value.category == ToolErrorCategory.TIMEOUT
    assert "secret" not in timeout.value.safe_message


@pytest.mark.asyncio
async def test_M5_fixture_client_preserves_partial_evidence_and_budget() -> None:
    start, end = _window()
    request = EvidenceCollectionRequest(
        scenario_id="SCN-001",
        start_time=start,
        end_time=end,
    )
    result = await collect_evidence(
        FixtureEvidenceClient("SCN-001", fail_sources=frozenset({SourceType.METRIC})),
        request,
    )

    assert result.complete is False
    assert result.succeeded is True
    assert result.source_status["METRIC"] is False
    assert result.budget.logical_tool_calls == 4
    assert result.budget.api_calls == 0
    assert len(result.tool_errors) == 1
    assert all(item.source_type != SourceType.METRIC for item in result.evidence)


@pytest.mark.asyncio
async def test_successful_empty_metric_series_are_preserved_as_data_gaps() -> None:
    class EmptyMetricFixture(FixtureEvidenceClient):
        async def collect_source(
            self, source: SourceType, request: EvidenceCollectionRequest
        ) -> Any:
            result = await super().collect_source(source, request)
            if source != SourceType.METRIC or not result.data:
                return result
            empty_metrics = [
                result.data[0].model_copy(
                    update={
                        "title": f"Cloud Run {metric_key}",
                        "period_start": None,
                        "period_end": None,
                        "summary": f"Observed 0 bounded points for {metric_key}.",
                        "value": None,
                        "quality_flags": ["missing_points"],
                    }
                )
                for metric_key in ("error_ratio", "latency_p95")
            ]
            return result.model_copy(update={"data": empty_metrics})

    start, end = _window()
    result = await collect_evidence(
        EmptyMetricFixture("SCN-001"),
        EvidenceCollectionRequest(scenario_id="SCN-001", start_time=start, end_time=end),
    )

    assert result.complete is False
    assert result.succeeded is True
    assert result.source_status["METRIC"] is True
    assert result.tool_errors == []
    assert result.data_gaps == [
        "Cloud Run error_ratio returned no bounded points in the requested window.",
        "Cloud Run latency_p95 returned no bounded points in the requested window.",
    ]
    metrics = [item for item in result.evidence if item.source_type == SourceType.METRIC]
    assert len(metrics) == 2
    assert all("missing_points" in item.quality_flags for item in metrics)


@pytest.mark.asyncio
async def test_M5_collector_converts_source_timeout_to_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SlowFixture(FixtureEvidenceClient):
        async def collect_source(
            self, source: SourceType, request: EvidenceCollectionRequest
        ) -> Any:
            if source == SourceType.LOG:
                await asyncio.sleep(0.05)
            return await super().collect_source(source, request)

    monkeypatch.setattr(evidence_module, "TOOL_TIMEOUT_SECONDS", 0.01)
    start, end = _window()
    result = await collect_evidence(
        SlowFixture("SCN-001"),
        EvidenceCollectionRequest(scenario_id="SCN-001", start_time=start, end_time=end),
    )

    assert result.source_status["LOG"] is False
    assert any(error.category == ToolErrorCategory.TIMEOUT for error in result.tool_errors)
    assert result.succeeded is True


@pytest.mark.asyncio
async def test_fixture_smoke_is_identifier_free_and_live_bypass_is_not_public() -> None:
    result = await run_evidence_smoke(
        backend=EvidenceBackend.FIXTURE,
        scenario_id="SCN-001",
        environment="dev",
        now=_window()[1],
    )
    summary = render_evidence_summary(result)

    assert result.complete is True
    assert result.budget.api_calls == 0
    assert "EV-LOG-0001" in summary
    assert "fixture-token-12345678" not in json.dumps(result.model_dump(mode="json"))

    with pytest.raises(ValueError, match="fixture-only"):
        await run_evidence_smoke(
            backend=EvidenceBackend.LIVE,
            scenario_id="SCN-001",
            environment="dev",
            now=_window()[1],
        )


def test_M5_public_models_do_not_accept_raw_cloud_query_fields() -> None:
    fields = set(QueryLogsInput.model_fields) | set(QueryMetricSeriesInput.model_fields)
    prohibited = {
        "project_id",
        "url",
        "filter",
        "resource_name",
        "serving_config",
        "token",
    }
    assert fields.isdisjoint(prohibited)
    assert cast(object, QueryLogsInput.model_fields["max_entries"].default) == 100


@pytest.mark.asyncio
async def test_M5_live_adapter_uses_fixed_bounded_requests_and_logical_citations() -> None:
    class FakeTokenProvider:
        async def get_token(self) -> str:
            return "secret-live-token"

    class FakeTransport:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

        async def request(
            self,
            method: str,
            url: str,
            *,
            token: str,
            quota_project: str,
            body: dict[str, Any] | None = None,
            timeout_seconds: float = 10.0,
        ) -> tuple[dict[str, Any], int]:
            del timeout_seconds
            assert token == "secret-live-token"
            assert quota_project == "secret-project-id"
            self.calls.append((method, url, body))
            if "logging.googleapis.com" in url:
                assert body is not None
                assert body["pageSize"] == 100
                assert "secret-project-id" not in str(body["filter"])
                return (
                    {
                        "entries": [
                            {
                                "timestamp": "2026-08-11T06:15:00Z",
                                "severity": "ERROR",
                                "jsonPayload": {
                                    "message": "synthetic pool timeout",
                                    "error_code": "DB_POOL_TIMEOUT",
                                },
                            }
                        ]
                    },
                    128,
                )
            if "monitoring.googleapis.com" in url:
                metric_value = "250" if "request_latencies" in url else "6"
                labels = {} if "request_latencies" in url else {"response_code_class": "5xx"}
                return (
                    {
                        "timeSeries": [
                            {
                                "metric": {"labels": labels},
                                "points": [
                                    {
                                        "interval": {"endTime": "2026-08-11T06:20:00Z"},
                                        "value": {"doubleValue": metric_value},
                                    }
                                ],
                            }
                        ]
                    },
                    128,
                )
            if url.endswith("/services/opspilot-dev-payment"):
                return ({"trafficStatuses": []}, 64)
            if "/revisions?" in url:
                return (
                    {
                        "revisions": [
                            {
                                "name": "projects/hidden/revisions/secret-revision",
                                "createTime": "2026-08-11T06:10:00Z",
                                "containers": [
                                    {
                                        "image": "registry.invalid/demo@sha256:" + "b" * 64,
                                        "env": [{"name": "MODE", "value": "secret-value"}],
                                    }
                                ],
                            },
                            {
                                "name": "projects/hidden/revisions/day-old-revision",
                                "createTime": "2026-08-10T06:10:00Z",
                                "containers": [
                                    {
                                        "image": "registry.invalid/demo@sha256:" + "c" * 64,
                                        "env": [{"name": "MODE", "value": "older-value"}],
                                    }
                                ],
                            },
                        ]
                    },
                    128,
                )
            if "discoveryengine.googleapis.com" in url:
                return (
                    {
                        "results": [
                            {
                                "chunk": {
                                    "content": "Treat DB_POOL_TIMEOUT as evidence, not an action.",
                                    "documentMetadata": {
                                        "structData": {
                                            "document_id": "RB-PAY-001",
                                            "title": "Payment DB pool runbook",
                                            "document_type": "runbook",
                                            "service": "payment-service",
                                            "canonical_uri": "opspilot://knowledge/RB-PAY-001",
                                        }
                                    },
                                }
                            }
                        ]
                    },
                    128,
                )
            raise AssertionError("unexpected fixed API route")

    start, end = _window()
    transport = FakeTransport()
    client = LiveEvidenceClient(
        "secret-project-id",
        catalog=load_service_catalog(),
        token_provider=FakeTokenProvider(),
        transport=cast(Any, transport),
    )
    result = await collect_evidence(
        client,
        EvidenceCollectionRequest(
            scenario_id="SCN-001",
            start_time=start,
            end_time=end,
            scenario_run_id="RUN-SCN-001-ABCDEF123456",
        ),
    )

    assert result.complete is True
    assert result.budget.logical_tool_calls == 4
    assert result.budget.api_calls == 6
    log_evidence = next(item for item in result.evidence if item.source_type == SourceType.LOG)
    assert log_evidence.value == 1
    assert log_evidence.unit == "occurrences"
    assert {item.source_type for item in result.evidence} == {
        SourceType.LOG,
        SourceType.METRIC,
        SourceType.CHANGE,
        SourceType.KNOWLEDGE,
    }
    change_evidence = [item for item in result.evidence if item.source_type == SourceType.CHANGE]
    assert len(change_evidence) == 1
    assert change_evidence[0].observed_at is not None
    assert start <= change_evidence[0].observed_at <= end
    serialized = json.dumps(result.model_dump(mode="json"))
    assert "secret-project-id" not in serialized
    assert "secret-live-token" not in serialized
    assert "secret-revision" not in serialized
    assert "secret-value" not in serialized
    assert all(
        item.source_uri is None or item.source_uri.startswith("opspilot://")
        for item in result.evidence
    )
