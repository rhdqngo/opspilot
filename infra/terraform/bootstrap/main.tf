locals {
  labels = {
    app                 = "opspilot"
    environment         = var.environment
    owner               = "portfolio"
    managed_by          = "terraform"
    data_classification = "synthetic"
    cost_center         = "personal-lab"
  }

  bootstrap_services = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "bootstrap" {
  for_each = local.bootstrap_services

  project                    = var.project_id
  service                    = each.value
  disable_dependent_services = false
  disable_on_destroy         = false
}

resource "google_storage_bucket" "terraform_state" {
  name     = "opspilot-${var.environment}-tfstate-${data.google_project.current.number}"
  project  = var.project_id
  location = var.region
  labels   = local.labels

  force_destroy               = false
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      days_since_noncurrent_time = 30
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.bootstrap]
}

resource "google_service_account" "ci_plan" {
  project      = var.project_id
  account_id   = "opspilot-${var.environment}-ci-plan"
  display_name = "OpsPilot ${var.environment} Terraform plan"
  description  = "Read-only Terraform plan identity federated from one GitHub repository."

  depends_on = [google_project_service.bootstrap]
}

resource "google_project_iam_custom_role" "ci_plan_reader" {
  project     = var.project_id
  role_id     = "opspilotTerraformPlanReader"
  title       = "OpsPilot Terraform Plan Reader"
  description = "Read-only permissions required to refresh the M1 Terraform plan."
  stage       = "GA"

  permissions = [
    "artifactregistry.repositories.get",
    "artifactregistry.repositories.list",
    "billing.resourcebudgets.read",
    "cloudtasks.queues.get",
    "cloudtasks.queues.list",
    "datastore.databases.get",
    "datastore.indexes.get",
    "datastore.indexes.list",
    "discoveryengine.dataStores.get",
    "discoveryengine.dataStores.list",
    "discoveryengine.engines.get",
    "discoveryengine.engines.list",
    "discoveryengine.schemas.get",
    "discoveryengine.schemas.list",
    "iam.serviceAccounts.get",
    "iam.serviceAccounts.getIamPolicy",
    "iam.serviceAccounts.list",
    "iam.roles.get",
    "monitoring.notificationChannels.get",
    "monitoring.notificationChannels.list",
    "pubsub.subscriptions.get",
    "pubsub.subscriptions.getIamPolicy",
    "pubsub.subscriptions.list",
    "pubsub.topics.get",
    "pubsub.topics.getIamPolicy",
    "pubsub.topics.list",
    "resourcemanager.projects.get",
    "resourcemanager.projects.getIamPolicy",
    "run.services.get",
    "run.services.getIamPolicy",
    "run.services.list",
    "serviceusage.services.get",
    "serviceusage.services.list",
    "serviceusage.services.use",
    "storage.buckets.get",
    "workflows.workflows.get",
    "workflows.workflows.getIamPolicy",
    "workflows.workflows.list",
  ]
}

resource "google_project_iam_member" "ci_plan_reader" {
  project = var.project_id
  role    = google_project_iam_custom_role.ci_plan_reader.name
  member  = "serviceAccount:${google_service_account.ci_plan.email}"
}

resource "google_storage_bucket_iam_member" "ci_plan_state_reader" {
  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.ci_plan.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "opspilot-github"
  display_name              = "OpsPilot GitHub"
  description               = "OIDC identities admitted from the immutable OpsPilot repository ID."
  disabled                  = false

  depends_on = [google_project_service.bootstrap]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "opspilot-repository"
  display_name                       = "OpsPilot repository"
  description                        = "GitHub OIDC provider restricted by numeric owner and repository IDs."

  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
  }

  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.repository_owner_id == '${var.github_owner_id}'",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_plan_impersonation" {
  service_account_id = google_service_account.ci_plan.name
  role               = "roles/iam.workloadIdentityUser"
  member = format(
    "principalSet://iam.googleapis.com/%s/attribute.repository_id/%s",
    google_iam_workload_identity_pool.github.name,
    var.github_repository_id,
  )
}
