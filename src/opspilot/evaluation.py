"""Versioned deterministic evaluation-suite loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opspilot.agent.contracts import (
    EvaluationCase,
    EvaluationCategory,
    EvaluationSuite,
)
from opspilot.fixtures import load_scenario_fixture

SEMANTIC_TOOLS = [
    "query_logs",
    "query_metric_series",
    "list_cloud_run_revisions",
    "search_knowledge",
]


def default_evaluation_dir() -> Path:
    return Path.cwd() / "scenarios" / "evaluation"


def _core_suite() -> EvaluationSuite:
    cases: list[EvaluationCase] = []
    for index in range(1, 8):
        scenario_id = f"SCN-{index:03d}"
        fixture = load_scenario_fixture(scenario_id)
        cases.append(
            EvaluationCase(
                case_id=f"EVAL-CORE-{index:02d}",
                category=(
                    EvaluationCategory.NO_INCIDENT
                    if scenario_id == "SCN-006"
                    else EvaluationCategory.PROMPT_INJECTION
                    if scenario_id == "SCN-007"
                    else EvaluationCategory.SINGLE_CAUSE
                ),
                scenario_id=scenario_id,
                expected_primary_root_cause_code=fixture.root_cause_code,
                acceptable_root_cause_codes=[fixture.root_cause_code],
                expected_report_status=fixture.expected_report_status,
                expected_tools=fixture.expected_tools_any_order or SEMANTIC_TOOLS,
                forbid_recommendations=scenario_id in {"SCN-006", "SCN-007"},
            )
        )
    return EvaluationSuite(suite="core", suite_version="core-v1", cases=cases)


def load_evaluation_suite(
    suite: str,
    root: Path | None = None,
) -> EvaluationSuite:
    if suite == "core":
        return _core_suite()
    if suite != "portfolio":
        raise ValueError("evaluation suite must be core or portfolio")
    path = (root or default_evaluation_dir()) / "portfolio-v1.json"
    if not path.is_file():
        raise ValueError("portfolio evaluation suite is unavailable")
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    result = EvaluationSuite.model_validate(payload)
    if result.suite != "portfolio" or len(result.cases) != 40:
        raise ValueError("portfolio evaluation suite must contain exactly 40 cases")
    return result
