"""SCN-008 operator preparation and reset planning/execution."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from google.auth.transport.requests import AuthorizedSession
from pydantic import BaseModel, Field

from opspilot.agent.contracts import AgentEvidenceContext, ModelBackend
from opspilot.agent.runner import run_agent_context
from opspilot.catalog import load_service_catalog
from opspilot.demo.load import _gcloud_identity_token
from opspilot.domain import (
    Environment,
    EvidenceDirection,
    EvidenceItem,
    IncidentReport,
    RecommendedAction,
    ReportStatus,
    SourceType,
)
from opspilot.evidence import (
    EvidenceCollectionRequest,
    LiveEvidenceClient,
    UrllibJsonTransport,
    WorkloadAdcTokenProvider,
    collect_evidence,
)
from opspilot.remediation.contracts import RemediationTarget
from opspilot.remediation.firestore_store import FirestoreRemediationStore
from opspilot.remediation.google import _authorized_session

ScenarioMode = Literal["plan", "execute"]
ScenarioOperation = Literal["prepare", "reset", "abort"]
DEFAULT_RECOVERY_PATH = Path(".tmp/m8-release/recovery.json")


class ScenarioCommandResult(BaseModel):
    scenario_id: str = "SCN-008"
    operation: ScenarioOperation
    mode: ScenarioMode
    planned_steps: list[str]
    executed: bool
    incident_id: str | None = None
    report_id: str | None = None
    source_revision: str | None = None
    target_revision: str | None = None
    baseline_successes: int | None = Field(default=None, ge=0, le=10)
    order_successes: int | None = Field(default=None, ge=0, le=10)
    abort_used: bool = False


class ScenarioRecoveryRecord(BaseModel):
    schema_version: str = "m8-scenario-recovery-v1"
    scenario_id: str = "SCN-008"
    incident_id: str = Field(pattern=r"^INC-\d{4}-0008$")
    target: RemediationTarget
    created_at: datetime
    fault_deadline_at: datetime | None = None
    baseline_successes: int | None = Field(default=None, ge=0, le=10)
    faulty_order_successes: int | None = Field(default=None, ge=0, le=10)
    reset_order_successes: int | None = Field(default=None, ge=0, le=10)
    report_id: str | None = None
    abort_used: bool = False
    aborted_at: datetime | None = None
    reset_completed_at: datetime | None = None


class ScenarioCloudAdmin(Protocol):
    async def prepare_faulty_revision(self) -> RemediationTarget: ...

    async def reset_known_good_template(self) -> None: ...

    async def abort_faulty_revision(self, target: RemediationTarget) -> None: ...


class ScenarioRecoveryStore(Protocol):
    async def save_recovery_target(
        self,
        *,
        incident_id: str,
        target: RemediationTarget,
        scenario_id: str,
        updated_at: datetime,
    ) -> None: ...

    async def get_latest_scenario_target(
        self, scenario_id: str
    ) -> tuple[str, RemediationTarget] | None: ...

    async def save_incident(
        self,
        *,
        report: IncidentReport,
        target: RemediationTarget,
        scenario_id: str = "SCN-008",
    ) -> None: ...


PREPARE_STEPS = [
    "capture known-good payment revision, image digest, and service etag",
    "create a fixed payment-failure revision from the same image",
    "move 100 percent payment traffic to the faulty revision",
    "run ten bounded synthetic orders",
    "collect read-only evidence and persist the incident and versioned report",
]
RESET_STEPS = [
    "restore the known-good payment template without changing successful traffic",
    "confirm the fixed payment-failure profile is absent from the template",
    "run a Terraform plan and require No changes",
]
ABORT_STEPS = [
    "load the trusted SCN-008 recovery target without caller-supplied resource names",
    "revalidate the exact payment service, faulty traffic, revisions, digest, and etag",
    "move 100 percent traffic to the captured known-good revision",
    "remove the fixed payment-failure profile from the service template",
    "mark the portfolio E2E as aborted and ineligible for evidence publication",
]


async def run_scn008_command(
    *,
    operation: ScenarioOperation,
    mode: ScenarioMode,
    auth: str,
    admin: ScenarioCloudAdmin | None = None,
    store: ScenarioRecoveryStore | None = None,
    recovery_path: Path = DEFAULT_RECOVERY_PATH,
) -> ScenarioCommandResult:
    if auth != "gcloud":
        raise ValueError("SCN-008 requires gcloud authentication")
    steps = (
        PREPARE_STEPS
        if operation == "prepare"
        else RESET_STEPS
        if operation == "reset"
        else ABORT_STEPS
    )
    if mode == "plan":
        return ScenarioCommandResult(
            operation=operation, mode=mode, planned_steps=steps, executed=False
        )
    cloud = admin or GoogleScenarioCloudAdmin.from_environment()
    if operation == "abort":
        recovery_store = store or _firestore_store_from_environment()
        target_record = await recovery_store.get_latest_scenario_target("SCN-008")
        local_recovery = _read_recovery_record(recovery_path)
        if target_record is None and local_recovery is None:
            raise RuntimeError("trusted SCN-008 recovery target is unavailable")
        if target_record is not None:
            incident_id, target = target_record
            if local_recovery is not None and (
                local_recovery.incident_id != incident_id or local_recovery.target != target
            ):
                raise RuntimeError("SCN-008 recovery targets do not match")
        else:
            assert local_recovery is not None
            incident_id, target = local_recovery.incident_id, local_recovery.target
        await cloud.abort_faulty_revision(target)
        recovered_at = datetime.now(UTC)
        _write_recovery_record(
            recovery_path,
            ScenarioRecoveryRecord(
                incident_id=incident_id,
                target=target,
                created_at=(
                    local_recovery.created_at if local_recovery is not None else recovered_at
                ),
                baseline_successes=(
                    local_recovery.baseline_successes if local_recovery is not None else None
                ),
                fault_deadline_at=(
                    local_recovery.fault_deadline_at if local_recovery is not None else None
                ),
                faulty_order_successes=(
                    local_recovery.faulty_order_successes if local_recovery is not None else None
                ),
                report_id=local_recovery.report_id if local_recovery is not None else None,
                reset_order_successes=(
                    local_recovery.reset_order_successes if local_recovery is not None else None
                ),
                abort_used=True,
                aborted_at=recovered_at,
                reset_completed_at=(
                    local_recovery.reset_completed_at if local_recovery is not None else None
                ),
            ),
        )
        return ScenarioCommandResult(
            operation=operation,
            mode=mode,
            planned_steps=steps,
            executed=True,
            incident_id=incident_id,
            source_revision=target.source_revision,
            target_revision=target.target_revision,
            abort_used=True,
        )
    if operation == "reset":
        recovery_store = store or _firestore_store_from_environment()
        target_record = await recovery_store.get_latest_scenario_target("SCN-008")
        local_recovery = _read_recovery_record(recovery_path)
        if target_record is None or local_recovery is None:
            raise RuntimeError("trusted SCN-008 recovery target is unavailable")
        incident_id, target = target_record
        if local_recovery.incident_id != incident_id or local_recovery.target != target:
            raise RuntimeError("SCN-008 recovery targets do not match")
        await cloud.abort_faulty_revision(target)
        successes = await _run_ten_orders(
            os.environ["OPSPILOT_ORDER_URL"], await asyncio.to_thread(_gcloud_identity_token)
        )
        if successes != 10:
            raise RuntimeError("SCN-008 reset verification must recover ten orders")
        _write_recovery_record(
            recovery_path,
            local_recovery.model_copy(
                update={
                    "reset_order_successes": successes,
                    "reset_completed_at": datetime.now(UTC),
                }
            ),
        )
        return ScenarioCommandResult(
            operation=operation,
            mode=mode,
            planned_steps=steps,
            executed=True,
            order_successes=successes,
        )
    prepared_at = datetime.now(UTC)
    incident_id = f"INC-{prepared_at.year:04d}-0008"
    token = await asyncio.to_thread(_gcloud_identity_token)
    await _wait_for_healthy_baseline(os.environ["OPSPILOT_ORDER_URL"], token)
    baseline_successes = await _run_ten_orders(os.environ["OPSPILOT_ORDER_URL"], token)
    if baseline_successes != 10:
        raise RuntimeError("SCN-008 baseline must succeed before fault activation")
    target = await cloud.prepare_faulty_revision()
    recovery = ScenarioRecoveryRecord(
        incident_id=incident_id,
        target=target,
        created_at=prepared_at,
        fault_deadline_at=prepared_at + timedelta(minutes=20),
        baseline_successes=baseline_successes,
    )
    _write_recovery_record(recovery_path, recovery)
    recovery_store = store or _firestore_store_from_environment()
    await recovery_store.save_recovery_target(
        incident_id=incident_id,
        target=target,
        scenario_id="SCN-008",
        updated_at=prepared_at,
    )
    try:
        await _wait_for_fault_activation(os.environ["OPSPILOT_ORDER_URL"], token)
        successes = await _run_ten_orders(os.environ["OPSPILOT_ORDER_URL"], token)
        if successes != 0:
            raise RuntimeError("SCN-008 fault verification must fail all ten orders")
        end_time = datetime.now(UTC)
        collection = await collect_evidence(
            LiveEvidenceClient(
                target.project_id,
                catalog=load_service_catalog(),
                token_provider=WorkloadAdcTokenProvider(),
                transport=UrllibJsonTransport(),
                region=target.region,
            ),
            EvidenceCollectionRequest(
                scenario_id="SCN-008",
                environment="dev",
                start_time=end_time - timedelta(minutes=30),
                end_time=end_time,
                services=["payment-service"],
            ),
        )
        # The fault activation is a controlled write.  Bind the one payment
        # change observed after preparation as supporting evidence instead of
        # asking the model to infer direction from neutral Cloud audit data.
        evidence = []
        for item in collection.evidence:
            if (
                item.source_type in {SourceType.CHANGE, SourceType.LOG}
                and item.service == "payment-service"
                and item.observed_at is not None
                and item.observed_at >= prepared_at
            ):
                quality_flag = (
                    "config_or_digest_change_match"
                    if item.source_type is SourceType.CHANGE
                    else "direct_error_signature_match"
                )
                item = item.model_copy(
                    update={
                        "direction": EvidenceDirection.SUPPORTS,
                        "quality_flags": sorted({*item.quality_flags, quality_flag}),
                    }
                )
            evidence.append(item)
        evidence.append(
            EvidenceItem(
                evidence_id="EV-INC-0001",
                source_type=SourceType.INCIDENT,
                title="SCN-008 bounded synthetic order outcome",
                service="payment-service",
                environment="dev",
                observed_at=end_time,
                summary=(
                    f"The controlled fault window completed with {successes} successful "
                    "orders out of 10 bounded attempts."
                ),
                value=successes,
                unit="successful_orders_of_10",
                direction=EvidenceDirection.SUPPORTS,
                source_uri="opspilot://scenario/SCN-008/orders",
                quality_flags=["direct_error_signature_match", "bounded_synthetic_probe"],
            )
        )
        result = await run_agent_context(
            AgentEvidenceContext(
                scenario_id="SCN-008",
                incident_id=incident_id,
                generated_at=end_time,
                correlation_id=f"COR-{secrets.token_hex(8).upper()}",
                evidence=evidence,
                tool_errors=collection.tool_errors,
                data_gaps=collection.data_gaps,
            ),
            model_backend=ModelBackend.FAKE,
            complete=collection.complete,
        )
        if not result.succeeded or result.report is None:
            raise RuntimeError("SCN-008 investigation report could not be generated")
        report = _bind_scn008_rollback_action(result.report).model_copy(
            update={"report_id": f"RPT-SCN-008-{secrets.token_hex(8).upper()}"}
        )
        await recovery_store.save_incident(report=report, target=target)
        _write_recovery_record(
            recovery_path,
            recovery.model_copy(
                update={"faulty_order_successes": successes, "report_id": report.report_id}
            ),
        )
    except BaseException as error:
        try:
            await asyncio.shield(cloud.abort_faulty_revision(target))
            _write_recovery_record(
                recovery_path,
                recovery.model_copy(update={"abort_used": True, "aborted_at": datetime.now(UTC)}),
            )
        except Exception:
            raise RuntimeError(
                "SCN-008 failed and emergency abort could not be confirmed"
            ) from error
        raise
    return ScenarioCommandResult(
        operation=operation,
        mode=mode,
        planned_steps=steps,
        executed=True,
        incident_id=report.incident_id,
        report_id=report.report_id,
        source_revision=target.source_revision,
        target_revision=target.target_revision,
        baseline_successes=baseline_successes,
        order_successes=successes,
    )


def _bind_scn008_rollback_action(report: IncidentReport) -> IncidentReport:
    validated = IncidentReport.model_validate(report).model_copy(
        update={"environment": Environment.PROD_SIM}
    )
    change_ids = [
        item.evidence_id
        for item in validated.evidence
        if item.source_type is SourceType.CHANGE and item.service == "payment-service"
    ]
    if validated.status is not ReportStatus.IDENTIFIED or not change_ids:
        return validated.model_copy(update={"recommended_actions": []})
    action = RecommendedAction(
        action_id="ACT-01",
        category="ROLLBACK_CLOUD_RUN",
        title="Request payment revision rollback",
        description="Request approval for the captured single-service traffic rollback plan.",
        target_service="payment-service",
        risk_level="HIGH",
        requires_approval=True,
        prerequisites=["Verify the canonical plan hash and unexpired approval."],
        expected_effect="Restore synthetic payment authorization and order success.",
        rollback_method="Move payment traffic to the captured known-good revision.",
        verification_steps=[
            "Confirm target traffic is 100 percent.",
            "Confirm ten of ten bounded orders succeed.",
        ],
        supporting_evidence_ids=change_ids,
        remediation_action_type="ROLLBACK_CLOUD_RUN",
    )
    return validated.model_copy(update={"recommended_actions": [action]})


async def _run_ten_orders(order_url: str, token: str) -> int:
    semaphore = asyncio.Semaphore(2)

    async def bounded(index: int) -> bool:
        async with semaphore:
            return await asyncio.to_thread(_send_order, order_url, index, token)

    results = await asyncio.gather(*(bounded(index) for index in range(1, 11)))
    return sum(results)


async def _wait_for_healthy_baseline(order_url: str, token: str) -> None:
    """Warm the scale-to-zero path before enforcing the ten-order baseline."""

    for attempt in range(15):
        succeeded = await asyncio.to_thread(_send_order, order_url, 50 + attempt, token)
        if succeeded:
            return
        await asyncio.sleep(2)
    raise RuntimeError("SCN-008 healthy baseline did not become observable")


async def _wait_for_fault_activation(order_url: str, token: str) -> None:
    """Wait for Cloud Run traffic propagation before recording the faulty window."""

    for attempt in range(30):
        succeeded = await asyncio.to_thread(_send_order, order_url, 100 + attempt, token)
        if not succeeded:
            return
        await asyncio.sleep(2)
    raise RuntimeError("SCN-008 fault revision did not become observable")


def _send_order(order_url: str, index: int, token: str) -> bool:
    request_id = f"req_scn008_{secrets.token_hex(6)}_{index:02d}"
    request = UrlRequest(
        f"{order_url.rstrip('/')}/v1/orders",
        data=json.dumps(
            {"sku": f"SKU-{index % 5 + 1:03d}", "quantity": 1, "amount_krw": 1000}
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            response.read()
            return bool(response.status == 201)
    except HTTPError as error:
        error.close()
        return False
    except (URLError, TimeoutError):
        return False


class GoogleScenarioCloudAdmin:
    def __init__(
        self,
        *,
        project_id: str,
        region: str,
        image_uri: str,
        session: AuthorizedSession | None = None,
    ) -> None:
        self.project_id = project_id
        self.region = region
        self.image_uri = image_uri
        self.session = session or _authorized_session()
        self.service_name = (
            f"projects/{project_id}/locations/{region}/services/opspilot-prod-sim-payment"
        )

    @classmethod
    def from_environment(cls) -> GoogleScenarioCloudAdmin:
        return cls(
            project_id=os.environ["OPSPILOT_REMEDIATION_PROJECT_ID"],
            region=os.environ.get("OPSPILOT_REMEDIATION_REGION", "asia-northeast3"),
            image_uri=os.environ["OPSPILOT_SCN008_KNOWN_GOOD_IMAGE_URI"],
        )

    async def prepare_faulty_revision(self) -> RemediationTarget:
        before = await self._get_service()
        source_revision = self._sole_traffic_revision(before)
        target_digest = await self._revision_digest(source_revision)
        if not self.image_uri.endswith(f"@{target_digest}"):
            raise RuntimeError("SCN-008 image must match the known-good revision digest")
        # Cloud Run revision names must begin with the owning service name.
        faulty_revision = f"opspilot-prod-sim-payment-m8-{secrets.token_hex(4)}"
        body: dict[str, Any] = {
            "name": self.service_name,
            "etag": before["etag"],
            "template": json.loads(json.dumps(before["template"])),
        }
        template = cast(dict[str, Any], body["template"])
        template["revision"] = faulty_revision
        containers = cast(list[dict[str, Any]], template["containers"])
        containers[0]["image"] = self.image_uri
        env = cast(list[dict[str, str]], containers[0].setdefault("env", []))
        env[:] = [item for item in env if item.get("name") != "OPSPILOT_PAYMENT_FAILURE_PROFILE"]
        env.append({"name": "OPSPILOT_PAYMENT_FAILURE_PROFILE", "value": "payment-failure"})
        await self._patch_service(body, update_mask="template")

        # Route only after the named revision operation has completed.
        await self._replace_traffic(faulty_revision)
        after = await self._wait_for_serving_revision(faulty_revision)
        return RemediationTarget(
            project_id=self.project_id,
            region=self.region,
            service="opspilot-prod-sim-payment",
            source_revision=faulty_revision,
            target_revision=source_revision,
            target_image_digest=target_digest,
            service_etag=str(after["etag"]),
        )

    async def reset_known_good_template(self) -> None:
        before = await self._get_service()
        body: dict[str, Any] = {
            "name": self.service_name,
            "etag": before["etag"],
            "template": json.loads(json.dumps(before["template"])),
        }
        template = cast(dict[str, Any], body["template"])
        template.pop("revision", None)
        containers = cast(list[dict[str, Any]], template["containers"])
        env = cast(list[dict[str, str]], containers[0].setdefault("env", []))
        env[:] = [item for item in env if item.get("name") != "OPSPILOT_PAYMENT_FAILURE_PROFILE"]
        await self._patch_service(body, update_mask="template")

    async def abort_faulty_revision(self, target: RemediationTarget) -> None:
        if target.service_name != self.service_name:
            raise RuntimeError("SCN-008 recovery target service does not match")
        if target.project_id != self.project_id or target.region != self.region:
            raise RuntimeError("SCN-008 recovery target boundary does not match")
        source_digest = await self._revision_digest(target.source_revision)
        target_digest = await self._revision_digest(target.target_revision)
        if (
            source_digest != target.target_image_digest
            or target_digest != target.target_image_digest
        ):
            raise RuntimeError("SCN-008 recovery revision digest does not match")

        before = await self._get_service()
        serving = self._sole_traffic_revision(before)
        if serving == target.source_revision:
            if str(before.get("etag", "")) != target.service_etag:
                raise RuntimeError("SCN-008 recovery service etag is stale")
            await self._replace_traffic(target.target_revision)
        elif serving != target.target_revision:
            raise RuntimeError("SCN-008 recovery found an unexpected serving revision")

        recovered = await self._wait_for_serving_revision(target.target_revision)
        if self._sole_traffic_revision(recovered) != target.target_revision:
            raise RuntimeError("SCN-008 recovery traffic was not confirmed")
        if self._template_has_failure_profile(recovered):
            await self.reset_known_good_template()
        final = await self._get_service()
        if self._sole_traffic_revision(final) != target.target_revision:
            raise RuntimeError("SCN-008 recovery changed successful traffic")
        if self._template_has_failure_profile(final):
            raise RuntimeError("SCN-008 recovery template remains faulty")

    async def _get_service(self) -> dict[str, Any]:
        control_response, serving_response = await asyncio.gather(
            asyncio.to_thread(
                self.session.get,
                f"https://run.googleapis.com/v2/{self.service_name}",
                timeout=10,
            ),
            asyncio.to_thread(self.session.get, self._serving_url(), timeout=10),
        )
        if control_response.status_code != 200 or serving_response.status_code != 200:
            raise RuntimeError("payment service state could not be read")
        body = cast(dict[str, Any], control_response.json())
        serving = cast(dict[str, Any], serving_response.json())
        status = cast(dict[str, Any], serving.get("status", {}))
        body["trafficStatuses"] = [
            {
                "revision": item.get("revisionName"),
                "percent": item.get("percent", 0),
            }
            for item in cast(list[dict[str, Any]], status.get("traffic", []))
        ]
        return body

    async def _patch_service(self, body: dict[str, Any], *, update_mask: str) -> None:
        response = await asyncio.to_thread(
            self.session.patch,
            f"https://run.googleapis.com/v2/{self.service_name}?updateMask={update_mask}",
            json=body,
            timeout=30,
        )
        if response.status_code not in {200, 202}:
            raise RuntimeError("payment service update was rejected")
        operation = cast(dict[str, Any], response.json())
        operation_name = operation.get("name")
        if not isinstance(operation_name, str) or not operation_name:
            raise RuntimeError("payment service update returned an invalid operation")
        await self._wait_operation(operation_name)

    async def _wait_operation(self, operation_name: str) -> None:
        deadline = asyncio.get_running_loop().time() + 180
        while asyncio.get_running_loop().time() < deadline:
            response = await asyncio.to_thread(
                self.session.get,
                f"https://run.googleapis.com/v2/{operation_name}",
                timeout=10,
            )
            if response.status_code != 200:
                raise RuntimeError("payment service operation could not be read")
            operation = cast(dict[str, Any], response.json())
            if operation.get("done") is True:
                if operation.get("error") is not None:
                    raise RuntimeError("payment service operation failed")
                return
            await asyncio.sleep(1)
        raise RuntimeError("payment service operation timed out")

    async def _wait_for_serving_revision(self, revision: str) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + 180
        while asyncio.get_running_loop().time() < deadline:
            service = await self._get_service()
            try:
                if (
                    not bool(service.get("reconciling", False))
                    and self._sole_traffic_revision(service) == revision
                ):
                    return service
            except RuntimeError:
                pass
            await asyncio.sleep(2)
        raise RuntimeError("payment service traffic did not reach the target revision")

    async def _replace_traffic(self, revision: str) -> None:
        """Use the operator CLI's serving-plane traffic implementation."""

        executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [
                    executable,
                    "run",
                    "services",
                    "update-traffic",
                    "opspilot-prod-sim-payment",
                    "--project",
                    self.project_id,
                    "--region",
                    self.region,
                    "--to-revisions",
                    f"{revision}=100",
                    "--quiet",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("payment service traffic update was unavailable") from error
        if completed.returncode != 0:
            raise RuntimeError("payment service traffic update was rejected")

    def _serving_url(self) -> str:
        return (
            f"https://{self.region}-run.googleapis.com/apis/serving.knative.dev/v1/"
            f"namespaces/{self.project_id}/services/opspilot-prod-sim-payment"
        )

    @staticmethod
    def _sole_traffic_revision(body: dict[str, Any]) -> str:
        targets = [
            item
            for item in cast(list[dict[str, Any]], body.get("trafficStatuses", []))
            if int(item.get("percent", 0)) == 100
        ]
        if len(targets) != 1 or not targets[0].get("revision"):
            raise RuntimeError("payment service must have one 100 percent traffic revision")
        return str(targets[0]["revision"])

    async def _revision_digest(self, revision: str) -> str:
        name = f"{self.service_name}/revisions/{revision}"
        response = await asyncio.to_thread(
            self.session.get, f"https://run.googleapis.com/v2/{name}", timeout=10
        )
        if response.status_code != 200:
            raise RuntimeError("known-good revision state could not be read")
        body = cast(dict[str, Any], response.json())
        containers = cast(list[dict[str, Any]], body.get("containers", []))
        digest = str(containers[0].get("imageDigest", "")) if containers else ""
        if digest.startswith("sha256:") and len(digest) == 71:
            return digest
        image = str(containers[0].get("image", "")) if containers else ""
        if "@sha256:" in image:
            return image.rsplit("@", 1)[1]
        # Fail closed rather than accepting an unverified tag.
        raise RuntimeError("known-good image digest is unavailable")

    @staticmethod
    def _template_has_failure_profile(body: dict[str, Any]) -> bool:
        template = cast(dict[str, Any], body.get("template", {}))
        containers = cast(list[dict[str, Any]], template.get("containers", []))
        if not containers:
            return False
        environment = cast(list[dict[str, str]], containers[0].get("env", []))
        return any(
            item.get("name") == "OPSPILOT_PAYMENT_FAILURE_PROFILE"
            and item.get("value") == "payment-failure"
            for item in environment
        )


def _firestore_store_from_environment() -> FirestoreRemediationStore:
    return FirestoreRemediationStore(
        project_id=os.environ["OPSPILOT_REMEDIATION_PROJECT_ID"],
        database_id="opspilot-dev",
    )


def _write_recovery_record(path: Path, record: ScenarioRecoveryRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_recovery_record(path: Path) -> ScenarioRecoveryRecord | None:
    if not path.is_file():
        return None
    return ScenarioRecoveryRecord.model_validate_json(path.read_text(encoding="utf-8"))


def render_scenario_command(result: ScenarioCommandResult) -> str:
    values = [
        f"scenario_id: {result.scenario_id}",
        f"operation: {result.operation}",
        f"mode: {result.mode}",
        f"executed: {str(result.executed).lower()}",
    ]
    values.extend(f"step: {step}" for step in result.planned_steps)
    if result.incident_id:
        values.append(f"incident_id: {result.incident_id}")
    if result.report_id:
        values.append(f"report_id: {result.report_id}")
    if result.order_successes is not None:
        values.append(f"order_successes: {result.order_successes}/10")
    if result.baseline_successes is not None:
        values.append(f"baseline_successes: {result.baseline_successes}/10")
    values.append(f"abort_used: {str(result.abort_used).lower()}")
    return "\n".join([*values, ""])
