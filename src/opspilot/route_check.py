"""Identifier-free diagnostics for the private Cloud Run demo route."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel, Field

DEMO_REGION = "asia-northeast3"
DEMO_SERVICES: tuple[str, ...] = (
    "opspilot-dev-order",
    "opspilot-dev-payment",
    "opspilot-dev-inventory",
)
BlockerCode = Literal[
    "none",
    "service_unready",
    "endpoint_not_found",
    "iam_denied",
    "transport_error",
    "application_error",
    "unknown",
]


class CloudRunRouteCheckResult(BaseModel):
    """Redacted route state suitable for local MVP endpoint diagnostics."""

    account_alias_match: bool = False
    user_credentials: bool = False
    default_project_configured: bool = False
    services_found: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    services_ready: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    services_with_full_traffic: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    canonical_urls_consistent: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    default_urls_enabled: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    ingress_all_services: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    iam_enforced_services: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    private_iam_services: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    operator_invoke_permission: bool = False
    unauthenticated_status_codes: list[int] = Field(default_factory=list)
    authenticated_status_codes: list[int] = Field(default_factory=list)
    pre_container_404_services: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    container_application_logs: int = Field(default=0, ge=0, le=len(DEMO_SERVICES))
    route_ready: bool = False
    blocker_code: BlockerCode = "unknown"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str


CommandRunner = Callable[[Sequence[str]], CommandResult]
ApiRequester = Callable[[str, str, dict[str, Any] | None, str], dict[str, Any]]
HttpStatusRequester = Callable[[str, str | None, str], int]


def _default_runner(arguments: Sequence[str]) -> CommandResult:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    try:
        completed = subprocess.run(
            [executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CommandResult(1, "")
    return CommandResult(completed.returncode, completed.stdout.strip())


def _request_json(
    token: str,
    url: str,
    body: dict[str, Any] | None,
    quota_project: str,
) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": quota_project,
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Google API read failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Google API returned an unexpected response")
    return payload


def _request_status(url: str, token: str | None, request_id: str) -> int:
    headers = {"X-Request-ID": request_id}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            return int(response.status)
    except HTTPError as exc:
        return int(exc.code)
    except (URLError, TimeoutError):
        return 0


def _json_dict(result: CommandResult) -> dict[str, Any]:
    if result.returncode != 0 or not result.stdout:
        return {}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _json_list(result: CommandResult) -> list[dict[str, Any]] | None:
    if result.returncode != 0:
        return None
    if not result.stdout:
        return []
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return None
    return value


def _is_ready(service: dict[str, Any]) -> bool:
    conditions = service.get("status", {}).get("conditions", [])
    return any(
        condition.get("type") == "Ready" and condition.get("status") == "True"
        for condition in conditions
        if isinstance(condition, dict)
    )


def _has_full_traffic(service: dict[str, Any]) -> bool:
    traffic = service.get("status", {}).get("traffic", [])
    return (
        bool(traffic)
        and sum(int(item.get("percent", 0)) for item in traffic if isinstance(item, dict)) == 100
    )


def _is_private_policy(policy: dict[str, Any]) -> bool:
    public_members = {"allUsers", "allAuthenticatedUsers"}
    bindings = policy.get("bindings", [])
    members = {
        member
        for binding in bindings
        if isinstance(binding, dict)
        for member in binding.get("members", [])
        if isinstance(member, str)
    }
    return not members.intersection(public_members)


def classify_route(result: CloudRunRouteCheckResult) -> CloudRunRouteCheckResult:
    """Set the stable readiness and blocker classification from redacted observations."""

    expected = len(DEMO_SERVICES)
    service_ready = all(
        value == expected
        for value in (
            result.services_found,
            result.services_ready,
            result.services_with_full_traffic,
        )
    )
    endpoint_configured = all(
        value == expected
        for value in (
            result.canonical_urls_consistent,
            result.default_urls_enabled,
            result.ingress_all_services,
            result.iam_enforced_services,
            result.private_iam_services,
        )
    )
    route_ready = all(
        (
            result.account_alias_match,
            result.user_credentials,
            result.default_project_configured,
            service_ready,
            endpoint_configured,
            result.operator_invoke_permission,
            result.unauthenticated_status_codes == [403] * expected,
            result.authenticated_status_codes == [200] * expected,
            result.pre_container_404_services == 0,
            result.container_application_logs == expected,
        )
    )
    if route_ready:
        blocker: BlockerCode = "none"
    elif not service_ready:
        blocker = "service_unready"
    elif 0 in result.unauthenticated_status_codes or 0 in result.authenticated_status_codes:
        blocker = "transport_error"
    elif 404 in result.authenticated_status_codes and result.container_application_logs == 0:
        blocker = "endpoint_not_found"
    elif 401 in result.authenticated_status_codes or 403 in result.authenticated_status_codes:
        blocker = "iam_denied"
    elif any(code >= 400 for code in result.authenticated_status_codes):
        blocker = "application_error"
    else:
        blocker = "unknown"
    return result.model_copy(update={"route_ready": route_ready, "blocker_code": blocker})


def run_route_check(
    *,
    account_alias: str = "Edu_687",
    runner: CommandRunner = _default_runner,
    requester: ApiRequester = _request_json,
    status_requester: HttpStatusRequester = _request_status,
    sleeper: Callable[[float], None] = time.sleep,
) -> CloudRunRouteCheckResult:
    """Inspect the fixed M2 route without returning identifiers or credential material."""

    active_account = runner(("auth", "list", "--filter=status:ACTIVE", "--format=value(account)"))
    access_token = runner(("auth", "print-access-token"))
    identity_token = runner(("auth", "print-identity-token"))
    project_result = runner(("config", "get-value", "project"))
    result = CloudRunRouteCheckResult(
        account_alias_match=(
            active_account.returncode == 0
            and account_alias.casefold() in active_account.stdout.casefold()
        ),
        user_credentials=(
            access_token.returncode == 0
            and bool(access_token.stdout)
            and identity_token.returncode == 0
            and bool(identity_token.stdout)
        ),
        default_project_configured=project_result.returncode == 0 and bool(project_result.stdout),
    )
    if not (result.user_credentials and result.default_project_configured):
        return classify_route(result)

    project_id = project_result.stdout
    try:
        permission_payload = requester(
            access_token.stdout,
            "https://cloudresourcemanager.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}:testIamPermissions",
            {"permissions": ["run.routes.invoke"]},
            project_id,
        )
        result.operator_invoke_permission = "run.routes.invoke" in permission_payload.get(
            "permissions", []
        )
    except RuntimeError:
        pass

    service_urls: list[str] = []
    for service_name in DEMO_SERVICES:
        service = _json_dict(
            runner(
                (
                    "run",
                    "services",
                    "describe",
                    service_name,
                    f"--region={DEMO_REGION}",
                    "--format=json",
                )
            )
        )
        if not service:
            continue
        result.services_found += 1
        result.services_ready += int(_is_ready(service))
        result.services_with_full_traffic += int(_has_full_traffic(service))
        policy = _json_dict(
            runner(
                (
                    "run",
                    "services",
                    "get-iam-policy",
                    service_name,
                    f"--region={DEMO_REGION}",
                    "--format=json",
                )
            )
        )
        result.private_iam_services += int(bool(policy) and _is_private_policy(policy))
        try:
            v2_service = requester(
                access_token.stdout,
                "https://run.googleapis.com/v2/projects/"
                f"{quote(project_id, safe='')}/locations/{DEMO_REGION}/services/"
                f"{quote(service_name, safe='')}",
                None,
                project_id,
            )
        except RuntimeError:
            continue
        result.default_urls_enabled += int(not bool(v2_service.get("defaultUriDisabled")))
        result.ingress_all_services += int(v2_service.get("ingress") == "INGRESS_TRAFFIC_ALL")
        result.iam_enforced_services += int(not bool(v2_service.get("invokerIamDisabled")))
        service_uri = v2_service.get("uri")
        status_uri = service.get("status", {}).get("url")
        if isinstance(service_uri, str) and service_uri.startswith("https://"):
            result.canonical_urls_consistent += int(status_uri == service_uri)
            service_urls.append(service_uri.rstrip("/"))

    for service_uri in service_urls:
        health_url = f"{service_uri}/healthz"
        request_id = f"req_route_{uuid4().hex[:20]}"
        result.unauthenticated_status_codes.append(status_requester(health_url, None, request_id))
        authenticated_status = status_requester(health_url, identity_token.stdout, request_id)
        result.authenticated_status_codes.append(authenticated_status)
        result.pre_container_404_services += int(authenticated_status == 404)
        log_filter = f'resource.type="cloud_run_revision" AND jsonPayload.request_id="{request_id}"'
        logs: list[dict[str, Any]] | None = []
        attempts = 3 if authenticated_status == 200 else 1
        for attempt in range(attempts):
            logs = _json_list(
                runner(
                    (
                        "logging",
                        "read",
                        log_filter,
                        "--freshness=5m",
                        "--limit=1",
                        "--format=json",
                    )
                )
            )
            if logs or logs is None:
                break
            if attempt < attempts - 1:
                sleeper(float(attempt + 1))
        result.container_application_logs += int(bool(logs))

    result.unauthenticated_status_codes.sort()
    result.authenticated_status_codes.sort()
    return classify_route(result)


def render_route_summary(result: CloudRunRouteCheckResult) -> str:
    """Render the stable route contract without identifiers."""

    return "\n".join(
        (
            f"account_alias_match={'pass' if result.account_alias_match else 'fail'}",
            f"user_credentials={'pass' if result.user_credentials else 'fail'}",
            f"default_project_configured={'pass' if result.default_project_configured else 'fail'}",
            f"services_found={result.services_found}",
            f"services_ready={result.services_ready}",
            f"services_with_full_traffic={result.services_with_full_traffic}",
            f"canonical_urls_consistent={result.canonical_urls_consistent}",
            f"default_urls_enabled={result.default_urls_enabled}",
            f"ingress_all_services={result.ingress_all_services}",
            f"iam_enforced_services={result.iam_enforced_services}",
            f"private_iam_services={result.private_iam_services}",
            f"operator_invoke_permission={'pass' if result.operator_invoke_permission else 'fail'}",
            "unauthenticated_status_codes="
            + ",".join(str(code) for code in result.unauthenticated_status_codes),
            "authenticated_status_codes="
            + ",".join(str(code) for code in result.authenticated_status_codes),
            f"pre_container_404_services={result.pre_container_404_services}",
            f"container_application_logs={result.container_application_logs}",
            f"route_ready={'pass' if result.route_ready else 'fail'}",
            f"blocker_code={result.blocker_code}",
            "",
        )
    )
