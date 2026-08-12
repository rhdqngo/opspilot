from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from opspilot.agent.enterprise import (
    REGISTER_GATE,
    EnterpriseApiFailure,
    run_enterprise_registration,
)
from opspilot.agent.runtime import RUNTIME_DISPLAY_NAME
from opspilot.domain import ToolErrorCategory
from opspilot.evidence import LiveEvidenceFailure, WorkloadAdcTokenProvider


class FakeInventory:
    def __init__(
        self,
        *,
        apps: int = 1,
        runtimes: int = 1,
        registration_runtime: str | None = None,
        failure: str | None = None,
    ) -> None:
        self.apps = apps
        self.runtimes = runtimes
        self.registration_runtime = registration_runtime
        self.failure = failure
        self.mutations = 0

    def _fail(self) -> None:
        if self.failure:
            raise EnterpriseApiFailure(self.failure)

    def list_apps(self) -> list[Mapping[str, Any]]:
        self._fail()
        return [{"name": f"hidden-app-{index}"} for index in range(self.apps)]

    def list_runtimes(self) -> list[Mapping[str, Any]]:
        self._fail()
        return [
            {"name": f"hidden-runtime-{index}", "displayName": RUNTIME_DISPLAY_NAME}
            for index in range(self.runtimes)
        ]

    def list_registrations(self, _app_name: str) -> list[Mapping[str, Any]]:
        self._fail()
        if self.registration_runtime is None:
            return []
        return [
            {
                "displayName": RUNTIME_DISPLAY_NAME,
                "adkAgentDefinition": {
                    "provisionedReasoningEngine": {
                        "reasoningEngine": self.registration_runtime,
                    }
                },
            }
        ]

    def register(self, _app_name: str, _runtime_name: str) -> None:
        self._fail()
        self.mutations += 1


def test_M7_enterprise_plan_is_read_only_and_identifier_free() -> None:
    inventory = FakeInventory()

    result = run_enterprise_registration("plan", inventory=inventory)

    assert result.succeeded is True
    assert result.mutation_count == 0
    assert result.app_count == 1
    assert result.runtime_match_count == 1
    assert inventory.mutations == 0
    output = result.model_dump_json()
    assert "hidden-app" not in output
    assert "hidden-runtime" not in output


def test_M7_enterprise_apply_requires_explicit_process_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(REGISTER_GATE, raising=False)
    inventory = FakeInventory()

    result = run_enterprise_registration("apply", inventory=inventory)

    assert result.succeeded is False
    assert result.blocker_code == "gate_disabled"
    assert inventory.mutations == 0


def test_M7_enterprise_apply_is_idempotent_for_same_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(REGISTER_GATE, "true")
    inventory = FakeInventory(registration_runtime="hidden-runtime-0")

    result = run_enterprise_registration("apply", inventory=inventory)

    assert result.succeeded is True
    assert result.no_op is True
    assert result.mutation_count == 0
    assert inventory.mutations == 0


def test_M7_enterprise_stops_on_app_runtime_or_name_conflict() -> None:
    assert run_enterprise_registration("plan", inventory=FakeInventory(apps=2)).blocker_code == (
        "app_not_unique"
    )
    assert (
        run_enterprise_registration("plan", inventory=FakeInventory(runtimes=0)).blocker_code
        == "runtime_not_unique"
    )
    assert (
        run_enterprise_registration(
            "plan", inventory=FakeInventory(registration_runtime="other-runtime")
        ).blocker_code
        == "display_name_conflict"
    )


@pytest.mark.parametrize(
    "failure",
    ["unauthorized", "forbidden", "not_found", "upstream_error", "invalid_response"],
)
def test_M7_enterprise_normalizes_failures_without_raw_errors(failure: str) -> None:
    result = run_enterprise_registration("plan", inventory=FakeInventory(failure=failure))

    assert result.succeeded is False
    assert result.blocker_code == failure
    assert "hidden" not in result.model_dump_json()


def test_M7_enterprise_normalizes_expired_adc_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def expired_adc(_provider: WorkloadAdcTokenProvider) -> str:
        raise LiveEvidenceFailure(
            "EVIDENCE_WORKLOAD_ADC_FAILED",
            ToolErrorCategory.AUTH,
            retryable=False,
            safe_message="credential unavailable",
        )

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "hidden-project")
    monkeypatch.setattr(WorkloadAdcTokenProvider, "get_token", expired_adc)

    result = run_enterprise_registration("plan")

    assert result.succeeded is False
    assert result.blocker_code == "unauthorized"
    assert "hidden-project" not in result.model_dump_json()
