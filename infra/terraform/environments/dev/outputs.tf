output "artifact_registry_repository" {
  description = "Artifact Registry repository resource identifier."
  value       = google_artifact_registry_repository.apps.id
  sensitive   = true
}

output "investigator_service_account_email" {
  description = "Unprivileged investigator service account email."
  value       = google_service_account.investigator.email
  sensitive   = true
}

output "knowledge_bucket_name" {
  description = "M4 knowledge bucket name; present only after the separate apply approval."
  value       = try(google_storage_bucket.knowledge[0].name, null)
  sensitive   = true
}

output "knowledge_data_store_name" {
  description = "M4 Agent Search data store name."
  value       = try(google_discovery_engine_data_store.knowledge[0].name, null)
  sensitive   = true
}

output "knowledge_engine_name" {
  description = "M4 Agent Search engine name."
  value       = try(google_discovery_engine_search_engine.knowledge[0].name, null)
  sensitive   = true
}

output "agent_runtime_name" {
  description = "M7 Agent Runtime resource name after the separate apply approval."
  value       = try(google_vertex_ai_reasoning_engine.opspilot[0].name, null)
  sensitive   = true
}

output "remediation_control_url" {
  description = "M8 authenticated remediation control API URL after separate apply approval."
  value       = try(google_cloud_run_v2_service.remediation_control[0].uri, null)
  sensitive   = true
}

output "remediation_executor_name" {
  description = "M8 internal-only remediation executor resource name."
  value       = try(google_cloud_run_v2_service.remediation_executor[0].name, null)
  sensitive   = true
}

output "remediation_workflow_name" {
  description = "M8 callback workflow name."
  value       = try(google_workflows_workflow.remediation[0].name, null)
  sensitive   = true
}
