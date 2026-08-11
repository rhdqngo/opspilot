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

M1_PROJECT_PERMISSIONS: tuple[str, ...] = (
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
    "monitoring.notificationChannels.create",
    "billing.resourcebudgets.read",
    "billing.resourcebudgets.write",
    "discoveryengine.engines.list",
)

M2_PROJECT_PERMISSIONS: tuple[str, ...] = (
    "serviceusage.services.enable",
    "run.services.create",
    "run.services.update",
    "run.services.get",
    "run.services.getIamPolicy",
    "run.services.list",
    "run.services.setIamPolicy",
    "run.routes.invoke",
    "iam.serviceAccounts.create",
    "iam.serviceAccounts.actAs",
    "artifactregistry.repositories.uploadArtifacts",
    "logging.logEntries.list",
    "monitoring.timeSeries.list",
)

M4_PROJECT_PERMISSIONS: tuple[str, ...] = (
    "serviceusage.services.use",
    "storage.buckets.create",
    "storage.objects.create",
    "storage.objects.delete",
    "storage.objects.get",
    "storage.objects.list",
    "discoveryengine.dataStores.create",
    "discoveryengine.dataStores.delete",
    "discoveryengine.dataStores.get",
    "discoveryengine.dataStores.list",
    "discoveryengine.dataStores.update",
    "discoveryengine.schemas.create",
    "discoveryengine.schemas.delete",
    "discoveryengine.schemas.get",
    "discoveryengine.schemas.list",
    "discoveryengine.schemas.update",
    "discoveryengine.engines.create",
    "discoveryengine.engines.delete",
    "discoveryengine.engines.get",
    "discoveryengine.engines.list",
    "discoveryengine.engines.update",
    "discoveryengine.documents.import",
    "discoveryengine.documents.get",
    "discoveryengine.documents.list",
    "discoveryengine.operations.get",
    "discoveryengine.servingConfigs.search",
)

M5_OPERATOR_PROJECT_PERMISSIONS: tuple[str, ...] = (
    "iam.roles.create",
    "iam.roles.update",
    "iam.serviceAccounts.setIamPolicy",
    "resourcemanager.projects.setIamPolicy",
)

M5_INVESTIGATOR_PERMISSIONS: tuple[str, ...] = (
    "discoveryengine.servingConfigs.search",
    "logging.logEntries.list",
    "monitoring.timeSeries.list",
    "resourcemanager.projects.get",
    "run.revisions.list",
    "run.services.get",
    "serviceusage.services.use",
)

M7_OPERATOR_PROJECT_PERMISSIONS: tuple[str, ...] = (
    "aiplatform.reasoningEngines.create",
    "aiplatform.reasoningEngines.get",
    "aiplatform.reasoningEngines.list",
    "aiplatform.reasoningEngines.update",
    "aiplatform.reasoningEngines.query",
    "iam.serviceAccounts.actAs",
    "iam.serviceAccounts.setIamPolicy",
    "discoveryengine.agents.create",
    "discoveryengine.agents.get",
    "discoveryengine.agents.list",
    "discoveryengine.agents.update",
    "discoveryengine.operations.get",
)

M7_INVESTIGATOR_PERMISSIONS: tuple[str, ...] = tuple(
    (*M5_INVESTIGATOR_PERMISSIONS, "aiplatform.endpoints.predict")
)

PROJECT_PERMISSIONS: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            *M1_PROJECT_PERMISSIONS,
            *M2_PROJECT_PERMISSIONS,
            *M4_PROJECT_PERMISSIONS,
            *M5_OPERATOR_PROJECT_PERMISSIONS,
        )
    )
)

M2_CANDIDATE_SERVICES: tuple[str, ...] = (
    "opspilot-dev-order",
    "opspilot-dev-payment",
    "opspilot-dev-inventory",
)

M4_CANDIDATE_ID = "opspilot-dev-knowledge"
M7_RUNTIME_DISPLAY_NAME = "OpsPilot Incident Commander"


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
    m2_permissions_ready: bool = False
    missing_m2_permissions: list[str] = Field(default_factory=list)
    m2_candidate_check_available: bool = False
    m2_candidate_names_available: bool = False
    m2_candidate_service_conflicts: int = Field(default=0, ge=0)
    m2_deploy_ready: bool = False
    m4_permissions_ready: bool = False
    missing_m4_permissions: list[str] = Field(default_factory=list)
    m4_candidate_check_available: bool = False
    m4_candidate_names_available: bool = False
    m4_candidate_bucket_conflicts: int = Field(default=0, ge=0)
    m4_candidate_data_store_conflicts: int = Field(default=0, ge=0)
    m4_candidate_engine_conflicts: int = Field(default=0, ge=0)
    m4_apply_ready: bool = False
    m5_operator_permissions_ready: bool = False
    missing_m5_operator_permissions: list[str] = Field(default_factory=list)
    investigator_impersonation_check_available: bool = False
    investigator_impersonation_ready: bool = False
    investigator_target_permission_count: int = Field(
        default=len(M5_INVESTIGATOR_PERMISSIONS), ge=0
    )
    m5_apply_ready: bool = False
    m7_operator_permissions_ready: bool = False
    missing_m7_operator_permissions: list[str] = Field(default_factory=list)
    m7_investigator_target_permission_count: int = Field(
        default=len(M7_INVESTIGATOR_PERMISSIONS), ge=0
    )
    m7_candidate_check_available: bool = False
    m7_existing_app_count: int = Field(default=0, ge=0)
    m7_runtime_name_conflicts: int = Field(default=0, ge=0)
    m7_registration_name_conflicts: int = Field(default=0, ge=0)
    m7_apply_ready: bool = False
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


def _load_json_list(result: CommandResult) -> list[dict[str, Any]] | None:
    if result.returncode != 0 or not result.stdout:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return None
    return value


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
            permission for permission in M1_PROJECT_PERMISSIONS if permission not in granted
        ]
        result.missing_m2_permissions = [
            permission for permission in M2_PROJECT_PERMISSIONS if permission not in granted
        ]
        result.missing_m4_permissions = [
            permission for permission in M4_PROJECT_PERMISSIONS if permission not in granted
        ]
        result.missing_m5_operator_permissions = [
            permission
            for permission in M5_OPERATOR_PROJECT_PERMISSIONS
            if permission not in granted
        ]
        result.api_activation_permission = "serviceusage.services.enable" in granted
        result.m1_permissions_ready = not result.missing_project_permissions
        result.m2_permissions_ready = not result.missing_m2_permissions
        result.m4_permissions_ready = not result.missing_m4_permissions
        result.m5_operator_permissions_ready = not result.missing_m5_operator_permissions
    except RuntimeError:
        result.missing_project_permissions = list(M1_PROJECT_PERMISSIONS)
        result.missing_m2_permissions = list(M2_PROJECT_PERMISSIONS)
        result.missing_m4_permissions = list(M4_PROJECT_PERMISSIONS)
        result.missing_m5_operator_permissions = list(M5_OPERATOR_PROJECT_PERMISSIONS)

    granted_m7: set[str] = set()
    for permission in M7_OPERATOR_PROJECT_PERMISSIONS:
        try:
            m7_payload = requester(
                user_token.stdout,
                "https://cloudresourcemanager.googleapis.com/v1/projects/"
                f"{quote(project_id, safe='')}:testIamPermissions",
                {"permissions": [permission]},
                project_id,
            )
            if permission in m7_payload.get("permissions", []):
                granted_m7.add(permission)
        except RuntimeError:
            continue
    result.missing_m7_operator_permissions = [
        permission for permission in M7_OPERATOR_PROJECT_PERMISSIONS if permission not in granted_m7
    ]
    result.m7_operator_permissions_ready = not result.missing_m7_operator_permissions

    investigator_email = f"opspilot-dev-agent@{project_id}.iam.gserviceaccount.com"
    try:
        impersonation = requester(
            user_token.stdout,
            "https://iam.googleapis.com/v1/projects/-/serviceAccounts/"
            f"{quote(investigator_email, safe='')}:testIamPermissions",
            {"permissions": ["iam.serviceAccounts.getAccessToken"]},
            project_id,
        )
        result.investigator_impersonation_check_available = True
        result.investigator_impersonation_ready = (
            "iam.serviceAccounts.getAccessToken" in impersonation.get("permissions", [])
        )
    except RuntimeError:
        pass

    candidate_filter = "metadata.name=(" + " ".join(M2_CANDIDATE_SERVICES) + ")"
    candidates = _load_json_list(
        runner(
            (
                "run",
                "services",
                "list",
                "--region=asia-northeast3",
                f"--filter={candidate_filter}",
                "--format=json",
            )
        )
    )
    if candidates is not None:
        result.m2_candidate_check_available = True
        result.m2_candidate_service_conflicts = len(candidates)
        result.m2_candidate_names_available = not candidates

    bucket_candidates = _load_json_list(
        runner(
            (
                "storage",
                "buckets",
                "list",
                f"--filter=name:{M4_CANDIDATE_ID}-",
                "--format=json",
            )
        )
    )
    if bucket_candidates is not None:
        result.m4_candidate_bucket_conflicts = len(bucket_candidates)

    try:
        engines = requester(
            user_token.stdout,
            "https://discoveryengine.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}/locations/global/collections/"
            "default_collection/engines?pageSize=100",
            None,
            project_id,
        )
        result.gemini_enterprise_access = True
        result.gemini_enterprise_app_exists = bool(engines.get("engines"))
        engine_items = engines.get("engines", [])
        enterprise_apps: list[dict[str, Any]] = []
        if isinstance(engine_items, list):
            enterprise_apps = [
                item
                for item in engine_items
                if isinstance(item, dict) and item.get("appType") == "APP_TYPE_INTRANET"
            ]
            result.m7_existing_app_count = len(enterprise_apps)
            result.m4_candidate_engine_conflicts = sum(
                1
                for item in engine_items
                if isinstance(item, dict)
                and str(item.get("name", "")).endswith(f"/engines/{M4_CANDIDATE_ID}")
            )
        data_stores = requester(
            user_token.stdout,
            "https://discoveryengine.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}/locations/global/collections/"
            "default_collection/dataStores?pageSize=100",
            None,
            project_id,
        )
        data_store_items = data_stores.get("dataStores", [])
        if isinstance(data_store_items, list):
            result.m4_candidate_data_store_conflicts = sum(
                1
                for item in data_store_items
                if isinstance(item, dict)
                and str(item.get("name", "")).endswith(f"/dataStores/{M4_CANDIDATE_ID}")
            )
        result.m4_candidate_check_available = bucket_candidates is not None
        result.m4_candidate_names_available = (
            result.m4_candidate_check_available
            and result.m4_candidate_bucket_conflicts == 0
            and result.m4_candidate_data_store_conflicts == 0
            and result.m4_candidate_engine_conflicts == 0
        )
        runtimes = requester(
            user_token.stdout,
            f"https://asia-northeast3-aiplatform.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}/locations/asia-northeast3/reasoningEngines",
            None,
            project_id,
        )
        runtime_items = runtimes.get("reasoningEngines", [])
        if isinstance(runtime_items, list):
            result.m7_runtime_name_conflicts = sum(
                1
                for item in runtime_items
                if isinstance(item, dict) and item.get("displayName") == M7_RUNTIME_DISPLAY_NAME
            )
            result.m7_candidate_check_available = True
        if len(enterprise_apps) == 1:
            app_name = str(enterprise_apps[0].get("name", ""))
            registrations = requester(
                user_token.stdout,
                "https://discoveryengine.googleapis.com/v1alpha/"
                f"{quote(app_name, safe='/')}/assistants/default_assistant/agents?pageSize=100",
                None,
                project_id,
            )
            registration_items = registrations.get("agents", [])
            if isinstance(registration_items, list):
                result.m7_registration_name_conflicts = sum(
                    1
                    for item in registration_items
                    if isinstance(item, dict) and item.get("displayName") == M7_RUNTIME_DISPLAY_NAME
                )
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
    result.m2_deploy_ready = all(
        (
            result.m0_ready,
            result.m2_permissions_ready,
            result.m2_candidate_names_available,
        )
    )
    result.m4_apply_ready = all(
        (
            result.m0_ready,
            result.m4_permissions_ready,
            result.m4_candidate_names_available,
        )
    )
    result.m5_apply_ready = all(
        (
            result.m0_ready,
            result.m5_operator_permissions_ready,
            result.investigator_impersonation_ready,
        )
    )
    result.m7_apply_ready = all(
        (
            result.m0_ready,
            result.m7_operator_permissions_ready,
            result.m7_candidate_check_available,
            result.m7_existing_app_count == 1,
            result.m7_runtime_name_conflicts == 0,
            result.m7_registration_name_conflicts == 0,
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
    if result.missing_m2_permissions:
        lines.append("missing_m2_permissions=" + ",".join(result.missing_m2_permissions))
    if result.missing_m4_permissions:
        lines.append("missing_m4_permissions=" + ",".join(result.missing_m4_permissions))
    if result.missing_m5_operator_permissions:
        lines.append(
            "missing_m5_operator_permissions=" + ",".join(result.missing_m5_operator_permissions)
        )
    if result.missing_m7_operator_permissions:
        lines.append(
            "missing_m7_operator_permissions=" + ",".join(result.missing_m7_operator_permissions)
        )
    lines.append(f"m2_candidate_service_conflicts={result.m2_candidate_service_conflicts}")
    lines.append(f"m4_candidate_bucket_conflicts={result.m4_candidate_bucket_conflicts}")
    lines.append(f"m4_candidate_data_store_conflicts={result.m4_candidate_data_store_conflicts}")
    lines.append(f"m4_candidate_engine_conflicts={result.m4_candidate_engine_conflicts}")
    lines.append(
        f"investigator_target_permission_count={result.investigator_target_permission_count}"
    )
    lines.append(
        f"m7_investigator_target_permission_count={result.m7_investigator_target_permission_count}"
    )
    lines.append(f"m7_existing_app_count={result.m7_existing_app_count}")
    lines.append(f"m7_runtime_name_conflicts={result.m7_runtime_name_conflicts}")
    lines.append(f"m7_registration_name_conflicts={result.m7_registration_name_conflicts}")
    return "\n".join(lines) + "\n"
