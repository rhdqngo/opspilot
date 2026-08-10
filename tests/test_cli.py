from __future__ import annotations

import pytest

from opspilot.cli import main


def test_FR_020_cli_replays_SCN_001_as_markdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["replay", "--scenario", "SCN-001", "--format", "markdown"])
    assert exit_code == 0
    assert "EV-LOG-0001" in capsys.readouterr().out
