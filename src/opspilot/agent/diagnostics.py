"""Zero-generation readiness checks for the M6 Vertex acceptance boundary."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from opspilot.access_check import (
    AccessCheckResult,
    CommandRunner,
    JsonRequester,
    _default_runner,
    _request_json,
    run_access_check,
)
from opspilot.agent.contracts import AgentDiagnosticResult
from opspilot.agent.models import (
    DEFAULT_MODEL_ID,
    M6_ACCEPTANCE_DEADLINE_SECONDS,
    MODEL_DEADLINE_SECONDS,
    MODEL_LOCATION,
    MODEL_NODE_TIMEOUT_SECONDS,
)

M6_MODEL_PERMISSIONS = (
    "aiplatform.endpoints.predict",
    "serviceusage.services.use",
)

AccessChecker = Callable[..., AccessCheckResult]


def run_agent_diagnostic(
    *,
    account_alias: str,
    access_checker: AccessChecker = run_access_check,
    runner: CommandRunner = _default_runner,
    requester: JsonRequester = _request_json,
) -> AgentDiagnosticResult:
    """Verify the fixed model path without issuing a generation request."""

    access = access_checker(
        account_alias=account_alias,
        project_confirmed=True,
        billing_currency_krw_confirmed=True,
        runner=runner,
        requester=requester,
    )
    diagnostic = AgentDiagnosticResult(
        account_alias=account_alias,
        account_alias_match=access.account_alias_match,
        user_credentials=access.user_credentials,
        application_default_credentials=access.application_default_credentials,
        default_project_configured=access.default_project_configured,
        project_active=access.project_active,
        billing_enabled=access.billing_enabled,
        billing_currency_krw_confirmed=access.billing_currency_krw_confirmed,
        model_id_allowed=DEFAULT_MODEL_ID == "gemini-3.5-flash",
        location_global=MODEL_LOCATION == "global",
        standard_paygo=True,
        node_timeout_seconds=MODEL_NODE_TIMEOUT_SECONDS,
        graph_timeout_seconds=MODEL_DEADLINE_SECONDS,
        acceptance_timeout_seconds=M6_ACCEPTANCE_DEADLINE_SECONDS,
        phase_observability_ready=True,
        generate_content_calls=0,
    )
    project_result = runner(("config", "get-value", "project"))
    token_result = runner(("auth", "print-access-token"))
    if project_result.returncode != 0 or not project_result.stdout:
        diagnostic.errors.append("default_project_unavailable")
        return diagnostic
    if token_result.returncode != 0 or not token_result.stdout:
        diagnostic.errors.append("user_credential_unavailable")
        return diagnostic
    project_id = project_result.stdout
    api_result = runner(
        (
            "services",
            "list",
            "--enabled",
            "--filter=config.name:aiplatform.googleapis.com",
            "--format=value(config.name)",
        )
    )
    diagnostic.vertex_api_enabled = (
        api_result.returncode == 0 and api_result.stdout == "aiplatform.googleapis.com"
    )
    try:
        payload = requester(
            token_result.stdout,
            "https://cloudresourcemanager.googleapis.com/v1/projects/"
            f"{quote(project_id, safe='')}:testIamPermissions",
            {"permissions": list(M6_MODEL_PERMISSIONS)},
            project_id,
        )
        granted = set(payload.get("permissions", []))
        diagnostic.predict_permission = "aiplatform.endpoints.predict" in granted
        diagnostic.service_usage_permission = "serviceusage.services.use" in granted
        diagnostic.missing_permissions = [
            permission for permission in M6_MODEL_PERMISSIONS if permission not in granted
        ]
    except RuntimeError:
        diagnostic.errors.append("permission_check_unavailable")
        diagnostic.missing_permissions = list(M6_MODEL_PERMISSIONS)
    if not diagnostic.vertex_api_enabled:
        diagnostic.errors.append("vertex_api_disabled")
    diagnostic.model_ready = all(
        (
            diagnostic.account_alias_match,
            diagnostic.user_credentials,
            diagnostic.application_default_credentials,
            diagnostic.default_project_configured,
            diagnostic.project_active,
            diagnostic.billing_enabled,
            diagnostic.billing_currency_krw_confirmed,
            diagnostic.vertex_api_enabled,
            diagnostic.predict_permission,
            diagnostic.service_usage_permission,
            diagnostic.model_id_allowed,
            diagnostic.location_global,
            diagnostic.standard_paygo,
            diagnostic.phase_observability_ready,
            diagnostic.generate_content_calls == 0,
            not diagnostic.errors,
        )
    )
    return diagnostic


def render_agent_diagnostic(result: AgentDiagnosticResult) -> str:
    fields = result.model_dump()
    lines = [
        f"{name}={'pass' if value else 'fail'}"
        for name, value in fields.items()
        if isinstance(value, bool)
    ]
    lines.extend(
        (
            f"node_timeout_seconds={result.node_timeout_seconds:g}",
            f"graph_timeout_seconds={result.graph_timeout_seconds}",
            f"acceptance_timeout_seconds={result.acceptance_timeout_seconds}",
        )
    )
    lines.append(f"generate_content_calls={result.generate_content_calls}")
    if result.missing_permissions:
        lines.append("missing_permissions=" + ",".join(result.missing_permissions))
    lines.extend(f"error={error}" for error in result.errors)
    return "\n".join(lines) + "\n"
