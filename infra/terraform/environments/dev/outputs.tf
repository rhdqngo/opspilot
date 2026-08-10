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
