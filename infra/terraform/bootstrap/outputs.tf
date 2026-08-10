output "state_bucket_name" {
  description = "GCS bucket used for Terraform state after the approved bootstrap apply."
  value       = google_storage_bucket.terraform_state.name
  sensitive   = true
}

output "workload_identity_provider_name" {
  description = "Full GitHub Workload Identity Provider resource name."
  value       = google_iam_workload_identity_pool_provider.github.name
  sensitive   = true
}

output "ci_plan_service_account_email" {
  description = "Read-only service account impersonated by the GitHub plan workflow."
  value       = google_service_account.ci_plan.email
  sensitive   = true
}
