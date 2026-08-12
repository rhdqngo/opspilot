from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from opspilot.portfolio import remediation_release
from opspilot.portfolio.remediation_release import (
    ARTIFACT_SCHEMA_VERSION,
    ProcessResult,
    RemediationReleaseRunner,
)


class FakeProcesses:
    def __init__(self, *, failed: str | None = None) -> None:
        self.failed = failed
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, command: Sequence[str], root: Path, environment: Mapping[str, str]
    ) -> ProcessResult:
        del root
        assert environment["UV_CACHE_DIR"]
        call = tuple(command)
        self.calls.append(call)
        joined = " ".join(call)
        return ProcessResult(1 if self.failed and self.failed in joined else 0, "configured")


class FakeProbe:
    def __init__(self, *, abort_used: bool = False) -> None:
        self.abort_used = abort_used

    def post_apply(self) -> dict[str, object]:
        return {
            "control_ready": True,
            "executor_ready": True,
            "unauthenticated_control_denied": True,
            "approver_control_allowed": True,
        }

    def e2e(self, recovery_path: Path) -> dict[str, object]:
        assert recovery_path.name == "recovery.json"
        return {
            "checks": {
                "abort_not_used": not self.abort_used,
                "preapproval_updates": True,
                "postapproval_updates": True,
                "terraform_no_changes": True,
            },
            "image_digest": "sha256:" + "a" * 64,
            "orders": {
                "baseline_successes": 10,
                "faulty_successes": 0,
                "recovery_successes": 10,
                "reset_successes": 10,
            },
            "audit": {
                "state_transitions": [
                    "WAITING_APPROVAL",
                    "APPROVED",
                    "EXECUTING",
                    "SUCCEEDED",
                ],
                "actor_hash_present": True,
                "self_approved": True,
                "execution_attempt_count": 1,
            },
            "traffic_updates": {"before_approval": 0, "after_approval": 1},
            "verification": {
                "target_traffic_percent": 100,
                "order_successes": 10,
                "metric_windows_recorded": True,
            },
        }


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".tmp").mkdir(parents=True)
    return root


def _clean_source(_: Path) -> dict[str, object]:
    return {
        "git_commit": "abc123",
        "working_tree_dirty": False,
        "source_tree_sha256": "0" * 64,
    }


def _write_allowed_plan(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "terraform-plan.json").write_text(
        json.dumps(
            {
                "resource_changes": [
                    {"change": {"actions": ["create"]}},
                    {"change": {"actions": ["no-op"]}},
                ]
            }
        ),
        encoding="utf-8",
    )


def test_M8_preflight_is_read_only_and_aggregates_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    commands = FakeProcesses(failed="docker info")
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    monkeypatch.setattr(shutil, "which", lambda _: "available")
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=commands,
        probe=FakeProbe(),
    )

    code, artifact = runner.preflight()

    assert code == 2
    assert artifact["status"] == "failed"
    failure_codes = artifact["failure_codes"]
    assert isinstance(failure_codes, list)
    assert "docker_daemon" in failure_codes
    joined = [" ".join(value) for value in commands.calls]
    assert not any("docker push" in value for value in joined)
    assert not any("terraform apply" in value for value in joined)
    assert not any("--mode execute" in value for value in joined)
    assert not any("remediation decide" in value for value in joined)
    assert any("--auth gcloud" in value for value in joined if "scenario prepare" in value)
    assert any(value.startswith("available auth list") for value in joined)


def test_M8_verify_sanitizes_results_and_abort_blocks_e2e(tmp_path: Path) -> None:
    root = _root(tmp_path)
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=FakeProcesses(),
        probe=FakeProbe(abort_used=True),
    )
    _write_allowed_plan(runner.output)
    code, artifact = runner.verify("e2e")
    assert code == 2
    assert artifact["failure_codes"] == ["abort_not_used"]
    serialized = json.dumps(artifact)
    for forbidden in ("project_id", "callback_url", 'actor_hash"', "remediation_id"):
        assert forbidden not in serialized


def test_M8_publish_requires_every_clean_phase_and_writes_only_sanitized_evidence(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=FakeProcesses(),
        probe=FakeProbe(),
    )
    runner.output.mkdir(parents=True)
    _write_allowed_plan(runner.output)
    preflight = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "phase": "preflight",
        "status": "passed",
        "source": _clean_source(root),
        "checks": {"clean_working_tree": True},
        "failure_codes": [],
    }
    (runner.output / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
    runner.verify("post-apply")
    runner.verify("e2e")

    code, artifact = runner.publish()

    assert code == 0
    assert artifact["status"] == "passed"
    published = root / "docs/portfolio/results/remediation-release-v1.json"
    assert published.is_file()
    serialized = published.read_text(encoding="utf-8")
    assert "sha256:" in serialized
    for forbidden in (
        "project_id",
        "region",
        "callback_url",
        "workflow_execution",
        "remediation_id",
        'actor_hash"',
    ):
        assert forbidden not in serialized


def test_M8_failed_publish_does_not_replace_tracked_artifact(tmp_path: Path) -> None:
    root = _root(tmp_path)
    destination = root / "docs/portfolio/results"
    destination.mkdir(parents=True)
    tracked = destination / "remediation-release-v1.json"
    tracked.write_text("old\n", encoding="utf-8")
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=FakeProcesses(),
        probe=FakeProbe(),
    )
    runner.output.mkdir(parents=True)
    for phase in ("preflight", "post-apply", "e2e"):
        (runner.output / f"{phase}.json").write_text(
            json.dumps({"phase": phase, "status": "failed"}), encoding="utf-8"
        )
    code, _ = runner.publish()
    assert code == 2
    assert tracked.read_text(encoding="utf-8") == "old\n"


def test_M8_release_output_is_bounded_to_tmp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"must remain under \.tmp"):
        RemediationReleaseRunner(root=_root(tmp_path), output=Path("docs/results"))
