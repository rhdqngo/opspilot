from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from opspilot.remediation.contracts import RemediationTarget
from opspilot.remediation.scenario import (
    GoogleScenarioCloudAdmin,
    ScenarioRecoveryRecord,
    run_scn008_command,
)

DIGEST = "sha256:" + "a" * 64
TARGET = RemediationTarget(
    project_id="portfolio-project",
    region="asia-northeast3",
    service="opspilot-prod-sim-payment",
    source_revision="payment-faulty",
    target_revision="payment-good",
    target_image_digest=DIGEST,
    service_etag="etag-faulty",
)


class FakeRecoveryStore:
    def __init__(self, target: RemediationTarget | None = TARGET) -> None:
        self.target = target

    async def get_latest_scenario_target(
        self, scenario_id: str
    ) -> tuple[str, RemediationTarget] | None:
        assert scenario_id == "SCN-008"
        return ("INC-2026-0008", self.target) if self.target is not None else None

    async def save_recovery_target(self, **_: object) -> None:
        raise AssertionError("abort must not replace the trusted target")

    async def save_incident(self, **_: object) -> None:
        raise AssertionError("abort must not replace the incident report")


class RecordingRecoveryStore(FakeRecoveryStore):
    def __init__(self) -> None:
        super().__init__(None)
        self.saved: RemediationTarget | None = None

    async def save_recovery_target(self, **values: object) -> None:
        target = values.get("target")
        assert isinstance(target, RemediationTarget)
        self.saved = target


class FakeScenarioAdmin:
    def __init__(self) -> None:
        self.aborts: list[RemediationTarget] = []

    async def prepare_faulty_revision(self) -> RemediationTarget:
        return TARGET

    async def reset_known_good_template(self) -> None:
        raise AssertionError("not used")

    async def abort_faulty_revision(self, target: RemediationTarget) -> None:
        self.aborts.append(target)


class StubGoogleScenarioAdmin(GoogleScenarioCloudAdmin):
    def __init__(self, *, etag: str = "etag-faulty", digest: str = DIGEST) -> None:
        super().__init__(
            project_id="portfolio-project",
            region="asia-northeast3",
            image_uri=f"registry.invalid/payment@{DIGEST}",
            session=object(),  # type: ignore[arg-type]
        )
        self.etag = etag
        self.digest = digest
        self.serving = "payment-faulty"
        self.failure_profile = True
        self.patch_masks: list[str] = []
        self.patches: list[dict[str, Any]] = []
        self.last_patch: dict[str, Any] | None = None

    async def _get_service(self) -> dict[str, Any]:
        environment = (
            [{"name": "OPSPILOT_PAYMENT_FAILURE_PROFILE", "value": "payment-failure"}]
            if self.failure_profile
            else []
        )
        return {
            "name": self.service_name,
            "etag": self.etag,
            "trafficStatuses": [{"revision": self.serving, "percent": 100}],
            "template": {"containers": [{"image": self.image_uri, "env": environment}]},
        }

    async def _revision_digest(self, revision: str) -> str:
        del revision
        return self.digest

    async def _patch_service(self, body: dict[str, Any], *, update_mask: str) -> None:
        self.patch_masks.append(update_mask)
        self.patches.append(body)
        self.last_patch = body
        if update_mask == "template,traffic":
            self.serving = str(body["traffic"][0]["revision"])
            self.etag = "etag-faulty-created"
            self.failure_profile = True
        elif update_mask == "traffic":
            self.serving = str(body["traffic"][0]["revision"])
            self.etag = "etag-recovered"
        elif update_mask == "template":
            environment = body["template"]["containers"][0].get("env", [])
            self.failure_profile = any(
                item.get("name") == "OPSPILOT_PAYMENT_FAILURE_PROFILE" for item in environment
            )
            self.etag = "etag-template-updated"

    async def _replace_traffic(self, revision: str) -> None:
        body = {"traffic": [{"revision": revision, "percent": 100}]}
        self.patch_masks.append("traffic")
        self.patches.append(body)
        self.last_patch = body
        self.serving = revision
        self.etag = "etag-recovered"


async def test_M8_abort_uses_only_matching_trusted_target_and_marks_local_recovery(
    tmp_path: Path,
) -> None:
    recovery_path = tmp_path / "recovery.json"
    recovery_path.write_text(
        ScenarioRecoveryRecord(
            incident_id="INC-2026-0008",
            target=TARGET,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            baseline_successes=10,
            faulty_order_successes=0,
        ).model_dump_json(),
        encoding="utf-8",
    )
    admin = FakeScenarioAdmin()

    result = await run_scn008_command(
        operation="abort",
        mode="execute",
        auth="gcloud",
        admin=admin,
        store=FakeRecoveryStore(),
        recovery_path=recovery_path,
    )

    assert admin.aborts == [TARGET]
    assert result.abort_used is True
    saved = ScenarioRecoveryRecord.model_validate_json(recovery_path.read_text(encoding="utf-8"))
    assert saved.abort_used is True
    assert saved.aborted_at is not None
    assert saved.baseline_successes == 10


async def test_M8_reset_routes_to_the_matching_trusted_revision_before_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery_path = tmp_path / "recovery.json"
    recovery_path.write_text(
        ScenarioRecoveryRecord(
            incident_id="INC-2026-0008",
            target=TARGET,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            baseline_successes=10,
            faulty_order_successes=0,
        ).model_dump_json(),
        encoding="utf-8",
    )
    admin = FakeScenarioAdmin()

    async def ten_orders(*_: object) -> int:
        return 10

    async def healthy(*_: object) -> None:
        return None

    monkeypatch.setenv("OPSPILOT_ORDER_URL", "https://order.example.invalid")
    monkeypatch.setattr("opspilot.remediation.scenario._gcloud_identity_token", lambda: "token")
    monkeypatch.setattr("opspilot.remediation.scenario._wait_for_healthy_baseline", healthy)
    monkeypatch.setattr("opspilot.remediation.scenario._run_ten_orders", ten_orders)

    result = await run_scn008_command(
        operation="reset",
        mode="execute",
        auth="gcloud",
        admin=admin,
        store=FakeRecoveryStore(),
        recovery_path=recovery_path,
    )

    assert admin.aborts == [TARGET]
    assert result.order_successes == 10
    saved = ScenarioRecoveryRecord.model_validate_json(recovery_path.read_text(encoding="utf-8"))
    assert saved.reset_order_successes == 10
    assert saved.reset_completed_at is not None


async def test_M8_abort_rejects_mismatched_local_and_firestore_targets(tmp_path: Path) -> None:
    local = TARGET.model_copy(update={"service_etag": "different"})
    recovery_path = tmp_path / "recovery.json"
    recovery_path.write_text(
        ScenarioRecoveryRecord(
            incident_id="INC-2026-0008",
            target=local,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
        ).model_dump_json(),
        encoding="utf-8",
    )
    admin = FakeScenarioAdmin()
    with pytest.raises(RuntimeError, match="do not match"):
        await run_scn008_command(
            operation="abort",
            mode="execute",
            auth="gcloud",
            admin=admin,
            store=FakeRecoveryStore(),
            recovery_path=recovery_path,
        )
    assert admin.aborts == []


async def test_M8_abort_is_idempotent_after_guarded_traffic_and_template_recovery() -> None:
    admin = StubGoogleScenarioAdmin()
    await admin.abort_faulty_revision(TARGET)
    await admin.abort_faulty_revision(TARGET)
    assert admin.patch_masks == ["traffic", "template"]
    assert admin.serving == "payment-good"
    assert admin.failure_profile is False


async def test_M8_abort_stale_etag_or_digest_mismatch_makes_zero_updates() -> None:
    stale = StubGoogleScenarioAdmin(etag="stale")
    with pytest.raises(RuntimeError, match="etag is stale"):
        await stale.abort_faulty_revision(TARGET)
    assert stale.patch_masks == []

    digest = StubGoogleScenarioAdmin(digest="sha256:" + "b" * 64)
    with pytest.raises(RuntimeError, match="digest does not match"):
        await digest.abort_faulty_revision(TARGET)
    assert digest.patch_masks == []


async def test_M8_faulty_revision_name_uses_the_cloud_run_service_prefix() -> None:
    admin = StubGoogleScenarioAdmin()

    target = await admin.prepare_faulty_revision()

    assert target.source_revision.startswith("opspilot-prod-sim-payment-m8-")
    assert admin.patch_masks == ["template", "traffic"]
    assert admin.patches[0]["template"]["revision"] == target.source_revision
    assert admin.patches[1]["traffic"][0]["revision"] == target.source_revision


def test_M8_scenario_image_environment_is_distinct_from_control_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPSPILOT_REMEDIATION_PROJECT_ID", "portfolio-project")
    monkeypatch.setenv("OPSPILOT_REMEDIATION_REGION", "asia-northeast3")
    monkeypatch.setenv("OPSPILOT_SCN008_KNOWN_GOOD_IMAGE_URI", f"registry.invalid/payment@{DIGEST}")
    monkeypatch.setenv(
        "OPSPILOT_REMEDIATION_IMAGE_URI", "registry.invalid/control@sha256:" + "b" * 64
    )
    monkeypatch.setattr("opspilot.remediation.scenario._authorized_session", lambda: object())
    admin = GoogleScenarioCloudAdmin.from_environment()
    assert admin.image_uri.endswith(DIGEST)


async def test_M8_prepare_failure_after_fault_activation_runs_emergency_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = FakeScenarioAdmin()
    store = RecordingRecoveryStore()
    monkeypatch.setenv("OPSPILOT_ORDER_URL", "https://order.example.invalid")
    monkeypatch.setattr("opspilot.remediation.scenario._gcloud_identity_token", lambda: "token")
    monkeypatch.setattr("opspilot.remediation.scenario._run_ten_orders", lambda *_: _ten())

    async def fault_active(*_: object) -> None:
        return None

    async def fail_collection(*_: object, **__: object) -> object:
        raise RuntimeError("safe injected collection failure")

    async def _ten() -> int:
        return 10

    monkeypatch.setattr("opspilot.remediation.scenario._wait_for_fault_activation", fault_active)
    monkeypatch.setattr("opspilot.remediation.scenario._wait_for_healthy_baseline", fault_active)
    monkeypatch.setattr("opspilot.remediation.scenario.collect_evidence", fail_collection)
    recovery_path = tmp_path / "recovery.json"
    with pytest.raises(RuntimeError, match="fail all ten orders"):
        await run_scn008_command(
            operation="prepare",
            mode="execute",
            auth="gcloud",
            admin=admin,
            store=store,
            recovery_path=recovery_path,
        )
    assert store.saved == TARGET
    assert admin.aborts == [TARGET]
    recovery = ScenarioRecoveryRecord.model_validate_json(recovery_path.read_text(encoding="utf-8"))
    assert recovery.abort_used is True
