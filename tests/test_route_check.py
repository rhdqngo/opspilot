from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from opspilot.route_check import (
    DEMO_SERVICES,
    CloudRunRouteCheckResult,
    CommandResult,
    classify_route,
    render_route_summary,
    run_route_check,
)


def _healthy_result(**updates: Any) -> CloudRunRouteCheckResult:
    expected = len(DEMO_SERVICES)
    values: dict[str, Any] = {
        "account_alias_match": True,
        "user_credentials": True,
        "default_project_configured": True,
        "services_found": expected,
        "services_ready": expected,
        "services_with_full_traffic": expected,
        "default_urls_enabled": expected,
        "ingress_all_services": expected,
        "iam_enforced_services": expected,
        "private_iam_services": expected,
        "operator_invoke_permission": True,
        "unauthenticated_status_codes": [403] * expected,
        "authenticated_status_codes": [200] * expected,
    }
    values.update(updates)
    return CloudRunRouteCheckResult(**values)


def test_route_check_classifies_pre_container_404_as_route_restricted() -> None:
    result = classify_route(
        _healthy_result(
            unauthenticated_status_codes=[404] * 3,
            authenticated_status_codes=[404] * 3,
            pre_container_404_services=3,
        )
    )

    assert result.route_ready is False
    assert result.blocker_code == "route_restricted"


def test_route_check_accepts_iam_403_and_authenticated_200() -> None:
    result = classify_route(_healthy_result())

    assert result.route_ready is True
    assert result.blocker_code == "none"


def test_route_check_distinguishes_authenticated_iam_denial() -> None:
    result = classify_route(_healthy_result(authenticated_status_codes=[403] * 3))

    assert result.route_ready is False
    assert result.blocker_code == "iam_denied"


def test_route_check_distinguishes_unready_service_and_unknown_http_failure() -> None:
    unready = classify_route(_healthy_result(services_ready=2))
    unknown = classify_route(_healthy_result(authenticated_status_codes=[0] * 3))

    assert unready.blocker_code == "service_unready"
    assert unknown.blocker_code == "unknown"


def test_route_check_converts_gcloud_failures_to_safe_state() -> None:
    result = run_route_check(runner=lambda _arguments: CommandResult(1, ""))

    assert result.route_ready is False
    assert result.blocker_code == "service_unready"
    assert result.user_credentials is False


class FakeRunner:
    def __call__(self, arguments: Sequence[str]) -> CommandResult:
        command = tuple(arguments)
        if command[:2] == ("auth", "list"):
            return CommandResult(0, "operator+Edu_687@example.invalid")
        if command == ("auth", "print-access-token"):
            return CommandResult(0, "secret-access-token")
        if command == ("auth", "print-identity-token"):
            return CommandResult(0, "secret-identity-token")
        if command == ("config", "get-value", "project"):
            return CommandResult(0, "secret-project-id")
        if command[:3] == ("run", "services", "describe"):
            return CommandResult(
                0,
                json.dumps(
                    {
                        "status": {
                            "conditions": [{"type": "Ready", "status": "True"}],
                            "traffic": [{"percent": 100}],
                        }
                    }
                ),
            )
        if command[:3] == ("run", "services", "get-iam-policy"):
            return CommandResult(
                0,
                json.dumps(
                    {
                        "bindings": [
                            {
                                "role": "roles/run.invoker",
                                "members": ["serviceAccount:private@example.invalid"],
                            }
                        ]
                    }
                ),
            )
        if command[:2] == ("logging", "read"):
            assert 'logName:"run.googleapis.com%2Frequests"' in command[2]
            return CommandResult(0, "[]")
        if command[:3] == ("resource-manager", "org-policies", "list"):
            return CommandResult(0, "[]")
        if command[:2] == ("projects", "get-ancestors"):
            return CommandResult(0, '[{"type":"organization","id":"secret-org-id"}]')
        if command[:3] == ("access-context-manager", "policies", "list"):
            return CommandResult(1, "")
        raise AssertionError(f"Unexpected command shape: {command!r}")


def _requester(
    token: str,
    url: str,
    body: dict[str, Any] | None,
    quota_project: str,
) -> dict[str, Any]:
    assert token == "secret-access-token"
    assert quota_project == "secret-project-id"
    if "cloudresourcemanager" in url:
        assert body == {"permissions": ["run.routes.invoke"]}
        return {"permissions": ["run.routes.invoke"]}
    if "run.googleapis.com" in url:
        service_name = url.rsplit("/", 1)[-1]
        return {
            "uri": f"https://{service_name}.secret.example",
            "ingress": "INGRESS_TRAFFIC_ALL",
            "defaultUriDisabled": False,
            "invokerIamDisabled": False,
        }
    raise AssertionError(f"Unexpected URL shape: {url}")


def test_route_check_handles_unreadable_vpc_policy_and_redacts_identifiers() -> None:
    result = run_route_check(
        runner=FakeRunner(),
        requester=_requester,
        status_requester=lambda _url, _token: 404,
    )

    assert result.blocker_code == "route_restricted"
    assert result.project_org_policies_readable is True
    assert result.vpc_sc_policies_readable is False
    output = result.model_dump_json() + render_route_summary(result)
    for secret_value in (
        "secret-project-id",
        "secret-access-token",
        "secret-identity-token",
        "secret.example",
        "example.invalid",
        "secret-org-id",
    ):
        assert secret_value not in output
