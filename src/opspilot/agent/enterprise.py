"""Guarded Gemini Enterprise registration planning for the fixed M7 runtime."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from opspilot.agent.runtime import RUNTIME_DISPLAY_NAME, RUNTIME_REGION
from opspilot.evidence import WorkloadAdcTokenProvider

REGISTER_GATE = "OPSPILOT_ENTERPRISE_REGISTER_ENABLED"
SAFE_FAILURE_CODES = frozenset(
    {
        "configuration_unavailable",
        "unauthorized",
        "forbidden",
        "not_found",
        "upstream_error",
        "invalid_response",
    }
)
EnterpriseBlocker = Literal[
    "none",
    "gate_disabled",
    "configuration_unavailable",
    "app_not_unique",
    "runtime_not_unique",
    "display_name_conflict",
    "unauthorized",
    "forbidden",
    "not_found",
    "upstream_error",
    "invalid_response",
]


class EnterpriseRegistrationResult(BaseModel):
    mode: Literal["plan", "apply"]
    succeeded: bool
    mutation_count: int = Field(default=0, ge=0, le=1)
    app_count: int = Field(default=0, ge=0)
    runtime_match_count: int = Field(default=0, ge=0)
    registration_match_count: int = Field(default=0, ge=0)
    display_name_conflict_count: int = Field(default=0, ge=0)
    no_op: bool = False
    blocker_code: EnterpriseBlocker = "none"


class EnterpriseInventory(Protocol):
    def list_apps(self) -> list[Mapping[str, Any]]: ...

    def list_runtimes(self) -> list[Mapping[str, Any]]: ...

    def list_registrations(self, app_name: str) -> list[Mapping[str, Any]]: ...

    def register(self, app_name: str, runtime_name: str) -> None: ...


class EnterpriseApiFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RestEnterpriseInventory:
    """ADC-backed API adapter; resource names never leave this private boundary."""

    def __init__(self) -> None:
        self._project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not self._project:
            raise EnterpriseApiFailure("configuration_unavailable")
        self._token_provider = WorkloadAdcTokenProvider()

    def _request(
        self,
        url: str,
        *,
        method: Literal["GET", "POST"] = "GET",
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        import asyncio

        try:
            token = asyncio.run(self._token_provider.get_token())
            request = Request(
                url,
                data=json.dumps(body).encode() if body is not None else None,
                method=method,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Goog-User-Project": self._project,
                },
            )
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as error:
            error.read(16 * 1024 + 1)
            codes = {401: "unauthorized", 403: "forbidden", 404: "not_found"}
            raise EnterpriseApiFailure(codes.get(error.code, "upstream_error")) from None
        except (URLError, TimeoutError):
            raise EnterpriseApiFailure("upstream_error") from None
        except (ValueError, TypeError):
            raise EnterpriseApiFailure("invalid_response") from None
        if not isinstance(payload, dict):
            raise EnterpriseApiFailure("invalid_response")
        return payload

    def list_apps(self) -> list[Mapping[str, Any]]:
        payload = self._request(
            "https://discoveryengine.googleapis.com/v1/projects/"
            f"{quote(self._project, safe='')}/locations/global/collections/"
            "default_collection/engines?pageSize=100"
        )
        return [
            item
            for item in _items(payload, "engines")
            if item.get("appType") == "APP_TYPE_INTRANET"
        ]

    def list_runtimes(self) -> list[Mapping[str, Any]]:
        payload = self._request(
            f"https://{RUNTIME_REGION}-aiplatform.googleapis.com/v1/projects/"
            f"{quote(self._project, safe='')}/locations/{RUNTIME_REGION}/reasoningEngines"
        )
        return _items(payload, "reasoningEngines")

    def list_registrations(self, app_name: str) -> list[Mapping[str, Any]]:
        payload = self._request(
            "https://discoveryengine.googleapis.com/v1alpha/"
            f"{quote(app_name, safe='/')}/assistants/default_assistant/agents?pageSize=100"
        )
        return _items(payload, "agents")

    def register(self, app_name: str, runtime_name: str) -> None:
        self._request(
            "https://discoveryengine.googleapis.com/v1alpha/"
            f"{quote(app_name, safe='/')}/assistants/default_assistant/agents",
            method="POST",
            body={
                "displayName": RUNTIME_DISPLAY_NAME,
                "description": (
                    "Read-only payment-service incident investigation over the recent 30 minutes."
                ),
                "adkAgentDefinition": {
                    "provisionedReasoningEngine": {"reasoningEngine": runtime_name}
                },
            },
        )


def _items(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise EnterpriseApiFailure("invalid_response")
    return value


def run_enterprise_registration(
    mode: Literal["plan", "apply"],
    *,
    inventory: EnterpriseInventory | None = None,
) -> EnterpriseRegistrationResult:
    try:
        client = inventory or RestEnterpriseInventory()
        apps = client.list_apps()
        if len(apps) != 1:
            return EnterpriseRegistrationResult(
                mode=mode,
                succeeded=False,
                app_count=len(apps),
                blocker_code="app_not_unique",
            )
        app_name = str(apps[0].get("name", ""))
        runtimes = [
            item
            for item in client.list_runtimes()
            if item.get("displayName") == RUNTIME_DISPLAY_NAME
        ]
        registrations = client.list_registrations(app_name)
        matches = [
            item for item in registrations if item.get("displayName") == RUNTIME_DISPLAY_NAME
        ]
        if len(runtimes) != 1:
            return EnterpriseRegistrationResult(
                mode=mode,
                succeeded=False,
                app_count=1,
                runtime_match_count=len(runtimes),
                registration_match_count=len(matches),
                blocker_code="runtime_not_unique",
            )
        runtime_name = str(runtimes[0].get("name", ""))
        matching_runtime = [
            item
            for item in matches
            if item.get("adkAgentDefinition", {})
            .get("provisionedReasoningEngine", {})
            .get("reasoningEngine")
            == runtime_name
        ]
        conflicts = len(matches) - len(matching_runtime)
        if conflicts:
            return EnterpriseRegistrationResult(
                mode=mode,
                succeeded=False,
                app_count=1,
                runtime_match_count=1,
                registration_match_count=len(matching_runtime),
                display_name_conflict_count=conflicts,
                blocker_code="display_name_conflict",
            )
        if matching_runtime:
            return EnterpriseRegistrationResult(
                mode=mode,
                succeeded=True,
                app_count=1,
                runtime_match_count=1,
                registration_match_count=1,
                no_op=True,
            )
        if mode == "plan":
            return EnterpriseRegistrationResult(
                mode=mode,
                succeeded=True,
                app_count=1,
                runtime_match_count=1,
            )
        if os.environ.get(REGISTER_GATE) != "true":
            return EnterpriseRegistrationResult(
                mode=mode,
                succeeded=False,
                app_count=1,
                runtime_match_count=1,
                blocker_code="gate_disabled",
            )
        client.register(app_name, runtime_name)
        return EnterpriseRegistrationResult(
            mode=mode,
            succeeded=True,
            mutation_count=1,
            app_count=1,
            runtime_match_count=1,
            registration_match_count=1,
        )
    except EnterpriseApiFailure as error:
        code = cast(
            EnterpriseBlocker,
            error.code if error.code in SAFE_FAILURE_CODES else "upstream_error",
        )
        return EnterpriseRegistrationResult(mode=mode, succeeded=False, blocker_code=code)


def render_enterprise_summary(result: EnterpriseRegistrationResult) -> str:
    return "\n".join(f"{key}: {value}" for key, value in result.model_dump().items()) + "\n"
