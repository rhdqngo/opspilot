"""Environment-only configuration for the demo services."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field, HttpUrl, model_validator

from opspilot.demo.models import DemoService, DownstreamAuthMode


class DemoSettings(BaseModel):
    service: DemoService
    environment: str = Field(default="dev", pattern=r"^[a-z][a-z0-9-]{1,15}$")
    revision: str = Field(default="local", min_length=1, max_length=128)
    project_id: str = ""
    downstream_auth: DownstreamAuthMode = DownstreamAuthMode.LOCAL
    payment_service_url: HttpUrl | None = None
    inventory_service_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_order_dependencies(self) -> DemoSettings:
        if self.service is DemoService.ORDER and (
            self.payment_service_url is None or self.inventory_service_url is None
        ):
            raise ValueError("order service requires payment and inventory service URLs")
        return self

    @classmethod
    def from_environment(cls) -> DemoSettings:
        return cls(
            service=os.environ.get("OPSPILOT_DEMO_SERVICE", ""),
            environment=os.environ.get("OPSPILOT_ENVIRONMENT", "dev"),
            revision=os.environ.get("K_REVISION", "local"),
            project_id=os.environ.get("OPSPILOT_PROJECT_ID", ""),
            downstream_auth=os.environ.get("OPSPILOT_DOWNSTREAM_AUTH", "local"),
            payment_service_url=os.environ.get("OPSPILOT_PAYMENT_SERVICE_URL") or None,
            inventory_service_url=os.environ.get("OPSPILOT_INVENTORY_SERVICE_URL") or None,
        )
