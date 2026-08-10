from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from opspilot.access_check import (
    M1_PROJECT_PERMISSIONS,
    M2_PROJECT_PERMISSIONS,
    PROJECT_PERMISSIONS,
    AccessCheckResult,
    CommandResult,
    render_access_summary,
    run_access_check,
)


class FakeRunner:
    def __init__(
        self,
        *,
        user_credentials: bool = True,
        adc_credentials: bool = True,
        account: str = "operator+Edu_687@example.invalid",
        billing_enabled: bool = True,
    ) -> None:
        self.user_credentials = user_credentials
        self.adc_credentials = adc_credentials
        self.account = account
        self.billing_enabled = billing_enabled

    def __call__(self, arguments: Sequence[str]) -> CommandResult:
        command = tuple(arguments)
        if command[:2] == ("auth", "list"):
            return CommandResult(0, self.account)
        if command == ("auth", "print-access-token"):
            return (
                CommandResult(0, "secret-user-token")
                if self.user_credentials
                else CommandResult(1, "")
            )
        if command == ("auth", "application-default", "print-access-token"):
            return (
                CommandResult(0, "secret-adc-token")
                if self.adc_credentials
                else CommandResult(1, "")
            )
        if command == ("config", "get-value", "project"):
            return CommandResult(0, "secret-project-id")
        if command[:2] == ("projects", "describe"):
            return CommandResult(0, '{"lifecycleState":"ACTIVE","projectId":"secret-project-id"}')
        if command[:3] == ("billing", "projects", "describe"):
            enabled = "true" if self.billing_enabled else "false"
            return CommandResult(
                0,
                f'{{"billingEnabled":{enabled},"billingAccountName":"secret-billing-id"}}',
            )
        if command[:3] == ("run", "services", "list"):
            return CommandResult(0, "[]")
        raise AssertionError(f"Unexpected command shape: {command!r}")


def _requester(
    _token: str,
    url: str,
    body: dict[str, Any] | None,
    quota_project: str,
) -> dict[str, Any]:
    assert quota_project == "secret-project-id"
    if url.startswith("https://cloudresourcemanager.googleapis.com"):
        assert body is not None
        return {"permissions": list(PROJECT_PERMISSIONS)}
    if url.startswith("https://discoveryengine.googleapis.com"):
        return {"engines": [{"name": "secret-engine-id"}]}
    raise AssertionError(f"Unexpected URL shape: {url}")


def test_access_check_distinguishes_user_and_adc_credentials() -> None:
    result = run_access_check(runner=FakeRunner(adc_credentials=False), requester=_requester)

    assert result.user_credentials is True
    assert result.application_default_credentials is False
    assert result.m0_ready is False


def test_access_check_rejects_alias_mismatch_and_disabled_billing() -> None:
    result = run_access_check(
        runner=FakeRunner(account="different@example.invalid", billing_enabled=False),
        requester=_requester,
    )

    assert result.account_alias_match is False
    assert result.billing_enabled is False
    assert result.m0_ready is False


def test_access_check_reports_only_missing_permission_names() -> None:
    def partial_requester(
        token: str,
        url: str,
        body: dict[str, Any] | None,
        quota_project: str,
    ) -> dict[str, Any]:
        assert token == "secret-user-token"
        response = _requester(token, url, body, quota_project)
        if "cloudresourcemanager" in url:
            response["permissions"] = [
                permission
                for permission in PROJECT_PERMISSIONS
                if permission != "monitoring.notificationChannels.create"
            ]
        return response

    result = run_access_check(
        project_confirmed=True,
        billing_currency_krw_confirmed=True,
        runner=FakeRunner(),
        requester=partial_requester,
    )

    assert result.missing_project_permissions == ["monitoring.notificationChannels.create"]
    assert result.m1_permissions_ready is False
    summary = render_access_summary(result)
    assert "secret-user-token" not in summary
    assert "secret-project-id" not in summary
    assert "secret-billing-id" not in summary


def test_M2_access_check_reports_permissions_and_candidate_conflicts_without_identifiers() -> None:
    class ConflictRunner(FakeRunner):
        def __call__(self, arguments: Sequence[str]) -> CommandResult:
            if tuple(arguments)[:3] == ("run", "services", "list"):
                return CommandResult(0, '[{"metadata":{"name":"opspilot-dev-order"}}]')
            return super().__call__(arguments)

    def missing_upload_requester(
        token: str,
        url: str,
        body: dict[str, Any] | None,
        quota_project: str,
    ) -> dict[str, Any]:
        response = _requester(token, url, body, quota_project)
        if "cloudresourcemanager" in url:
            response["permissions"] = [
                permission
                for permission in PROJECT_PERMISSIONS
                if permission != "artifactregistry.repositories.uploadArtifacts"
            ]
        return response

    result = run_access_check(
        project_confirmed=True,
        billing_currency_krw_confirmed=True,
        runner=ConflictRunner(),
        requester=missing_upload_requester,
    )

    assert result.m1_permissions_ready is True
    assert result.missing_project_permissions == []
    assert result.missing_m2_permissions == ["artifactregistry.repositories.uploadArtifacts"]
    assert result.m2_permissions_ready is False
    assert result.m2_candidate_service_conflicts == 1
    assert result.m2_candidate_names_available is False
    assert result.m2_deploy_ready is False
    summary = render_access_summary(result)
    assert "opspilot-dev-order" not in summary
    assert "secret-project-id" not in summary


def test_access_check_requires_manual_project_and_krw_confirmation() -> None:
    result = run_access_check(runner=FakeRunner(), requester=_requester)

    assert result.m1_permissions_ready is True
    assert result.m2_permissions_ready is True
    assert result.m2_candidate_names_available is True
    assert result.gemini_enterprise_app_exists is True
    assert result.project_confirmed is False
    assert result.billing_currency_krw_confirmed is False
    assert result.m0_ready is False


def test_access_summary_contains_only_redacted_contract_fields() -> None:
    summary = render_access_summary(AccessCheckResult())

    assert "account_alias_match=fail" in summary
    assert "project_id" not in summary
    assert "billing_account" not in summary


def test_M1_and_M2_permission_sets_stay_explicitly_separated() -> None:
    assert set(M1_PROJECT_PERMISSIONS).issubset(PROJECT_PERMISSIONS)
    assert set(M2_PROJECT_PERMISSIONS).issubset(PROJECT_PERMISSIONS)
    assert "run.services.create" not in M1_PROJECT_PERMISSIONS
