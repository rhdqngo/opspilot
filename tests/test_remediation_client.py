from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.request import Request

import pytest

from opspilot.remediation.client import RemediationApiClient, render_remediation
from opspilot.remediation.contracts import (
    Principal,
    RemediationPlan,
    RemediationRecord,
    RemediationStatus,
    VerificationPlan,
)


def _record() -> RemediationRecord:
    now = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    plan = RemediationPlan(
        incident_id="INC-2026-0008",
        report_id="RPT-SCN-008-001",
        action_id="ACT-01",
        source_revision="payment-faulty",
        target_revision="payment-good",
        target_image_digest="sha256:" + "a" * 64,
        service_etag="etag-faulty",
        evidence_ids=["EV-CHG-0008"],
        expected_effect="recover",
        verification=VerificationPlan(),
        created_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    principal = Principal(
        subject="subject-1", email="approver@example.invalid", email_verified=True
    )
    return RemediationRecord(
        remediation_id="REM-0123456789ABCDEF",
        incident_id=plan.incident_id,
        report_id=plan.report_id,
        action_id=plan.action_id,
        plan=plan,
        plan_hash=plan.plan_hash,
        status=RemediationStatus.WAITING_APPROVAL,
        requester_actor_hash=principal.actor_hash,
        created_at=now,
        updated_at=now,
        expires_at=plan.expires_at,
    )


class FakeResponse:
    status = 202

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_M8_client_retries_with_the_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Request] = []
    payload = json.dumps(_record().model_dump(mode="json")).encode()

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        assert timeout == 30
        calls.append(request)
        if len(calls) == 1:
            raise URLError("lost response")
        return FakeResponse(payload)

    monkeypatch.setattr("opspilot.remediation.client.gcloud_identity_token", lambda _: "token")
    monkeypatch.setattr("opspilot.remediation.client.urlopen", fake_urlopen)
    monkeypatch.setattr("opspilot.remediation.client.time.sleep", lambda _: None)
    client = RemediationApiClient("https://control.example.invalid", "audience")
    record = client.request(
        incident_id="INC-2026-0008",
        report_id="RPT-SCN-008-001",
        action_id="ACT-01",
        idempotency_key="fixed-request-key",
    )
    assert record.remediation_id == "REM-0123456789ABCDEF"
    assert len(calls) == 2
    assert {call.get_header("Idempotency-key") for call in calls} == {"fixed-request-key"}


def test_M8_remediation_json_output_is_machine_readable_and_token_free() -> None:
    rendered = render_remediation(_record(), "json")
    payload = json.loads(rendered)
    assert payload["status"] == "WAITING_APPROVAL"
    assert "token" not in rendered.casefold()
