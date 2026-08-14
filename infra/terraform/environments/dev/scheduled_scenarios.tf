resource "google_service_account" "scheduled_scenario_runner" {
  count = var.enable_scheduled_scenarios ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-scenario"
  display_name = "OpsPilot ${var.environment} scheduled scenario runner"
  description  = "Runs only bounded request-scoped SCN-001 traffic against the dev order service."

  depends_on = [google_project_service.m1]
}

resource "google_service_account" "scheduled_scenario_trigger" {
  count = var.enable_scheduled_scenarios ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-scenario-trigger"
  display_name = "OpsPilot ${var.environment} scheduled scenario trigger"
  description  = "OAuth identity that may invoke only the bounded SCN-001 Cloud Run Job."

  depends_on = [google_project_service.m1]
}

resource "google_cloud_run_v2_job" "scheduled_scn001" {
  count = var.enable_scheduled_scenarios ? 1 : 0

  project             = var.project_id
  name                = "opspilot-${var.environment}-scn001"
  location            = var.region
  deletion_protection = false
  labels              = local.labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.scheduled_scenario_runner[0].email
      timeout         = "300s"
      max_retries     = 0

      containers {
        image = var.scheduled_scenario_image_uri
        args = [
          "scenario",
          "run",
          "--scenario",
          "SCN-001",
          "--env",
          "dev",
          "--auth",
          "workload",
          "--format",
          "json",
        ]

        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }

        env {
          name  = "OPSPILOT_DEV_ORDER_URL"
          value = google_cloud_run_v2_service.demo_order[0].uri
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", nonsensitive(var.scheduled_scenario_image_uri)))
      error_message = "scheduled_scenario_image_uri must be an immutable Artifact Registry digest."
    }
  }

  depends_on = [google_project_service.m1]
}

resource "google_cloud_run_v2_service_iam_member" "scheduled_runner_invokes_dev_order" {
  count = var.enable_scheduled_scenarios ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.demo_order[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduled_scenario_runner[0].email}"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invokes_scn001" {
  count = var.enable_scheduled_scenarios ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.scheduled_scn001[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduled_scenario_trigger[0].email}"
}

resource "google_cloud_scheduler_job" "scheduled_scn001" {
  count = var.enable_scheduled_scenarios ? 1 : 0

  project     = var.project_id
  region      = var.region
  name        = "opspilot-${var.environment}-scn001-30m"
  description = "Runs bounded request-scoped SCN-001 every 30 minutes."
  schedule    = "5,35 * * * *"
  time_zone   = "Asia/Seoul"
  paused      = false

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.scheduled_scn001[0].name}:run"
    body        = base64encode("{}")

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.scheduled_scenario_trigger[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_invokes_scn001,
    google_project_service.m1,
  ]
}
