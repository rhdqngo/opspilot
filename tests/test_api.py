from __future__ import annotations

import base64
import json
import time
from typing import Any, cast

from fastapi.testclient import TestClient

from opspilot.api import create_app


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
            json={"query": "inventory-service recent 15 minutes errors"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "## Summary" in response.text
        assert "## Sources" in response.text


def test_API_rejects_unknown_services_action_requests_and_unpersisted_incidents() -> None:
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
        assert (
            client.post(
                "/api/v1/investigations",
                json={
                    "query": "payment-service 오류 분석",
                    "incident_id": "INC-2026-0002",
                },
            ).status_code
            == 422
        )


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
