from __future__ import annotations

from pathlib import Path

import pytest

from opspilot.cli import main
from opspilot.demo.models import LoadSummary, ScenarioPhaseSummary, ScenarioRunSummary


def test_cli_replays_scn_001_as_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["replay", "--scenario", "SCN-001", "--format", "markdown"]) == 0
    assert "EV-LOG-0001" in capsys.readouterr().out


def test_demo_load_prints_only_aggregate_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
    assert main(["demo", "load"]) == 0
    output = capsys.readouterr().out
    assert '"succeeded":10' in output
    assert "http" not in output


def test_scenario_run_prints_redacted_aggregate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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
    assert main(["scenario", "run", "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"ground_truth_matched":true' in output
    assert "http" not in output


def test_knowledge_and_evidence_cli_are_local_only(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["knowledge", "validate", "--format", "json"]) == 0
    assert '"document_count": 13' in capsys.readouterr().out
    assert main(["knowledge", "smoke", "--format", "json"]) == 0
    assert '"passed_count": 10' in capsys.readouterr().out
    assert main(["evidence", "smoke", "--scenario", "SCN-001", "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"api_calls": 0' in output
    assert "project_id" not in output


def test_agent_cli_keeps_fixture_eval_and_runtime_package_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["agent", "eval", "--format", "summary"]) == 0
    assert "passed_cases: 7" in capsys.readouterr().out
    assert main(["agent", "runtime", "package", "--output", ".tmp/test-cli-runtime"]) == 0
    assert "succeeded: True" in capsys.readouterr().out
    assert Path(".tmp/test-cli-runtime/opspilot-agent-runtime.tar.gz").is_file()


@pytest.mark.parametrize(
    "argv",
    [
        ["access-check"],
        ["route-check"],
        ["knowledge", "diagnose"],
        ["knowledge", "probe"],
        ["agent", "diagnose"],
        ["agent", "accept"],
        ["agent", "runtime", "probe"],
        ["agent", "enterprise", "plan"],
    ],
)
def test_removed_milestone_commands_are_not_public(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        main(argv)
