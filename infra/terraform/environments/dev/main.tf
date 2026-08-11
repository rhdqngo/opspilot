locals {
  labels = {
    app                 = "opspilot"
    environment         = var.environment
    owner               = "portfolio"
    managed_by          = "terraform"
    data_classification = "synthetic"
    cost_center         = "personal-lab"
  }

  m1_project_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "discoveryengine.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "monitoring.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])

  m2_project_services = var.deploy_demo ? toset([
    "logging.googleapis.com",
    "run.googleapis.com",
  ]) : toset([])

  project_services = setunion(local.m1_project_services, local.m2_project_services)

  demo_service_names = var.deploy_demo ? toset([
    "order",
    "payment",
    "inventory",
  ]) : toset([])

  demo_leaf_service_names = var.deploy_demo ? toset([
    "payment",
    "inventory",
  ]) : toset([])
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "m1" {
  for_each = local.project_services

  project                    = var.project_id
  service                    = each.value
  disable_dependent_services = false
  disable_on_destroy         = false
}

resource "google_artifact_registry_repository" "apps" {
  project       = var.project_id
  location      = var.region
  repository_id = "opspilot-${var.environment}-apps-an3"
  description   = "OpsPilot synthetic demo container images"
  format        = "DOCKER"
  mode          = "STANDARD_REPOSITORY"
  labels        = local.labels

  depends_on = [google_project_service.m1]
}

resource "google_service_account" "investigator" {
  project      = var.project_id
  account_id   = "opspilot-${var.environment}-agent"
  display_name = "OpsPilot ${var.environment} investigator"
  description  = "Unprivileged placeholder identity; telemetry roles are deferred to M5."

  depends_on = [google_project_service.m1]
}

resource "google_service_account" "demo" {
  for_each = local.demo_service_names

  project      = var.project_id
  account_id   = "opspilot-${var.environment}-${each.key}"
  display_name = "OpsPilot ${var.environment} ${each.key} runtime"
  description  = "Unprivileged runtime identity for the synthetic ${each.key} demo service."

  depends_on = [google_project_service.m1]
}

resource "google_cloud_run_v2_service" "demo_leaf" {
  for_each = local.demo_leaf_service_names

  project              = var.project_id
  name                 = "opspilot-${var.environment}-${each.key}"
  location             = var.region
  description          = "OpsPilot synthetic ${each.key} demo service"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  labels               = local.labels

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.demo[each.key].email
    timeout                          = "10s"
    max_instance_request_concurrency = 20
    labels = merge(local.labels, {
      release_phase = "m2-mvp"
    })

    containers {
      image = var.demo_image_uri

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = false
      }

      env {
        name  = "OPSPILOT_DEMO_SERVICE"
        value = each.key
      }

      env {
        name  = "OPSPILOT_ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "OPSPILOT_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "OPSPILOT_DOWNSTREAM_AUTH"
        value = "metadata"
      }

      startup_probe {
        failure_threshold = 5
        period_seconds    = 2
        timeout_seconds   = 1

        http_get {
          path = "/readyz"
        }
      }

      liveness_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 1

        http_get {
          path = "/healthz"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", nonsensitive(var.demo_image_uri)))
      error_message = "demo_image_uri must be an immutable Artifact Registry digest."
    }
  }

  depends_on = [google_project_service.m1]
}

resource "google_cloud_run_v2_service" "demo_order" {
  count = var.deploy_demo ? 1 : 0

  project              = var.project_id
  name                 = "opspilot-${var.environment}-order"
  location             = var.region
  description          = "OpsPilot synthetic order demo service"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  labels               = local.labels

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.demo["order"].email
    timeout                          = "10s"
    max_instance_request_concurrency = 20
    labels = merge(local.labels, {
      release_phase = "m2-mvp"
    })

    containers {
      image = var.demo_image_uri

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = false
      }

      env {
        name  = "OPSPILOT_DEMO_SERVICE"
        value = "order"
      }

      env {
        name  = "OPSPILOT_ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "OPSPILOT_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "OPSPILOT_DOWNSTREAM_AUTH"
        value = "metadata"
      }

      env {
        name  = "OPSPILOT_PAYMENT_SERVICE_URL"
        value = google_cloud_run_v2_service.demo_leaf["payment"].uri
      }

      env {
        name  = "OPSPILOT_INVENTORY_SERVICE_URL"
        value = google_cloud_run_v2_service.demo_leaf["inventory"].uri
      }

      startup_probe {
        failure_threshold = 5
        period_seconds    = 2
        timeout_seconds   = 1

        http_get {
          path = "/readyz"
        }
      }

      liveness_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 1

        http_get {
          path = "/healthz"
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("@sha256:[0-9a-f]{64}$", nonsensitive(var.demo_image_uri)))
      error_message = "demo_image_uri must be an immutable Artifact Registry digest."
    }
  }

  depends_on = [google_project_service.m1]
}

resource "google_cloud_run_v2_service_iam_member" "order_invokes_leaf" {
  for_each = local.demo_leaf_service_names

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.demo_leaf[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.demo["order"].email}"
}

resource "google_monitoring_notification_channel" "budget_email" {
  project      = var.project_id
  display_name = "OpsPilot ${var.environment} budget alerts"
  type         = "email"

  labels = {
    email_address = var.budget_notification_email
  }

  user_labels = local.labels

  depends_on = [google_project_service.m1]
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "OpsPilot ${var.environment} monthly guardrail"
  deletion_policy = "PREVENT"

  # The API default is OWNERSHIP_SCOPE_UNSPECIFIED, which is equivalent to ALL_USERS.
  # Omitting it avoids perpetual drift when project-level budget access returns no explicit value.

  budget_filter {
    projects               = ["projects/${data.google_project.current.number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "KRW"
      units         = "50000"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    disable_default_iam_recipients  = false
    enable_project_level_recipients = true
    monitoring_notification_channels = [
      google_monitoring_notification_channel.budget_email.id,
    ]
  }

  depends_on = [google_project_service.m1]
}
