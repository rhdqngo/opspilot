from __future__ import annotations

import json
import shutil
import time
from collections.abc import Mapping, Sequence
from http.client import RemoteDisconnected
from pathlib import Path

import pytest

from opspilot.portfolio import remediation_release
from opspilot.portfolio.remediation_release import (
    ALLOWED_M8_CREATE_ADDRESSES,
    ALLOWED_M8_MOVES,
    ARTIFACT_SCHEMA_VERSION,
    ProcessResult,
    RemediationReleaseRunner,
    terraform_plan_summary,
)

DIGEST = "sha256:" + "a" * 64


def test_M8_status_code_treats_startup_disconnect_as_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def disconnect(*_args: object, **_kwargs: object) -> object:
        raise RemoteDisconnected("not ready")

    monkeypatch.setattr(remediation_release, "urlopen", disconnect)

    assert remediation_release._status_code("http://127.0.0.1:49153/health") == 0


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

    def post_apply(self, expected_image_digest: str) -> dict[str, object]:
        assert expected_image_digest == DIGEST
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
            "payment_image_digest": "sha256:" + "b" * 64,
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
        "git_commit": "a" * 40,
        "working_tree_dirty": False,
        "source_tree_sha256": "0" * 64,
    }


def _write_allowed_plan(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    changes: list[dict[str, object]] = []
    for address in sorted(ALLOWED_M8_CREATE_ADDRESSES):
        after: dict[str, object] = {}
        if address.startswith("google_cloud_run_v2_service.remediation_"):
            after = {"template": [{"containers": [{"image": f"registry/image@{DIGEST}"}]}]}
        changes.append({"address": address, "change": {"actions": ["create"], "after": after}})
    for previous, address in sorted(ALLOWED_M8_MOVES):
        changes.append(
            {
                "address": address,
                "previous_address": previous,
                "change": {"actions": ["no-op"]},
            }
        )
    (output / "terraform-plan.json").write_text(
        json.dumps({"resource_changes": changes}),
        encoding="utf-8",
    )
    (output / "remediation.tfplan").write_bytes(b"reviewed binary plan")


def _write_image_phase(output: Path, source: Mapping[str, object]) -> None:
    (output / "image.json").write_text(
        json.dumps(
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "phase": "image",
                "status": "passed",
                "source": dict(source),
                "checks": {"registry_digest_verified": True},
                "failure_codes": [],
                "image": {
                    "digest": DIGEST,
                    "platform": "linux/amd64",
                    "container_user": "65532:65532",
                    "control_health": True,
                    "executor_health": True,
                },
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
    scenario_plans = [value for value in joined if "opspilot scenario" in value]
    assert len(scenario_plans) == 3
    assert all("--auth gcloud" in value for value in scenario_plans)
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


def test_M8_terraform_plan_requires_exact_addresses_moves_and_images(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write_allowed_plan(root / ".tmp/m8-release")

    allowed = terraform_plan_summary(
        root / ".tmp/m8-release/terraform-plan.json", expected_image_digest=DIGEST
    )
    assert allowed["allowed"] is True
    assert allowed["create"] == 21

    payload = json.loads((root / ".tmp/m8-release/terraform-plan.json").read_text())
    payload["resource_changes"][0]["address"] = "google_storage_bucket.unexpected[0]"
    (root / ".tmp/m8-release/terraform-plan.json").write_text(json.dumps(payload))
    rejected = terraform_plan_summary(
        root / ".tmp/m8-release/terraform-plan.json", expected_image_digest=DIGEST
    )
    assert rejected["allowed"] is False
    assert rejected["addresses_allowed"] is False

    _write_allowed_plan(root / ".tmp/m8-release")
    payload = json.loads((root / ".tmp/m8-release/terraform-plan.json").read_text())
    service_change = next(
        change
        for change in payload["resource_changes"]
        if change["address"] == "google_cloud_run_v2_service.remediation_control[0]"
    )
    service_change["change"]["after"]["template"][0]["containers"][0]["image"] = (
        "registry/image@sha256:" + "c" * 64
    )
    (root / ".tmp/m8-release/terraform-plan.json").write_text(json.dumps(payload))
    wrong_image = terraform_plan_summary(
        root / ".tmp/m8-release/terraform-plan.json", expected_image_digest=DIGEST
    )
    assert wrong_image["allowed"] is False
    assert wrong_image["images_bound"] is False


class ImageProcesses:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, command: Sequence[str], root: Path, environment: Mapping[str, str]
    ) -> ProcessResult:
        del root, environment
        call = tuple(command)
        self.calls.append(call)
        joined = " ".join(call)
        if "image inspect" in joined and ".Os" in joined:
            return ProcessResult(0, "linux/amd64\n")
        if "image inspect" in joined and ".Config.User" in joined:
            return ProcessResult(0, "65532:65532\n")
        if "image inspect" in joined and ".RepoDigests" in joined:
            return ProcessResult(0, json.dumps([f"registry/image@{DIGEST}"]))
        if "artifacts docker images describe" in joined:
            return ProcessResult(0, f"{DIGEST}\n")
        if "docker run" in joined:
            return ProcessResult(0, "container-id\n")
        if "docker port" in joined:
            return ProcessResult(0, "127.0.0.1:49153\n")
        return ProcessResult(0, "")


def test_M8_image_phase_binds_clean_source_and_always_cleans_containers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    source = _clean_source(root)
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    (output / "preflight.json").write_text(
        json.dumps({"status": "passed", "source": source}), encoding="utf-8"
    )
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    monkeypatch.setattr(remediation_release, "_status_code", lambda _: 200)
    monkeypatch.setenv("OPSPILOT_M8_LOCAL_IMAGE", f"opspilot-m8:{'a' * 40}")
    monkeypatch.setenv("OPSPILOT_M8_REGISTRY_IMAGE_URI", f"registry/image@{DIGEST}")
    processes = ImageProcesses()
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=processes,
        probe=FakeProbe(),
    )

    code, artifact = runner.verify("image")

    assert code == 0
    assert artifact["status"] == "passed"
    assert artifact["image"] == {
        "digest": DIGEST,
        "platform": "linux/amd64",
        "container_user": "65532:65532",
        "control_health": True,
        "executor_health": True,
    }
    cleanup_calls = [call for call in processes.calls if call[:3] == ("docker", "rm", "-f")]
    assert len(cleanup_calls) == 2
    run_calls = [call for call in processes.calls if call[:2] == ("docker", "run")]
    assert len(run_calls) == 2
    assert all("OPSPILOT_REMEDIATION_PROJECT_ID=local-health" in call for call in run_calls)
    assert all(
        "OPSPILOT_REMEDIATION_ORDER_URL=https://example.invalid" in call for call in run_calls
    )
    assert "registry/image" not in json.dumps(artifact)


def test_M8_image_phase_rejects_dirty_source_and_cleans_failed_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    clean_source = _clean_source(root)
    dirty_source = {**clean_source, "working_tree_dirty": True}
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    (output / "preflight.json").write_text(
        json.dumps({"status": "passed", "source": clean_source}), encoding="utf-8"
    )
    monkeypatch.setattr(remediation_release, "source_metadata", lambda _: dirty_source)
    monkeypatch.setattr(remediation_release, "_status_code", lambda _: 503)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setenv("OPSPILOT_M8_LOCAL_IMAGE", f"opspilot-m8:{'a' * 40}")
    monkeypatch.setenv("OPSPILOT_M8_REGISTRY_IMAGE_URI", f"registry/image@{DIGEST}")
    processes = ImageProcesses()
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=processes,
        probe=FakeProbe(),
    )

    code, artifact = runner.verify("image")

    assert code == 2
    assert artifact["failure_codes"] == [
        "source_clean",
        "source_matches_preflight",
        "control_health",
        "executor_health",
    ]
    cleanup_calls = [call for call in processes.calls if call[:3] == ("docker", "rm", "-f")]
    assert len(cleanup_calls) == 2


def test_M8_post_apply_rejects_changed_binary_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    source = _clean_source(root)
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    _write_allowed_plan(output)
    _write_image_phase(output, source)
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=FakeProcesses(),
        probe=FakeProbe(),
    )
    plan_code, _ = runner.verify("terraform-plan")
    assert plan_code == 0
    (output / "remediation.tfplan").write_bytes(b"changed after approval")

    code, artifact = runner.verify("post-apply")

    assert code == 2
    assert artifact["failure_codes"] == ["POST_APPLY_FAILED"]


def test_M8_publish_requires_every_clean_phase_and_writes_only_sanitized_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    preflight = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "phase": "preflight",
        "status": "passed",
        "source": _clean_source(root),
        "checks": {"clean_working_tree": True},
        "failure_codes": [],
    }
    (runner.output / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
    _write_image_phase(runner.output, _clean_source(root))
    runner.verify("terraform-plan")
    runner.verify("post-apply")
    runner.verify("e2e")

    code, artifact = runner.publish()

    assert code == 0
    assert artifact["status"] == "passed"
    published = root / "docs/portfolio/results/remediation-release-v1.json"
    assert published.is_file()
    serialized = published.read_text(encoding="utf-8")
    published_payload = json.loads(serialized)
    images = published_payload["evidence"]["images"]
    assert images["control_executor"]["digest"] == DIGEST
    assert images["payment_known_good"]["digest"] == "sha256:" + "b" * 64
    for forbidden in (
        "project_id",
        "region",
        "callback_url",
        "workflow_execution",
        "remediation_id",
        "registry/image",
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
    for phase in ("preflight", "image", "post-apply", "e2e"):
        (runner.output / f"{phase}.json").write_text(
            json.dumps({"phase": phase, "status": "failed"}), encoding="utf-8"
        )
    (runner.output / "terraform-plan-verification.json").write_text(
        json.dumps({"phase": "terraform-plan", "status": "failed"}), encoding="utf-8"
    )
    code, _ = runner.publish()
    assert code == 2
    assert tracked.read_text(encoding="utf-8") == "old\n"


def test_M8_release_output_is_bounded_to_tmp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"must remain under \.tmp"):
        RemediationReleaseRunner(root=_root(tmp_path), output=Path("docs/results"))
