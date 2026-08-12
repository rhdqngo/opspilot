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

  m7_project_services = var.deploy_agent_runtime ? toset([
    "aiplatform.googleapis.com",
    "cloudtrace.googleapis.com",
    "telemetry.googleapis.com",
  ]) : toset([])

  m8_project_services = var.enable_remediation ? toset([
    "firestore.googleapis.com",
    "workflowexecutions.googleapis.com",
    "workflows.googleapis.com",
  ]) : toset([])

  project_services = setunion(
    local.m1_project_services,
    local.m2_project_services,
    local.m7_project_services,
    local.m8_project_services,
  )

  demo_service_names = var.deploy_demo ? toset([
    "order",
    "payment",
    "inventory",
  ]) : toset([])

  demo_leaf_service_names = var.deploy_demo ? toset([
    "inventory",
  ]) : toset([])

  runtime_class_methods = [{
    name     = "streaming_agent_run_with_events"
    api_mode = "async_stream"
    parameters = {
      type = "object"
      properties = {
        request_json = {
          type = "string"
        }
      }
      required = ["request_json"]
    }
  }]
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_storage_bucket" "knowledge" {
  count = var.deploy_knowledge ? 1 : 0

  project                     = var.project_id
  name                        = "opspilot-${var.environment}-knowledge-${data.google_project.current.number}"
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = local.labels

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
    }

    action {
      type = "Delete"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.m1]
}

resource "google_discovery_engine_data_store" "knowledge" {
  count = var.deploy_knowledge ? 1 : 0

  project                      = var.project_id
  location                     = var.search_location
  data_store_id                = "opspilot-${var.environment}-knowledge"
  display_name                 = "OpsPilot ${var.environment} synthetic knowledge"
  industry_vertical            = "GENERIC"
  content_config               = "CONTENT_REQUIRED"
  solution_types               = ["SOLUTION_TYPE_SEARCH"]
  skip_default_schema_creation = true
  deletion_policy              = "PREVENT"

  document_processing_config {
    default_parsing_config {
      digital_parsing_config {}
    }

    chunking_config {
      layout_based_chunking_config {
        chunk_size                = 300
        include_ancestor_headings = true
      }
    }
  }

  depends_on = [google_project_service.m1]
}

resource "google_discovery_engine_schema" "knowledge" {
  count = var.deploy_knowledge ? 1 : 0

  project         = var.project_id
  location        = var.search_location
  data_store_id   = google_discovery_engine_data_store.knowledge[0].data_store_id
  schema_id       = "default_schema"
  deletion_policy = "PREVENT"
  json_schema = jsonencode({
    "$schema" = "https://json-schema.org/draft/2020-12/schema"
    type      = "object"
    properties = {
      title = {
        type               = "string"
        keyPropertyMapping = "title"
        retrievable        = true
      }
      canonical_uri = {
        type               = "string"
        keyPropertyMapping = "uri"
        retrievable        = true
      }
      document_id = {
        type        = "string"
        indexable   = true
        retrievable = true
      }
      document_type = {
        type        = "string"
        indexable   = true
        retrievable = true
      }
      service = {
        type        = "string"
        indexable   = true
        retrievable = true
      }
      version = {
        type        = "string"
        retrievable = true
      }
      owner = {
        type        = "string"
        retrievable = true
      }
      updated_at = {
        type        = "string"
        retrievable = true
      }
      review_due_at = {
        type        = "string"
        retrievable = true
      }
      tags = {
        type = "array"
        items = {
          type        = "string"
          indexable   = true
          retrievable = true
        }
      }
      section = {
        type        = "string"
        retrievable = true
      }
      description = {
        type        = "string"
        retrievable = true
      }
      security_test = {
        type        = "boolean"
        indexable   = true
        retrievable = true
      }
    }
  })

  depends_on = [google_discovery_engine_data_store.knowledge]
}

resource "google_discovery_engine_search_engine" "knowledge" {
  count = var.deploy_knowledge ? 1 : 0

  project           = var.project_id
  location          = var.search_location
  collection_id     = "default_collection"
  engine_id         = "opspilot-${var.environment}-knowledge"
  display_name      = "OpsPilot ${var.environment} synthetic knowledge"
  industry_vertical = "GENERIC"
  data_store_ids    = [google_discovery_engine_data_store.knowledge[0].data_store_id]
  disable_analytics = true
  deletion_policy   = "PREVENT"

  search_engine_config {
    search_tier = "SEARCH_TIER_STANDARD"
  }

  depends_on = [google_discovery_engine_schema.knowledge]
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

resource "google_project_iam_custom_role" "investigator_reader" {
  count = var.enable_live_evidence || var.deploy_agent_runtime ? 1 : 0

  project     = var.project_id
  role_id     = "opspilotInvestigatorReader"
  title       = "OpsPilot Investigator Reader"
  description = "Bounded read-only access for M5 live evidence collection."
  stage       = "GA"

  permissions = concat([
    "discoveryengine.servingConfigs.search",
    "logging.logEntries.list",
    "monitoring.timeSeries.list",
    "resourcemanager.projects.get",
    "run.revisions.list",
    "run.services.get",
    "serviceusage.services.use",
  ], var.deploy_agent_runtime ? ["aiplatform.endpoints.predict"] : [])
}

resource "google_project_iam_member" "investigator_reader" {
  count = var.enable_live_evidence || var.deploy_agent_runtime ? 1 : 0

  project = var.project_id
  role    = google_project_iam_custom_role.investigator_reader[0].name
  member  = "serviceAccount:${google_service_account.investigator.email}"
}

resource "google_service_account_iam_member" "investigator_operator_token_creator" {
  count = var.enable_live_evidence ? 1 : 0

  service_account_id = google_service_account.investigator.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:${var.investigator_operator_email}"
}

resource "google_service_account_iam_member" "runtime_service_agent_token_creator" {
  count = var.deploy_agent_runtime ? 1 : 0

  service_account_id = google_service_account.investigator.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
}

resource "google_vertex_ai_reasoning_engine" "opspilot" {
  count = var.deploy_agent_runtime ? 1 : 0

  project         = var.project_id
  region          = var.region
  display_name    = "OpsPilot Incident Commander"
  description     = "Fixed-scope read-only payment-service incident investigation runtime."
  labels          = local.labels
  deletion_policy = "PREVENT"

  spec {
    agent_framework = "google-adk"
    class_methods   = jsonencode(local.runtime_class_methods)
    service_account = google_service_account.investigator.email

    deployment_spec {
      min_instances         = 0
      max_instances         = 1
      container_concurrency = 3
      resource_limits = {
        cpu    = "1"
        memory = "1Gi"
      }

      env {
        name  = "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"
        value = "true"
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
        value = "false"
      }

      env {
        name  = "OPSPILOT_LIVE_MODEL_ENABLED"
        value = "true"
      }
    }

    source_code_spec {
      inline_source {
        source_archive = var.agent_runtime_source_archive
      }

      python_spec {
        version           = "3.12"
        entrypoint_module = "opspilot.agent.runtime_agent"
        entrypoint_object = "root_agent"
        requirements_file = "requirements.txt"
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.enable_live_evidence
      error_message = "Agent Runtime requires the existing read-only M5 evidence role."
    }

    precondition {
      condition     = can(regex("^[0-9a-f]{64}$", var.agent_runtime_source_sha256))
      error_message = "The deterministic runtime source hash is required."
    }
  }

  depends_on = [
    google_project_service.m1,
    google_project_iam_member.investigator_reader,
    google_service_account_iam_member.runtime_service_agent_token_creator,
  ]
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

      dynamic "env" {
        for_each = var.enable_scenarios ? [1] : []
        content {
          name  = "OPSPILOT_SCENARIOS_ENABLED"
          value = "true"
        }
      }

      startup_probe {
        failure_threshold = 5
        period_seconds    = 2
        timeout_seconds   = 1

        http_get {
          path = "/ready"
        }
      }

      liveness_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 1

        http_get {
          path = "/health"
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

moved {
  from = google_cloud_run_v2_service.demo_leaf["payment"]
  to   = google_cloud_run_v2_service.demo_payment[0]
}

resource "google_cloud_run_v2_service" "demo_payment" {
  count = var.deploy_demo ? 1 : 0

  project              = var.project_id
  name                 = "opspilot-${var.environment}-payment"
  location             = var.region
  description          = "OpsPilot synthetic payment demo service"
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  deletion_protection  = false
  labels               = local.labels

  scaling {
    min_instance_count = 0
    max_instance_count = 2
  }

  template {
    service_account                  = google_service_account.demo["payment"].email
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
        value = "payment"
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

      dynamic "env" {
        for_each = var.enable_scenarios ? [1] : []
        content {
          name  = "OPSPILOT_SCENARIOS_ENABLED"
          value = "true"
        }
      }

      startup_probe {
        failure_threshold = 5
        period_seconds    = 2
        timeout_seconds   = 1

        http_get {
          path = "/ready"
        }
      }

      liveness_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 1

        http_get {
          path = "/health"
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [traffic]

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

      dynamic "env" {
        for_each = var.enable_scenarios ? [1] : []
        content {
          name  = "OPSPILOT_SCENARIOS_ENABLED"
          value = "true"
        }
      }

      env {
        name  = "OPSPILOT_PAYMENT_SERVICE_URL"
        value = google_cloud_run_v2_service.demo_payment[0].uri
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
          path = "/ready"
        }
      }

      liveness_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 1

        http_get {
          path = "/health"
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

moved {
  from = google_cloud_run_v2_service_iam_member.order_invokes_leaf["payment"]
  to   = google_cloud_run_v2_service_iam_member.order_invokes_payment[0]
}

resource "google_cloud_run_v2_service_iam_member" "order_invokes_payment" {
  count = var.deploy_demo ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.demo_payment[0].name
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
