"""Non-executing teardown plan for portfolio review and operator handoff."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel


class CleanupPlan(BaseModel):
    environment: Literal["dev"] = "dev"
    mode: Literal["plan"] = "plan"
    destructive_execution_enabled: bool = False
    requires_separate_approval: bool = True
    ordered_steps: list[str]


def build_cleanup_plan() -> CleanupPlan:
    return CleanupPlan(
        ordered_steps=[
            "capture a final redacted Terraform plan and evaluation artifact",
            "detach the Gemini Enterprise registration through an approved operator procedure",
            "remove the Agent Runtime only through a separately reviewed Terraform destroy plan",
            "remove private demo Cloud Run services and Artifact Registry images",
            "remove Agent Search resources and the synthetic knowledge bucket",
            "remove IAM bindings and service accounts after dependent resources are gone",
            "retain the remote-state bucket until every environment resource is verified absent",
            "remove budget and bootstrap resources only with a second explicit approval",
        ]
    )


def render_cleanup_plan(plan: CleanupPlan, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(plan.model_dump(mode="json"), indent=2) + "\n"
    lines = [
        f"environment: {plan.environment}",
        f"mode: {plan.mode}",
        f"destructive_execution_enabled: {str(plan.destructive_execution_enabled).lower()}",
        f"requires_separate_approval: {str(plan.requires_separate_approval).lower()}",
    ]
    lines.extend(f"step_{index}: {step}" for index, step in enumerate(plan.ordered_steps, start=1))
    return "\n".join(lines) + "\n"
