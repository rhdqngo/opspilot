from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from http.client import RemoteDisconnected
from pathlib import Path

import pytest

from opspilot.portfolio import remediation_release
from opspilot.portfolio.remediation_release import (
    ARTIFACT_SCHEMA_VERSION,
    RELEASE_CONTEXT_FILENAME,
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


def _write_context(output: Path, source: Mapping[str, object] | None = None) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    context = remediation_release._release_context(source or _clean_source(Path()))
    (output / RELEASE_CONTEXT_FILENAME).write_text(json.dumps(context), encoding="utf-8")
    return context


def _write_preflight(output: Path, context: Mapping[str, object]) -> None:
    (output / "preflight.json").write_text(
        json.dumps(
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "phase": "preflight",
                "status": "passed",
                "release_context_sha256": context["context_sha256"],
                "checks": {"clean_working_tree": True},
                "failure_codes": [],
            }
        ),
        encoding="utf-8",
    )


def _write_allowed_plan(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    changes: list[dict[str, object]] = []
    for address in sorted(remediation_release.M8_IMAGE_SERVICE_ADDRESSES):
        changes.append(
            {
                "address": address,
                "change": {
                    "actions": ["update"],
                    "after": {
                        "template": [{"containers": [{"image": f"registry/image@{DIGEST}"}]}]
                    },
                },
            }
        )
    (output / "terraform-plan.json").write_text(
        json.dumps({"resource_changes": changes}), encoding="utf-8"
    )
    (output / "remediation.tfplan").write_bytes(b"reviewed binary plan")


def _write_image_phase(output: Path, context: Mapping[str, object]) -> None:
    (output / "image.json").write_text(
        json.dumps(
            {
                "schema_version": ARTIFACT_SCHEMA_VERSION,
                "phase": "image",
                "status": "passed",
                "release_context_sha256": context["context_sha256"],
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


def test_M8_preflight_runs_only_release_and_remediation_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    commands = FakeProcesses(failed="remediation eval")
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=commands,
        probe=FakeProbe(),
    )

    code, artifact = runner.preflight()

    assert code == 2
    assert artifact["failure_codes"] == ["remediation_evaluation"]
    joined = [" ".join(value) for value in commands.calls]
    assert len(joined) == 2
    assert any("portfolio_release.py check --include-infra" in value for value in joined)
    assert any("remediation eval" in value for value in joined)
    assert not any("gcloud" in value or "docker info" in value for value in joined)
    assert (runner.output / RELEASE_CONTEXT_FILENAME).is_file()


def test_M8_verify_sanitizes_results_and_abort_blocks_e2e(tmp_path: Path) -> None:
    root = _root(tmp_path)
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=FakeProcesses(),
        probe=FakeProbe(abort_used=True),
    )
    _write_context(runner.output)

    code, artifact = runner.verify("e2e")

    assert code == 2
    assert artifact["failure_codes"] == ["abort_not_used"]
    serialized = json.dumps(artifact)
    for forbidden in ("project_id", "callback_url", 'actor_hash"', "remediation_id"):
        assert forbidden not in serialized


def test_M8_terraform_plan_enforces_scope_public_iam_actions_and_digest(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    output = root / ".tmp/m8-release"
    _write_allowed_plan(output)

    allowed = terraform_plan_summary(output / "terraform-plan.json", DIGEST)
    assert allowed["allowed"] is True
    assert allowed["update"] == 2

    payload = json.loads((output / "terraform-plan.json").read_text())
    payload["resource_changes"].append(
        {
            "address": "google_service_account.remediation_extra[0]",
            "change": {"actions": ["create"], "after": {}},
        }
    )
    (output / "terraform-plan.json").write_text(json.dumps(payload))
    assert terraform_plan_summary(output / "terraform-plan.json", DIGEST)["allowed"] is True

    for address, actions, after in (
        ("google_storage_bucket.unexpected[0]", ["update"], {}),
        ("google_storage_bucket.unexpected[0]", ["delete"], {}),
        ("google_storage_bucket.unexpected[0]", ["delete", "create"], {}),
        (
            "google_cloud_run_v2_service_iam_member.remediation_public[0]",
            ["create"],
            {"member": "allUsers"},
        ),
    ):
        _write_allowed_plan(output)
        payload = json.loads((output / "terraform-plan.json").read_text())
        payload["resource_changes"].append(
            {"address": address, "change": {"actions": actions, "after": after}}
        )
        (output / "terraform-plan.json").write_text(json.dumps(payload))
        assert terraform_plan_summary(output / "terraform-plan.json", DIGEST)["allowed"] is False

    _write_allowed_plan(output)
    payload = json.loads((output / "terraform-plan.json").read_text())
    service_change = next(
        change
        for change in payload["resource_changes"]
        if change["address"] == "google_cloud_run_v2_service.remediation_control[0]"
    )
    service_change["change"]["after"]["template"][0]["containers"][0]["image"] = (
        "registry/image@sha256:" + "c" * 64
    )
    (output / "terraform-plan.json").write_text(json.dumps(payload))
    wrong_image = terraform_plan_summary(output / "terraform-plan.json", DIGEST)
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


def test_M8_image_phase_binds_context_and_always_cleans_containers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    context = _write_context(output)
    _write_preflight(output, context)
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
    assert artifact["release_context_sha256"] == context["context_sha256"]
    image = artifact["image"]
    assert isinstance(image, Mapping)
    assert image["digest"] == DIGEST
    cleanup_calls = [call for call in processes.calls if call[:3] == ("docker", "rm", "-f")]
    assert len(cleanup_calls) == 2
    assert "registry/image" not in json.dumps(artifact)


def test_M8_image_phase_cleans_failed_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    context = _write_context(output)
    _write_preflight(output, context)
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
    assert artifact["failure_codes"] == ["control_health", "executor_health"]
    cleanup_calls = [call for call in processes.calls if call[:3] == ("docker", "rm", "-f")]
    assert len(cleanup_calls) == 2


def test_M8_terraform_phase_rejects_source_context_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    context = _write_context(output)
    _write_image_phase(output, context)
    _write_allowed_plan(output)
    changed = {**_clean_source(root), "source_tree_sha256": "1" * 64}
    monkeypatch.setattr(remediation_release, "source_metadata", lambda _: changed)
    runner = RemediationReleaseRunner(root=root, output=Path(".tmp/m8-release"))

    code, artifact = runner.verify("terraform-plan")

    assert code == 2
    assert artifact["failure_codes"] == ["release_context_matches"]


def test_M8_post_apply_rejects_changed_binary_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    output = root / ".tmp/m8-release"
    output.mkdir(parents=True)
    context = _write_context(output)
    _write_image_phase(output, context)
    _write_allowed_plan(output)
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    runner = RemediationReleaseRunner(root=root, output=Path(".tmp/m8-release"), probe=FakeProbe())
    assert runner.verify("terraform-plan")[0] == 0
    (output / "remediation.tfplan").write_bytes(b"changed after approval")

    code, artifact = runner.verify("post-apply")

    assert code == 2
    assert artifact["failure_codes"] == ["POST_APPLY_FAILED"]


def test_M8_publish_requires_aligned_context_and_sanitizes_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    runner = RemediationReleaseRunner(
        root=root,
        output=Path(".tmp/m8-release"),
        process_runner=FakeProcesses(),
        probe=FakeProbe(),
    )
    runner.output.mkdir(parents=True)
    context = _write_context(runner.output)
    _write_preflight(runner.output, context)
    _write_image_phase(runner.output, context)
    _write_allowed_plan(runner.output)
    monkeypatch.setattr(remediation_release, "source_metadata", _clean_source)
    assert runner.verify("terraform-plan")[0] == 0
    assert runner.verify("post-apply")[0] == 0
    assert runner.verify("e2e")[0] == 0

    code, artifact = runner.publish()

    assert code == 0
    assert artifact["status"] == "passed"
    assert artifact["release_context_sha256"] == context["context_sha256"]
    published = root / "docs/portfolio/results/remediation-release-v1.json"
    serialized = published.read_text(encoding="utf-8")
    images = json.loads(serialized)["evidence"]["images"]
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
    runner = RemediationReleaseRunner(root=root, output=Path(".tmp/m8-release"))
    runner.output.mkdir(parents=True)
    context = _write_context(runner.output)
    for phase in ("preflight", "image", "post-apply", "e2e"):
        (runner.output / f"{phase}.json").write_text(
            json.dumps(
                {
                    "phase": phase,
                    "status": "failed",
                    "release_context_sha256": context["context_sha256"],
                }
            ),
            encoding="utf-8",
        )
    (runner.output / "terraform-plan-verification.json").write_text(
        json.dumps(
            {
                "phase": "terraform-plan",
                "status": "failed",
                "release_context_sha256": context["context_sha256"],
            }
        ),
        encoding="utf-8",
    )

    code, _ = runner.publish()

    assert code == 2
    assert tracked.read_text(encoding="utf-8") == "old\n"


def test_M8_release_output_is_bounded_to_tmp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"must remain under \.tmp"):
        RemediationReleaseRunner(root=_root(tmp_path), output=Path("docs/results"))
