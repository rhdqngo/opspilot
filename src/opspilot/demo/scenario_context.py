"""Strict request-scoped synthetic scenario context."""

from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel, Field

SCENARIO_HEADER = "X-OpsPilot-Scenario"
RUN_HEADER = "X-OpsPilot-Scenario-Run"
STEP_HEADER = "X-OpsPilot-Scenario-Step"
RUN_PATTERN = re.compile(r"^RUN-SCN-001-[A-Z0-9]{12}$")


class ScenarioContext(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-001$")
    run_id: str = Field(pattern=r"^RUN-SCN-001-[A-Z0-9]{12}$")
    step: int = Field(ge=1, le=10)

    @property
    def inject_payment_failure(self) -> bool:
        return self.step <= 6

    def headers(self) -> dict[str, str]:
        return {
            SCENARIO_HEADER: self.scenario_id,
            RUN_HEADER: self.run_id,
            STEP_HEADER: str(self.step),
        }


class ScenarioContextError(ValueError):
    pass


def parse_scenario_context(
    headers: Mapping[str, str], *, scenarios_enabled: bool
) -> ScenarioContext | None:
    values = (
        headers.get(SCENARIO_HEADER),
        headers.get(RUN_HEADER),
        headers.get(STEP_HEADER),
    )
    if all(value is None for value in values):
        return None
    if not scenarios_enabled:
        raise ScenarioContextError("scenario injection is disabled")
    if any(value is None for value in values):
        raise ScenarioContextError("scenario context is incomplete")
    scenario_id, run_id, raw_step = values
    if scenario_id != "SCN-001" or run_id is None or not RUN_PATTERN.fullmatch(run_id):
        raise ScenarioContextError("scenario context is invalid")
    try:
        step = int(raw_step or "")
    except ValueError as exc:
        raise ScenarioContextError("scenario context is invalid") from exc
    try:
        return ScenarioContext(scenario_id=scenario_id, run_id=run_id, step=step)
    except ValueError as exc:
        raise ScenarioContextError("scenario context is invalid") from exc
