from __future__ import annotations

import base64
import json
import time
from typing import Any, cast

from fastapi.testclient import TestClient

from opspilot.api import create_app
from opspilot.audit import audit_hash
from opspilot.remediation.contracts import Principal


class FakeTokenVerifier:
    def __init__(self, *, email: str = "runtime@example.invalid") -> None:
        self.email = email

    def verify(self, token: str, *, audience: str) -> Principal:
        assert token == "valid-token"
        assert audience == "opspilot-investigation-api"
        return Principal(
            subject="verified-subject",
            email=self.email,
            email_verified=True,
        )


def _wait_for_completion(client: TestClient, investigation_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for _ in range(100):
        response = client.get(f"/api/v1/investigations/{investigation_id}")
        assert response.status_code == 200
        payload = cast(dict[str, Any], response.json())
        if payload["status"] in {"COMPLETE", "FAILED"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("investigation did not complete")


def _pubsub(payload: dict[str, Any], message_id: str) -> dict[str, Any]:
    return {
        "message": {
            "messageId": message_id,
            "data": base64.b64encode(json.dumps(payload).encode()).decode(),
            "attributes": {"ignored": "not persisted"},
        },
        "subscription": "ignored",
    }


def test_health_and_readiness() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/healthz").json()["status"] == "ok"
        assert client.get("/readyz").json()["allowlisted_services"] == 3


def test_investigation_api_supports_all_catalog_services_and_versioned_reports() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/investigations",
            json={"query": "order-service payment-service 최근 45분 오류 분석", "mode": "STANDARD"},
        )
        assert response.status_code == 202
        started = cast(dict[str, Any], response.json())
        assert started["incident_id"].startswith("INC-")
        completed = _wait_for_completion(client, cast(str, started["investigation_id"]))
        assert completed["status"] == "COMPLETE"
        assert completed["report_version"] == 1
        incident_id = cast(str, completed["incident_id"])

        incident = client.get(f"/api/v1/incidents/{incident_id}")
        assert incident.status_code == 200
        assert incident.json()["latest_report_version"] == 1
        json_report = client.get(f"/api/v1/incidents/{incident_id}/reports/latest")
        assert json_report.status_code == 200
        assert json_report.json()["affected_services"] == ["order-service", "payment-service"]
        assert json_report.json()["report_version"] == 1
        markdown_report = client.get(
            f"/api/v1/incidents/{incident_id}/reports/latest",
            headers={"Accept": "text/markdown"},
        )
        assert markdown_report.status_code == 200
        assert markdown_report.headers["content-type"].startswith("text/markdown")

        replay = client.post(f"/api/v1/incidents/{incident_id}/replays")
        assert replay.status_code == 202
        replayed = _wait_for_completion(client, replay.json()["investigation_id"])
        assert replayed["report_version"] == 2
        versions = client.get(f"/api/v1/incidents/{incident_id}/reports").json()
        assert [item["report_version"] for item in versions] == [1, 2]
        comparison = client.get(
            f"/api/v1/incidents/{incident_id}/reports/compare",
            params={"from_version": 1, "to_version": 2},
        )
        assert comparison.status_code == 200
        assert comparison.json()["from_version"] == 1
        assert comparison.json()["to_version"] == 2
        assert comparison.json()["evidence_ids"]["changed"] is False


def test_runtime_bridge_waits_for_the_same_queued_persisted_report() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/internal/v1/runtime/investigations",
            json={
                "query": "inventory-service recent 15 minutes errors",
                "run_id": "RUN-0123456789ABCDEF",
                "correlation_id": "COR-0123456789ABCDEF",
                "trace_id": "0123456789abcdef0123456789abcdef",
                "actor_hash": "a" * 64,
                "session_hash": "b" * 64,
                "query_hash": audit_hash(
                    "enterprise_query",
                    "inventory-service recent 15 minutes errors",
                ),
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "## Summary" in response.text
        assert "## Sources" in response.text


def test_runtime_bridge_localizes_korean_and_renders_default_dev_assumption() -> None:
    query = "payment-service 최근 15분 오류를 분석해줘"
    with TestClient(create_app()) as client:
        response = client.post(
            "/internal/v1/runtime/investigations",
            json={
                "query": query,
                "run_id": "RUN-1234567890ABCDEF",
                "correlation_id": "COR-1234567890ABCDEF",
                "trace_id": "1234567890abcdef1234567890abcdef",
                "query_hash": audit_hash("enterprise_query", query),
                "output_language": "ko",
            },
        )

        assert response.status_code == 200
        assert "## 요약" in response.text
        assert "## 가정" in response.text
        assert "환경이 지정되지 않아 DEV를 사용합니다." in response.text


def test_api_hashes_verified_actor_and_rejects_unauthenticated_calls(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("OPSPILOT_INVESTIGATION_AUDIENCE", "opspilot-investigation-api")
    with TestClient(create_app(token_verifier=FakeTokenVerifier())) as client:
        unauthorized = client.post(
            "/api/v1/investigations",
            json={"query": "dev payment-service last 10 minutes errors"},
        )
        assert unauthorized.status_code == 401

        started = client.post(
            "/api/v1/investigations",
            headers={
                "Authorization": "Bearer valid-token",
                "X-Cloud-Trace-Context": "0123456789abcdef0123456789abcdef/1;o=1",
            },
            json={
                "query": (
                    "dev payment-service last 10 minutes errors "
                    "operator@example.invalid token=supersecret123"
                )
            },
        )
        assert started.status_code == 202
        assert started.json()["trace_id"] == "0123456789abcdef0123456789abcdef"
        status_payload = client.get(
            f"/api/v1/investigations/{started.json()['investigation_id']}"
        ).json()
        assert status_payload["audit"]["source"] == "direct_api"
        assert status_payload["audit"]["actor_hash"] == audit_hash(
            "direct_api_actor", "verified-subject"
        )
        serialized = json.dumps(status_payload)
        assert "operator@example.invalid" not in serialized
        assert "supersecret123" not in serialized


def test_API_rejects_unknown_services_and_actions_but_creates_named_incidents() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/investigations/INV-MISSING").status_code == 404
        assert client.get("/api/v1/incidents/INC-2026-9999/reports/latest").status_code == 404
        assert (
            client.post(
                "/api/v1/investigations", json={"query": "unknown-service 오류 분석"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/investigations", json={"query": "payment-service 롤백해줘"}
            ).status_code
            == 422
        )
        named = client.post(
            "/api/v1/investigations",
            json={
                "query": "payment-service 오류 분석",
                "incident_id": "INC-2026-0002",
            },
        )
        assert named.status_code == 202
        assert named.json()["incident_id"] == "INC-2026-0002"
        assert client.get("/api/v1/incidents/INC-2026-0002").status_code == 200


def test_monitoring_pubsub_open_close_deduplicates_and_starts_no_investigation() -> None:
    payload = {
        "incident": {
            "incident_id": "provider-secret-incident-key",
            "state": "OPEN",
            "started_at": "2026-08-13T00:00:00Z",
            "resource": {
                "labels": {
                    "service_name": "inventory-service",
                    "user_email": "must-not-persist@example.invalid",
                }
            },
            "documentation": {"content": "raw payload must not persist"},
        }
    }
    with TestClient(create_app()) as client:
        opened = client.post("/internal/v1/alerts/monitoring", json=_pubsub(payload, "message-1"))
        assert opened.status_code == 200
        assert opened.json()["investigation_started"] is False
        incident_id = opened.json()["incident_id"]
        duplicate = client.post(
            "/internal/v1/alerts/monitoring", json=_pubsub(payload, "message-1")
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["created_or_updated"] is False
        assert duplicate.json()["incident_id"] == incident_id

        payload["incident"]["state"] = "CLOSED"
        payload["incident"]["ended_at"] = "2026-08-13T00:15:00Z"
        closed = client.post("/internal/v1/alerts/monitoring", json=_pubsub(payload, "message-2"))
        assert closed.status_code == 200
        assert closed.json()["incident_id"] == incident_id
        stored = client.get(f"/api/v1/incidents/{incident_id}").json()
        assert stored["state"] == "CLOSED"
        serialized = json.dumps(stored)
        assert "provider-secret-incident-key" not in serialized
        assert "must-not-persist" not in serialized
        assert "raw payload" not in serialized


def test_monitoring_pubsub_rejects_bad_envelope_and_unknown_service() -> None:
    with TestClient(create_app()) as client:
        assert (
            client.post(
                "/internal/v1/alerts/monitoring",
                json={"message": {"messageId": "bad-1", "data": "%%%"}},
            ).status_code
            == 422
        )
        unknown = {
            "incident": {
                "incident_id": "x",
                "state": "OPEN",
                "resource": {"labels": {"service_name": "unknown-service"}},
            }
        }
        assert (
            client.post(
                "/internal/v1/alerts/monitoring", json=_pubsub(unknown, "bad-2")
            ).status_code
            == 422
        )


def test_public_api_exposes_no_generalized_remediation_route() -> None:
    paths = create_app().openapi()["paths"]
    assert all("remediation" not in path for path in paths)
