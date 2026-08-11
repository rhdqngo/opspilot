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
    condition = (
      length(google_project_service.m1) == 10 &&
      length(google_service_account.demo) == 0 &&
      length(google_cloud_run_v2_service.demo_leaf) == 0 &&
      length(google_cloud_run_v2_service.demo_order) == 0 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 0 &&
      length(google_storage_bucket.knowledge) == 0 &&
      length(google_discovery_engine_data_store.knowledge) == 0 &&
      length(google_discovery_engine_schema.knowledge) == 0 &&
      length(google_discovery_engine_search_engine.knowledge) == 0
    )
    error_message = "The default M2 gate must preserve the M1-only resource graph."
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

run "m2_deploy_ready_contract" {
  command = plan

  variables {
    project_id                = "example-project"
    billing_account_id        = "000000-000000-000000"
    budget_notification_email = "operator@example.invalid"
    deploy_demo               = true
    demo_image_uri            = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  assert {
    condition     = length(google_project_service.m1) == 12
    error_message = "M2 must add only Logging and Cloud Run to the ten M1 managed APIs."
  }

  assert {
    condition     = length(google_service_account.demo) == 3
    error_message = "M2 must define exactly three isolated runtime identities."
  }

  assert {
    condition     = length(google_cloud_run_v2_service.demo_leaf) == 2 && length(google_cloud_run_v2_service.demo_order) == 1
    error_message = "M2 must define exactly three Cloud Run services."
  }

  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 2
    error_message = "Only the two order-to-leaf invoker grants are allowed."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.scaling[0].min_instance_count == 0 && service.scaling[0].max_instance_count == 2],
      [google_cloud_run_v2_service.demo_order[0].scaling[0].min_instance_count == 0 && google_cloud_run_v2_service.demo_order[0].scaling[0].max_instance_count == 2],
    ))
    error_message = "All M2 services must scale from zero and cap at two instances."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.template[0].containers[0].image == var.demo_image_uri],
      [google_cloud_run_v2_service.demo_order[0].template[0].containers[0].image == var.demo_image_uri],
    ))
    error_message = "All M2 services must share the reviewed immutable image digest."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.template[0].containers[0].startup_probe[0].http_get[0].path == "/ready" && service.template[0].containers[0].liveness_probe[0].http_get[0].path == "/health"],
      [google_cloud_run_v2_service.demo_order[0].template[0].containers[0].startup_probe[0].http_get[0].path == "/ready" && google_cloud_run_v2_service.demo_order[0].template[0].containers[0].liveness_probe[0].http_get[0].path == "/health"],
    ))
    error_message = "Cloud Run probes must avoid reserved paths ending in z."
  }

  assert {
    condition = alltrue([
      for binding in google_cloud_run_v2_service_iam_member.order_invokes_leaf :
      binding.role == "roles/run.invoker" && startswith(binding.member, "serviceAccount:")
    ])
    error_message = "M2 must grant only authenticated order-to-leaf invocation."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.labels["data_classification"] == "synthetic"],
      [google_cloud_run_v2_service.demo_order[0].labels["data_classification"] == "synthetic"],
    ))
    error_message = "All M2 services must retain the synthetic-data label."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.ingress == "INGRESS_TRAFFIC_ALL" && service.invoker_iam_disabled == false],
      [google_cloud_run_v2_service.demo_order[0].ingress == "INGRESS_TRAFFIC_ALL" && google_cloud_run_v2_service.demo_order[0].invoker_iam_disabled == false],
    ))
    error_message = "The MVP endpoint must remain reachable through Cloud Run ingress with IAM enforced."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.template[0].labels["release_phase"] == "m2-mvp"],
      [google_cloud_run_v2_service.demo_order[0].template[0].labels["release_phase"] == "m2-mvp"],
    ))
    error_message = "The controlled MVP refresh marker must create only new service revisions."
  }
}

run "m3_scenario_gate_contract" {
  command = plan

  variables {
    project_id                = "example-project"
    billing_account_id        = "000000-000000-000000"
    budget_notification_email = "operator@example.invalid"
    deploy_demo               = true
    enable_scenarios          = true
    demo_image_uri            = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : contains([for item in service.template[0].containers[0].env : "${item.name}=${item.value}"], "OPSPILOT_SCENARIOS_ENABLED=true")],
      [contains([for item in google_cloud_run_v2_service.demo_order[0].template[0].containers[0].env : "${item.name}=${item.value}"], "OPSPILOT_SCENARIOS_ENABLED=true")],
    ))
    error_message = "M3 scenario behavior must remain behind the explicit environment gate."
  }

  assert {
    condition = (
      length(google_project_service.m1) == 12 &&
      length(google_service_account.demo) == 3 &&
      length(google_cloud_run_v2_service.demo_leaf) == 2 &&
      length(google_cloud_run_v2_service.demo_order) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 2
    )
    error_message = "M3 Approval 1 must not add cloud resources or IAM bindings."
  }
}

run "m4_knowledge_apply_ready_contract" {
  command = plan

  variables {
    project_id                = "example-project"
    billing_account_id        = "000000-000000-000000"
    budget_notification_email = "operator@example.invalid"
    deploy_demo               = true
    enable_scenarios          = true
    deploy_knowledge          = true
    search_location           = "global"
    demo_image_uri            = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  assert {
    condition = (
      length(google_storage_bucket.knowledge) == 1 &&
      length(google_discovery_engine_data_store.knowledge) == 1 &&
      length(google_discovery_engine_schema.knowledge) == 1 &&
      length(google_discovery_engine_search_engine.knowledge) == 1
    )
    error_message = "The M4 gate must add exactly the bucket, data store, schema, and search engine."
  }

  assert {
    condition = (
      google_storage_bucket.knowledge[0].force_destroy == false &&
      google_storage_bucket.knowledge[0].uniform_bucket_level_access == true &&
      google_storage_bucket.knowledge[0].public_access_prevention == "enforced" &&
      google_storage_bucket.knowledge[0].versioning[0].enabled == true
    )
    error_message = "The M4 knowledge bucket must remain private, versioned, and protected."
  }

  assert {
    condition = (
      google_discovery_engine_data_store.knowledge[0].location == "global" &&
      google_discovery_engine_data_store.knowledge[0].content_config == "CONTENT_REQUIRED" &&
      google_discovery_engine_data_store.knowledge[0].deletion_policy == "PREVENT" &&
      google_discovery_engine_data_store.knowledge[0].document_processing_config[0].chunking_config[0].layout_based_chunking_config[0].chunk_size == 300
    )
    error_message = "M4 must use the bounded global unstructured knowledge data store."
  }

  assert {
    condition = (
      google_discovery_engine_search_engine.knowledge[0].search_engine_config[0].search_tier == "SEARCH_TIER_STANDARD" &&
      google_discovery_engine_search_engine.knowledge[0].disable_analytics == true
    )
    error_message = "M4 must use Standard Search without analytics or LLM add-ons."
  }

  assert {
    condition = (
      jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.tags.type == "array" &&
      jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.tags.items.type == "string" &&
      jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.tags.items.indexable == true &&
      jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.tags.items.retrievable == true &&
      !can(jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.tags.indexable) &&
      !can(jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.tags.retrievable)
    )
    error_message = "Array metadata annotations must be attached to the scalar item schema."
  }

  assert {
    condition = (
      length(google_project_service.m1) == 12 &&
      length(google_service_account.demo) == 3 &&
      length(google_cloud_run_v2_service.demo_leaf) == 2 &&
      length(google_cloud_run_v2_service.demo_order) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 2
    )
    error_message = "M4 must not change the existing API, runtime identity, Cloud Run, or IAM graph."
  }
}
