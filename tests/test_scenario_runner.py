from __future__ import annotations

import pytest

from opspilot.demo.scenario_context import ScenarioContext
from opspilot.demo.scenario_runner import render_scenario_summary, run_scenario


@pytest.mark.asyncio
async def test_M3_scenario_runner_matches_baseline_incident_recovery_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, ScenarioContext | None]] = []

    async def sender(
        target: str,
        phase: str,
        index: int,
        token: str | None,
        scenario: ScenarioContext | None,
    ) -> tuple[int, int, bool]:
        assert target == "http://order.example.invalid"
        assert token is None
        calls.append((phase, index, scenario))
        status = 502 if scenario is not None and scenario.inject_payment_failure else 201
        return status, 10 + index, True

    monkeypatch.setenv("OPSPILOT_ORDER_URL", "http://order.example.invalid")
    result = await run_scenario(scenario_id="SCN-001", auth="local", sender=sender)

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
async def test_M3_scenario_runner_rejects_non_live_scenario() -> None:
    with pytest.raises(ValueError, match="only SCN-001"):
        await run_scenario(scenario_id="SCN-002", auth="local")
