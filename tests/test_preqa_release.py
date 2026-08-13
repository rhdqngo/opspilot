from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from opspilot.portfolio.preqa_release import (
    IMAGE_ADDRESS,
    RUNTIME_ADDRESS,
    PreQaReleaseRunner,
    _context_matches_source,
    terraform_no_changes,
    terraform_plan_summary,
)

RUNTIME_BYTES = b"deterministic-runtime"
RUNTIME_SHA256 = hashlib.sha256(RUNTIME_BYTES).hexdigest()
IMAGE_DIGEST = f"sha256:{'a' * 64}"


def _change(address: str, actions: list[str], before: object, after: object) -> dict[str, object]:
    return {
        "address": address,
        "mode": "managed",
        "type": address.split(".", 1)[0],
        "name": "fixture",
        "change": {"actions": actions, "before": before, "after": after},
    }


def _allowed_plan() -> dict[str, object]:
    return {
        "resource_changes": [
            _change(
                IMAGE_ADDRESS,
                ["update"],
                {"template": {"containers": [{"image": "old@sha256:" + "b" * 64}]}},
                {"template": {"containers": [{"image": f"registry/investigation@{IMAGE_DIGEST}"}]}},
            ),
            _change(
                RUNTIME_ADDRESS,
                ["update"],
                {"name": "projects/redacted/locations/redacted/reasoningEngines/stable"},
                {
                    "name": "projects/redacted/locations/redacted/reasoningEngines/stable",
                    "source_code": {"source_archive": base64.b64encode(RUNTIME_BYTES).decode()},
                },
            ),
        ]
    }


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _summary(path: Path) -> dict[str, object]:
    return terraform_plan_summary(
        path,
        expected_image_digest=IMAGE_DIGEST,
        expected_runtime_sha256=RUNTIME_SHA256,
    )


def test_preqa_plan_accepts_only_two_expected_in_place_updates(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    _write(path, _allowed_plan())

    summary = _summary(path)

    assert summary == {
        "allowed": True,
        "add": 0,
        "update": 2,
        "destroy": 0,
        "exact_scope": True,
        "actions_valid": True,
        "image_bound": True,
        "runtime_bound": True,
        "runtime_name_stable": True,
        "public_iam_absent": True,
    }


@pytest.mark.parametrize(
    ("mutation", "failure"),
    (
        ("extra", "exact_scope"),
        ("replace", "actions_valid"),
        ("wrong_image", "image_bound"),
        ("wrong_runtime", "runtime_bound"),
        ("runtime_replaced", "runtime_name_stable"),
        ("public_iam", "public_iam_absent"),
    ),
)
def test_preqa_plan_rejects_scope_and_source_binding_drift(
    tmp_path: Path, mutation: str, failure: str
) -> None:
    payload = _allowed_plan()
    changes = payload["resource_changes"]
    assert isinstance(changes, list)
    if mutation == "extra":
        changes.append(_change("google_firestore_database.extra", ["update"], {}, {}))
    elif mutation == "replace":
        changes[0]["change"]["actions"] = ["delete", "create"]
    elif mutation == "wrong_image":
        changes[0]["change"]["after"] = {
            "template": {"containers": [{"image": "registry/wrong@sha256:" + "b" * 64}]}
        }
    elif mutation == "wrong_runtime":
        changes[1]["change"]["after"]["source_code"]["source_archive"] = base64.b64encode(
            b"tampered"
        ).decode()
    elif mutation == "runtime_replaced":
        changes[1]["change"]["after"]["name"] = "replacement"
    else:
        changes[0]["change"]["after"]["member"] = "allUsers"
    path = tmp_path / "plan.json"
    _write(path, payload)

    summary = _summary(path)

    assert summary["allowed"] is False
    assert summary[failure] is False


def test_preqa_plan_rejects_create_delete_and_reports_counts(tmp_path: Path) -> None:
    payload = _allowed_plan()
    changes = payload["resource_changes"]
    assert isinstance(changes, list)
    changes[0]["change"]["actions"] = ["delete", "create"]
    path = tmp_path / "plan.json"
    _write(path, payload)

    summary = _summary(path)

    assert summary["allowed"] is False
    assert (summary["add"], summary["update"], summary["destroy"]) == (1, 1, 1)


def test_preqa_final_plan_requires_all_resources_to_be_noop(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    _write(path, {"resource_changes": [_change(IMAGE_ADDRESS, ["no-op"], {}, {})]})
    assert terraform_no_changes(path) is True

    _write(path, _allowed_plan())
    assert terraform_no_changes(path) is False


def test_preqa_recovery_plan_accepts_only_explicit_allowed_subset(tmp_path: Path) -> None:
    payload = _allowed_plan()
    changes = payload["resource_changes"]
    assert isinstance(changes, list)
    payload["resource_changes"] = changes[:1]
    path = tmp_path / "plan.json"
    _write(path, payload)

    summary = terraform_plan_summary(
        path,
        expected_image_digest=IMAGE_DIGEST,
        expected_runtime_sha256=RUNTIME_SHA256,
        expected_addresses=frozenset({IMAGE_ADDRESS}),
    )

    assert summary["allowed"] is True
    assert summary["exact_scope"] is True
    with pytest.raises(ValueError, match="non-empty allowed subset"):
        terraform_plan_summary(
            path,
            expected_image_digest=IMAGE_DIGEST,
            expected_runtime_sha256=RUNTIME_SHA256,
            expected_addresses=frozenset({"google_project_iam_member.forbidden"}),
        )


def test_release_context_detects_source_context_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "opspilot.portfolio.preqa_release.source_metadata",
        lambda _root: {
            "git_commit": "commit-a",
            "working_tree_dirty": False,
            "source_tree_sha256": "1" * 64,
        },
    )
    context: dict[str, object] = {
        "source": {
            "git_commit": "commit-a",
            "working_tree_dirty": False,
            "source_tree_sha256": "1" * 64,
        },
        "runtime": {"file_count": 11, "sha256": "2" * 64},
    }
    assert _context_matches_source(context, tmp_path) is True
    source = context["source"]
    assert isinstance(source, dict)
    source["source_tree_sha256"] = "3" * 64
    assert _context_matches_source(context, tmp_path) is False


def test_record_rejects_unknown_or_missing_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    output = root / ".tmp" / "preqa"
    output.mkdir(parents=True)
    source = {
        "git_commit": "commit-a",
        "working_tree_dirty": False,
        "source_tree_sha256": "1" * 64,
    }
    monkeypatch.setattr("opspilot.portfolio.preqa_release.source_metadata", lambda _root: source)
    _write(
        output / "release-context.json",
        {"source": source, "runtime": {"file_count": 11, "sha256": "2" * 64}},
    )
    _write(
        output / "final-plan-input.json",
        {"terraform_no_changes": True, "unexpected": True},
    )

    exit_code, artifact = PreQaReleaseRunner(root=root, output=Path(".tmp/preqa")).record(
        "final-plan"
    )

    assert exit_code == 2
    assert artifact["checks"]["fixed_schema"] is False  # type: ignore[index]


def test_terraform_plan_keeps_raw_plan_separate_from_phase_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    output = root / ".tmp" / "preqa"
    output.mkdir(parents=True)
    source = {
        "git_commit": "commit-a",
        "working_tree_dirty": False,
        "source_tree_sha256": "1" * 64,
    }
    monkeypatch.setattr("opspilot.portfolio.preqa_release.source_metadata", lambda _root: source)
    monkeypatch.setenv("OPSPILOT_PREQA_IMAGE_DIGEST", IMAGE_DIGEST)
    _write(
        output / "release-context.json",
        {"source": source, "runtime": {"file_count": 11, "sha256": RUNTIME_SHA256}},
    )
    _write(output / "terraform-plan-raw.json", _allowed_plan())
    (output / "preqa.tfplan").write_bytes(b"reviewed-plan")

    exit_code, artifact = PreQaReleaseRunner(root=root, output=Path(".tmp/preqa")).terraform_plan()

    assert exit_code == 0
    assert artifact["status"] == "passed"
    assert (output / "terraform-plan-raw.json").is_file()
    assert json.loads((output / "terraform-plan.json").read_text())["phase"] == "terraform-plan"
