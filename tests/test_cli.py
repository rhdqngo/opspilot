from __future__ import annotations

import pytest

from opspilot.cli import main
from opspilot.demo.models import LoadSummary


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
