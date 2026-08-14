mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "123456789012"
    }
  }
}

mock_provider "google-beta" {}

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
      length(google_cloud_run_v2_service.demo_payment) == 0 &&
      length(google_cloud_run_v2_service.demo_order) == 0 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 0 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_payment) == 0 &&
      length(google_storage_bucket.knowledge) == 0 &&
      length(google_discovery_engine_data_store.knowledge) == 0 &&
      length(google_discovery_engine_schema.knowledge) == 0 &&
      length(google_discovery_engine_search_engine.knowledge) == 0 &&
      length(google_project_iam_custom_role.investigator_reader) == 0 &&
      length(google_project_iam_member.investigator_reader) == 0 &&
      length(google_project_iam_custom_role.runtime_project_metadata) == 0 &&
      length(google_project_iam_member.runtime_project_metadata) == 0 &&
      length(google_service_account_iam_member.investigator_operator_token_creator) == 0 &&
      length(google_service_account_iam_member.runtime_service_agent_token_creator) == 0 &&
      length(google_vertex_ai_reasoning_engine.opspilot) == 0 &&
      length(google_firestore_database.remediation) == 0 &&
      length(google_firestore_field.remediation_ttl) == 0 &&
      length(google_service_account.remediation_control) == 0 &&
      length(google_service_account.remediation_workflow) == 0 &&
      length(google_service_account.remediation_executor) == 0 &&
      length(google_cloud_run_v2_service.remediation_control) == 0 &&
      length(google_cloud_run_v2_service.remediation_executor) == 0 &&
      length(google_project_service_identity.workflows) == 0 &&
      length(google_workflows_workflow.remediation) == 0
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
    condition     = length(google_cloud_run_v2_service.demo_leaf) == 1 && length(google_cloud_run_v2_service.demo_payment) == 1 && length(google_cloud_run_v2_service.demo_order) == 1
    error_message = "M2 must define exactly three Cloud Run services."
  }

  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 1 && length(google_cloud_run_v2_service_iam_member.order_invokes_payment) == 1
    error_message = "Only the two order-to-leaf invoker grants are allowed."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.scaling[0].min_instance_count == 0 && service.scaling[0].max_instance_count == 2],
      [google_cloud_run_v2_service.demo_payment[0].scaling[0].min_instance_count == 0 && google_cloud_run_v2_service.demo_payment[0].scaling[0].max_instance_count == 2],
      [google_cloud_run_v2_service.demo_order[0].scaling[0].min_instance_count == 0 && google_cloud_run_v2_service.demo_order[0].scaling[0].max_instance_count == 2],
    ))
    error_message = "All M2 services must scale from zero and cap at two instances."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.template[0].containers[0].image == var.demo_image_uri],
      [google_cloud_run_v2_service.demo_payment[0].template[0].containers[0].image == var.demo_image_uri],
      [google_cloud_run_v2_service.demo_order[0].template[0].containers[0].image == var.demo_image_uri],
    ))
    error_message = "All M2 services must share the reviewed immutable image digest."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.template[0].containers[0].startup_probe[0].http_get[0].path == "/ready" && service.template[0].containers[0].liveness_probe[0].http_get[0].path == "/health"],
      [google_cloud_run_v2_service.demo_payment[0].template[0].containers[0].startup_probe[0].http_get[0].path == "/ready" && google_cloud_run_v2_service.demo_payment[0].template[0].containers[0].liveness_probe[0].http_get[0].path == "/health"],
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
      [google_cloud_run_v2_service.demo_payment[0].labels["data_classification"] == "synthetic"],
      [google_cloud_run_v2_service.demo_order[0].labels["data_classification"] == "synthetic"],
    ))
    error_message = "All M2 services must retain the synthetic-data label."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.ingress == "INGRESS_TRAFFIC_ALL" && service.invoker_iam_disabled == false],
      [google_cloud_run_v2_service.demo_payment[0].ingress == "INGRESS_TRAFFIC_ALL" && google_cloud_run_v2_service.demo_payment[0].invoker_iam_disabled == false],
      [google_cloud_run_v2_service.demo_order[0].ingress == "INGRESS_TRAFFIC_ALL" && google_cloud_run_v2_service.demo_order[0].invoker_iam_disabled == false],
    ))
    error_message = "The MVP endpoint must remain reachable through Cloud Run ingress with IAM enforced."
  }

  assert {
    condition = alltrue(concat(
      [for service in google_cloud_run_v2_service.demo_leaf : service.template[0].labels["release_phase"] == "m2-mvp"],
      [google_cloud_run_v2_service.demo_payment[0].template[0].labels["release_phase"] == "m2-mvp"],
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
      [contains([for item in google_cloud_run_v2_service.demo_payment[0].template[0].containers[0].env : "${item.name}=${item.value}"], "OPSPILOT_SCENARIOS_ENABLED=true")],
      [contains([for item in google_cloud_run_v2_service.demo_order[0].template[0].containers[0].env : "${item.name}=${item.value}"], "OPSPILOT_SCENARIOS_ENABLED=true")],
    ))
    error_message = "M3 scenario behavior must remain behind the explicit environment gate."
  }

  assert {
    condition = (
      length(google_project_service.m1) == 12 &&
      length(google_service_account.demo) == 3 &&
      length(google_cloud_run_v2_service.demo_leaf) == 1 &&
      length(google_cloud_run_v2_service.demo_payment) == 1 &&
      length(google_cloud_run_v2_service.demo_order) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_payment) == 1
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
      jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.title.keyPropertyMapping == "title" &&
      jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.title.retrievable == true &&
      !can(jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.title.searchable) &&
      !can(jsondecode(google_discovery_engine_schema.knowledge[0].json_schema).properties.title.indexable)
    )
    error_message = "The title key property must not carry searchable or indexable annotations."
  }

  assert {
    condition = (
      length(google_project_service.m1) == 12 &&
      length(google_service_account.demo) == 3 &&
      length(google_cloud_run_v2_service.demo_leaf) == 1 &&
      length(google_cloud_run_v2_service.demo_payment) == 1 &&
      length(google_cloud_run_v2_service.demo_order) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_payment) == 1
    )
    error_message = "M4 must not change the existing API, runtime identity, Cloud Run, or IAM graph."
  }
}

run "m5_live_evidence_apply_ready_contract" {
  command = plan

  variables {
    project_id                  = "example-project"
    billing_account_id          = "000000-000000-000000"
    budget_notification_email   = "operator@example.invalid"
    deploy_demo                 = true
    enable_scenarios            = true
    deploy_knowledge            = true
    search_location             = "global"
    enable_live_evidence        = true
    investigator_operator_email = "operator@example.invalid"
    demo_image_uri              = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  assert {
    condition = (
      length(google_project_iam_custom_role.investigator_reader) == 1 &&
      length(google_project_iam_member.investigator_reader) == 1 &&
      length(google_service_account_iam_member.investigator_operator_token_creator) == 1
    )
    error_message = "M5 must add exactly one investigator custom role and one binding."
  }

  assert {
    condition = (
      google_service_account_iam_member.investigator_operator_token_creator[0].role == "roles/iam.serviceAccountTokenCreator" &&
      google_service_account_iam_member.investigator_operator_token_creator[0].member == "user:operator@example.invalid"
    )
    error_message = "Operator impersonation must be limited to the fixed investigator service account."
  }

  assert {
    condition = toset(google_project_iam_custom_role.investigator_reader[0].permissions) == toset([
      "discoveryengine.servingConfigs.search",
      "logging.logEntries.list",
      "monitoring.timeSeries.list",
      "resourcemanager.projects.get",
      "run.revisions.list",
      "run.services.get",
      "serviceusage.services.use",
    ])
    error_message = "The investigator role must contain only the approved read permissions."
  }

  assert {
    condition = (
      length(google_project_service.m1) == 12 &&
      length(google_service_account.demo) == 3 &&
      length(google_cloud_run_v2_service.demo_leaf) == 1 &&
      length(google_cloud_run_v2_service.demo_payment) == 1 &&
      length(google_cloud_run_v2_service.demo_order) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_leaf) == 1 &&
      length(google_cloud_run_v2_service_iam_member.order_invokes_payment) == 1 &&
      length(google_storage_bucket.knowledge) == 1 &&
      length(google_discovery_engine_data_store.knowledge) == 1 &&
      length(google_discovery_engine_schema.knowledge) == 1 &&
      length(google_discovery_engine_search_engine.knowledge) == 1
    )
    error_message = "M5 must not change the existing API, workload, Search, or runtime IAM graph."
  }
}

run "m7_agent_runtime_apply_ready_contract" {
  command = plan

  variables {
    project_id                   = "example-project"
    billing_account_id           = "000000-000000-000000"
    budget_notification_email    = "operator@example.invalid"
    deploy_demo                  = true
    enable_scenarios             = true
    deploy_knowledge             = true
    search_location              = "global"
    enable_live_evidence         = true
    investigator_operator_email  = "operator@example.invalid"
    deploy_agent_runtime         = true
    agent_runtime_source_archive = "H4sIAAAAAAAA/wMAAAAAAAAAAAA="
    agent_runtime_source_sha256  = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    demo_image_uri               = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }

  assert {
    condition     = length(google_project_service.m1) == 15
    error_message = "M7 may add only the three Runtime telemetry/API service addresses."
  }

  assert {
    condition = (
      length(google_service_account_iam_member.runtime_service_agent_token_creator) == 1 &&
      length(google_project_iam_custom_role.runtime_project_metadata) == 1 &&
      length(google_project_iam_member.runtime_project_metadata) == 1 &&
      length(google_vertex_ai_reasoning_engine.opspilot) == 1
    )
    error_message = "M7 must add one leaf Token Creator grant, one project-metadata binding, and one Agent Runtime only."
  }

  assert {
    condition     = toset(google_project_iam_custom_role.runtime_project_metadata[0].permissions) == toset(["resourcemanager.projects.get"])
    error_message = "The Runtime project lookup role must contain exactly one read-only permission."
  }

  assert {
    condition = toset(google_project_iam_custom_role.investigator_reader[0].permissions) == toset([
      "aiplatform.endpoints.predict",
      "discoveryengine.servingConfigs.search",
      "logging.logEntries.list",
      "monitoring.timeSeries.list",
      "resourcemanager.projects.get",
      "run.revisions.list",
      "run.services.get",
      "serviceusage.services.use",
    ])
    error_message = "M7 may add only Vertex prediction to the existing investigator role."
  }

  assert {
    condition = (
      google_service_account_iam_member.runtime_service_agent_token_creator[0].role == "roles/iam.serviceAccountTokenCreator" &&
      startswith(google_service_account_iam_member.runtime_service_agent_token_creator[0].member, "serviceAccount:service-")
    )
    error_message = "The Runtime service agent grant must remain leaf-scoped to the investigator identity."
  }

  assert {
    condition = (
      google_vertex_ai_reasoning_engine.opspilot[0].region == "asia-northeast3" &&
      google_vertex_ai_reasoning_engine.opspilot[0].deletion_policy == "PREVENT" &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].agent_framework == "google-adk"
    )
    error_message = "M7 must use the fixed Seoul ADK runtime and existing private investigator identity."
  }

  assert {
    condition = jsondecode(google_vertex_ai_reasoning_engine.opspilot[0].spec[0].class_methods) == [{
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
    error_message = "M7 must expose only the fixed AgentSpace async-stream operation."
  }

  assert {
    condition = (
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].min_instances == 0 &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].max_instances == 1 &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].container_concurrency == 3 &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].resource_limits["cpu"] == "1" &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].resource_limits["memory"] == "1Gi"
    )
    error_message = "The Runtime must scale to zero and retain the MVP resource ceiling."
  }

  assert {
    condition = (
      contains([for item in google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].env : "${item.name}=${item.value}"], "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true") &&
      contains([for item in google_vertex_ai_reasoning_engine.opspilot[0].spec[0].deployment_spec[0].env : "${item.name}=${item.value}"], "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false")
    )
    error_message = "Provider telemetry must remain enabled without model message-content capture."
  }

  assert {
    condition = (
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].source_code_spec[0].python_spec[0].version == "3.12" &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].source_code_spec[0].python_spec[0].entrypoint_module == "opspilot.agent.runtime_agent" &&
      google_vertex_ai_reasoning_engine.opspilot[0].spec[0].source_code_spec[0].python_spec[0].entrypoint_object == "root_agent"
    )
    error_message = "M7 must use the deterministic Python 3.12 runtime entrypoint."
  }
}

run "m8_remediation_default_off_and_apply_ready_contract" {
  command = plan

  variables {
    project_id                 = "example-project"
    billing_account_id         = "000000-000000-000000"
    budget_notification_email  = "operator@example.invalid"
    deploy_demo                = true
    enable_formal_environments = true
    enable_scenarios           = true
    enable_remediation         = true
    remediation_approver_group = "approvers@example.invalid"
    demo_image_uri             = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    remediation_image_uri      = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }

  assert {
    condition     = length(google_project_service.m1) == 15
    error_message = "M8 may add only Firestore, Workflows, and Workflow Executions APIs."
  }

  assert {
    condition = (
      length(google_project_service_identity.workflows) == 1 &&
      google_project_service_identity.workflows[0].service == "workflows.googleapis.com"
    )
    error_message = "M8 must materialize the Google-managed Workflows service identity before the Workflow."
  }

  assert {
    condition = (
      length(google_firestore_database.remediation) == 1 &&
      google_firestore_database.remediation[0].name == "opspilot-dev" &&
      google_firestore_database.remediation[0].type == "FIRESTORE_NATIVE" &&
      length(google_firestore_field.remediation_ttl) == 2
    )
    error_message = "M8 must create the named Native database and two cleanup TTL policies."
  }

  assert {
    condition = (
      length(google_service_account.remediation_control) == 1 &&
      length(google_service_account.remediation_workflow) == 1 &&
      length(google_service_account.remediation_executor) == 1 &&
      google_service_account.remediation_control[0].account_id == "opspilot-dev-rem-control" &&
      google_service_account.remediation_workflow[0].account_id == "opspilot-dev-rem-workflow" &&
      google_service_account.remediation_executor[0].account_id == "opspilot-dev-rem-executor" &&
      google_service_account.investigator.account_id == "opspilot-dev-agent"
    )
    error_message = "Control, workflow, executor, and read-only Runtime identities must remain separate."
  }

  assert {
    condition = (
      google_cloud_run_v2_service.remediation_control[0].ingress == "INGRESS_TRAFFIC_ALL" &&
      google_cloud_run_v2_service.remediation_executor[0].ingress == "INGRESS_TRAFFIC_INTERNAL_ONLY" &&
      google_cloud_run_v2_service.remediation_executor[0].scaling[0].max_instance_count == 1 &&
      google_cloud_run_v2_service.remediation_executor[0].template[0].max_instance_request_concurrency == 1
    )
    error_message = "Only the control API is externally reachable; executor ingress and scale remain bounded."
  }

  assert {
    condition = (
      google_cloud_run_v2_service_iam_member.remediation_group_invoker[0].member == "group:approvers@example.invalid" &&
      google_cloud_run_v2_service_iam_member.workflow_invokes_control[0].role == "roles/run.invoker" &&
      google_cloud_run_v2_service_iam_member.workflow_invokes_executor[0].role == "roles/run.invoker"
    )
    error_message = "Invoker IAM must preserve the approver group and workflow-only internal calls."
  }

  assert {
    condition = toset(google_project_iam_custom_role.remediation_executor_cloud_run[0].permissions) == toset([
      "run.operations.get",
      "run.revisions.get",
      "run.services.get",
      "run.services.update",
    ])
    error_message = "Executor permissions must exclude deployment, IAM, environment, and image mutation."
  }

  assert {
    condition = (
      length(google_service_account.formal_demo) == 6 &&
      length(google_cloud_run_v2_service.formal_order) == 2 &&
      length(google_cloud_run_v2_service.formal_payment) == 2 &&
      length(google_cloud_run_v2_service.formal_inventory) == 2 &&
      toset(google_project_iam_custom_role.remediation_executor_image_reader[0].permissions) == toset(["artifactregistry.repositories.downloadArtifacts"]) &&
      google_cloud_run_v2_service_iam_member.remediation_executor_payment[0].name == "opspilot-prod-sim-payment" &&
      google_service_account_iam_member.remediation_executor_acts_as_payment[0].role == "roles/iam.serviceAccountUser" &&
      !contains(google_project_iam_custom_role.remediation_control[0].permissions, "run.services.update")
    )
    error_message = "Traffic update permission must be conditioned on the exact payment service only."
  }
}

run "persistent_investigation_boundary_contract" {
  command = plan

  variables {
    project_id                       = "example-project"
    billing_account_id               = "000000-000000-000000"
    budget_notification_email        = "operator@example.invalid"
    deploy_demo                      = true
    enable_scenarios                 = true
    deploy_knowledge                 = true
    enable_live_evidence             = true
    investigator_operator_email      = "operator@example.invalid"
    deploy_agent_runtime             = true
    agent_runtime_source_archive     = "H4sIAAAAAAAA/wMAAAAAAAAAAAA="
    agent_runtime_source_sha256      = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    demo_image_uri                   = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    enable_persistent_investigations = true
    investigation_image_uri          = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-investigation@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }

  assert {
    condition = (
      length(google_cloud_run_v2_service.investigation_api) == 1 &&
      length(google_cloud_tasks_queue.investigations) == 1 &&
      length(google_pubsub_topic.monitoring_incidents) == 1 &&
      length(google_pubsub_subscription.monitoring_incidents) == 1 &&
      length(google_firestore_database.remediation) == 1
    )
    error_message = "Persistent investigations require one API/worker, one queue, and the protected Firestore database."
  }

  assert {
    condition = (
      length(google_project_iam_member.investigator_reader) == 0 &&
      length(google_project_iam_member.investigation_api_reader) == 1 &&
      google_cloud_run_v2_service_iam_member.runtime_invokes_investigation_api[0].role == "roles/run.invoker" &&
      google_cloud_run_v2_service_iam_member.tasks_invoke_investigation_api[0].role == "roles/run.invoker" &&
      google_cloud_run_v2_service_iam_member.alerts_invoke_investigation_api[0].role == "roles/run.invoker" &&
      google_service_account_iam_member.investigation_api_acts_as_tasks[0].role == "roles/iam.serviceAccountUser"
    )
    error_message = "Runtime must lose direct evidence access and retain only API invocation; tasks use a separate identity."
  }

  assert {
    condition = toset(google_project_iam_custom_role.investigation_store[0].permissions) == toset([
      "aiplatform.endpoints.predict",
      "cloudtasks.tasks.create",
      "datastore.databases.get",
      "datastore.entities.create",
      "datastore.entities.get",
      "datastore.entities.list",
      "datastore.entities.update",
    ])
    error_message = "The investigation API store role must remain write-bounded and exclude delete permissions."
  }

  assert {
    condition = (
      length(google_firestore_field.conversation_context_ttl) == 1 &&
      google_firestore_field.conversation_context_ttl[0].collection == "conversation_contexts" &&
      google_firestore_field.conversation_context_ttl[0].field == "expires_at"
    )
    error_message = "Persistent conversations require one 24-hour context TTL field policy."
  }

  assert {
    condition = (
      length(google_cloud_run_v2_service.investigation_api[0].custom_audiences) == 1 &&
      contains(google_cloud_run_v2_service.investigation_api[0].custom_audiences, "opspilot-investigation-api")
    )
    error_message = "The investigation API must use a fixed audience; the resource precondition enforces its immutable image digest."
  }

  assert {
    condition = alltrue([
      for required_name in [
        "OPSPILOT_INVESTIGATION_AUDIENCE",
        "OPSPILOT_INVESTIGATION_RUNTIME_SERVICE_ACCOUNT",
        "OPSPILOT_INVESTIGATION_TASK_SERVICE_ACCOUNT",
        "OPSPILOT_INVESTIGATION_ALERT_SERVICE_ACCOUNT",
        ] : contains(
        [for item in google_cloud_run_v2_service.investigation_api[0].template[0].containers[0].env : item.name],
        required_name,
      )
    ])
    error_message = "The investigation API must verify the separate Runtime, task, and alert caller identities."
  }
}

run "scheduled_scenarios_default_off" {
  command = plan

  variables {
    project_id                = "example-project"
    billing_account_id        = "000000-000000-000000"
    budget_notification_email = "operator@example.invalid"
  }

  assert {
    condition = (
      length(google_service_account.scheduled_scenario_runner) == 0 &&
      length(google_service_account.scheduled_scenario_trigger) == 0 &&
      length(google_cloud_run_v2_job.scheduled_scn001) == 0 &&
      length(google_cloud_scheduler_job.scheduled_scn001) == 0 &&
      length(google_cloud_run_v2_service_iam_member.scheduled_runner_invokes_dev_order) == 0 &&
      length(google_cloud_run_v2_job_iam_member.scheduler_invokes_scn001) == 0
    )
    error_message = "Scheduled scenario resources must remain disabled by default."
  }

  assert {
    condition     = !contains(keys(google_project_service.m1), "cloudscheduler.googleapis.com")
    error_message = "Cloud Scheduler API must not be enabled while scheduled scenarios are off."
  }
}

run "scheduled_scenarios_bounded_contract" {
  command = plan

  variables {
    project_id                   = "example-project"
    billing_account_id           = "000000-000000-000000"
    budget_notification_email    = "operator@example.invalid"
    deploy_demo                  = true
    enable_scenarios             = true
    enable_scheduled_scenarios   = true
    demo_image_uri               = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    scheduled_scenario_image_uri = "asia-northeast3-docker.pkg.dev/example-project/opspilot-dev-apps-an3/opspilot-scheduled-scenario@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }

  assert {
    condition = (
      length(google_project_service.m1) == 13 &&
      contains(keys(google_project_service.m1), "cloudscheduler.googleapis.com") &&
      length(google_service_account.scheduled_scenario_runner) == 1 &&
      length(google_service_account.scheduled_scenario_trigger) == 1 &&
      length(google_cloud_run_v2_job.scheduled_scn001) == 1 &&
      length(google_cloud_scheduler_job.scheduled_scn001) == 1 &&
      length(google_cloud_run_v2_service_iam_member.scheduled_runner_invokes_dev_order) == 1 &&
      length(google_cloud_run_v2_job_iam_member.scheduler_invokes_scn001) == 1
    )
    error_message = "Enabling scheduled scenarios must add exactly the bounded scheduler resource set."
  }

  assert {
    condition = (
      google_cloud_run_v2_job.scheduled_scn001[0].template[0].task_count == 1 &&
      google_cloud_run_v2_job.scheduled_scn001[0].template[0].parallelism == 1 &&
      google_cloud_run_v2_job.scheduled_scn001[0].template[0].template[0].timeout == "300s" &&
      google_cloud_run_v2_job.scheduled_scn001[0].template[0].template[0].max_retries == 0 &&
      google_cloud_scheduler_job.scheduled_scn001[0].schedule == "5,35 * * * *" &&
      google_cloud_scheduler_job.scheduled_scn001[0].time_zone == "Asia/Seoul" &&
      google_cloud_scheduler_job.scheduled_scn001[0].retry_config[0].retry_count == 0
    )
    error_message = "The Job and Scheduler cadence, concurrency, timeout, and retry bounds must remain fixed."
  }

  assert {
    condition = (
      google_cloud_run_v2_service_iam_member.scheduled_runner_invokes_dev_order[0].name == "opspilot-dev-order" &&
      google_cloud_run_v2_service_iam_member.scheduled_runner_invokes_dev_order[0].role == "roles/run.invoker" &&
      google_cloud_run_v2_job_iam_member.scheduler_invokes_scn001[0].role == "roles/run.invoker" &&
      google_service_account.scheduled_scenario_runner[0].account_id == "opspilot-dev-scenario" &&
      google_service_account.scheduled_scenario_trigger[0].account_id == "opspilot-dev-scenario-trigger"
    )
    error_message = "Each identity must receive only its exact resource-level Run invoker grant."
  }

  assert {
    condition = (
      nonsensitive(google_cloud_run_v2_job.scheduled_scn001[0].template[0].template[0].containers[0].image) == nonsensitive(var.scheduled_scenario_image_uri) &&
      join("|", google_cloud_run_v2_job.scheduled_scn001[0].template[0].template[0].containers[0].args) == "scenario|run|--scenario|SCN-001|--env|dev|--auth|workload|--format|json" &&
      contains([for item in google_cloud_run_v2_job.scheduled_scn001[0].template[0].template[0].containers[0].env : item.name], "OPSPILOT_DEV_ORDER_URL")
    )
    error_message = "The dedicated image may run only SCN-001 in dev with workload authentication."
  }
}
