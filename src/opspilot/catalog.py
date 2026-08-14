"""Service allowlist loading and request validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from opspilot.domain import Environment, InvestigationRequest


class ServiceDefinition(BaseModel):
    environments: list[str]
    metrics: list[str]
    aliases: list[str] = Field(default_factory=list)
    cloud_run_services: dict[str, str] = Field(default_factory=dict)

    def target_for(self, service: str, environment: Environment) -> str:
        target = self.cloud_run_services.get(environment.value)
        if target:
            return target
        return f"opspilot-{environment.value}-{service.removesuffix('-service')}"


class ServiceCatalog(BaseModel):
    version: str
    max_query_window_minutes: int = Field(ge=1, le=1_440)
    services: dict[str, ServiceDefinition]

    def resolve_services(self, query: str) -> list[str]:
        lowered = query.casefold()
        resolved: set[str] = set()
        for service, definition in self.services.items():
            candidates = [service, *definition.aliases]
            for candidate in candidates:
                token = candidate.casefold().strip()
                if not token:
                    continue
                if re.search(r"[a-z0-9]", token):
                    matched = re.search(rf"(?<![a-z0-9-]){re.escape(token)}(?![a-z0-9-])", lowered)
                else:
                    matched = re.search(re.escape(token), lowered)
                if matched:
                    resolved.add(service)
                    break
        return sorted(resolved)

    def cloud_run_service(self, service: str, environment: Environment) -> str:
        definition = self.services.get(service)
        if definition is None:
            raise ValueError("service is not allowlisted")
        if environment.value not in definition.environments:
            raise ValueError(f"environment {environment.value!r} is not allowed for {service!r}")
        return definition.target_for(service, environment)


def default_catalog_path() -> Path:
    workspace_catalog = Path.cwd() / "config" / "services.yaml"
    if workspace_catalog.is_file():
        return workspace_catalog
    return Path(__file__).parent / "resources" / "services.yaml"


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
