"""Bounded HTTP and identity-token adapters for demo service calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from opspilot.demo.models import DownstreamAuthMode


class DependencyCallError(RuntimeError):
    """Safe downstream failure that never includes response bodies or credentials."""


class DependencyClient(Protocol):
    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        request_id: str,
        trace_context: str | None,
        scenario_headers: Mapping[str, str] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]: ...


class IdentityTokenProvider(Protocol):
    async def get_token(self, audience: str) -> str | None: ...


class LocalIdentityTokenProvider:
    async def get_token(self, audience: str) -> str | None:
        del audience
        return None


class MetadataIdentityTokenProvider:
    _BASE_URL = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/identity"
    )

    async def get_token(self, audience: str) -> str:
        return await asyncio.to_thread(self._fetch_token, audience)

    def _fetch_token(self, audience: str) -> str:
        url = f"{self._BASE_URL}?audience={quote(audience, safe='')}&format=full"
        request = UrlRequest(url, headers={"Metadata-Flavor": "Google"})
        try:
            with urlopen(request, timeout=2) as response:
                token = cast(bytes, response.read()).decode("utf-8").strip()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise DependencyCallError("identity token unavailable") from exc
        if not token:
            raise DependencyCallError("identity token unavailable")
        return token


class UrlLibDependencyClient:
    def __init__(self, auth_mode: DownstreamAuthMode) -> None:
        self._token_provider: IdentityTokenProvider = (
            MetadataIdentityTokenProvider()
            if auth_mode is DownstreamAuthMode.METADATA
            else LocalIdentityTokenProvider()
        )

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        request_id: str,
        trace_context: str | None,
        scenario_headers: Mapping[str, str] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        audience = url.split("/v1/", maxsplit=1)[0]
        token = await self._token_provider.get_token(audience)
        return await asyncio.to_thread(
            self._post_json,
            url,
            payload,
            request_id,
            trace_context,
            scenario_headers,
            token,
            timeout_seconds,
        )

    @staticmethod
    def _post_json(
        url: str,
        payload: Mapping[str, object],
        request_id: str,
        trace_context: str | None,
        scenario_headers: Mapping[str, str] | None,
        token: str | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "X-Request-ID": request_id}
        if trace_context:
            headers["X-Cloud-Trace-Context"] = trace_context
        if scenario_headers:
            headers.update(scenario_headers)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = UrlRequest(
            url,
            data=json.dumps(dict(payload)).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                parsed = json.load(response)
        except HTTPError as exc:
            raise DependencyCallError("downstream returned an error") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DependencyCallError("downstream is unavailable") from exc
        if not isinstance(parsed, dict):
            raise DependencyCallError("downstream returned an invalid response")
        return cast(dict[str, Any], parsed)
