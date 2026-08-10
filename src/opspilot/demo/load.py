"""Bounded synthetic load generation for local and authenticated demo smoke tests."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from math import ceil
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from opspilot.demo.models import LoadSummary

OrderSender = Callable[[str, int, str | None], Awaitable[tuple[bool, int, bool]]]


def _gcloud_identity_token() -> str:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    completed = subprocess.run(
        [executable, "auth", "print-identity-token"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    token = completed.stdout.strip()
    if completed.returncode != 0 or not token:
        raise RuntimeError("gcloud identity token is unavailable")
    return token


async def _send_order(target: str, index: int, token: str | None) -> tuple[bool, int, bool]:
    return await asyncio.to_thread(_send_order_sync, target, index, token)


def _send_order_sync(target: str, index: int, token: str | None) -> tuple[bool, int, bool]:
    request_id = f"req_load_{index:08d}"
    headers = {"Content-Type": "application/json", "X-Request-ID": request_id}
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
            succeeded = response.status == 201
            returned_request_id = response.headers.get("X-Request-ID") == request_id
    except (HTTPError, URLError, TimeoutError):
        succeeded = False
        returned_request_id = False
    latency_ms = max(0, round((perf_counter() - started) * 1_000))
    return succeeded, latency_ms, returned_request_id


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, ceil(len(ordered) * percentile) - 1)
    return ordered[index]


async def run_load(
    *,
    orders: int,
    concurrency: int,
    auth: str,
    sender: OrderSender = _send_order,
) -> LoadSummary:
    if not 1 <= orders <= 100:
        raise ValueError("orders must be between 1 and 100")
    if not 1 <= concurrency <= 10:
        raise ValueError("concurrency must be between 1 and 10")
    if auth not in {"local", "gcloud"}:
        raise ValueError("auth must be local or gcloud")

    target = os.environ.get("OPSPILOT_ORDER_URL", "http://127.0.0.1:8100")
    token = await asyncio.to_thread(_gcloud_identity_token) if auth == "gcloud" else None
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(index: int) -> tuple[bool, int, bool]:
        async with semaphore:
            return await sender(target, index, token)

    results = await asyncio.gather(*(bounded(index) for index in range(orders)))
    latencies = [latency for _, latency, _ in results]
    succeeded = sum(1 for ok, _, _ in results if ok)
    return LoadSummary(
        attempted=orders,
        succeeded=succeeded,
        failed=orders - succeeded,
        request_ids=sum(1 for _, _, request_id_ok in results if request_id_ok),
        latency_p50_ms=_percentile(latencies, 0.5),
        latency_p95_ms=_percentile(latencies, 0.95),
    )
