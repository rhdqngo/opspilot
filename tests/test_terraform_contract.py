from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = ROOT / "infra" / "terraform"


def _terraform_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in TERRAFORM_ROOT.rglob("*.tf"))


def test_M1_terraform_excludes_keys_remediation_and_command_hooks() -> None:
    source = _terraform_source()

    assert 'resource "google_service_account_key"' not in source
    assert "remediation" not in source.lower()
    assert "local-exec" not in source
    assert "remote-exec" not in source


def test_M1_state_bucket_contract_is_protected_in_source() -> None:
    source = (TERRAFORM_ROOT / "bootstrap" / "main.tf").read_text(encoding="utf-8")

    assert "force_destroy               = false" in source
    assert 'public_access_prevention    = "enforced"' in source
    assert "uniform_bucket_level_access = true" in source
    assert "enabled = true" in source
    assert "days_since_noncurrent_time = 30" in source
    assert "prevent_destroy = true" in source


def test_M1_runtime_backend_files_are_ignored() -> None:
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "backend.tf" in ignore_rules
    assert "backend.hcl" in ignore_rules


def test_M1_ci_custom_role_is_read_only() -> None:
    source = (TERRAFORM_ROOT / "bootstrap" / "main.tf").read_text(encoding="utf-8")
    match = re.search(r"permissions\s*=\s*\[(.*?)\]", source, flags=re.DOTALL)

    assert match is not None
    permissions = re.findall(r'"([a-zA-Z0-9.]+)"', match.group(1))
    assert permissions
    assert all(
        permission.endswith((".get", ".getIamPolicy", ".list", ".read"))
        for permission in permissions
    )
    assert {"run.services.get", "run.services.getIamPolicy", "run.services.list"}.issubset(
        permissions
    )


def test_M1_workflows_pin_actions_and_keep_live_plan_manual() -> None:
    workflow_root = ROOT / ".github" / "workflows"
    workflows = [path.read_text(encoding="utf-8") for path in workflow_root.glob("*.yml")]
    action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s]+)", "\n".join(workflows))

    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)

    live_plan = (workflow_root / "terraform-plan.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in live_plan
    assert "pull_request:" not in live_plan
    assert "vars.TF_PLAN_ENABLED == 'true'" in live_plan
    assert "vars.TF_M2_IMAGE_READY == 'true'" in live_plan
    assert 'TF_VAR_deploy_demo: "true"' in live_plan
    assert "TF_VAR_demo_image_uri" in live_plan
    assert live_plan.count("-lock=false") == 2
    assert "vars.TF_DEV_STATE_READY != 'true'" in live_plan
    assert "vars.TF_DEV_STATE_READY == 'true'" in live_plan
    assert "init -backend=false -input=false" in live_plan

    pull_request_checks = (workflow_root / "pr-checks.yml").read_text(encoding="utf-8")
    assert "id-token: write" not in pull_request_checks
    assert "google-github-actions/auth" not in pull_request_checks
    assert "docker build --platform linux/amd64" in pull_request_checks
    assert "docker compose up -d --no-build" in pull_request_checks


def test_M2_terraform_defines_only_private_bounded_demo_resources() -> None:
    dev_source = (TERRAFORM_ROOT / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert "default     = false" in variables
    assert "@sha256:[0-9a-f]{64}" in variables
    assert dev_source.count('resource "google_cloud_run_v2_service"') == 2
    assert 'resource "google_service_account" "demo"' in dev_source
    assert 'resource "google_cloud_run_v2_service_iam_member" "order_invokes_leaf"' in dev_source
    assert 'role     = "roles/run.invoker"' in dev_source
    assert "allUsers" not in dev_source
    assert "min_instance_count = 0" in dev_source
    assert "max_instance_count = 2" in dev_source
    assert 'memory = "256Mi"' in dev_source
    assert "firestore" not in dev_source.lower()
    assert "alert_policy" not in dev_source
    assert 'release_phase = "m2-mvp"' in dev_source
    assert "google_compute_network" not in dev_source
    assert "google_vpc_access_connector" not in dev_source
    assert "google_access_context_manager" not in dev_source
