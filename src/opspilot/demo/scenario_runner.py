"""Bounded baseline/incident/recovery runner for synthetic scenarios."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from collections.abc import Awaitable, Callable
from math import ceil
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from opspilot.demo.load import _gcloud_identity_token
from opspilot.demo.models import ScenarioPhaseSummary, ScenarioRunSummary
from opspilot.demo.scenario_context import ScenarioContext

ScenarioSender = Callable[
    [str, str, int, str | None, ScenarioContext | None],
    Awaitable[tuple[int, int, bool]],
]


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * percentile) - 1)]


async def _send_scenario_order(
    target: str,
    phase: str,
    index: int,
    token: str | None,
    scenario: ScenarioContext | None,
) -> tuple[int, int, bool]:
    return await asyncio.to_thread(_send_scenario_order_sync, target, phase, index, token, scenario)


def _send_scenario_order_sync(
    target: str,
    phase: str,
    index: int,
    token: str | None,
    scenario: ScenarioContext | None,
) -> tuple[int, int, bool]:
    run_fragment = scenario.run_id[-12:].lower() if scenario else secrets.token_hex(6)
    request_id = f"req_scn_{run_fragment}_{phase}_{index:02d}"
    trace_id = secrets.token_hex(16)
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": request_id,
        "X-Cloud-Trace-Context": f"{trace_id}/1;o=1",
    }
    if scenario:
        headers.update(scenario.headers())
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = UrlRequest(
        f"{target.rstrip('/')}/v1/orders",
        data=json.dumps(
            {"sku": f"SKU-{index % 5 + 1:03d}", "quantity": 1, "amount_krw": 1000}
        ).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = perf_counter()
    try:
        with urlopen(request, timeout=8) as response:
            response.read()
            status_code = response.status
            request_id_ok = response.headers.get("X-Request-ID") == request_id
    except HTTPError as exc:
        status_code = exc.code
        request_id_ok = exc.headers.get("X-Request-ID") == request_id
        exc.close()
    except (URLError, TimeoutError):
        status_code = 0
        request_id_ok = False
    latency_ms = max(0, round((perf_counter() - started) * 1_000))
    return status_code, latency_ms, request_id_ok


async def _run_phase(
    *,
    target: str,
    phase: str,
    count: int,
    token: str | None,
    run_id: str,
    sender: ScenarioSender,
) -> tuple[ScenarioPhaseSummary, list[int]]:
    semaphore = asyncio.Semaphore(2)

    async def bounded(index: int) -> tuple[int, int, bool]:
        scenario = (
            ScenarioContext(scenario_id="SCN-001", run_id=run_id, step=index)
            if phase == "incident"
            else None
        )
        async with semaphore:
            return await sender(target, phase, index, token, scenario)

    results = await asyncio.gather(*(bounded(index) for index in range(1, count + 1)))
    statuses = [status for status, _, _ in results]
    latencies = [latency for _, latency, _ in results]
    return (
        ScenarioPhaseSummary(
            attempted=count,
            fulfilled=sum(status == 201 for status in statuses),
            failed=sum(status != 201 for status in statuses),
            request_ids=sum(request_id_ok for _, _, request_id_ok in results),
            latency_p50_ms=_percentile(latencies, 0.5),
            latency_p95_ms=_percentile(latencies, 0.95),
        ),
        statuses,
    )


async def run_scenario(
    *,
    scenario_id: str,
    auth: str,
    sender: ScenarioSender = _send_scenario_order,
) -> ScenarioRunSummary:
    if scenario_id != "SCN-001":
        raise ValueError("only SCN-001 supports live execution in M3 MVP")
    if auth not in {"local", "gcloud"}:
        raise ValueError("auth must be local or gcloud")
    target = os.environ.get("OPSPILOT_ORDER_URL", "http://127.0.0.1:8100")
    token = await asyncio.to_thread(_gcloud_identity_token) if auth == "gcloud" else None
    run_id = f"RUN-SCN-001-{secrets.token_hex(6).upper()}"

    baseline, baseline_statuses = await _run_phase(
        target=target,
        phase="baseline",
        count=5,
        token=token,
        run_id=run_id,
        sender=sender,
    )
    incident, incident_statuses = await _run_phase(
        target=target,
        phase="incident",
        count=10,
        token=token,
        run_id=run_id,
        sender=sender,
    )
    recovery, recovery_statuses = await _run_phase(
        target=target,
        phase="recovery",
        count=5,
        token=token,
        run_id=run_id,
        sender=sender,
    )
    expected_incident = [502] * 6 + [201] * 4
    matched = (
        baseline_statuses == [201] * 5
        and incident_statuses == expected_incident
        and recovery_statuses == [201] * 5
    )
    return ScenarioRunSummary(
        scenario_id="SCN-001",
        run_id=run_id,
        baseline=baseline,
        incident=incident,
        recovery=recovery,
        trace_count=20,
        recovered=recovery.fulfilled == 5,
        ground_truth_matched=matched,
    )


def render_scenario_summary(result: ScenarioRunSummary) -> str:
    return "\n".join(
        [
            f"scenario_id: {result.scenario_id}",
            f"run_id: {result.run_id}",
            f"baseline: {result.baseline.fulfilled}/{result.baseline.attempted} fulfilled",
            f"incident: {result.incident.fulfilled} fulfilled, {result.incident.failed} failed",
            f"recovery: {result.recovery.fulfilled}/{result.recovery.attempted} fulfilled",
            f"trace_count: {result.trace_count}",
            f"recovered: {str(result.recovered).lower()}",
            f"ground_truth_matched: {str(result.ground_truth_matched).lower()}",
            "",
        ]
    )
