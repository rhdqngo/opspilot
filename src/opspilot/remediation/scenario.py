"""SCN-008 operator preparation and reset planning/execution."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
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
from opspilot.domain import IncidentReport, RecommendedAction, ReportStatus, SourceType
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
ScenarioOperation = Literal["prepare", "reset"]


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
    order_successes: int | None = Field(default=None, ge=0, le=10)


class ScenarioCloudAdmin(Protocol):
    async def prepare_faulty_revision(self) -> RemediationTarget: ...

    async def reset_known_good_template(self) -> None: ...


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


async def run_scn008_command(
    *,
    operation: ScenarioOperation,
    mode: ScenarioMode,
    auth: str,
    admin: ScenarioCloudAdmin | None = None,
    store: FirestoreRemediationStore | None = None,
) -> ScenarioCommandResult:
    if auth != "gcloud":
        raise ValueError("SCN-008 requires gcloud authentication")
    steps = PREPARE_STEPS if operation == "prepare" else RESET_STEPS
    if mode == "plan":
        return ScenarioCommandResult(
            operation=operation, mode=mode, planned_steps=steps, executed=False
        )
    cloud = admin or GoogleScenarioCloudAdmin.from_environment()
    if operation == "reset":
        await cloud.reset_known_good_template()
        return ScenarioCommandResult(
            operation=operation, mode=mode, planned_steps=steps, executed=True
        )
    target = await cloud.prepare_faulty_revision()
    successes = await _run_ten_orders(
        os.environ["OPSPILOT_ORDER_URL"], await asyncio.to_thread(_gcloud_identity_token)
    )
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
    result = await run_agent_context(
        AgentEvidenceContext(
            scenario_id="SCN-008",
            incident_id=f"INC-{end_time.year:04d}-0008",
            generated_at=end_time,
            correlation_id=f"COR-{secrets.token_hex(8).upper()}",
            evidence=collection.evidence,
            tool_errors=collection.tool_errors,
            data_gaps=collection.data_gaps,
        ),
        model_backend=ModelBackend.FAKE,
        complete=collection.complete,
    )
    if not result.succeeded or result.report is None:
        raise RuntimeError("SCN-008 investigation report could not be generated")
    report = _bind_scn008_rollback_action(result.report)
    if store is None:
        project_id = os.environ["OPSPILOT_REMEDIATION_PROJECT_ID"]
        store = FirestoreRemediationStore(project_id=project_id, database_id="opspilot-dev")
    await store.save_incident(report=report, target=target)
    return ScenarioCommandResult(
        operation=operation,
        mode=mode,
        planned_steps=steps,
        executed=True,
        incident_id=report.incident_id,
        report_id=report.report_id,
        source_revision=target.source_revision,
        target_revision=target.target_revision,
        order_successes=successes,
    )


def _bind_scn008_rollback_action(report: IncidentReport) -> IncidentReport:
    validated = IncidentReport.model_validate(report)
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
    )
    return validated.model_copy(update={"recommended_actions": [action]})


async def _run_ten_orders(order_url: str, token: str) -> int:
    semaphore = asyncio.Semaphore(2)

    async def bounded(index: int) -> bool:
        async with semaphore:
            return await asyncio.to_thread(_send_order, order_url, index, token)

    results = await asyncio.gather(*(bounded(index) for index in range(1, 11)))
    return sum(results)


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
            f"projects/{project_id}/locations/{region}/services/opspilot-dev-payment"
        )

    @classmethod
    def from_environment(cls) -> GoogleScenarioCloudAdmin:
        return cls(
            project_id=os.environ["OPSPILOT_REMEDIATION_PROJECT_ID"],
            region=os.environ.get("OPSPILOT_REMEDIATION_REGION", "asia-northeast3"),
            image_uri=os.environ["OPSPILOT_REMEDIATION_IMAGE_URI"],
        )

    async def prepare_faulty_revision(self) -> RemediationTarget:
        before = await self._get_service()
        source_revision = self._sole_traffic_revision(before)
        target_digest = await self._revision_digest(source_revision)
        if not self.image_uri.endswith(f"@{target_digest}"):
            raise RuntimeError("SCN-008 image must match the known-good revision digest")
        faulty_revision = f"payment-m8-{secrets.token_hex(4)}"
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
        body["traffic"] = [
            {
                "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                "revision": faulty_revision,
                "percent": 100,
            }
        ]
        await self._patch_service(body, update_mask="template,traffic")
        after = await self._get_service()
        return RemediationTarget(
            project_id=self.project_id,
            region=self.region,
            service="opspilot-dev-payment",
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

    async def _get_service(self) -> dict[str, Any]:
        response = await asyncio.to_thread(
            self.session.get,
            f"https://run.googleapis.com/v2/{self.service_name}",
            timeout=10,
        )
        if response.status_code != 200:
            raise RuntimeError("payment service state could not be read")
        return cast(dict[str, Any], response.json())

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
    return "\n".join([*values, ""])
