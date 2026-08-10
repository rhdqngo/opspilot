from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from opspilot.demo.api import create_app
from opspilot.demo.client import DependencyCallError
from opspilot.demo.config import DemoSettings
from opspilot.demo.models import DemoService


class FakeDependencyClient:
    def __init__(self, *, fail_payment: bool = False, mismatch_inventory_id: bool = False) -> None:
        self.fail_payment = fail_payment
        self.mismatch_inventory_id = mismatch_inventory_id
        self.calls: list[dict[str, Any]] = []

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        request_id: str,
        trace_context: str | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "url": url,
                "payload": payload,
                "request_id": request_id,
                "trace_context": trace_context,
                "timeout_seconds": timeout_seconds,
            }
        )
        if "/payments/" in url:
            if self.fail_payment:
                raise DependencyCallError("fixture failure")
            return {
                "authorization_id": "pay_0123456789abcdef",
                "status": "APPROVED",
                "request_id": request_id,
            }
        return {
            "reservation_id": "res_0123456789abcdef",
            "status": "RESERVED",
            "request_id": "req_wrong_0000" if self.mismatch_inventory_id else request_id,
        }


def _settings(service: DemoService) -> DemoSettings:
    values: dict[str, object] = {"service": service}
    if service is DemoService.ORDER:
        values.update(
            payment_service_url="http://payment:8080",
            inventory_service_url="http://inventory:8080",
        )
    return DemoSettings.model_validate(values)


def test_M2_order_fulfills_and_propagates_request_and_trace_ids() -> None:
    dependency = FakeDependencyClient()
    trace_context = "4bf92f3577b34da6a3ce929d0e0e4736/123;o=1"
    with TestClient(create_app(_settings(DemoService.ORDER), dependency)) as client:
        response = client.post(
            "/v1/orders",
            json={"sku": "SKU-001", "quantity": 2, "amount_krw": 2500},
            headers={"X-Request-ID": "req_demo_0001", "X-Cloud-Trace-Context": trace_context},
        )

    assert response.status_code == 201
    assert response.headers["X-Request-ID"] == "req_demo_0001"
    assert response.json()["status"] == "FULFILLED"
    assert len(dependency.calls) == 2
    assert {call["request_id"] for call in dependency.calls} == {"req_demo_0001"}
    assert {call["trace_context"] for call in dependency.calls} == {trace_context}
    assert {call["timeout_seconds"] for call in dependency.calls} == {3.0}


def test_M2_order_returns_partial_safe_failure() -> None:
    dependency = FakeDependencyClient(fail_payment=True)
    with TestClient(create_app(_settings(DemoService.ORDER), dependency)) as client:
        response = client.post(
            "/v1/orders",
            json={"sku": "SKU-001", "quantity": 1, "amount_krw": 1000},
            headers={"X-Request-ID": "req_demo_0002"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "order_id": response.json()["order_id"],
        "request_id": "req_demo_0002",
        "status": "FAILED",
        "payment_status": "FAILED",
        "inventory_status": "RESERVED",
        "authorization_id": None,
        "reservation_id": "res_0123456789abcdef",
        "error_code": "DOWNSTREAM_FAILURE",
    }


def test_M2_order_rejects_a_mismatched_downstream_request_id() -> None:
    dependency = FakeDependencyClient(mismatch_inventory_id=True)
    with TestClient(create_app(_settings(DemoService.ORDER), dependency)) as client:
        response = client.post(
            "/v1/orders",
            json={"sku": "SKU-001", "quantity": 1, "amount_krw": 1000},
            headers={"X-Request-ID": "req_demo_0005"},
        )

    assert response.status_code == 502
    assert response.json()["payment_status"] == "APPROVED"
    assert response.json()["inventory_status"] == "FAILED"


@pytest.mark.parametrize(
    ("service", "path", "payload", "result_status"),
    [
        (
            DemoService.PAYMENT,
            "/v1/payments/authorizations",
            {"order_id": "ord_0123456789abcdef", "amount_krw": 1000},
            "APPROVED",
        ),
        (
            DemoService.INVENTORY,
            "/v1/inventory/reservations",
            {"order_id": "ord_0123456789abcdef", "sku": "SKU-001", "quantity": 1},
            "RESERVED",
        ),
    ],
)
def test_M2_leaf_services_expose_only_their_contract(
    service: DemoService,
    path: str,
    payload: dict[str, object],
    result_status: str,
) -> None:
    with TestClient(create_app(_settings(service))) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"status": "ready"}
        response = client.post(path, json=payload, headers={"X-Request-ID": "req_demo_0003"})
        assert client.post("/v1/orders", json={}).status_code == 404

    assert response.status_code == 201
    assert response.json()["status"] == result_status


def test_M2_rejects_bad_inputs_request_ids_and_service_roles() -> None:
    with TestClient(create_app(_settings(DemoService.PAYMENT))) as client:
        bad_payload = client.post(
            "/v1/payments/authorizations",
            json={"order_id": "not-an-order", "amount_krw": 1},
        )
        bad_request_id = client.get("/healthz", headers={"X-Request-ID": "short"})

    assert bad_payload.status_code == 422
    assert bad_request_id.status_code == 400
    with pytest.raises(ValidationError):
        DemoSettings(service="unknown")


def test_M2_structured_log_is_fixed_shape_and_contains_no_payload_or_credentials(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(DemoService.PAYMENT).model_copy(
        update={"project_id": "example-project", "revision": "payment-00001"}
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/payments/authorizations",
            json={"order_id": "ord_0123456789abcdef", "amount_krw": 987654},
            headers={
                "X-Request-ID": "req_demo_0004",
                "X-Cloud-Trace-Context": "4bf92f3577b34da6a3ce929d0e0e4736/123;o=1",
                "Authorization": "Bearer secret-token-value",
            },
        )
    assert response.status_code == 201

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    record = next(item for item in records if item["path"].endswith("authorizations"))
    assert set(record) == {
        "severity",
        "message",
        "service",
        "environment",
        "revision",
        "request_id",
        "trace_id",
        "event_type",
        "method",
        "path",
        "status_code",
        "latency_ms",
        "logging.googleapis.com/trace",
    }
    rendered = json.dumps(records)
    assert "987654" not in rendered
    assert "secret-token-value" not in rendered
