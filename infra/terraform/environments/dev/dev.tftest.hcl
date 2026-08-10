mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "123456789012"
    }
  }
}

run "bounded_dev_foundation" {
  command = plan

  variables {
    project_id                = "example-project"
    billing_account_id        = "000000-000000-000000"
    budget_notification_email = "operator@example.invalid"
  }

  assert {
    condition     = google_artifact_registry_repository.apps.format == "DOCKER"
    error_message = "M1 must create a Docker Artifact Registry repository."
  }

  assert {
    condition     = google_artifact_registry_repository.apps.location == var.region
    error_message = "Artifact Registry must use the selected regional location."
  }

  assert {
    condition     = google_artifact_registry_repository.apps.repository_id == "opspilot-dev-apps-an3"
    error_message = "The dev Docker repository name must stay deterministic."
  }

  assert {
    condition     = google_artifact_registry_repository.apps.labels["data_classification"] == "synthetic"
    error_message = "M1 resources must be labeled as synthetic data."
  }

  assert {
    condition     = google_monitoring_notification_channel.budget_email.type == "email"
    error_message = "The M1 budget must have an explicit email notification channel."
  }

  assert {
    condition     = google_billing_budget.monthly.amount[0].specified_amount[0].currency_code == "KRW"
    error_message = "The monthly budget must use the verified KRW billing currency."
  }

  assert {
    condition     = google_billing_budget.monthly.amount[0].specified_amount[0].units == "50000"
    error_message = "The monthly budget must remain fixed at KRW 50,000."
  }

  assert {
    condition     = google_billing_budget.monthly.deletion_policy == "PREVENT"
    error_message = "The monthly budget must be protected from deletion."
  }

  assert {
    condition     = google_billing_budget.monthly.all_updates_rule[0].enable_project_level_recipients
    error_message = "Project-level recipients must receive alerts for the single-project budget."
  }

  assert {
    condition = toset([
      for rule in google_billing_budget.monthly.threshold_rules : rule.threshold_percent
    ]) == toset([0.5, 0.8, 1.0])
    error_message = "Budget thresholds must be 50, 80, and 100 percent."
  }

  assert {
    condition = alltrue([
      for service in google_project_service.m1 : service.disable_on_destroy == false
    ])
    error_message = "Terraform destroy must not disable shared project APIs."
  }
}
