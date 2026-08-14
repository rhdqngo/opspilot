from __future__ import annotations

from pathlib import Path

import pytest

from opspilot.cli import build_parser, main
from opspilot.demo.models import LoadSummary, ScenarioPhaseSummary, ScenarioRunSummary


def test_serve_uses_cloud_run_port_and_public_bind_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        observed["app"] = app
        observed.update(kwargs)

    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setattr("opspilot.cli.uvicorn.run", fake_run)

    assert main(["serve"]) == 0
    assert observed == {
        "app": "opspilot.api:create_app",
        "factory": True,
        "host": "0.0.0.0",
        "port": 8080,
    }


def test_serve_keeps_local_defaults_and_explicit_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, int]] = []

    def fake_run(_app: str, **kwargs: object) -> None:
        observed.append((str(kwargs["host"]), int(str(kwargs["port"]))))

    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr("opspilot.cli.uvicorn.run", fake_run)

    assert main(["serve"]) == 0
    assert main(["serve", "--host", "0.0.0.0", "--port", "9000"]) == 0
    assert observed == [("127.0.0.1", 8000), ("0.0.0.0", 9000)]


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

    async def fake_run_scenario(
        *, scenario_id: str, auth: str, environment: str
    ) -> ScenarioRunSummary:
        assert (scenario_id, auth, environment) == ("SCN-001", "local", "dev")
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


def test_cleanup_plan_never_executes_or_claims_approval(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["cleanup", "plan", "--format", "json"]) == 0
    output = capsys.readouterr().out
    assert '"destructive_execution_enabled": false' in output
    assert '"requires_separate_approval": true' in output
    assert "terraform apply" not in output.casefold()


def test_agent_cli_keeps_fixture_eval_and_runtime_package_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["agent", "eval", "--format", "summary"]) == 0
    assert "passed_cases: 7" in capsys.readouterr().out
    assert (
        main(
            [
                "agent",
                "eval",
                "--suite",
                "portfolio",
                "--format",
                "summary",
                "--output",
                ".tmp/test-evaluation-artifacts",
            ]
        )
        == 0
    )
    portfolio = capsys.readouterr().out
    assert "suite_version: portfolio-v1" in portfolio
    assert "passed_cases: 40" in portfolio
    assert "gate_failures: none" in portfolio
    assert Path(".tmp/test-evaluation-artifacts/portfolio-v1.json").is_file()
    assert Path(".tmp/test-evaluation-artifacts/portfolio-v1.md").is_file()
    assert main(["agent", "runtime", "package", "--output", ".tmp/test-cli-runtime"]) == 0
    assert "succeeded: True" in capsys.readouterr().out
    assert Path(".tmp/test-cli-runtime/opspilot-agent-runtime.tar.gz").is_file()


def test_M8_cli_exposes_plan_only_scn008_and_remediation_gate_without_token_args(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["scenario", "prepare", "--scenario", "SCN-008", "--mode", "plan"]) == 0
    output = capsys.readouterr().out
    assert "executed: false" in output
    assert "capture known-good payment revision" in output
    assert main(["scenario", "abort", "--scenario", "SCN-008", "--mode", "plan"]) == 0
    assert "ineligible for evidence publication" in capsys.readouterr().out

    assert main(["remediation", "eval", "--format", "summary"]) == 0
    evaluation = capsys.readouterr().out
    assert "suite_version: remediation-v1" in evaluation
    assert "passed_cases: 12" in evaluation

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["remediation", "show", "--id", "REM-0123456789ABCDEF", "--token", "secret"]
        )
    parsed = build_parser().parse_args(
        [
            "remediation",
            "request",
            "--incident",
            "INC-2026-0008",
            "--report",
            "RPT-SCN-008-001",
            "--action",
            "ACT-01",
            "--idempotency-key",
            "fixed-request-key",
        ]
    )
    assert parsed.idempotency_key == "fixed-request-key"
    shown = build_parser().parse_args(
        ["remediation", "show", "--id", "REM-0123456789ABCDEF", "--format", "json"]
    )
    assert shown.format == "json"


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
