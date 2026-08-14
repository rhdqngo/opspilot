from __future__ import annotations

import json
from pathlib import Path

from opspilot.portfolio.scheduled_scenario_release import (
    BOOTSTRAP_ADDRESS,
    BOOTSTRAP_PERMISSIONS,
    DEV_ADDRESSES,
    bootstrap_plan_summary,
    dev_plan_summary,
)


def _write(path: Path, changes: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"resource_changes": changes}), encoding="utf-8")


def _change(address: str, actions: list[str], before: object, after: object) -> dict[str, object]:
    return {
        "address": address,
        "change": {"actions": actions, "before": before, "after": after},
    }


def test_bootstrap_plan_allows_only_five_read_permissions(tmp_path: Path) -> None:
    plan = tmp_path / "bootstrap.json"
    existing = ["run.services.get"]
    _write(
        plan,
        [
            _change(
                BOOTSTRAP_ADDRESS,
                ["update"],
                {"permissions": existing},
                {"permissions": existing + sorted(BOOTSTRAP_PERMISSIONS)},
            )
        ],
    )

    assert bootstrap_plan_summary(plan)["allowed"] is True

    _write(
        plan,
        [
            _change(
                BOOTSTRAP_ADDRESS,
                ["update"],
                {"permissions": existing},
                {"permissions": [*existing, "run.jobs.run"]},
            )
        ],
    )
    assert bootstrap_plan_summary(plan)["allowed"] is False


def test_dev_plan_requires_exact_seven_creates_and_image_digest(tmp_path: Path) -> None:
    plan = tmp_path / "dev.json"
    digest = "sha256:" + "a" * 64
    changes = []
    for address in DEV_ADDRESSES:
        after: object = {"name": "bounded"}
        if address == "google_cloud_run_v2_job.scheduled_scn001[0]":
            after = {"template": {"containers": [{"image": f"registry/runner@{digest}"}]}}
        changes.append(_change(address, ["create"], None, after))
    _write(plan, changes)

    summary = dev_plan_summary(plan, expected_image_digest=digest)
    assert summary["allowed"] is True
    assert summary["add"] == 7

    changes.append(_change("google_project_iam_member.broad", ["create"], None, {}))
    _write(plan, changes)
    assert dev_plan_summary(plan, expected_image_digest=digest)["allowed"] is False


def test_dev_plan_rejects_public_invoker_and_replacement(tmp_path: Path) -> None:
    plan = tmp_path / "dev.json"
    digest = "sha256:" + "b" * 64
    changes = []
    for address in DEV_ADDRESSES:
        after: object = {"name": "bounded"}
        if address == "google_cloud_run_v2_job.scheduled_scn001[0]":
            after = {"image": f"registry/runner@{digest}"}
        if address.endswith("scheduler_invokes_scn001[0]"):
            after = {"member": "allUsers"}
        changes.append(_change(address, ["create"], None, after))
    _write(plan, changes)
    assert dev_plan_summary(plan, expected_image_digest=digest)["allowed"] is False

    changes[-1]["change"] = {"actions": ["delete", "create"], "before": {}, "after": {}}
    _write(plan, changes)
    assert dev_plan_summary(plan, expected_image_digest=digest)["allowed"] is False
