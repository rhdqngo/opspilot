"""Typed contracts for the synthetic ecommerce demo services."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DemoService(StrEnum):
    ORDER = "order"
    PAYMENT = "payment"
    INVENTORY = "inventory"


class DownstreamAuthMode(StrEnum):
    LOCAL = "local"
    METADATA = "metadata"


class OrderCreateRequest(BaseModel):
    sku: str = Field(min_length=5, max_length=64, pattern=r"^SKU-[A-Z0-9][A-Z0-9_-]*$")
    quantity: int = Field(ge=1, le=10)
    amount_krw: int = Field(ge=100, le=1_000_000)


class PaymentAuthorizationRequest(BaseModel):
    order_id: str = Field(pattern=r"^ord_[0-9a-f]{16}$")
    amount_krw: int = Field(ge=100, le=1_000_000)


class PaymentAuthorizationResponse(BaseModel):
    authorization_id: str = Field(pattern=r"^pay_[0-9a-f]{16}$")
    status: Literal["APPROVED"] = "APPROVED"
    request_id: str


class InventoryReservationRequest(BaseModel):
    order_id: str = Field(pattern=r"^ord_[0-9a-f]{16}$")
    sku: str = Field(min_length=5, max_length=64, pattern=r"^SKU-[A-Z0-9][A-Z0-9_-]*$")
    quantity: int = Field(ge=1, le=10)


class InventoryReservationResponse(BaseModel):
    reservation_id: str = Field(pattern=r"^res_[0-9a-f]{16}$")
    status: Literal["RESERVED"] = "RESERVED"
    request_id: str


class OrderResponse(BaseModel):
    order_id: str = Field(pattern=r"^ord_[0-9a-f]{16}$")
    request_id: str
    status: Literal["FULFILLED", "FAILED"]
    payment_status: Literal["APPROVED", "FAILED"]
    inventory_status: Literal["RESERVED", "FAILED"]
    authorization_id: str | None = None
    reservation_id: str | None = None
    error_code: Literal["DOWNSTREAM_FAILURE"] | None = None


class LoadSummary(BaseModel):
    attempted: int = Field(ge=1)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    request_ids: int = Field(ge=0)
    latency_p50_ms: int = Field(ge=0)
    latency_p95_ms: int = Field(ge=0)
