"""Service allowlist loading and request validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from opspilot.domain import InvestigationRequest


class ServiceDefinition(BaseModel):
    environments: list[str]
    metrics: list[str]


class ServiceCatalog(BaseModel):
    version: str
    max_query_window_minutes: int = Field(ge=1, le=1_440)
    services: dict[str, ServiceDefinition]


def default_catalog_path() -> Path:
    return Path.cwd() / "config" / "services.yaml"


def load_service_catalog(path: Path | None = None) -> ServiceCatalog:
    selected = path or default_catalog_path()
    with selected.open(encoding="utf-8") as stream:
        payload: Any = yaml.safe_load(stream)
    return ServiceCatalog.model_validate(payload)


def validate_request_scope(
    request: InvestigationRequest, catalog: ServiceCatalog
) -> InvestigationRequest:
    unknown = sorted(set(request.services) - set(catalog.services))
    if unknown:
        raise ValueError(f"services are not allowlisted: {unknown}")
    for service in request.services:
        if request.environment.value not in catalog.services[service].environments:
            raise ValueError(
                f"environment {request.environment.value!r} is not allowed for {service!r}"
            )
    return request
