"""Terraform plan guard for the bounded scheduled SCN-001 portfolio experience."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}$")
BOOTSTRAP_ADDRESS = "google_project_iam_custom_role.ci_plan_reader"
BOOTSTRAP_PERMISSIONS = frozenset(
    {
        "cloudscheduler.jobs.get",
        "cloudscheduler.jobs.list",
        "run.jobs.get",
        "run.jobs.getIamPolicy",
        "run.jobs.list",
    }
)
DEV_ADDRESSES = frozenset(
    {
        'google_project_service.m1["cloudscheduler.googleapis.com"]',
        "google_service_account.scheduled_scenario_runner[0]",
        "google_service_account.scheduled_scenario_trigger[0]",
        "google_cloud_run_v2_job.scheduled_scn001[0]",
        "google_cloud_scheduler_job.scheduled_scn001[0]",
        "google_cloud_run_v2_service_iam_member.scheduled_runner_invokes_dev_order[0]",
        "google_cloud_run_v2_job_iam_member.scheduler_invokes_scn001[0]",
    }
)


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Terraform plan JSON must be an object")
    return cast(dict[str, object], value)


def _walk_key(value: object, key: str) -> list[object]:
    found: list[object] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key:
                found.append(child)
            found.extend(_walk_key(child, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_key(child, key))
    return found


def _changes(path: Path) -> list[dict[str, object]]:
    raw = _read(path).get("resource_changes", [])
    if not isinstance(raw, list):
        raise ValueError("Terraform resource_changes must be a list")
    return [cast(dict[str, object], item) for item in raw if isinstance(item, dict)]


def bootstrap_plan_summary(path: Path) -> dict[str, object]:
    changes = []
    permissions_valid = False
    for item in _changes(path):
        change = item.get("change")
        if not isinstance(change, dict) or change.get("actions") == ["no-op"]:
            continue
        address = str(item.get("address", ""))
        changes.append(address)
        if address != BOOTSTRAP_ADDRESS or change.get("actions") != ["update"]:
            continue
        before = {
            str(permission)
            for value in _walk_key(change.get("before"), "permissions")
            if isinstance(value, list)
            for permission in value
            if isinstance(permission, str)
        }
        after = {
            str(permission)
            for value in _walk_key(change.get("after"), "permissions")
            if isinstance(value, list)
            for permission in value
            if isinstance(permission, str)
        }
        permissions_valid = after - before == BOOTSTRAP_PERMISSIONS and before <= after
    allowed = changes == [BOOTSTRAP_ADDRESS] and permissions_valid
    return {
        "phase": "bootstrap",
        "allowed": allowed,
        "changed_addresses": changes,
        "update": len(changes),
        "permissions_valid": permissions_valid,
    }


def dev_plan_summary(path: Path, *, expected_image_digest: str) -> dict[str, object]:
    if DIGEST_PATTERN.fullmatch(expected_image_digest) is None:
        raise ValueError("scheduled scenario image digest is invalid")
    changed: list[str] = []
    actions_valid = True
    public_iam_absent = True
    image_bound = False
    for item in _changes(path):
        change = item.get("change")
        if not isinstance(change, dict) or change.get("actions") == ["no-op"]:
            continue
        address = str(item.get("address", ""))
        changed.append(address)
        if address not in DEV_ADDRESSES or change.get("actions") != ["create"]:
            actions_valid = False
        after = change.get("after")
        serialized = json.dumps(after, sort_keys=True)
        if "allUsers" in serialized or "allAuthenticatedUsers" in serialized:
            public_iam_absent = False
        if address == "google_cloud_run_v2_job.scheduled_scn001[0]":
            images = [str(value) for value in _walk_key(after, "image") if isinstance(value, str)]
            image_bound = any(value.endswith(f"@{expected_image_digest}") for value in images)
    exact_scope = set(changed) == DEV_ADDRESSES and len(changed) == len(DEV_ADDRESSES)
    allowed = all((exact_scope, actions_valid, public_iam_absent, image_bound))
    return {
        "phase": "dev",
        "allowed": allowed,
        "add": len(changed),
        "update": 0,
        "destroy": 0,
        "changed_addresses": sorted(changed),
        "exact_scope": exact_scope,
        "actions_valid": actions_valid,
        "public_iam_absent": public_iam_absent,
        "image_bound": image_bound,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--phase", choices=("bootstrap", "dev"), required=True)
    parser.add_argument("--image-digest")
    args = parser.parse_args(argv)
    if args.phase == "bootstrap":
        summary = bootstrap_plan_summary(args.plan_json)
    else:
        if args.image_digest is None:
            parser.error("--image-digest is required for the dev phase")
        summary = dev_plan_summary(args.plan_json, expected_image_digest=args.image_digest)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["allowed"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
