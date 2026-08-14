resource "google_service_account" "formal_demo" {
  for_each = local.formal_service_instances

  project      = var.project_id
  account_id   = "opspilot-${each.value.environment}-${each.value.service}"
  display_name = "OpsPilot ${each.value.environment} ${each.value.service} runtime"
  description  = "Unprivileged identity for a synthetic formal-agent workload."

  depends_on = [google_project_service.m1]
}

resource "google_cloud_run_v2_service" "formal_inventory" {
  for_each = local.formal_environments

  project              = var.project_id
  name                 = "opspilot-${each.key}-inventory"
  location             = var.region
  description          = "OpsPilot ${each.key} synthetic inventory service"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  labels               = merge(local.labels, { environment = each.key })

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.formal_demo["${each.key}-inventory"].email
    timeout                          = "10s"
    max_instance_request_concurrency = 20
    labels = merge(local.labels, {
      environment   = each.key
      release_phase = "formal-agent"
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
        cpu_idle = true
      }

      env {
        name  = "OPSPILOT_DEMO_SERVICE"
        value = "inventory"
      }
      env {
        name  = "OPSPILOT_ENVIRONMENT"
        value = each.key
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
        name  = "OPSPILOT_SCENARIOS_ENABLED"
        value = "true"
      }

      startup_probe {
        http_get { path = "/ready" }
      }
      liveness_probe {
        http_get { path = "/health" }
      }
    }
  }
}

resource "google_cloud_run_v2_service" "formal_payment" {
  for_each = local.formal_environments

  project              = var.project_id
  name                 = "opspilot-${each.key}-payment"
  location             = var.region
  description          = "OpsPilot ${each.key} synthetic payment service"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  labels               = merge(local.labels, { environment = each.key })

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.formal_demo["${each.key}-payment"].email
    timeout                          = "10s"
    max_instance_request_concurrency = 20
    labels = merge(local.labels, {
      environment   = each.key
      release_phase = "formal-agent"
    })

    containers {
      image = var.demo_image_uri
      ports { container_port = 8080 }
      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }
      env {
        name  = "OPSPILOT_DEMO_SERVICE"
        value = "payment"
      }
      env {
        name  = "OPSPILOT_ENVIRONMENT"
        value = each.key
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
        name  = "OPSPILOT_SCENARIOS_ENABLED"
        value = "true"
      }
      startup_probe {
        http_get {
          path = "/ready"
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
    ignore_changes = [traffic]
  }
}

resource "google_cloud_run_v2_service" "formal_order" {
  for_each = local.formal_environments

  project              = var.project_id
  name                 = "opspilot-${each.key}-order"
  location             = var.region
  description          = "OpsPilot ${each.key} synthetic order service"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  labels               = merge(local.labels, { environment = each.key })

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.formal_demo["${each.key}-order"].email
    timeout                          = "10s"
    max_instance_request_concurrency = 20
    labels = merge(local.labels, {
      environment   = each.key
      release_phase = "formal-agent"
    })

    containers {
      image = var.demo_image_uri
      ports { container_port = 8080 }
      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }
      env {
        name  = "OPSPILOT_DEMO_SERVICE"
        value = "order"
      }
      env {
        name  = "OPSPILOT_ENVIRONMENT"
        value = each.key
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
        name  = "OPSPILOT_SCENARIOS_ENABLED"
        value = "true"
      }
      env {
        name  = "OPSPILOT_PAYMENT_SERVICE_URL"
        value = google_cloud_run_v2_service.formal_payment[each.key].uri
      }
      env {
        name  = "OPSPILOT_INVENTORY_SERVICE_URL"
        value = google_cloud_run_v2_service.formal_inventory[each.key].uri
      }
      startup_probe {
        http_get {
          path = "/ready"
        }
      }
      liveness_probe {
        http_get {
          path = "/health"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "formal_order_invokes_payment" {
  for_each = local.formal_environments

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.formal_payment[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.formal_demo["${each.key}-order"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "formal_order_invokes_inventory" {
  for_each = local.formal_environments

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.formal_inventory[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.formal_demo["${each.key}-order"].email}"
}
