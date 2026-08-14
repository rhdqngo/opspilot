"""Service-to-service bridge that can only create approval-waiting remediation requests."""

from __future__ import annotations

import asyncio
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import id_token
from pydantic import BaseModel

from opspilot.domain import IncidentReport
from opspilot.retry import RetryPolicy, run_with_retry


class RemediationRequestReference(BaseModel):
    remediation_id: str
    status: str
    expires_at: str


class RemediationRequestGateway(Protocol):
    async def request(
        self,
        *,
        incident_id: str,
        report: IncidentReport,
        actor_hash: str,
        idempotency_key: str,
    ) -> RemediationRequestReference: ...


class HttpRemediationRequestGateway:
    def __init__(self, *, base_url: str, audience: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.audience = audience

    async def request(
        self,
        *,
        incident_id: str,
        report: IncidentReport,
        actor_hash: str,
        idempotency_key: str,
    ) -> RemediationRequestReference:
        rollback = next(
            (
                action
                for action in report.recommended_actions
                if action.category == "ROLLBACK_CLOUD_RUN"
                and action.target_service == "payment-service"
            ),
            None,
        )
        if rollback is None:
            raise ValueError("report has no eligible rollback action")
        token = await asyncio.to_thread(id_token.fetch_id_token, AuthRequest(), self.audience)
        payload = {
            "report_id": report.report_id,
            "report_version": report.report_version,
            "action_id": rollback.action_id,
            "verification_window_minutes": 10,
            "requester_actor_hash": f"sha256:{actor_hash}",
        }
        body = json.dumps(payload, separators=(",", ":")).encode()

        class RetryableFailure(RuntimeError):
            pass

        def send() -> object:
            request = Request(
                (
                    f"{self.base_url}/internal/v1/incidents/"
                    f"{quote(incident_id)}/remediation-requests"
                ),
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
            )
            try:
                with urlopen(request, timeout=10) as response:
                    return json.loads(response.read())
            except HTTPError as error:
                status = error.code
                error.close()
                if status == 429 or status >= 500:
                    raise RetryableFailure(
                        "remediation control is temporarily unavailable"
                    ) from error
                raise ValueError("remediation request was rejected by policy") from error
            except (URLError, TimeoutError) as error:
                raise RetryableFailure("remediation control is temporarily unavailable") from error

        try:
            result = await asyncio.to_thread(
                run_with_retry,
                send,
                policy=RetryPolicy(deadline_seconds=20),
                should_retry=lambda error: isinstance(error, RetryableFailure),
            )
        except RetryableFailure as error:
            raise ValueError("remediation control is temporarily unavailable") from error
        return RemediationRequestReference.model_validate(result)
