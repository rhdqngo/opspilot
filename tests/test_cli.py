from __future__ import annotations

import pytest

from opspilot.cli import main
from opspilot.demo.models import LoadSummary, ScenarioPhaseSummary, ScenarioRunSummary
from opspilot.route_check import CloudRunRouteCheckResult


def test_FR_020_cli_replays_SCN_001_as_markdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["replay", "--scenario", "SCN-001", "--format", "markdown"])
    assert exit_code == 0
    assert "EV-LOG-0001" in capsys.readouterr().out


def test_M2_cli_load_prints_only_aggregate_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_load(*, orders: int, concurrency: int, auth: str) -> LoadSummary:
        assert (orders, concurrency, auth) == (10, 2, "local")
        return LoadSummary(
            attempted=10,
            succeeded=10,
            failed=0,
            request_ids=10,
            latency_p50_ms=12,
            latency_p95_ms=19,
        )

    monkeypatch.setattr("opspilot.cli.run_load", fake_load)
    exit_code = main(["demo", "load"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"succeeded":10' in output
    assert "http" not in output


def test_route_check_cli_returns_two_for_a_redacted_blocker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "opspilot.cli.run_route_check",
        lambda **_kwargs: CloudRunRouteCheckResult(
            services_found=3,
            services_ready=3,
            blocker_code="endpoint_not_found",
        ),
    )

    exit_code = main(["route-check", "--account-alias", "Edu_687", "--format", "json"])

    assert exit_code == 2
    output = capsys.readouterr().out
    assert '"blocker_code": "endpoint_not_found"' in output
    assert "http" not in output


def test_M3_cli_scenario_run_prints_redacted_aggregate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    phase = ScenarioPhaseSummary(
        attempted=5,
        fulfilled=5,
        failed=0,
        request_ids=5,
        latency_p50_ms=10,
        latency_p95_ms=12,
    )

    async def fake_run_scenario(*, scenario_id: str, auth: str) -> ScenarioRunSummary:
        assert (scenario_id, auth) == ("SCN-001", "local")
        return ScenarioRunSummary(
            scenario_id="SCN-001",
            run_id="RUN-SCN-001-ABCDEF123456",
            baseline=phase,
            incident=ScenarioPhaseSummary(
                attempted=10,
                fulfilled=4,
                failed=6,
                request_ids=10,
                latency_p50_ms=250,
                latency_p95_ms=260,
            ),
            recovery=phase,
            trace_count=20,
            recovered=True,
            ground_truth_matched=True,
        )

    monkeypatch.setattr("opspilot.cli.run_scenario", fake_run_scenario)
    exit_code = main(["scenario", "run", "--format", "json"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"ground_truth_matched":true' in output
    assert "http" not in output


def test_M4_cli_validates_and_smokes_local_corpus_without_cloud_identifiers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["knowledge", "validate", "--format", "json"]) == 0
    validation_output = capsys.readouterr().out
    assert '"document_count": 13' in validation_output

    assert main(["knowledge", "smoke", "--backend", "local", "--format", "json"]) == 0
    smoke_output = capsys.readouterr().out
    assert '"passed_count": 10' in smoke_output
    assert "gs://" not in smoke_output
    assert "project_id" not in smoke_output
    assert "token" not in smoke_output
