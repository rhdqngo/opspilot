"""Google API adapters that keep credentials and callback URLs out of outputs."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, cast

import google.auth
from google.auth.transport.requests import AuthorizedSession

from opspilot.remediation.contracts import RemediationDecision
from opspilot.remediation.errors import DependencyError


def _authorized_session() -> AuthorizedSession:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)  # type: ignore[no-untyped-call]


class GoogleWorkflowGateway:
    def __init__(self, workflow_name: str, session: AuthorizedSession | None = None) -> None:
        self.workflow_name = workflow_name
        self.session = session or _authorized_session()

    async def start(self, remediation_id: str, expires_at: datetime) -> str:
        payload = {
            "argument": json.dumps(
                {
                    "remediation_id": remediation_id,
                    "expires_at": expires_at.isoformat(),
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        }
        url = f"https://workflowexecutions.googleapis.com/v1/{self.workflow_name}/executions"
        response = await asyncio.to_thread(self.session.post, url, json=payload, timeout=10)
        if response.status_code not in {200, 201}:
            raise DependencyError("approval workflow could not be started")
        body = cast(dict[str, Any], response.json())
        name = body.get("name")
        if not isinstance(name, str) or not name:
            raise DependencyError("approval workflow returned an invalid response")
        return name


class GoogleCallbackSender:
    def __init__(self, session: AuthorizedSession | None = None) -> None:
        self.session = session or _authorized_session()

    async def send(
        self,
        callback_url: str,
        *,
        remediation_id: str,
        decision: RemediationDecision,
        plan_hash: str,
    ) -> None:
        response = await asyncio.to_thread(
            self.session.post,
            callback_url,
            json={
                "remediation_id": remediation_id,
                "decision": decision.value,
                "plan_hash": plan_hash,
            },
            timeout=10,
        )
        # Workflows returns 404 once a callback has already been consumed. The approval
        # transaction is idempotent, so that response is a successful replay, not a reason to
        # turn an already-recorded decision into an API failure.
        if response.status_code not in {200, 201, 202, 204, 404}:
            raise DependencyError("approval callback could not be delivered")
