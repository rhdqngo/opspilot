mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "123456789012"
    }
  }
}

run "secure_bootstrap_plan" {
  command = plan

  variables {
    project_id           = "example-project"
    github_owner_id      = "10001"
    github_repository_id = "20002"
  }

  assert {
    condition     = google_storage_bucket.terraform_state.force_destroy == false
    error_message = "The Terraform state bucket must not allow force deletion."
  }

  assert {
    condition = (
      contains(google_project_iam_custom_role.ci_plan_reader.permissions, "iam.roles.get") &&
      contains(google_project_iam_custom_role.ci_plan_reader.permissions, "resourcemanager.projects.getIamPolicy")
    )
    error_message = "Hosted M5 plans may read only the custom role and project IAM policy."
  }

  assert {
    condition     = google_storage_bucket.terraform_state.public_access_prevention == "enforced"
    error_message = "The Terraform state bucket must enforce public access prevention."
  }

  assert {
    condition     = google_storage_bucket.terraform_state.uniform_bucket_level_access
    error_message = "The Terraform state bucket must use uniform bucket-level access."
  }

  assert {
    condition     = google_storage_bucket.terraform_state.versioning[0].enabled
    error_message = "The Terraform state bucket must keep object versioning enabled."
  }

  assert {
    condition     = one(google_storage_bucket.terraform_state.lifecycle_rule[0].condition).days_since_noncurrent_time == 30
    error_message = "Noncurrent Terraform state versions must expire after 30 days."
  }

  assert {
    condition = alltrue([
      for permission in google_project_iam_custom_role.ci_plan_reader.permissions :
      permission == "serviceusage.services.use" || endswith(permission, ".get") || endswith(permission, ".getIamPolicy") || endswith(permission, ".list") || endswith(permission, ".read")
    ])
    error_message = "The CI plan custom role must contain reads plus service usage consumption only."
  }

  assert {
    condition = !contains(
      google_project_iam_custom_role.ci_plan_reader.permissions,
      "serviceusage.services.enable",
      ) && !contains(
      google_project_iam_custom_role.ci_plan_reader.permissions,
      "serviceusage.services.disable",
    )
    error_message = "The CI plan custom role must not enable or disable APIs."
  }

  assert {
    condition = strcontains(
      google_iam_workload_identity_pool_provider.github.attribute_condition,
      "repository_id"
      ) && strcontains(
      google_iam_workload_identity_pool_provider.github.attribute_condition,
      "repository_owner_id"
    )
    error_message = "GitHub WIF admission must use immutable numeric repository attributes."
  }
}
