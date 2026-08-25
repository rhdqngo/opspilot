"""FastAPI factories for the three synthetic ecommerce services."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from opspilot.demo.client import DependencyCallError, DependencyClient, UrlLibDependencyClient
from opspilot.demo.config import DemoSettings
from opspilot.demo.models import (
    DemoService,
    InventoryReservationRequest,
    InventoryReservationResponse,
    OrderCreateRequest,
    OrderResponse,
    PaymentAuthorizationRequest,
    PaymentAuthorizationResponse,
)
from opspilot.demo.scenario_context import (
    ScenarioContext,
    ScenarioContextError,
    parse_scenario_context,
)
from opspilot.demo.structured_logging import (
    emit_scenario_log,
    extract_trace_id,
    install_request_logging,
)

DOWNSTREAM_TIMEOUT_SECONDS = 3.0
ORDER_TIMEOUT_SECONDS = 5.0


def _request_id(request: Request) -> str:
    return cast(str, request.state.request_id)


def _trace_context(request: Request) -> str | None:
    return cast(str | None, request.state.trace_context)


async def _safe_call(
    client: DependencyClient,
    url: str,
    payload: dict[str, object],
    request: Request,
    scenario: ScenarioContext | None,
) -> dict[str, Any] | DependencyCallError:
    try:
        return await client.post_json(
            url,
            payload,
            request_id=_request_id(request),
            trace_context=_trace_context(request),
            scenario_headers=scenario.headers() if scenario else None,
            timeout_seconds=DOWNSTREAM_TIMEOUT_SECONDS,
        )
    except DependencyCallError as exc:
        return exc


def create_app(
    settings: DemoSettings | None = None,
    dependency_client: DependencyClient | None = None,
) -> FastAPI:
    runtime = settings or DemoSettings.from_environment()
    client = dependency_client or UrlLibDependencyClient(runtime.downstream_auth)
    app = FastAPI(title="OpsPilot synthetic ecommerce service", version="1.0")
    install_request_logging(app, runtime)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ready"}

    if runtime.service is DemoService.PAYMENT:

        @app.post(
            "/v1/payments/authorizations",
            status_code=status.HTTP_201_CREATED,
            response_model=PaymentAuthorizationResponse,
        )
        async def authorize(
            payload: PaymentAuthorizationRequest, request: Request
        ) -> PaymentAuthorizationResponse | JSONResponse:
            try:
                scenario = parse_scenario_context(
                    request.headers, scenarios_enabled=runtime.scenarios_enabled
                )
            except ScenarioContextError:
                return JSONResponse(
                    status_code=400,
                    content={"error_code": "INVALID_SCENARIO_CONTEXT"},
                )
            fixed_failure = runtime.payment_failure_profile == "payment-failure"
            if fixed_failure or (scenario is not None and scenario.inject_payment_failure):
                await asyncio.sleep(0.25)
                emit_scenario_log(
                    runtime,
                    request_id=_request_id(request),
                    trace_id=extract_trace_id(_trace_context(request)),
                    scenario_id=scenario.scenario_id if scenario else "SCN-008",
                    scenario_run_id=scenario.run_id if scenario else "RUN-SCN-008-FIXEDPROFILE",
                    scenario_step=scenario.step if scenario else 1,
                )
                return JSONResponse(status_code=503, content={"error_code": "DB_POOL_TIMEOUT"})
            return PaymentAuthorizationResponse(
                authorization_id=f"pay_{uuid4().hex[:16]}",
                request_id=_request_id(request),
            )

    if runtime.service is DemoService.INVENTORY:

        @app.post(
            "/v1/inventory/reservations",
            status_code=status.HTTP_201_CREATED,
            response_model=InventoryReservationResponse,
        )
        async def reserve(
            payload: InventoryReservationRequest, request: Request
        ) -> InventoryReservationResponse | JSONResponse:
            try:
                parse_scenario_context(request.headers, scenarios_enabled=runtime.scenarios_enabled)
            except ScenarioContextError:
                return JSONResponse(
                    status_code=400,
                    content={"error_code": "INVALID_SCENARIO_CONTEXT"},
                )
            return InventoryReservationResponse(
                reservation_id=f"res_{uuid4().hex[:16]}",
                request_id=_request_id(request),
            )

    if runtime.service is DemoService.ORDER:
        payment_url = f"{runtime.payment_service_url!s}".rstrip("/")
        inventory_url = f"{runtime.inventory_service_url!s}".rstrip("/")

        @app.post(
            "/v1/orders",
            status_code=status.HTTP_201_CREATED,
            response_model=OrderResponse,
            responses={502: {"model": OrderResponse}},
        )
        async def create_order(
            payload: OrderCreateRequest, request: Request
        ) -> OrderResponse | JSONResponse:
            try:
                scenario = parse_scenario_context(
                    request.headers, scenarios_enabled=runtime.scenarios_enabled
                )
            except ScenarioContextError:
                return JSONResponse(
                    status_code=400,
                    content={"error_code": "INVALID_SCENARIO_CONTEXT"},
                )
            order_id = f"ord_{uuid4().hex[:16]}"
            try:
                async with asyncio.timeout(ORDER_TIMEOUT_SECONDS):
                    payment_result, inventory_result = await asyncio.gather(
                        _safe_call(
                            client,
                            f"{payment_url}/v1/payments/authorizations",
                            {"order_id": order_id, "amount_krw": payload.amount_krw},
                            request,
                            scenario,
                        ),
                        _safe_call(
                            client,
                            f"{inventory_url}/v1/inventory/reservations",
                            {
                                "order_id": order_id,
                                "sku": payload.sku,
                                "quantity": payload.quantity,
                            },
                            request,
                            scenario,
                        ),
                    )
            except TimeoutError:
                payment_result = DependencyCallError("order dependency timeout")
                inventory_result = DependencyCallError("order dependency timeout")

            payment: PaymentAuthorizationResponse | None = None
            inventory: InventoryReservationResponse | None = None
            if isinstance(payment_result, dict):
                try:
                    payment = PaymentAuthorizationResponse.model_validate(payment_result)
                except ValueError:
                    pass
            if isinstance(inventory_result, dict):
                try:
                    inventory = InventoryReservationResponse.model_validate(inventory_result)
                except ValueError:
                    pass

            if payment is not None and payment.request_id != _request_id(request):
                payment = None
            if inventory is not None and inventory.request_id != _request_id(request):
                inventory = None

            if payment is not None and inventory is not None:
                return OrderResponse(
                    order_id=order_id,
                    request_id=_request_id(request),
                    status="FULFILLED",
                    payment_status="APPROVED",
                    inventory_status="RESERVED",
                    authorization_id=payment.authorization_id,
                    reservation_id=inventory.reservation_id,
                )

            failed = OrderResponse(
                order_id=order_id,
                request_id=_request_id(request),
                status="FAILED",
                payment_status="APPROVED" if payment else "FAILED",
                inventory_status="RESERVED" if inventory else "FAILED",
                authorization_id=payment.authorization_id if payment else None,
                reservation_id=inventory.reservation_id if inventory else None,
                error_code="DOWNSTREAM_FAILURE",
            )
            return JSONResponse(status_code=502, content=failed.model_dump(mode="json"))

    return app
