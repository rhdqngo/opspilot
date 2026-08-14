from __future__ import annotations

import pytest

from opspilot.demo.scenario_context import ScenarioContext
from opspilot.demo.scenario_runner import (
    _wait_for_healthy_baseline,
    render_scenario_summary,
    run_scenario,
)


@pytest.mark.asyncio
async def test_M3_scenario_runner_matches_baseline_incident_recovery_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, ScenarioContext | None]] = []
    lifecycle: list[str] = []

    async def warmer(target: str, token: str | None) -> None:
        assert target == "http://order.example.invalid"
        assert token is None
        lifecycle.append("warm")

    async def sender(
        target: str,
        phase: str,
        index: int,
        token: str | None,
        scenario: ScenarioContext | None,
    ) -> tuple[int, int, bool]:
        assert target == "http://order.example.invalid"
        assert token is None
        assert lifecycle == ["warm"]
        calls.append((phase, index, scenario))
        status = 502 if scenario is not None and scenario.inject_payment_failure else 201
        return status, 10 + index, True

    monkeypatch.setenv("OPSPILOT_ORDER_URL", "http://order.example.invalid")
    result = await run_scenario(scenario_id="SCN-001", auth="local", sender=sender, warmer=warmer)

    assert result.baseline.fulfilled == 5
    assert result.incident.model_dump()["fulfilled"] == 4
    assert result.incident.failed == 6
    assert result.recovery.fulfilled == 5
    assert result.trace_count == 20
    assert result.recovered is True
    assert result.ground_truth_matched is True
    assert len(calls) == 20
    rendered = render_scenario_summary(result)
    assert "ground_truth_matched: true" in rendered
    assert "http" not in rendered


@pytest.mark.asyncio
async def test_M3_scenario_runner_waits_for_scale_to_zero_service_without_counting_probe() -> None:
    attempts = 0
    order_attempts = 0
    sleeps: list[float] = []

    async def probe(target: str, token: str | None) -> bool:
        nonlocal attempts
        assert target == "https://order.example.invalid"
        assert token == "synthetic-token"
        attempts += 1
        return attempts == 3

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)

    async def order_probe(target: str, token: str | None) -> bool:
        nonlocal order_attempts
        assert target == "https://order.example.invalid"
        assert token == "synthetic-token"
        order_attempts += 1
        return True

    await _wait_for_healthy_baseline(
        "https://order.example.invalid",
        "synthetic-token",
        probe=probe,
        order_probe=order_probe,
        sleeper=sleeper,
    )

    assert attempts == 3
    assert order_attempts == 2
    assert sleeps == [2.0, 2.0, 1.0]


@pytest.mark.asyncio
async def test_M3_scenario_runner_requires_two_consecutive_healthy_orders() -> None:
    outcomes = iter((False, True, False, True, True))
    order_attempts = 0
    sleeps: list[float] = []

    async def ready(_target: str, _token: str | None) -> bool:
        return True

    async def order_probe(_target: str, _token: str | None) -> bool:
        nonlocal order_attempts
        order_attempts += 1
        return next(outcomes)

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)

    await _wait_for_healthy_baseline(
        "https://order.example.invalid",
        "synthetic-token",
        probe=ready,
        order_probe=order_probe,
        sleeper=sleeper,
    )

    assert order_attempts == 5
    assert sleeps == [1.0, 1.0, 1.0, 1.0]


@pytest.mark.asyncio
async def test_M3_scenario_runner_rejects_non_live_scenario() -> None:
    with pytest.raises(ValueError, match="only SCN-001"):
        await run_scenario(scenario_id="SCN-002", auth="local")
