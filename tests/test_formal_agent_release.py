from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from opspilot.portfolio.formal_agent_release import FormalPlanPhase, formal_plan_summary


def _write(path: Path, changes: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"resource_changes": changes}), encoding="utf-8")


def _change(address: str, actions: list[str], after: object) -> dict[str, object]:
    return {"address": address, "change": {"actions": actions, "before": {}, "after": after}}


def test_formal_release_accepts_only_phase_owned_workloads(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write(
        plan,
        [
            _change(
                'google_cloud_run_v2_service.formal_payment["prod-sim"]',
                ["create"],
                {"name": "synthetic-payment"},
            ),
            _change(
                'google_service_account.formal_demo["staging-order"]',
                ["create"],
                {"account_id": "synthetic-order"},
            ),
        ],
    )

    assert formal_plan_summary(plan, phase=FormalPlanPhase.WORKLOADS)["allowed"] is True

    _write(plan, [_change("google_project_iam_member.unreviewed", ["create"], {})])
    assert formal_plan_summary(plan, phase=FormalPlanPhase.WORKLOADS)["allowed"] is False


def test_formal_release_accepts_investigation_prerequisites(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write(
        plan,
        [
            _change(
                "google_project_iam_custom_role.investigation_store[0]",
                ["update"],
                {"permissions": ["aiplatform.endpoints.predict"]},
            ),
            _change(
                "google_firestore_field.conversation_context_ttl[0]",
                ["create"],
                {"collection": "conversation_contexts", "field": "expires_at"},
            ),
        ],
    )
    assert formal_plan_summary(plan, phase=FormalPlanPhase.INVESTIGATION)["allowed"] is True


def test_formal_release_binds_cutover_image_and_runtime_bytes(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    digest = "sha256:" + "a" * 64
    _write(
        plan,
        [
            _change(
                "google_cloud_run_v2_service.investigation_api[0]",
                ["update"],
                {"template": {"containers": [{"image": f"registry/image@{digest}"}]}},
            )
        ],
    )
    assert (
        formal_plan_summary(
            plan,
            phase=FormalPlanPhase.REMEDIATION,
            expected_image_digest=digest,
        )["allowed"]
        is True
    )

    archive = b"immutable-runtime"
    runtime_hash = hashlib.sha256(archive).hexdigest()
    _write(
        plan,
        [
            _change(
                "google_vertex_ai_reasoning_engine.opspilot[0]",
                ["update"],
                {"source_archive": base64.b64encode(archive).decode()},
            )
        ],
    )
    assert (
        formal_plan_summary(
            plan,
            phase=FormalPlanPhase.RUNTIME,
            expected_runtime_sha256=runtime_hash,
        )["allowed"]
        is True
    )


def test_formal_release_allows_only_named_m8_replacements_and_never_public_invoker(
    tmp_path: Path,
) -> None:
    plan = tmp_path / "plan.json"
    expected = "google_cloud_run_v2_service_iam_member.remediation_executor_payment[0]"
    digest = "sha256:" + "a" * 64
    _write(
        plan,
        [
            _change(expected, ["delete", "create"], {"member": "serviceAccount:safe"}),
            _change(
                "google_cloud_run_v2_service.investigation_api[0]",
                ["update"],
                {"template": {"containers": [{"image": f"registry/image@{digest}"}]}},
            ),
        ],
    )
    summary = formal_plan_summary(
        plan,
        phase=FormalPlanPhase.REMEDIATION,
        expected_image_digest=digest,
    )
    assert summary["allowed"] is True
    assert summary["replacements"] == [expected]

    _write(
        plan,
        [
            _change(
                "google_cloud_run_v2_service.remediation_control[0]",
                ["update"],
                {"member": "allUsers"},
            )
        ],
    )
    assert (
        formal_plan_summary(
            plan,
            phase=FormalPlanPhase.REMEDIATION,
            expected_image_digest=digest,
        )["allowed"]
        is False
    )
