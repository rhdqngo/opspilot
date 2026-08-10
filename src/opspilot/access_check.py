"""Redacted, read-only Google Cloud access checks for the M0 gate."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

PROJECT_PERMISSIONS: tuple[str, ...] = (
    "serviceusage.services.enable",
    "resourcemanager.projects.get",
    "resourcemanager.projects.getIamPolicy",
    "resourcemanager.projects.setIamPolicy",
    "iam.serviceAccounts.create",
    "iam.serviceAccounts.setIamPolicy",
    "iam.googleapis.com/workloadIdentityPools.create",
    "iam.googleapis.com/workloadIdentityPoolProviders.create",
    "iam.roles.create",
    "iam.roles.update",
    "storage.buckets.create",
    "artifactregistry.repositories.create",
    "billing.resourcebudgets.read",
    "billing.resourcebudgets.write",
    "discoveryengine.engines.list",
)


class AccessCheckResult(BaseModel):
    """Identifier-free result suitable for console output and documentation."""

    account_alias_match: bool = False
    user_credentials: bool = False
    application_default_credentials: bool = False
    default_project_configured: bool = False
    project_active: bool = False
    project_confirmed: bool = False
    billing_enabled: bool = False
    billing_currency_krw_confirmed: bool = False
    api_activation_permission: bool = False
    m1_permissions_ready: bool = False
    missing_project_permissions: list[str] = Field(default_factory=list)
    gemini_enterprise_access: bool = False
    gemini_enterprise_app_exists: bool = False
    m0_ready: bool = False


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str


CommandRunner = Callable[[Sequence[str]], CommandResult]
JsonRequester = Callable[[str, str, dict[str, Any] | None, str], dict[str, Any]]


def _default_runner(arguments: Sequence[str]) -> CommandResult:
    executable = shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"
    completed = subprocess.run(
        [executable, *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return CommandResult(returncode=completed.returncode, stdout=completed.stdout.strip())


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


def _load_json(result: CommandResult) -> dict[str, Any]:
    if result.returncode != 0 or not result.stdout:
        return {}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def run_access_check(
    *,
    account_alias: str = "Edu_687",
    project_confirmed: bool = False,
    billing_currency_krw_confirmed: bool = False,
    runner: CommandRunner = _default_runner,
    requester: JsonRequester = _request_json,
) -> AccessCheckResult:
    """Run non-mutating checks and return only redacted status fields."""

    active_account = runner(("auth", "list", "--filter=status:ACTIVE", "--format=value(account)"))
    user_token = runner(("auth", "print-access-token"))
    adc_token = runner(("auth", "application-default", "print-access-token"))
    project_result = runner(("config", "get-value", "project"))

    result = AccessCheckResult(
        account_alias_match=(
            active_account.returncode == 0
            and account_alias.casefold() in active_account.stdout.casefold()
        ),
        user_credentials=user_token.returncode == 0 and bool(user_token.stdout),
        application_default_credentials=adc_token.returncode == 0 and bool(adc_token.stdout),
        default_project_configured=project_result.returncode == 0 and bool(project_result.stdout),
        project_confirmed=project_confirmed,
        billing_currency_krw_confirmed=billing_currency_krw_confirmed,
    )
    if not (result.user_credentials and result.default_project_configured):
        return result

    project_id = project_result.stdout
    project_metadata = _load_json(runner(("projects", "describe", project_id, "--format=json")))
    billing_metadata = _load_json(
        runner(("billing", "projects", "describe", project_id, "--format=json"))
    )
    result.project_active = project_metadata.get("lifecycleState") == "ACTIVE"
    result.billing_enabled = bool(
        billing_metadata.get("billingEnabled") and billing_metadata.get("billingAccountName")
    )

    try:
        permission_payload = requester(
            user_token.stdout,
            "https://cloudresourcemanager.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}:testIamPermissions",
            {"permissions": list(PROJECT_PERMISSIONS)},
            project_id,
        )
        granted = set(permission_payload.get("permissions", []))
        result.missing_project_permissions = [
            permission for permission in PROJECT_PERMISSIONS if permission not in granted
        ]
        result.api_activation_permission = "serviceusage.services.enable" in granted
        result.m1_permissions_ready = not result.missing_project_permissions
    except RuntimeError:
        result.missing_project_permissions = list(PROJECT_PERMISSIONS)

    try:
        engines = requester(
            user_token.stdout,
            "https://discoveryengine.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}/locations/global/collections/"
            "default_collection/engines?pageSize=1",
            None,
            project_id,
        )
        result.gemini_enterprise_access = True
        result.gemini_enterprise_app_exists = bool(engines.get("engines"))
    except RuntimeError:
        pass

    result.m0_ready = all(
        (
            result.account_alias_match,
            result.user_credentials,
            result.application_default_credentials,
            result.default_project_configured,
            result.project_active,
            result.project_confirmed,
            result.billing_enabled,
            result.billing_currency_krw_confirmed,
            result.api_activation_permission,
            result.m1_permissions_ready,
            result.gemini_enterprise_access,
            result.gemini_enterprise_app_exists,
        )
    )
    return result


def render_access_summary(result: AccessCheckResult) -> str:
    """Render a stable summary without identifiers or credential material."""

    values = result.model_dump()
    lines = [
        f"{name}={'pass' if value else 'fail'}"
        for name, value in values.items()
        if isinstance(value, bool)
    ]
    if result.missing_project_permissions:
        lines.append("missing_project_permissions=" + ",".join(result.missing_project_permissions))
    return "\n".join(lines) + "\n"
