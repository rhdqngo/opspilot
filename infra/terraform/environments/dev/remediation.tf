locals {
  remediation_control_audience  = "opspilot-remediation-control"
  remediation_executor_audience = "opspilot-remediation-executor"
  remediation_workflow_id       = "opspilot-${var.environment}-remediation"
  remediation_workflow_name     = "projects/${var.project_id}/locations/${var.region}/workflows/${local.remediation_workflow_id}"
}

resource "google_firestore_database" "remediation" {
  count = var.enable_remediation || var.enable_persistent_investigations ? 1 : 0

  project                           = var.project_id
  name                              = "opspilot-dev"
  location_id                       = var.region
  type                              = "FIRESTORE_NATIVE"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = "ABANDON"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"

  depends_on = [google_project_service.m1]
}

resource "google_firestore_field" "remediation_ttl" {
  for_each = var.enable_remediation ? toset([
    "idempotency_keys",
    "remediation_callbacks",
  ]) : toset([])

  project    = var.project_id
  database   = google_firestore_database.remediation[0].name
  collection = each.key
  field      = "expires_at"

  ttl_config {}
  index_config {}
}

resource "google_service_account" "remediation_control" {
  count = var.enable_remediation ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-rem-control"
  display_name = "OpsPilot ${var.environment} remediation control"
  description  = "Authenticated approval and orchestration identity; never used by Agent Runtime."
}

resource "google_service_account" "remediation_workflow" {
  count = var.enable_remediation ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-rem-workflow"
  display_name = "OpsPilot ${var.environment} remediation workflow"
  description  = "Single-purpose callback and private executor orchestration identity."
}

resource "google_service_account" "remediation_executor" {
  count = var.enable_remediation ? 1 : 0

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-rem-executor"
  display_name = "OpsPilot ${var.environment} remediation executor"
  description  = "Single-purpose payment traffic update identity."
}

resource "google_project_iam_custom_role" "remediation_control" {
  count = var.enable_remediation ? 1 : 0

  project     = var.project_id
  role_id     = "opspilot_${replace(var.environment, "-", "_")}_remediation_control"
  title       = "OpsPilot ${var.environment} remediation control"
  description = "Transactions, approval workflow execution, and callback delivery only."
  permissions = [
    "datastore.databases.get",
    "datastore.entities.create",
    "datastore.entities.get",
    "datastore.entities.list",
    "datastore.entities.update",
    "logging.logEntries.list",
    "monitoring.timeSeries.list",
    "run.revisions.get",
    "run.revisions.list",
    "run.services.get",
    "serviceusage.services.use",
    "workflows.callbacks.send",
    "workflows.executions.create",
  ]
}

resource "google_project_iam_member" "remediation_control" {
  count = var.enable_remediation ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.remediation_control[0].name
  member  = "serviceAccount:${google_service_account.remediation_control[0].email}"
}

resource "google_project_iam_custom_role" "remediation_executor_cloud_run" {
  count = var.enable_remediation ? 1 : 0

  project     = var.project_id
  role_id     = "opspilot_${replace(var.environment, "-", "_")}_payment_traffic_executor"
  title       = "OpsPilot ${var.environment} payment traffic executor"
  description = "Read revisions and update only Cloud Run service traffic."
  permissions = [
    "run.operations.get",
    "run.revisions.get",
    "run.services.get",
    "run.services.update",
  ]
}

resource "google_cloud_run_v2_service_iam_member" "remediation_executor_payment" {
  count = var.enable_remediation ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.demo_payment[0].name
  role     = google_project_iam_custom_role.remediation_executor_cloud_run[0].name
  member   = "serviceAccount:${google_service_account.remediation_executor[0].email}"
}

resource "google_project_iam_custom_role" "remediation_executor_image_reader" {
  count = var.enable_remediation ? 1 : 0

  project     = var.project_id
  role_id     = "opspilot_${replace(var.environment, "-", "_")}_image_reader"
  title       = "OpsPilot ${var.environment} remediation image reader"
  description = "Read immutable image artifacts while replacing payment traffic only."
  permissions = ["artifactregistry.repositories.downloadArtifacts"]
}

resource "google_project_iam_member" "remediation_executor_image_reader" {
  count = var.enable_remediation ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.remediation_executor_image_reader[0].name
  member  = "serviceAccount:${google_service_account.remediation_executor[0].email}"
}

resource "google_service_account_iam_member" "remediation_executor_acts_as_payment" {
  count = var.enable_remediation ? 1 : 0

  service_account_id = google_service_account.demo["payment"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.remediation_executor[0].email}"
}

resource "google_project_iam_member" "remediation_executor_firestore_reader" {
  count = var.enable_remediation ? 1 : 0

  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.remediation_executor[0].email}"
}

resource "google_cloud_run_v2_service" "remediation_control" {
  count = var.enable_remediation ? 1 : 0

  project              = var.project_id
  name                 = "opspilot-${var.environment}-remediation-control"
  location             = var.region
  description          = "Approval-gated OpsPilot remediation control API"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  custom_audiences     = [local.remediation_control_audience]
  labels               = merge(local.labels, { release_phase = "m8-remediation" })

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.remediation_control[0].email
    timeout                          = "30s"
    max_instance_request_concurrency = 20

    containers {
      image = var.remediation_image_uri
      args  = ["remediation", "serve-control"]

      ports { container_port = 8080 }

      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = {
          OPSPILOT_REMEDIATION_PROJECT_ID               = var.project_id
          OPSPILOT_REMEDIATION_DATABASE_ID              = "opspilot-dev"
          OPSPILOT_REMEDIATION_CONTROL_AUDIENCE         = local.remediation_control_audience
          OPSPILOT_REMEDIATION_EXECUTOR_AUDIENCE        = local.remediation_executor_audience
          OPSPILOT_REMEDIATION_WORKFLOW_NAME            = local.remediation_workflow_name
          OPSPILOT_REMEDIATION_WORKFLOW_SERVICE_ACCOUNT = google_service_account.remediation_workflow[0].email
          OPSPILOT_REMEDIATION_ORDER_URL                = google_cloud_run_v2_service.demo_order[0].uri
        }
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
      }
      liveness_probe {
        http_get {
          path = "/health"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", nonsensitive(var.remediation_image_uri)))
      error_message = "remediation_image_uri must be immutable."
    }
  }
}

resource "google_cloud_run_v2_service" "remediation_executor" {
  count = var.enable_remediation ? 1 : 0

  project              = var.project_id
  name                 = "opspilot-${var.environment}-remediation-executor"
  location             = var.region
  description          = "Internal-only fixed payment traffic rollback executor"
  ingress              = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  invoker_iam_disabled = false
  deletion_protection  = false
  custom_audiences     = [local.remediation_executor_audience]
  labels               = merge(local.labels, { release_phase = "m8-remediation" })

  scaling {
    min_instance_count = 0
    max_instance_count = 1
  }

  template {
    service_account                  = google_service_account.remediation_executor[0].email
    timeout                          = "300s"
    max_instance_request_concurrency = 1

    containers {
      image = var.remediation_image_uri
      args  = ["remediation", "serve-executor"]

      ports { container_port = 8080 }

      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = {
          OPSPILOT_REMEDIATION_PROJECT_ID               = var.project_id
          OPSPILOT_REMEDIATION_DATABASE_ID              = "opspilot-dev"
          OPSPILOT_REMEDIATION_CONTROL_AUDIENCE         = local.remediation_control_audience
          OPSPILOT_REMEDIATION_EXECUTOR_AUDIENCE        = local.remediation_executor_audience
          OPSPILOT_REMEDIATION_WORKFLOW_NAME            = local.remediation_workflow_name
          OPSPILOT_REMEDIATION_WORKFLOW_SERVICE_ACCOUNT = google_service_account.remediation_workflow[0].email
          OPSPILOT_REMEDIATION_ORDER_URL                = google_cloud_run_v2_service.demo_order[0].uri
        }
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
      }
      liveness_probe {
        http_get {
          path = "/health"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", nonsensitive(var.remediation_image_uri)))
      error_message = "remediation_image_uri must be immutable."
    }
  }
}

resource "google_project_service_identity" "workflows" {
  provider = google-beta
  count    = var.enable_remediation ? 1 : 0

  project = var.project_id
  service = "workflows.googleapis.com"

  depends_on = [google_project_service.m1]
}

resource "google_workflows_workflow" "remediation" {
  count = var.enable_remediation ? 1 : 0

  project         = var.project_id
  name            = local.remediation_workflow_id
  region          = var.region
  description     = "15-minute approval callback and single private rollback execution"
  service_account = google_service_account.remediation_workflow[0].id
  labels          = local.labels
  source_contents = templatefile("${path.module}/../../../workflows/remediation.yaml.tftpl", {
    control_url       = google_cloud_run_v2_service.remediation_control[0].uri
    control_audience  = local.remediation_control_audience
    executor_url      = google_cloud_run_v2_service.remediation_executor[0].uri
    executor_audience = local.remediation_executor_audience
  })

  depends_on = [google_project_service_identity.workflows]
}

resource "google_cloud_run_v2_service_iam_member" "remediation_group_invoker" {
  count = var.enable_remediation ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.remediation_control[0].name
  role     = "roles/run.invoker"
  member   = "group:${var.remediation_approver_group}"
}

resource "google_cloud_run_v2_service_iam_member" "workflow_invokes_control" {
  count = var.enable_remediation ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.remediation_control[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.remediation_workflow[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "workflow_invokes_executor" {
  count = var.enable_remediation ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.remediation_executor[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.remediation_workflow[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "control_invokes_order" {
  count = var.enable_remediation ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.demo_order[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.remediation_control[0].email}"
}
