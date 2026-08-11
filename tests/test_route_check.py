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
        "canonical_urls_consistent": expected,
        "default_urls_enabled": expected,
        "ingress_all_services": expected,
        "iam_enforced_services": expected,
        "private_iam_services": expected,
        "operator_invoke_permission": True,
        "unauthenticated_status_codes": [403] * expected,
        "authenticated_status_codes": [200] * expected,
        "container_application_logs": expected,
    }
    values.update(updates)
    return CloudRunRouteCheckResult(**values)


def test_route_check_classifies_pre_container_404_as_endpoint_not_found() -> None:
    result = classify_route(
        _healthy_result(
            unauthenticated_status_codes=[404] * 3,
            authenticated_status_codes=[404] * 3,
            pre_container_404_services=3,
            container_application_logs=0,
        )
    )

    assert result.route_ready is False
    assert result.blocker_code == "endpoint_not_found"


def test_route_check_accepts_iam_403_and_authenticated_200() -> None:
    result = classify_route(_healthy_result())

    assert result.route_ready is True
    assert result.blocker_code == "none"


def test_route_check_does_not_fail_healthy_route_while_logs_are_delayed() -> None:
    result = classify_route(_healthy_result(container_application_logs=0))

    assert result.route_ready is True
    assert result.blocker_code == "none"


def test_route_check_distinguishes_authenticated_iam_denial() -> None:
    result = classify_route(_healthy_result(authenticated_status_codes=[403] * 3))

    assert result.route_ready is False
    assert result.blocker_code == "iam_denied"


def test_route_check_distinguishes_unready_service_and_transport_failure() -> None:
    unready = classify_route(_healthy_result(services_ready=2))
    transport = classify_route(_healthy_result(authenticated_status_codes=[0] * 3))

    assert unready.blocker_code == "service_unready"
    assert transport.blocker_code == "transport_error"


def test_route_check_distinguishes_application_failure() -> None:
    result = classify_route(_healthy_result(authenticated_status_codes=[500] * 3))

    assert result.blocker_code == "application_error"


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
                            "url": f"https://{command[3]}.secret.example",
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
            assert "jsonPayload.request_id=" in command[2]
            return CommandResult(0, "[]")
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


def test_route_check_redacts_endpoint_and_credential_identifiers() -> None:
    def status_requester(url: str, _token: str | None, _request_id: str) -> int:
        assert url.endswith("/health")
        return 404

    result = run_route_check(
        runner=FakeRunner(),
        requester=_requester,
        status_requester=status_requester,
    )

    assert result.blocker_code == "endpoint_not_found"
    assert result.canonical_urls_consistent == 3
    assert result.container_application_logs == 0
    output = result.model_dump_json() + render_route_summary(result)
    for secret_value in (
        "secret-project-id",
        "secret-access-token",
        "secret-identity-token",
        "secret.example",
        "example.invalid",
    ):
        assert secret_value not in output
