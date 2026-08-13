locals {
  investigation_api_audience = "opspilot-investigation-api"
  investigation_queue_id     = "opspilot-${var.environment}-investigations"
  investigation_api_url      = "https://opspilot-${var.environment}-investigation-api-${data.google_project.current.number}.${var.region}.run.app"
}

resource "google_project_service_identity" "cloud_tasks" {
  provider = google-beta
  count    = var.enable_persistent_investigations ? 1 : 0

  project = var.project_id
  service = "cloudtasks.googleapis.com"

  depends_on = [google_project_service.m1]
}

resource "google_project_service_identity" "pubsub" {
  provider = google-beta
  count    = var.enable_persistent_investigations ? 1 : 0

  project = var.project_id
  service = "pubsub.googleapis.com"

  depends_on = [google_project_service.m1]
}

resource "google_service_account" "investigation_api" {
  count = var.enable_persistent_investigations ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-inv-api"
  display_name = "OpsPilot ${var.environment} investigation API"
  description  = "Owns bounded operational reads, Cloud Tasks enqueue, and Firestore investigation writes."
}

resource "google_service_account" "investigation_tasks" {
  count = var.enable_persistent_investigations ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-inv-tasks"
  display_name = "OpsPilot ${var.environment} investigation task dispatcher"
  description  = "May invoke only the investigation API worker endpoint."
}

resource "google_service_account" "investigation_alerts" {
  count = var.enable_persistent_investigations ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-inv-alerts"
  display_name = "OpsPilot ${var.environment} monitoring alert dispatcher"
  description  = "May invoke only the internal Monitoring Pub/Sub intake endpoint."
}

resource "google_project_iam_custom_role" "investigation_store" {
  count = var.enable_persistent_investigations ? 1 : 0

  project     = var.project_id
  role_id     = "opspilotInvestigationStore"
  title       = "OpsPilot Investigation Store"
  description = "Minimum Firestore and task enqueue permissions for persistent investigations."
  stage       = "GA"
  permissions = [
    "cloudtasks.tasks.create",
    "datastore.databases.get",
    "datastore.entities.create",
    "datastore.entities.get",
    "datastore.entities.list",
    "datastore.entities.update",
  ]
}

resource "google_project_iam_member" "investigation_api_reader" {
  count = var.enable_persistent_investigations ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.investigator_reader[0].name
  member  = "serviceAccount:${google_service_account.investigation_api[0].email}"
}

resource "google_project_iam_member" "investigation_api_store" {
  count = var.enable_persistent_investigations ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.investigation_store[0].name
  member  = "serviceAccount:${google_service_account.investigation_api[0].email}"
}

resource "google_cloud_tasks_queue" "investigations" {
  count = var.enable_persistent_investigations ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = local.investigation_queue_id

  rate_limits {
    max_concurrent_dispatches = 3
    max_dispatches_per_second = 2
  }

  retry_config {
    max_attempts       = 5
    max_retry_duration = "900s"
    min_backoff        = "2s"
    max_backoff        = "60s"
    max_doublings      = 5
  }

  depends_on = [google_project_service.m1]
}

resource "google_service_account_iam_member" "cloud_tasks_mints_dispatch_token" {
  count = var.enable_persistent_investigations ? 1 : 0

  service_account_id = google_service_account.investigation_tasks[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_project_service_identity.cloud_tasks[0].email}"
}

resource "google_service_account_iam_member" "investigation_api_acts_as_tasks" {
  count = var.enable_persistent_investigations ? 1 : 0

  service_account_id = google_service_account.investigation_tasks[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.investigation_api[0].email}"
}

resource "google_service_account_iam_member" "pubsub_mints_alert_token" {
  count = var.enable_persistent_investigations ? 1 : 0

  service_account_id = google_service_account.investigation_alerts[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_project_service_identity.pubsub[0].email}"
}

resource "google_cloud_run_v2_service" "investigation_api" {
  count = var.enable_persistent_investigations ? 1 : 0

  project              = var.project_id
  name                 = "opspilot-${var.environment}-investigation-api"
  location             = var.region
  description          = "Authenticated persistent investigation API and Cloud Tasks worker"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  custom_audiences     = [local.investigation_api_audience]
  deletion_protection  = false
  labels               = local.labels

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.investigation_api[0].email
    timeout                          = "120s"
    max_instance_request_concurrency = 8

    containers {
      image = var.investigation_image_uri
      args  = ["serve"]

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      dynamic "env" {
        for_each = {
          OPSPILOT_INVESTIGATION_PROJECT_ID              = var.project_id
          OPSPILOT_INVESTIGATION_REGION                  = var.region
          OPSPILOT_INVESTIGATION_DATABASE_ID             = google_firestore_database.remediation[0].name
          OPSPILOT_INVESTIGATION_TASK_QUEUE              = google_cloud_tasks_queue.investigations[0].id
          OPSPILOT_INVESTIGATION_WORKER_URL              = local.investigation_api_url
          OPSPILOT_INVESTIGATION_TASK_SERVICE_ACCOUNT    = google_service_account.investigation_tasks[0].email
          OPSPILOT_INVESTIGATION_WORKER_AUDIENCE         = local.investigation_api_audience
          OPSPILOT_INVESTIGATION_AUDIENCE                = local.investigation_api_audience
          OPSPILOT_INVESTIGATION_RUNTIME_SERVICE_ACCOUNT = google_service_account.investigator.email
          OPSPILOT_INVESTIGATION_ALERT_SERVICE_ACCOUNT   = google_service_account.investigation_alerts[0].email
        }
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", nonsensitive(var.investigation_image_uri)))
      error_message = "investigation_image_uri must be immutable."
    }
  }

  depends_on = [
    google_firestore_database.remediation,
    google_project_iam_member.investigation_api_reader,
    google_project_iam_member.investigation_api_store,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "runtime_invokes_investigation_api" {
  count = var.enable_persistent_investigations ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.investigation_api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.investigator.email}"
}

resource "google_cloud_run_v2_service_iam_member" "tasks_invoke_investigation_api" {
  count = var.enable_persistent_investigations ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.investigation_api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.investigation_tasks[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "alerts_invoke_investigation_api" {
  count = var.enable_persistent_investigations ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.investigation_api[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.investigation_alerts[0].email}"
}

resource "google_pubsub_topic" "monitoring_incidents" {
  count = var.enable_persistent_investigations ? 1 : 0

  project = var.project_id
  name    = "opspilot-${var.environment}-monitoring-incidents"
  labels  = local.labels

  message_retention_duration = "86400s"
  depends_on                 = [google_project_service.m1]
}

resource "google_pubsub_subscription" "monitoring_incidents" {
  count = var.enable_persistent_investigations ? 1 : 0

  project = var.project_id
  name    = "opspilot-${var.environment}-monitoring-incidents-push"
  topic   = google_pubsub_topic.monitoring_incidents[0].id

  ack_deadline_seconds       = 30
  message_retention_duration = "86400s"
  retain_acked_messages      = false
  expiration_policy {
    ttl = "2678400s"
  }
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }
  push_config {
    push_endpoint = "${local.investigation_api_url}/internal/v1/alerts/monitoring"
    oidc_token {
      service_account_email = google_service_account.investigation_alerts[0].email
      audience              = local.investigation_api_audience
    }
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.alerts_invoke_investigation_api,
    google_service_account_iam_member.pubsub_mints_alert_token,
  ]
}
