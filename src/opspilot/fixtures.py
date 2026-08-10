"""Recorded synthetic scenario fixture loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from opspilot.domain import EvidenceItem


class ScenarioFixture(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    incident_id: str = Field(pattern=r"^INC-\d{4}-\d{4}$")
    title: str
    expected_root_cause: str
    evidence: list[EvidenceItem]


def default_fixture_dir() -> Path:
    return Path.cwd() / "scenarios" / "fixtures"


def load_scenario_fixture(scenario_id: str, fixture_dir: Path | None = None) -> ScenarioFixture:
    if not scenario_id.startswith("SCN-") or not scenario_id[4:].isdigit():
        raise ValueError("scenario ID must use SCN-NNN format")
    path = (fixture_dir or default_fixture_dir()) / f"{scenario_id}.json"
    if not path.is_file():
        raise ValueError(f"unknown scenario: {scenario_id}")
    with path.open(encoding="utf-8") as stream:
        payload: Any = json.load(stream)
    return ScenarioFixture.model_validate(payload)
