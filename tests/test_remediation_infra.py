from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_M8_workflow_keeps_callback_private_and_separates_execution_from_verification() -> None:
    workflow = (ROOT / "infra/workflows/remediation.yaml.tftpl").read_text(encoding="utf-8")

    assert "events.create_callback_endpoint" in workflow
    assert "events.await_callback" in workflow
    assert "timeout: 900" in workflow
    assert workflow.count("callback_details.url") == 1
    assert "callback_url: $${callback_details.url}" in workflow
    assert "sys.log" not in workflow
    assert "/begin-execution" in workflow
    assert "/execute" in workflow
    assert "/finish-execution" in workflow
    assert "traffic_update_succeeded" in workflow
    assert "verification_successes" not in workflow


def test_M8_terraform_is_default_off_and_executor_has_no_order_or_runtime_grant() -> None:
    variables = (ROOT / "infra/terraform/environments/dev/variables.tf").read_text(encoding="utf-8")
    remediation = (ROOT / "infra/terraform/environments/dev/remediation.tf").read_text(
        encoding="utf-8"
    )

    assert 'variable "enable_remediation"' in variables
    assert "default     = false" in variables
    assert 'ingress              = "INGRESS_TRAFFIC_INTERNAL_ONLY"' in remediation
    assert "max_instance_request_concurrency = 1" in remediation
    assert 'member   = "group:${var.remediation_approver_group}"' in remediation
    assert 'resource "google_project_service_identity" "workflows"' in remediation
    assert "provider = google-beta" in remediation
    assert 'service = "workflows.googleapis.com"' in remediation
    assert "depends_on = [google_project_service_identity.workflows]" in remediation
    assert 'title       = "payment-service-only"' in remediation
    assert (
        'resource "google_cloud_run_v2_service_iam_member" "executor_invokes_order"'
        not in remediation
    )
    assert "google_service_account.investigator" not in remediation


def test_M8_manual_ci_adds_real_remediation_gate_without_automatic_trigger() -> None:
    workflow = (ROOT / ".github/workflows/pr-checks.yml").read_text(encoding="utf-8")

    trigger = workflow.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "pull_request:" not in trigger
    assert "push:" not in trigger
    assert "opspilot remediation eval --suite remediation" in workflow
