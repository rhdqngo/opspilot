"""Environment-only M8 control-plane configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RemediationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSPILOT_REMEDIATION_", extra="ignore")

    project_id: str = Field(min_length=1)
    database_id: str = Field(default="opspilot-dev", pattern=r"^opspilot-dev$")
    control_audience: str = Field(min_length=1)
    executor_audience: str = Field(min_length=1)
    workflow_name: str = Field(pattern=r"^projects/[^/]+/locations/[^/]+/workflows/[^/]+$")
    workflow_service_account: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.iam\.gserviceaccount\.com$")
    investigation_service_account: str = ""
    order_url: str = Field(pattern=r"^https://")


class RemediationCliSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSPILOT_REMEDIATION_", extra="ignore")

    url: str = Field(pattern=r"^https://")
    control_audience: str = Field(min_length=1)
