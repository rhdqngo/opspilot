from __future__ import annotations

import http.client
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from opspilot.portfolio import demo
from opspilot.portfolio.demo import DemoCommandResult, PortfolioDemoRunner, demo_steps


class FakeDemoCommands:
    def __init__(self, *, fail_on: str | None = None, interrupt_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.interrupt_on = interrupt_on
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, command: Sequence[str], root: Path, environment: Mapping[str, str]
    ) -> DemoCommandResult:
        del root
        assert environment["UV_CACHE_DIR"]
        call = tuple(command)
        self.calls.append(call)
        joined = " ".join(call)
        if self.interrupt_on is not None and self.interrupt_on in joined:
            raise KeyboardInterrupt
        return DemoCommandResult(
            returncode=1 if self.fail_on is not None and self.fail_on in joined else 0,
            duration_ms=1,
        )


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".tmp").mkdir(parents=True)
    return root


def test_demo_dry_run_lists_bounded_order_without_executing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    commands = FakeDemoCommands()
    runner = PortfolioDemoRunner(
        root=root,
        output=Path(".tmp/demo"),
        build_image=False,
        dry_run=True,
        command_runner=commands,
    )

    assert runner.run() == 0

    assert commands.calls == []
    output = capsys.readouterr().out
    assert output.index("verify_image") < output.index("compose_up")
    assert output.index("scenario_scn_001") < output.index("portfolio_gate")
    summary = json.loads((root / ".tmp/demo/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "planned"
    assert all(step["status"] == "planned" for step in summary["steps"])


def test_demo_failure_after_compose_up_always_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    commands = FakeDemoCommands(fail_on="scenario run")
    monkeypatch.setattr("opspilot.portfolio.demo.shutil.which", lambda _name: "available")
    monkeypatch.setattr(demo, "_ports_are_free", lambda _ports: True)
    runner = PortfolioDemoRunner(
        root=root,
        output=Path(".tmp/demo"),
        build_image=False,
        dry_run=False,
        command_runner=commands,
        readiness_probe=lambda: True,
    )

    assert runner.run() == 2

    assert commands.calls[-1] == ("docker", "compose", "down", "--remove-orphans")
    summary = json.loads((root / ".tmp/demo/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["steps"][-1]["name"] == "compose_down"


def test_demo_readiness_failure_stops_before_workload_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    commands = FakeDemoCommands()
    monkeypatch.setattr("opspilot.portfolio.demo.shutil.which", lambda _name: "available")
    monkeypatch.setattr(demo, "_ports_are_free", lambda _ports: True)
    runner = PortfolioDemoRunner(
        root=root,
        output=Path(".tmp/demo"),
        build_image=False,
        dry_run=False,
        command_runner=commands,
    )
    monkeypatch.setattr(runner, "_wait_for_readiness", lambda: False)

    assert runner.run() == 2

    joined = [" ".join(call) for call in commands.calls]
    assert not any("demo load" in call for call in joined)
    assert joined[-1] == "docker compose down --remove-orphans"


def test_demo_cancellation_propagates_safe_status_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    commands = FakeDemoCommands(interrupt_on="demo load")
    monkeypatch.setattr("opspilot.portfolio.demo.shutil.which", lambda _name: "available")
    monkeypatch.setattr(demo, "_ports_are_free", lambda _ports: True)
    runner = PortfolioDemoRunner(
        root=root,
        output=Path(".tmp/demo"),
        build_image=False,
        dry_run=False,
        command_runner=commands,
        readiness_probe=lambda: True,
    )

    assert runner.run() == 130

    assert commands.calls[-1] == ("docker", "compose", "down", "--remove-orphans")
    summary = json.loads((root / ".tmp/demo/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "cancelled"


def test_demo_build_flag_replaces_image_inspection() -> None:
    without_build = demo_steps(Path(".tmp/demo"), False)
    with_build = demo_steps(Path(".tmp/demo"), True)
    assert without_build[0].name == "verify_image"
    assert with_build[0].name == "build_image"
    assert "--platform" in with_build[0].command


def test_readiness_treats_remote_disconnect_as_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def disconnect(*_args: object, **_kwargs: object) -> object:
        raise http.client.RemoteDisconnected("not ready")

    monkeypatch.setattr("opspilot.portfolio.demo.urllib.request.urlopen", disconnect)
    assert demo._default_readiness_probe() is False


def test_demo_output_is_bounded_to_tmp(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(ValueError, match=r"must remain under \.tmp"):
        PortfolioDemoRunner(
            root=root,
            output=Path("docs/demo"),
            build_image=False,
            dry_run=True,
        )
