"""Recorded synthetic scenario fixture loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from opspilot.domain import EvidenceItem, ReportStatus, SourceType


class ScenarioActionFixture(BaseModel):
    category: str = "MITIGATION"
    title: str
    description: str
    target_service: str | None = None
    risk_level: str = "HIGH"
    requires_approval: bool = True
    prerequisites: list[str] = Field(default_factory=list)
    expected_effect: str
    rollback_method: str | None = None
    verification_steps: list[str] = Field(default_factory=list)


class ScenarioTimelineFixture(BaseModel):
    offset_minutes: int = Field(ge=0, le=120)
    event_type: str
    description: str


class ScenarioFixture(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    incident_id: str = Field(pattern=r"^INC-\d{4}-\d{4}$")
    title: str
    expected_root_cause: str
    root_cause_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    primary_service: str
    expected_report_status: ReportStatus = ReportStatus.IDENTIFIED
    severity: str = "SEV-2"
    mechanism: str
    impact_summary: str
    required_evidence_types: list[SourceType] = Field(default_factory=list)
    minimum_evidence_count: int = Field(default=2, ge=1, le=4)
    next_checks: list[str] = Field(default_factory=list)
    expected_tools_any_order: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    expected_action: str | None = None
    must_request_approval: bool = False
    action: ScenarioActionFixture | None = None
    expected_timeline: list[ScenarioTimelineFixture] = Field(default_factory=list)
    evidence: list[EvidenceItem]

    @model_validator(mode="after")
    def validate_contract(self) -> ScenarioFixture:
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("scenario evidence IDs must be unique")
        if self.must_request_approval and (
            self.action is None or not self.action.requires_approval
        ):
            raise ValueError("approval-required scenarios need an approval-required action")
        if self.expected_report_status == ReportStatus.INCONCLUSIVE and self.action is not None:
            raise ValueError("inconclusive scenarios cannot define a recommended action")
        return self


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
