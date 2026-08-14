"""Four-phase Terraform plan guard for the formal Incident Commander rollout."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import cast

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}$")


class FormalPlanPhase(StrEnum):
    WORKLOADS = "workloads"
    INVESTIGATION = "investigation"
    RUNTIME = "runtime"
    REMEDIATION = "remediation"


PHASE_ADDRESS_PATTERNS: dict[FormalPlanPhase, tuple[re.Pattern[str], ...]] = {
    FormalPlanPhase.WORKLOADS: (
        re.compile(
            r'^google_service_account\.formal_demo\["(?:staging|prod-sim)-(?:order|payment|inventory)"\]$'
        ),
        re.compile(
            r'^google_cloud_run_v2_service\.formal_(?:order|payment|inventory)\["(?:staging|prod-sim)"\]$'
        ),
        re.compile(
            r'^google_cloud_run_v2_service_iam_member\.formal_order_invokes_(?:payment|inventory)\["(?:staging|prod-sim)"\]$'
        ),
    ),
    FormalPlanPhase.INVESTIGATION: (
        re.compile(r"^google_project_iam_custom_role\.investigation_store\[0\]$"),
        re.compile(r"^google_firestore_field\.conversation_context_ttl\[0\]$"),
    ),
    FormalPlanPhase.RUNTIME: (re.compile(r"^google_vertex_ai_reasoning_engine\.opspilot\[0\]$"),),
    FormalPlanPhase.REMEDIATION: (
        re.compile(r"^google_cloud_run_v2_service\.remediation_(?:control|executor)\[0\]$"),
        re.compile(r"^google_cloud_run_v2_service\.investigation_api\[0\]$"),
        re.compile(r"^google_cloud_run_v2_service_iam_member\.remediation_executor_payment\[0\]$"),
        re.compile(
            r"^google_service_account_iam_member\.remediation_executor_acts_as_payment\[0\]$"
        ),
        re.compile(r"^google_cloud_run_v2_service_iam_member\.control_invokes_order\[0\]$"),
        re.compile(
            r"^google_cloud_run_v2_service_iam_member\.investigation_invokes_remediation_control\[0\]$"
        ),
    ),
}

EXPECTED_REPLACEMENTS = frozenset(
    {
        "google_cloud_run_v2_service_iam_member.remediation_executor_payment[0]",
        "google_service_account_iam_member.remediation_executor_acts_as_payment[0]",
        "google_cloud_run_v2_service_iam_member.control_invokes_order[0]",
    }
)


def _read_json(path: Path) -> dict[str, object]:
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


def _address_allowed(phase: FormalPlanPhase, address: str) -> bool:
    return any(pattern.fullmatch(address) for pattern in PHASE_ADDRESS_PATTERNS[phase])


def _actions_allowed(phase: FormalPlanPhase, address: str, actions: object) -> bool:
    if actions in (["create"], ["update"]):
        return True
    return (
        phase is FormalPlanPhase.REMEDIATION
        and address in EXPECTED_REPLACEMENTS
        and isinstance(actions, list)
        and len(actions) == 2
        and set(actions) == {"create", "delete"}
    )


def formal_plan_summary(
    path: Path,
    *,
    phase: FormalPlanPhase,
    expected_image_digest: str | None = None,
    expected_runtime_sha256: str | None = None,
) -> dict[str, object]:
    """Reject cross-phase drift, unreviewed replacement, and public access."""

    if (
        expected_image_digest is not None
        and DIGEST_PATTERN.fullmatch(expected_image_digest) is None
    ):
        raise ValueError("expected investigation image digest is invalid")
    if (
        expected_runtime_sha256 is not None
        and SHA256_PATTERN.fullmatch(expected_runtime_sha256) is None
    ):
        raise ValueError("expected Runtime SHA-256 is invalid")
    if phase is FormalPlanPhase.REMEDIATION and expected_image_digest is None:
        raise ValueError("remediation cutover phase requires the reviewed image digest")
    if phase is FormalPlanPhase.RUNTIME and expected_runtime_sha256 is None:
        raise ValueError("runtime phase requires the reviewed archive SHA-256")

    raw_changes = _read_json(path).get("resource_changes", [])
    if not isinstance(raw_changes, list):
        raise ValueError("Terraform resource_changes must be a list")
    changed: list[str] = []
    action_scope_valid = True
    public_invoker_absent = True
    image_bound = phase is not FormalPlanPhase.REMEDIATION
    runtime_bound = phase is not FormalPlanPhase.RUNTIME
    replacements: list[str] = []
    for raw in raw_changes:
        if not isinstance(raw, dict) or not isinstance(raw.get("change"), dict):
            action_scope_valid = False
            continue
        address = str(raw.get("address", ""))
        change = cast(dict[str, object], raw["change"])
        actions = change.get("actions")
        if actions == ["no-op"]:
            continue
        changed.append(address)
        if not _address_allowed(phase, address) or not _actions_allowed(phase, address, actions):
            action_scope_valid = False
        if isinstance(actions, list) and "delete" in actions:
            replacements.append(address)
        after = change.get("after")
        serialized_after = json.dumps(after, sort_keys=True)
        if "allUsers" in serialized_after or "allAuthenticatedUsers" in serialized_after:
            public_invoker_absent = False
        if address == "google_cloud_run_v2_service.investigation_api[0]":
            images = [str(item) for item in _walk_key(after, "image") if isinstance(item, str)]
            image_bound = any(item.endswith(f"@{expected_image_digest}") for item in images)
        if address == "google_vertex_ai_reasoning_engine.opspilot[0]":
            archives = [
                item for item in _walk_key(after, "source_archive") if isinstance(item, str)
            ]
            hashes: list[str] = []
            for archive in archives:
                try:
                    hashes.append(
                        hashlib.sha256(base64.b64decode(archive, validate=True)).hexdigest()
                    )
                except (binascii.Error, ValueError):
                    continue
            runtime_bound = expected_runtime_sha256 in hashes
    allowed = bool(changed) and all(
        (action_scope_valid, public_invoker_absent, image_bound, runtime_bound)
    )
    return {
        "phase": phase.value,
        "allowed": allowed,
        "changed_addresses": sorted(changed),
        "changed_count": len(changed),
        "replacements": sorted(replacements),
        "action_scope_valid": action_scope_valid,
        "public_invoker_absent": public_invoker_absent,
        "image_bound": image_bound,
        "runtime_bound": runtime_bound,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--phase", choices=[item.value for item in FormalPlanPhase], required=True)
    parser.add_argument("--image-digest")
    parser.add_argument("--runtime-sha256")
    args = parser.parse_args(argv)
    summary = formal_plan_summary(
        args.plan_json,
        phase=FormalPlanPhase(args.phase),
        expected_image_digest=args.image_digest,
        expected_runtime_sha256=args.runtime_sha256,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["allowed"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
