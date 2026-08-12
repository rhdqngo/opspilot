"""Private, fixed-target Cloud Run rollback executor."""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import id_token
from pydantic import BaseModel, Field

from opspilot.remediation.contracts import (
    ExecutionRequest,
    RemediationRecord,
    RemediationStatus,
    VerificationEvidence,
    utc_now,
)
from opspilot.remediation.errors import ConflictError, DependencyError
from opspilot.remediation.google import _authorized_session
from opspilot.remediation.store import RemediationStore


class CloudRunServiceSnapshot(BaseModel):
    name: str
    etag: str
    traffic: dict[str, int]
    reconciling: bool = False


class CloudRunRevisionSnapshot(BaseModel):
    name: str
    ready: bool
    image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ExecutionOutcome(BaseModel):
    remediation_id: str
    execution_attempt_id: str
    traffic_update_succeeded: bool
    safe_failure_code: str | None = None


class CloudRunAdmin(Protocol):
    async def get_service(self, service_name: str) -> CloudRunServiceSnapshot: ...

    async def get_revision(self, revision_name: str) -> CloudRunRevisionSnapshot: ...

    async def update_traffic(
        self, service: CloudRunServiceSnapshot, *, target_revision: str
    ) -> str: ...

    async def wait_operation(self, operation_name: str, *, timeout_seconds: int) -> None: ...


class ExecutionGuardError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class FixedPaymentRollbackExecutor:
    def __init__(
        self,
        *,
        store: RemediationStore,
        cloud_run: CloudRunAdmin,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.store = store
        self.cloud_run = cloud_run
        self.now = now

    async def execute(self, remediation_id: str, request: ExecutionRequest) -> ExecutionOutcome:
        record = await self.store.get(remediation_id)
        if record is None:
            raise ConflictError("remediation not found")
        if (
            record.status is not RemediationStatus.EXECUTING
            or record.plan_hash != request.plan_hash
            or record.execution_attempt_id != request.execution_attempt_id
        ):
            raise ConflictError("remediation execution lease does not match")
        if self.now() >= record.expires_at:
            return self._failure(record, "EXECUTION_LEASE_EXPIRED")
        target = await self.store.get_target(record.incident_id)
        if target is None:
            return self._failure(record, "TRUSTED_TARGET_MISSING")
        try:
            if target.service_name != (
                f"projects/{target.project_id}/locations/{target.region}/services/"
                "opspilot-dev-payment"
            ):
                raise ExecutionGuardError("TARGET_SERVICE_MISMATCH")
            if (
                target.source_revision != record.plan.source_revision
                or target.target_revision != record.plan.target_revision
                or target.target_image_digest != record.plan.target_image_digest
                or target.service_etag != record.plan.service_etag
            ):
                raise ExecutionGuardError("TRUSTED_PLAN_MISMATCH")
            service = await self.cloud_run.get_service(target.service_name)
            if service.name != target.service_name:
                raise ExecutionGuardError("TARGET_SERVICE_MISMATCH")
            if service.etag != record.plan.service_etag:
                raise ExecutionGuardError("STALE_SERVICE_ETAG")
            already_recovered = (
                not service.reconciling and service.traffic.get(record.plan.target_revision) == 100
            )
            if not already_recovered and service.traffic.get(record.plan.source_revision) != 100:
                raise ExecutionGuardError("SOURCE_REVISION_NOT_SERVING")
            revision_name = (
                f"projects/{target.project_id}/locations/{target.region}/services/"
                f"{target.service}/revisions/{record.plan.target_revision}"
            )
            revision = await self.cloud_run.get_revision(revision_name)
            if not revision.ready:
                raise ExecutionGuardError("TARGET_REVISION_NOT_READY")
            if revision.image_digest != record.plan.target_image_digest:
                raise ExecutionGuardError("TARGET_IMAGE_DIGEST_MISMATCH")
            if not already_recovered:
                await self._update_or_confirm(service, record.plan.target_revision)
            serving = await self.cloud_run.get_service(target.service_name)
            if serving.reconciling or serving.traffic.get(record.plan.target_revision) != 100:
                raise ExecutionGuardError("TRAFFIC_UPDATE_NOT_CONFIRMED")
            return ExecutionOutcome(
                remediation_id=record.remediation_id,
                execution_attempt_id=request.execution_attempt_id,
                traffic_update_succeeded=True,
            )
        except ExecutionGuardError as error:
            return self._failure(record, error.code)
        except (DependencyError, TimeoutError):
            return self._failure(record, "EXECUTOR_DEPENDENCY_FAILURE")

    async def _update_or_confirm(
        self, service: CloudRunServiceSnapshot, target_revision: str
    ) -> None:
        try:
            operation = await self.cloud_run.update_traffic(
                service, target_revision=target_revision
            )
            await self.cloud_run.wait_operation(operation, timeout_seconds=120)
        except (DependencyError, TimeoutError):
            current = await self.cloud_run.get_service(service.name)
            if not current.reconciling and current.traffic.get(target_revision) == 100:
                return
            raise

    def _failure(self, record: RemediationRecord, code: str) -> ExecutionOutcome:
        if record.execution_attempt_id is None:
            raise ConflictError("execution attempt was not recorded")
        return ExecutionOutcome(
            remediation_id=record.remediation_id,
            execution_attempt_id=record.execution_attempt_id,
            traffic_update_succeeded=False,
            safe_failure_code=code,
        )


class GoogleCloudRunAdmin:
    def __init__(self, session: AuthorizedSession | None = None) -> None:
        self.session = session or _authorized_session()

    async def get_service(self, service_name: str) -> CloudRunServiceSnapshot:
        response = await asyncio.to_thread(
            self.session.get,
            f"https://run.googleapis.com/v2/{service_name}",
            timeout=10,
        )
        if response.status_code != 200:
            raise DependencyError("Cloud Run service state could not be read")
        body = cast(dict[str, Any], response.json())
        traffic = {
            str(item.get("revision")): int(item.get("percent", 0))
            for item in cast(list[dict[str, Any]], body.get("trafficStatuses", []))
            if item.get("revision")
        }
        return CloudRunServiceSnapshot(
            name=str(body.get("name", "")),
            etag=str(body.get("etag", "")),
            traffic=traffic,
            reconciling=bool(body.get("reconciling", False)),
        )

    async def get_revision(self, revision_name: str) -> CloudRunRevisionSnapshot:
        response = await asyncio.to_thread(
            self.session.get,
            f"https://run.googleapis.com/v2/{revision_name}",
            timeout=10,
        )
        if response.status_code != 200:
            raise DependencyError("Cloud Run revision state could not be read")
        body = cast(dict[str, Any], response.json())
        containers = cast(list[dict[str, Any]], body.get("containers", []))
        image_digest = ""
        if containers:
            image_digest = str(
                containers[0].get("imageDigest") or containers[0].get("image", "")
            ).rsplit("@", 1)[-1]
        condition = cast(dict[str, Any], body.get("terminalCondition", {}))
        ready = condition.get("state") == "CONDITION_SUCCEEDED"
        return CloudRunRevisionSnapshot(
            name=str(body.get("name", "")), ready=ready, image_digest=image_digest
        )

    async def update_traffic(
        self, service: CloudRunServiceSnapshot, *, target_revision: str
    ) -> str:
        response = await asyncio.to_thread(
            self.session.patch,
            f"https://run.googleapis.com/v2/{service.name}?updateMask=traffic",
            json={
                "name": service.name,
                "etag": service.etag,
                "traffic": [
                    {
                        "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                        "revision": target_revision,
                        "percent": 100,
                    }
                ],
            },
            timeout=10,
        )
        if response.status_code not in {200, 202}:
            raise DependencyError("Cloud Run traffic update was rejected")
        body = cast(dict[str, Any], response.json())
        name = body.get("name")
        if not isinstance(name, str) or not name:
            raise DependencyError("Cloud Run traffic update returned an invalid operation")
        return name

    async def wait_operation(self, operation_name: str, *, timeout_seconds: int) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            response = await asyncio.to_thread(
                self.session.get,
                f"https://run.googleapis.com/v2/{operation_name}",
                timeout=10,
            )
            if response.status_code != 200:
                raise DependencyError("Cloud Run operation state could not be read")
            body = cast(dict[str, Any], response.json())
            if body.get("done") is True:
                if "error" in body:
                    raise DependencyError("Cloud Run traffic operation failed")
                return
            await asyncio.sleep(1)
        raise TimeoutError("Cloud Run traffic operation timed out")


class GoogleControlRecoveryVerifier:
    """Control-plane traffic, ten-order, and auxiliary Monitoring verification."""

    def __init__(
        self,
        *,
        store: RemediationStore,
        cloud_run: CloudRunAdmin,
        project_id: str,
        order_url: str,
        audience: str,
        session: AuthorizedSession | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.store = store
        self.cloud_run = cloud_run
        self.project_id = project_id
        self.order_url = order_url.rstrip("/")
        self.audience = audience
        self.session = session or _authorized_session()
        self.now = now

    async def verify(self, record: RemediationRecord) -> VerificationEvidence:
        target = await self.store.get_target(record.incident_id)
        if target is None:
            raise DependencyError("trusted verification target could not be read")
        service = await self.cloud_run.get_service(target.service_name)
        target_percent = (
            0 if service.reconciling else service.traffic.get(record.plan.target_revision, 0)
        )
        try:
            token = await asyncio.to_thread(id_token.fetch_id_token, Request(), self.audience)
        except (GoogleAuthError, ValueError) as error:
            raise DependencyError(
                "order verification identity token could not be minted"
            ) from error
        semaphore = asyncio.Semaphore(2)

        async def bounded(index: int) -> bool:
            async with semaphore:
                return await asyncio.to_thread(self._send_order, index, token)

        results = await asyncio.gather(*(bounded(index) for index in range(1, 11)))
        verified_at = self.now()
        window = timedelta(minutes=record.plan.verification.window_minutes)
        before, after = await asyncio.gather(
            self._metric_points(record.plan.created_at - window, record.plan.created_at),
            self._metric_points(verified_at - window, verified_at),
        )
        return VerificationEvidence(
            target_traffic_percent=target_percent,
            order_successes=sum(results),
            metric_windows_recorded=before is not None and after is not None,
            metric_before_points=before or 0,
            metric_after_points=after or 0,
            verified_at=verified_at,
        )

    async def _metric_points(self, start: datetime, end: datetime) -> int | None:
        params: dict[str, str] = {
            "filter": (
                'metric.type="run.googleapis.com/request_count" AND '
                'resource.type="cloud_run_revision" AND '
                'resource.label.service_name="opspilot-dev-payment"'
            ),
            "interval.startTime": start.isoformat(),
            "interval.endTime": end.isoformat(),
            "aggregation.alignmentPeriod": "60s",
            "aggregation.perSeriesAligner": "ALIGN_SUM",
            "view": "FULL",
            "pageSize": "100",
        }
        response = await asyncio.to_thread(
            self.session.get,
            f"https://monitoring.googleapis.com/v3/projects/{self.project_id}/timeSeries",
            params=params,
            timeout=10,
        )
        if response.status_code != 200:
            return None
        body = cast(dict[str, Any], response.json())
        series = cast(list[dict[str, Any]], body.get("timeSeries", []))
        return sum(len(cast(list[dict[str, Any]], item.get("points", []))) for item in series)

    def _send_order(self, index: int, token: str) -> bool:
        request_id = f"req_m8_verify_{secrets.token_hex(6)}_{index:02d}"
        request = UrlRequest(
            f"{self.order_url}/v1/orders",
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
                return bool(
                    response.status == 201 and response.headers.get("X-Request-ID") == request_id
                )
        except HTTPError as error:
            error.close()
            return False
        except (URLError, TimeoutError):
            return False
