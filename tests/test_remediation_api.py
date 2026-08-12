from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from opspilot.remediation.api import create_app, create_executor_app
from opspilot.remediation.auth import GoogleIdTokenVerifier, require_service_account
from opspilot.remediation.config import RemediationSettings
from opspilot.remediation.contracts import Principal, RemediationTarget
from opspilot.remediation.errors import AuthenticationError, AuthorizationError
from opspilot.remediation.service import (
    LocalCallbackSender,
    LocalWorkflowGateway,
    RemediationCoordinator,
)
from opspilot.remediation.store import InMemoryRemediationStore
from opspilot.workflow import run_fixture_investigation


class FakeTokenVerifier:
    def verify(self, token: str, *, audience: str) -> Principal:
        if token != "valid-token" or audience != "https://control.example.invalid":
            from opspilot.remediation.errors import AuthenticationError

            raise AuthenticationError("identity token could not be verified")
        return Principal(subject="subject-1", email="approver@example.invalid", email_verified=True)


def _runtime_settings() -> RemediationSettings:
    return RemediationSettings(
        project_id="portfolio-project",
        database_id="opspilot-dev",
        control_audience="opspilot-remediation-control",
        executor_audience="opspilot-remediation-executor",
        workflow_name=(
            "projects/portfolio-project/locations/asia-northeast3/"
            "workflows/opspilot-dev-remediation"
        ),
        workflow_service_account=(
            "opspilot-dev-rem-workflow@portfolio-project.iam.gserviceaccount.com"
        ),
        order_url="https://order.example.invalid",
    )


def test_M8_container_health_does_not_require_adc_or_construct_cloud_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(*_: object, **__: object) -> object:
        raise AssertionError("health must not create a Firestore client")

    monkeypatch.setattr("opspilot.remediation.api.FirestoreRemediationStore", reject)
    for factory, boundary in (
        (create_app, "remediation-control"),
        (create_executor_app, "remediation-executor"),
    ):
        with TestClient(factory(settings=_runtime_settings())) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "boundary": boundary}


def test_M8_google_identity_claims_are_reverified_and_email_is_not_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": "opspilot-remediation-control",
        "sub": "stable-subject",
        "email": "approver@example.invalid",
        "email_verified": True,
    }

    def verify(token: str, request: object, audience: str) -> dict[str, object]:
        del token, request, audience
        return dict(claims)

    monkeypatch.setattr("opspilot.remediation.auth.id_token.verify_oauth2_token", verify)
    principal = GoogleIdTokenVerifier().verify(
        "opaque-token", audience="opspilot-remediation-control"
    )
    assert principal.actor_hash.startswith("sha256:")
    assert "email" not in principal.model_dump(mode="json")

    for field, value in (
        ("iss", "https://attacker.invalid"),
        ("aud", "wrong-audience"),
        ("email_verified", False),
        ("sub", ""),
    ):
        invalid = dict(claims)
        invalid[field] = value

        def verify_invalid(
            token: str,
            request: object,
            audience: str,
            snapshot: dict[str, object] = invalid,
        ) -> dict[str, object]:
            del token, request, audience
            return snapshot

        monkeypatch.setattr(
            "opspilot.remediation.auth.id_token.verify_oauth2_token", verify_invalid
        )
        with pytest.raises(AuthenticationError):
            GoogleIdTokenVerifier().verify("opaque-token", audience="opspilot-remediation-control")

    with pytest.raises(AuthorizationError):
        require_service_account(principal, allowed_email="workflow@example.invalid")


async def _client() -> TestClient:
    store = InMemoryRemediationStore()
    report = await run_fixture_investigation("SCN-008")
    await store.seed_incident(
        report=report,
        target=RemediationTarget(
            project_id="portfolio-project",
            region="asia-northeast3",
            service="opspilot-dev-payment",
            source_revision="payment-faulty",
            target_revision="payment-good",
            target_image_digest="sha256:" + "a" * 64,
            service_etag="etag-faulty",
        ),
    )
    coordinator = RemediationCoordinator(
        store=store,
        workflow=LocalWorkflowGateway(),
        callback_sender=LocalCallbackSender(),
        now=lambda: datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
    )
    return TestClient(create_app(coordinator=coordinator, token_verifier=FakeTokenVerifier()))


async def test_M8_control_api_requires_authentication_and_rejects_target_injection() -> None:
    client = await _client()
    with client:
        unauthenticated = client.post(
            "/api/v1/incidents/INC-2026-0008/remediations",
            headers={"Idempotency-Key": "request-key-0001"},
            json={"report_id": "RPT-SCN-008-001", "action_id": "ACT-01"},
        )
        injected = client.post(
            "/api/v1/incidents/INC-2026-0008/remediations",
            headers={
                "Authorization": "Bearer valid-token",
                "Idempotency-Key": "request-key-0002",
            },
            json={
                "report_id": "RPT-SCN-008-001",
                "action_id": "ACT-01",
                "target_revision": "attacker-revision",
            },
        )

    assert unauthenticated.status_code == 401
    assert "valid-token" not in unauthenticated.text
    assert injected.status_code == 422


async def test_M8_control_api_request_show_and_decision_contract() -> None:
    client = await _client()
    headers = {
        "Authorization": "Bearer valid-token",
        "Idempotency-Key": "request-key-0001",
    }
    with client:
        created = client.post(
            "/api/v1/incidents/INC-2026-0008/remediations",
            headers=headers,
            json={"report_id": "RPT-SCN-008-001", "action_id": "ACT-01"},
        )
        body = created.json()
        shown = client.get(
            f"/api/v1/remediations/{body['remediation_id']}",
            headers={"Authorization": "Bearer valid-token"},
        )
        decision_without_callback = client.post(
            f"/api/v1/remediations/{body['remediation_id']}/decision",
            headers={
                "Authorization": "Bearer valid-token",
                "Idempotency-Key": "decision-key-0001",
            },
            json={"decision": "APPROVE", "plan_hash": body["plan_hash"], "comment": "ok"},
        )

    assert created.status_code == 202
    assert body["status"] == "WAITING_APPROVAL"
    assert shown.status_code == 200
    assert decision_without_callback.status_code == 409
    assert "callback_url" not in created.text
