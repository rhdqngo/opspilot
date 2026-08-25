from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = ROOT / "infra" / "terraform"


def _terraform_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in TERRAFORM_ROOT.rglob("*.tf"))


def test_M1_terraform_excludes_keys_and_command_hooks_while_M8_is_default_off() -> None:
    source = _terraform_source()
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert 'resource "google_service_account_key"' not in source
    assert "local-exec" not in source
    assert "remote-exec" not in source
    remediation_default = re.search(
        r'variable "enable_remediation"\s*\{.*?default\s*=\s*(\w+)',
        variables,
        flags=re.DOTALL,
    )
    assert remediation_default is not None
    assert remediation_default.group(1) == "false"


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


def test_M1_ci_custom_role_is_least_privilege() -> None:
    source = (TERRAFORM_ROOT / "bootstrap" / "main.tf").read_text(encoding="utf-8")
    match = re.search(r"permissions\s*=\s*\[(.*?)\]", source, flags=re.DOTALL)

    assert match is not None
    permissions = re.findall(r'"([a-zA-Z0-9.]+)"', match.group(1))
    assert permissions
    assert all(
        permission == "serviceusage.services.use"
        or permission.endswith((".get", ".getIamPolicy", ".list", ".read"))
        for permission in permissions
    )
    assert permissions.count("serviceusage.services.use") == 1
    assert "serviceusage.services.enable" not in permissions
    assert "serviceusage.services.disable" not in permissions
    assert {"run.services.get", "run.services.getIamPolicy", "run.services.list"}.issubset(
        permissions
    )
    assert {
        "iam.roles.get",
        "iam.serviceAccounts.getIamPolicy",
        "resourcemanager.projects.getIamPolicy",
    }.issubset(permissions)
    assert {
        "cloudscheduler.jobs.get",
        "cloudscheduler.jobs.list",
        "run.jobs.get",
        "run.jobs.getIamPolicy",
        "run.jobs.list",
    }.issubset(permissions)


def test_scheduled_scenario_source_keeps_identity_and_target_scope_bounded() -> None:
    source = (TERRAFORM_ROOT / "environments" / "dev" / "scheduled_scenarios.tf").read_text(
        encoding="utf-8"
    )
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert 'variable "enable_scheduled_scenarios"' in variables
    assert re.search(
        r'variable "enable_scheduled_scenarios"\s*\{.*?default\s*=\s*false',
        variables,
        flags=re.DOTALL,
    )
    assert 'schedule    = "5,35 * * * *"' in source
    assert 'time_zone   = "Asia/Seoul"' in source
    assert "Cloud Scheduler's API default is retry_count=0" in source
    assert "retry_config {" not in source
    assert "max_retries     = 0" in source
    assert 'timeout         = "300s"' in source
    assert 'memory = "512Mi"' in source
    assert '"--auth",\n          "workload"' in source
    assert "name     = google_cloud_run_v2_service.demo_order[0].name" in source
    assert 'resource "google_cloud_run_v2_job_iam_member" "scheduler_invokes_scn001"' in source
    assert source.count('role     = "roles/run.invoker"') == 2
    assert "roles/iam.serviceAccountTokenCreator" not in source
    assert "allUsers" not in source
    assert "allAuthenticatedUsers" not in source
    assert "staging" not in source
    assert "prod-sim" not in source


def test_M1_workflows_pin_actions_and_keep_live_plan_manual() -> None:
    workflow_root = ROOT / ".github" / "workflows"
    workflows = [path.read_text(encoding="utf-8") for path in workflow_root.glob("*.yml")]
    action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s]+)", "\n".join(workflows))

    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)

    for workflow_name in ("pr-checks.yml", "terraform-checks.yml", "terraform-plan.yml"):
        workflow = (workflow_root / workflow_name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in workflow
        assert "pull_request:" not in workflow
        assert "push:" not in workflow

    live_plan = (workflow_root / "terraform-plan.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in live_plan
    assert "pull_request:" not in live_plan
    assert "vars.TF_PLAN_ENABLED == 'true'" in live_plan
    assert "vars.TF_M2_IMAGE_READY == 'true'" in live_plan
    assert "vars.TF_M3_IMAGE_READY == 'true'" in live_plan
    assert "vars.TF_M4_KNOWLEDGE_READY == 'true'" in live_plan
    assert "vars.TF_M5_LIVE_EVIDENCE_READY == 'true'" in live_plan
    assert "vars.TF_M7_RUNTIME_READY == 'true'" in live_plan
    assert "vars.TF_M8_REMEDIATION_READY == 'true'" in live_plan
    assert "vars.TF_PERSISTENT_INVESTIGATIONS_READY == 'true'" in live_plan
    sensitive_settings = (
        "GCP_PROJECT_ID",
        "GCP_PROJECT_NUMBER",
        "GCP_BILLING_ACCOUNT_ID",
        "GCP_DEMO_IMAGE_URI",
        "GCP_WIF_PROVIDER",
        "GCP_TERRAFORM_PLAN_SERVICE_ACCOUNT",
        "TF_STATE_BUCKET",
    )
    for setting in sensitive_settings:
        assert f"secrets.{setting}" in live_plan
        assert f"vars.{setting}" not in live_plan
    assert 'TF_VAR_deploy_demo: "true"' in live_plan
    assert 'TF_VAR_deploy_knowledge: "true"' in live_plan
    assert 'TF_VAR_enable_live_evidence: "true"' in live_plan
    assert 'TF_VAR_deploy_agent_runtime: "true"' in live_plan
    assert 'TF_VAR_enable_persistent_investigations: "true"' in live_plan
    assert 'TF_VAR_enable_remediation: "true"' in live_plan
    assert "opspilot agent runtime package" in live_plan
    assert "TF_VAR_agent_runtime_source_archive" in live_plan
    assert "TF_VAR_investigator_operator_email" in live_plan
    assert "secrets.GCP_INVESTIGATOR_OPERATOR_EMAIL" in live_plan
    assert "TF_VAR_demo_image_uri" in live_plan
    assert "TF_VAR_investigation_image_uri" in live_plan
    assert "secrets.GCP_INVESTIGATION_IMAGE_URI" in live_plan
    assert "TF_VAR_remediation_image_uri" in live_plan
    assert "secrets.GCP_REMEDIATION_IMAGE_URI" in live_plan
    assert "TF_VAR_remediation_approver_group" in live_plan
    assert "secrets.GCP_REMEDIATION_APPROVER_GROUP" in live_plan
    assert "OPSPILOT_REDACT_INVESTIGATION_IMAGE_URI" in live_plan
    assert "OPSPILOT_REDACT_REMEDIATION_IMAGE_URI" in live_plan
    assert "OPSPILOT_REDACT_REMEDIATION_APPROVER_GROUP" in live_plan
    assert "OPSPILOT_REDACT_INVESTIGATOR_OPERATOR_EMAIL" in live_plan
    assert "OPSPILOT_REDACT_WIF_PROVIDER" in live_plan
    assert "OPSPILOT_REDACT_TERRAFORM_PLAN_SERVICE_ACCOUNT" in live_plan
    assert 'raw_log="$RUNNER_TEMP/terraform-plan-raw.txt"' in live_plan
    assert '>"$raw_log" 2>&1' in live_plan
    assert 'python -m opspilot.plan_redaction < "$raw_log"' in live_plan
    assert 'rm -f "$raw_log"' in live_plan
    assert live_plan.count("-lock=false") == 2
    assert "vars.TF_DEV_STATE_READY != 'true'" in live_plan
    assert "vars.TF_DEV_STATE_READY == 'true'" in live_plan
    assert "init -backend=false -input=false" in live_plan

    pull_request_checks = (workflow_root / "pr-checks.yml").read_text(encoding="utf-8")
    assert "id-token: write" not in pull_request_checks
    assert "google-github-actions/auth" not in pull_request_checks
    assert "docker build --platform linux/amd64" in pull_request_checks
    assert "docker compose up -d --no-build" in pull_request_checks
    assert "opspilot knowledge validate" in pull_request_checks
    assert "opspilot knowledge smoke --format summary" in pull_request_checks
    assert "opspilot agent runtime package" in pull_request_checks
    assert "opspilot agent runtime validate" not in pull_request_checks
    assert "opspilot agent runtime smoke" not in pull_request_checks
    assert "opspilot agent runtime package" in pull_request_checks
    bootstrap_source = (TERRAFORM_ROOT / "bootstrap" / "main.tf").read_text(encoding="utf-8")
    assert "aiplatform.reasoningEngines.get" not in bootstrap_source
    assert "aiplatform.reasoningEngines.list" not in bootstrap_source
    assert '"cloudtasks.queues.get"' in bootstrap_source
    assert '"datastore.databases.get"' in bootstrap_source
    assert '"pubsub.subscriptions.get"' in bootstrap_source
    assert '"workflows.workflows.get"' in bootstrap_source


def test_M2_terraform_defines_only_private_bounded_demo_resources() -> None:
    dev_source = (TERRAFORM_ROOT / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert "default     = false" in variables
    assert "@sha256:[0-9a-f]{64}" in variables
    assert dev_source.count('resource "google_cloud_run_v2_service"') == 3
    assert 'resource "google_cloud_run_v2_service" "demo_payment"' in dev_source
    assert 'from = google_cloud_run_v2_service.demo_leaf["payment"]' in dev_source
    assert (
        'from = google_cloud_run_v2_service_iam_member.order_invokes_leaf["payment"]' in dev_source
    )
    assert "ignore_changes = [traffic]" in dev_source
    assert 'resource "google_service_account" "demo"' in dev_source
    assert 'resource "google_cloud_run_v2_service_iam_member" "order_invokes_leaf"' in dev_source
    assert 'role     = "roles/run.invoker"' in dev_source
    assert "allUsers" not in dev_source
    assert "min_instance_count = 0" in dev_source
    assert "max_instance_count = 2" in dev_source
    assert 'memory = "256Mi"' in dev_source
    assert 'resource "google_firestore' not in dev_source
    assert "alert_policy" not in dev_source
    assert 'release_phase = "m2-mvp"' in dev_source
    assert "google_compute_network" not in dev_source
    assert "google_vpc_access_connector" not in dev_source
    assert "google_access_context_manager" not in dev_source


def test_M4_terraform_is_default_off_and_defines_only_four_knowledge_resources() -> None:
    dev_source = (TERRAFORM_ROOT / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert 'variable "deploy_knowledge"' in variables
    assert 'variable "search_location"' in variables
    assert 'default     = "global"' in variables
    assert dev_source.count('resource "google_storage_bucket" "knowledge"') == 1
    assert dev_source.count('resource "google_discovery_engine_data_store" "knowledge"') == 1
    assert dev_source.count('resource "google_discovery_engine_schema" "knowledge"') == 1
    assert dev_source.count('resource "google_discovery_engine_search_engine" "knowledge"') == 1
    assert "SEARCH_TIER_STANDARD" in dev_source
    assert "SEARCH_ADD_ON_LLM" not in dev_source
    assert 'deletion_policy   = "PREVENT"' in dev_source
    assert "google_storage_bucket_object" not in dev_source
    assert "allUsers" not in dev_source


def test_M5_terraform_is_default_off_and_defines_only_bounded_investigator_iam() -> None:
    dev_source = (TERRAFORM_ROOT / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert 'variable "enable_live_evidence"' in variables
    assert 'variable "investigator_operator_email"' in variables
    assert 'resource "google_project_iam_custom_role" "investigator_reader"' in dev_source
    assert 'resource "google_project_iam_member" "investigator_reader"' in dev_source
    assert (
        'resource "google_service_account_iam_member" '
        '"investigator_operator_token_creator"' in dev_source
    )
    role = re.search(
        r'resource "google_project_iam_custom_role" "investigator_reader" \{(.*?)\n\}',
        dev_source,
        flags=re.DOTALL,
    )
    assert role is not None
    permission_block = re.search(
        r"permissions\s*=\s*concat\(\[(.*?)\]", role.group(1), flags=re.DOTALL
    )
    assert permission_block is not None
    permissions = set(re.findall(r'"([a-zA-Z0-9.]+)"', permission_block.group(1)))
    assert permissions == {
        "discoveryengine.servingConfigs.search",
        "logging.logEntries.list",
        "monitoring.timeSeries.list",
        "resourcemanager.projects.get",
        "run.revisions.list",
        "run.services.get",
        "serviceusage.services.use",
    }
    prohibited = ("create", "delete", "update", "setIamPolicy", "invoke", "import")
    assert not any(permission.endswith(prohibited) for permission in permissions)
    assert "allUsers" not in dev_source
    assert 'role               = "roles/iam.serviceAccountTokenCreator"' in dev_source
    assert 'member             = "user:${var.investigator_operator_email}"' in dev_source
    assert "service_account_id = google_service_account.investigator.name" in dev_source


def test_M7_terraform_is_default_off_and_defines_only_bounded_runtime_resources() -> None:
    dev_source = (TERRAFORM_ROOT / "environments" / "dev" / "main.tf").read_text(encoding="utf-8")
    variables = (TERRAFORM_ROOT / "environments" / "dev" / "variables.tf").read_text(
        encoding="utf-8"
    )

    assert 'variable "deploy_agent_runtime"' in variables
    assert 'resource "google_vertex_ai_reasoning_engine" "opspilot"' in dev_source
    assert dev_source.count('resource "google_vertex_ai_reasoning_engine"') == 1
    assert "count = var.deploy_agent_runtime ? 1 : 0" in dev_source
    assert 'agent_framework = "google-adk"' in dev_source
    assert "class_methods   = jsonencode(local.runtime_class_methods)" in dev_source
    assert dev_source.count('name     = "streaming_agent_run_with_events"') == 1
    assert dev_source.count('api_mode = "async_stream"') == 1
    assert dev_source.count('required = ["request_json"]') == 1
    assert "service_account = google_service_account.investigator.email" in dev_source
    assert "min_instances         = 0" in dev_source
    assert "max_instances         = 1" in dev_source
    assert 'memory = "1Gi"' in dev_source
    assert "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT" in dev_source
    assert 'name  = "OPSPILOT_RUNTIME_PROJECT_ID"' not in dev_source
    assert 'name  = "GOOGLE_CLOUD_PROJECT"' not in dev_source
    assert (
        'name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"\n        value = "true"'
    ) in dev_source
    assert 'resource "google_project_iam_custom_role" "runtime_project_metadata"' in dev_source
    assert 'permissions = ["resourcemanager.projects.get"]' in dev_source
    assert 'resource "google_project_iam_member" "runtime_project_metadata"' in dev_source
    assert "value = var.project_id" in dev_source
    assert 'value = "false"' in dev_source
    assert 'entrypoint_module = "opspilot.agent.runtime_agent"' in dev_source
    assert 'deletion_policy = "PREVENT"' in dev_source
    assert "aiplatform.endpoints.predict" in dev_source
    assert "allUsers" not in dev_source
    prohibited_resources = (
        "google_service_account_key",
        "google_compute_network",
        "google_vpc_access_connector",
        "google_access_context_manager",
        "google_secret_manager_secret",
    )
    assert not any(resource in dev_source for resource in prohibited_resources)
    assert "memory_bank" not in dev_source.casefold()
    assert "oauth" not in dev_source.casefold()
