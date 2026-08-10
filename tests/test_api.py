from __future__ import annotations

import time
from typing import Any, cast

from fastapi.testclient import TestClient

from opspilot.api import create_app


def _wait_for_completion(client: TestClient, investigation_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for _ in range(50):
        response = client.get(f"/api/v1/investigations/{investigation_id}")
        assert response.status_code == 200
        payload = cast(dict[str, Any], response.json())
        if payload["status"] in {"COMPLETE", "FAILED"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("investigation did not complete")


def test_health_and_readiness() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/healthz").json()["status"] == "ok"
        assert client.get("/readyz").json()["allowlisted_services"] == 3


def test_FR_023_investigation_api_returns_json_and_markdown_report() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/investigations",
            json={"query": "payment-service 오류율을 분석해줘", "mode": "STANDARD"},
        )
        assert response.status_code == 202
        started = cast(dict[str, Any], response.json())
        completed = _wait_for_completion(client, cast(str, started["investigation_id"]))
        assert completed["status"] == "COMPLETE"
        incident_id = cast(str, completed["incident_id"])
        json_report = client.get(f"/api/v1/incidents/{incident_id}/reports/latest")
        assert json_report.status_code == 200
        assert json_report.json()["hypotheses"][0]["evidence_support_score"] == 100
        markdown_report = client.get(
            f"/api/v1/incidents/{incident_id}/reports/latest",
            headers={"Accept": "text/markdown"},
        )
        assert markdown_report.status_code == 200
        assert markdown_report.headers["content-type"].startswith("text/markdown")
        assert "EV-LOG-0001" in markdown_report.text


def test_API_returns_404_and_422_for_invalid_requests() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/investigations/INV-MISSING").status_code == 404
        assert client.get("/api/v1/incidents/INC-2026-9999/reports/latest").status_code == 404
        response = client.post(
            "/api/v1/investigations",
            json={"query": "unknown-service 오류를 분석해줘"},
        )
        assert response.status_code == 422


def test_NFR_002_R0_exposes_no_remediation_route() -> None:
    paths = create_app().openapi()["paths"]
    assert all("remediation" not in path for path in paths)
