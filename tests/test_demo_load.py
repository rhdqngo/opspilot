from __future__ import annotations

import pytest

from opspilot.demo.load import run_load


@pytest.mark.asyncio
async def test_M2_load_generator_is_bounded_and_reports_only_aggregates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets: list[str] = []

    async def sender(target: str, index: int, token: str | None) -> tuple[bool, int, bool]:
        targets.append(target)
        assert token is None
        return index != 2, 10 + index, True

    monkeypatch.setenv("OPSPILOT_ORDER_URL", "http://order.example.invalid")
    summary = await run_load(orders=4, concurrency=2, auth="local", sender=sender)

    assert summary.model_dump() == {
        "attempted": 4,
        "succeeded": 3,
        "failed": 1,
        "request_ids": 4,
        "latency_p50_ms": 11,
        "latency_p95_ms": 13,
    }
    assert targets == ["http://order.example.invalid"] * 4


@pytest.mark.asyncio
async def test_M2_load_generator_rejects_unbounded_values() -> None:
    with pytest.raises(ValueError, match="orders"):
        await run_load(orders=101, concurrency=2, auth="local")
    with pytest.raises(ValueError, match="concurrency"):
        await run_load(orders=1, concurrency=11, auth="local")


@pytest.mark.asyncio
async def test_workload_load_uses_order_url_as_identity_token_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, str | None]] = []

    async def sender(target: str, _index: int, token: str | None) -> tuple[bool, int, bool]:
        observed.append((target, token))
        return True, 1, True

    def workload_token(audience: str) -> str:
        assert audience == "https://order.example.invalid"
        return "workload-token"

    monkeypatch.setenv("OPSPILOT_ORDER_URL", "https://order.example.invalid")
    monkeypatch.setattr("opspilot.demo.load._workload_identity_token", workload_token)
    monkeypatch.setattr(
        "opspilot.demo.load._gcloud_identity_token",
        lambda: pytest.fail("workload auth must not call gcloud"),
    )

    summary = await run_load(orders=1, concurrency=1, auth="workload", sender=sender)

    assert summary.succeeded == 1
    assert observed == [("https://order.example.invalid", "workload-token")]
