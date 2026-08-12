"""Token-safe CLI client for the authenticated remediation control API."""

from __future__ import annotations

import json
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from opspilot.remediation.contracts import RemediationRecord


def gcloud_identity_token(audience: str) -> str:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    try:
        completed = subprocess.run(
            [executable, "auth", "print-identity-token", f"--audiences={audience}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("gcloud identity token is unavailable") from error
    token = completed.stdout.strip()
    if completed.returncode != 0 or not token:
        raise RuntimeError("gcloud identity token is unavailable")
    return token


class RemediationApiClient:
    def __init__(self, base_url: str, audience: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.audience = audience

    def request(
        self,
        *,
        incident_id: str,
        report_id: str,
        action_id: str,
        idempotency_key: str,
    ) -> RemediationRecord:
        return self._send(
            "POST",
            f"/api/v1/incidents/{incident_id}/remediations",
            {
                "report_id": report_id,
                "action_id": action_id,
                "verification_window_minutes": 10,
            },
            idempotency_key=idempotency_key,
        )

    def show(self, remediation_id: str) -> RemediationRecord:
        return self._send("GET", f"/api/v1/remediations/{remediation_id}", None)

    def decide(
        self,
        *,
        remediation_id: str,
        decision: str,
        plan_hash: str,
        comment: str,
        idempotency_key: str,
    ) -> RemediationRecord:
        return self._send(
            "POST",
            f"/api/v1/remediations/{remediation_id}/decision",
            {"decision": decision.upper(), "plan_hash": plan_hash, "comment": comment},
            idempotency_key=idempotency_key,
        )

    def _send(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        *,
        idempotency_key: str | None = None,
    ) -> RemediationRecord:
        token = gcloud_identity_token(self.audience)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
        except HTTPError as error:
            error.close()
            raise RuntimeError(f"remediation API returned HTTP {error.code}") from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError("remediation API is unavailable") from error
        return RemediationRecord.model_validate(body)


def render_remediation(record: RemediationRecord) -> str:
    return "\n".join(
        [
            f"remediation_id: {record.remediation_id}",
            f"status: {record.status.value}",
            f"plan_hash: {record.plan_hash}",
            f"expires_at: {record.expires_at.isoformat()}",
            f"self_approved: {str(record.self_approved).lower()}",
            "",
        ]
    )
