# OpsPilot Cost Guardrails

Status: M6 complete; M7 Runtime operation contract ready after partial API/IAM apply
Currency evidence: KRW confirmed by the operator; the source image is not stored because it
contains account and project identifiers.

| Guardrail | M1 value |
| --- | --- |
| Monthly alerts-only budget | KRW 50,000 |
| Current-spend thresholds | 50%, 80%, 100% |
| Recipients | Project-level recipients plus default billing IAM recipients |
| Budget deletion policy | Prevent |
| Cloud Run minimum instances | 0 per applied service |
| Cloud Run maximum instances | 2 per service |
| Synthetic load | Manual, 100 orders and concurrency 10 hard maximum |
| Data | Synthetic ecommerce only |
| Remediation | Disabled |
| Agent Runtime source default | Disabled; Approval 1 has no deployment or runtime call |

The Google Cloud budget is an alert, not a hard spending cap. Later workloads must use
scale-to-zero, bounded log and metric queries, short retention, manual demo windows, and explicit
cleanup to keep the alert from becoming the only cost control.

## Current cost-bearing resources

- One regional Standard GCS bucket for Terraform state with versioning and 30-day noncurrent
  object cleanup.
- One regional Standard Docker Artifact Registry repository containing immutable M2 demo image
  digests. The prior digest is retained for audit/rollback; deletion requires separate approval.
- One email notification channel and one project-scoped KRW 50,000 budget. Budget APIs and email
  notifications have no configured runtime workload in M1.
- IAM, service-account, API, and WIF configuration do not directly incur resource runtime costs.

The investigator identity has no roles or user-managed keys. Three private Cloud Run services are
applied with scale-to-zero and no scheduled traffic. Final acceptance generated ten synthetic
orders plus bounded endpoint checks and confirmed Logging and Monitoring telemetry. No deliberate
failure or 5xx was generated. A budget is an alert rather than a hard spending cap; email delivery
remains unverified until a real threshold is reached.

The controlled refresh created new revisions for the existing services but added no managed
resource, image, scheduled traffic, minimum instance, or IAM grant. The services returned to zero
drift and scale to zero after validation.

## Applied M2 controls

- Three private Cloud Run services share one digest and use request-based CPU, 1 vCPU, 256 MiB,
  min 0, max 2, concurrency 20, and a 10-second request timeout.
- There is no scheduled load, Firestore, custom metric, alert policy, or fault injector.
- The three active revisions use one immutable Artifact Registry digest. No background demo window
  is active. Both hosted Terraform plan gates are enabled only for the manual read-only workflow.
Future work must not add any cost-bearing resource without a separate plan and approval.

## M7 Approval 1 impact

- Runtime validation, fixture smoke, deterministic packaging, Terraform validation, and CI are
  local-only.
- `deploy_agent_runtime=false` preserves the current 31 managed dev resources.
- No Runtime, API state, IAM grant, Enterprise registration, Search/evidence query, or Vertex model
  request is created by Approval 1.
- A future Approval 2 runtime remains min 0/max 1 at 1 vCPU and 1 GiB, concurrency 3. The project
  KRW 50,000 budget remains the operational ceiling; no subscription or provisioned throughput is
  enabled.
- GitHub workflows are manual-only and skipped as MVP gates. No M7 hosted-reader permission or
  bootstrap apply is required; the existing WIF infrastructure remains unchanged.

## M7 Approval 2 checkpoint

- One reviewed `5 create / 1 update` apply was attempted. Three managed API addresses, one leaf IAM
  member, and the investigator-role update succeeded; the Runtime failed startup and no Runtime
  remains deployed.
- No Runtime probe, Enterprise registration, supported investigation, Search request, evidence
  collection, or model request was issued. The failed Runtime therefore adds no ongoing instance
  cost.
- A corrective deploy is not authorized by this checkpoint. It requires a pinned Agent Platform
  SDK dependency, a new exact plan, and separate approval while the KRW 50,000 budget remains in
  force.

## M7 Approval 3 checkpoint

- The pinned SDK dependency passed isolated Python 3.12 installation and imports. The single
  reviewed Runtime-only one-create apply then failed registered-operation discovery because the
  raw ADK agent has no Runtime query method.
- Dev remains at 35 managed resources and 36 addresses. No Runtime, probe, registration, Preview
  request, evidence call, or model call exists, so this attempt adds no ongoing Runtime instance
  cost.
- The final deployment uses the verified official `AdkApp` wrapper and exact Runtime-only
  one-create gate. It introduces no new dependency, IAM, API, data, or optional feature. Before a
  successful create, paid Runtime, evidence, model, and Preview request counts remain zero.

## M3 impact

- Seven scenario fixtures and SCN-001 execution are local code only.
- The scenario profile is capped at 20 requests per run; local CI repeats it three times.
- `enable_scenarios=false` remains the Terraform default; the live environment enables it only
  behind the manual M3 image gate.
- Approval 2 pushed one immutable image and updated the three existing Cloud Run revisions without
  adding, deleting, or replacing a Terraform resource.
- Three live runs generated exactly 60 scenario orders. Expected synthetic failures were limited
  to the incident phases, followed by three successful 5/5 recovery phases.
- Logging and Monitoring reads were bounded. No custom metric, alert, scheduled load, persistent
  fault state, IAM grant, or remediation resource was added.
- All three services retain minimum instances zero and return to scale-to-zero after validation.

## M4 Approval 1 impact

- Thirteen Markdown documents, one deterministic catalog, and ten local retrieval queries are
  repository-only data and generate no Google Cloud charge.
- `deploy_knowledge=false` is the Terraform default. No knowledge bucket, data store, schema,
  engine, object, import operation, or billable Search query was created in Approval 1.
- The recovery approval completed the protected schema and Standard Search engine without changing
  Cloud Run, IAM, budget, network, or existing Search assets. Dev state now has 28 managed resources.
- The dedicated bucket contains thirteen text objects, one manifest, and one current snapshot.
  One FULL import completed with 13 successes and zero failures.
- The earlier failed Search request was followed under Approval 3 by one successful fixed probe and
  one successful ten-query acceptance batch. Observed M4 Search usage is therefore twelve requests
  in total, with a worst-case list price of approximately USD 0.018.
- Approval 2 is restricted to General pay-as-you-go Standard Search. Enterprise Search, AI
  Overview, LLM add-ons, configurable pricing subscriptions, OCR, and layout parsing are excluded.
- The applied corpus is far below the documented 10 GiB index free allowance. Ten Standard Search
  smoke requests have a maximum list price of USD 0.015 before any shared free-query allowance;
  actual billing must still be checked because existing project Search usage can share allowances.
- The existing KRW 50,000 alert remains the project guardrail. A configurable subscription or an
  unexpected add-on is a hard stop rather than an accepted cost increase.
- Approval 4 added one service-usage quota-consumption permission to the existing CI custom role.
  It created no cost-bearing resource and issued no Search request or import; the hosted plan was
  read-only and zero drift.

## M5 Approval 1 and Approval 2 boundary

- Typed evidence contracts, fixture/live adapters, and default-off IAM are repository-only changes.
- Fixture smoke performs four logical collectors and zero Google Cloud API calls.
- No Logging, Monitoring, Cloud Run Admin, or Agent Search request is executed in Approval 1.
- No image, workload, custom metric, alert, role, binding, or other cloud resource is changed.
- Approval 2 will cap live acceptance at one SCN-001 run, one Logging request, two Monitoring
  requests, one Cloud Run service read plus one revision list, and one Standard Search request.
- Approval 2 adds IAM bindings only. It creates no workload or persistent cost-bearing service.
- The accepted live batch used one Standard Search request plus bounded existing telemetry and
  Cloud Run reads. No import, image build/push, deployment, or persistent cost-bearing resource was
  added.

## Cleanup order

1. Disable `TF_M4_KNOWLEDGE_READY`, `TF_M3_IMAGE_READY`, `TF_M2_IMAGE_READY`, and the live plan gate.
2. Remove GitHub WIF repository variables.
3. Review the dev destroy plan and budget deletion protection.
4. Remove dev resources only after explicit approval.
5. Migrate bootstrap state away from GCS before any state bucket cleanup.
6. Remove WIF and CI identities only after no workflow depends on them.
7. Verify remaining budget alerts, APIs, images, objects, and state versions.

## M6 Approval 1 impact

- ADK orchestration, its fake model, and the seven-case evaluation run locally and in static CI.
- The default package stays unchanged; ADK 2.5 is installed only through the optional `agent` extra.
- Approval 1 performs zero Vertex model calls, Cloud API reads, deployments, IAM changes, or
  Terraform changes.
- A future live run is capped at two model calls with bounded input/output and requires the
  explicit process gate plus a separate approval. Actual Gemini pricing and quota must be checked
  immediately before that approval.

## M6 Approval 2 boundary

- The fixed live suite contains three fixture cases and at most nine attempted model requests.
- The model is `gemini-3.5-flash` on the `global` Standard PayGo endpoint. No provisioned
  throughput, grounding, tool call, Search request, or live telemetry read is part of this batch.
- At the documented rates of USD 1.50 per million input tokens and USD 9.00 per million output
  tokens, the conservative 64-KiB-per-request and 2,048-output-token limits cap the batch at about
  USD 1.06. Actual usage is recorded from provider usage metadata.
- IAM, Terraform, Cloud Run, corpus, import, image, runtime, and GitHub credential state remain
  unchanged.
- The single approved live run stopped during SCN-001 after two attempted requests and one
  successful response. Reported usage was 1,229 prompt tokens and 275 output tokens, about USD
  0.0044 at list price. Even treating both attempts at their full byte/token caps stays below about
  USD 0.24. No retry or additional model request was made.

## M6 Approval 3 boundary

- The model reviewer is replaced by deterministic citation checks, leaving RCA analysis and report
  composition as the only model nodes. Each case is capped at two attempts.
- The fixed three-case acceptance batch permits at most six new requests, no retry, and no probe.
- Applying the same conservative input and output limits yields a new-run ceiling of about USD
  0.71. Actual usage is recorded only from bounded provider metadata.
- IAM, Terraform, Cloud Run, Search, live evidence, deployment, and GitHub credential state remain
  unchanged.
- The approved batch stopped after SCN-001 used two successful requests. Reported usage was 2,901
  prompt tokens and 790 output tokens, about USD 0.0115 at the documented list rates. SCN-006 and
  SCN-007 made no request, and the process gate was removed.

## M6 Approval 4 boundary

- Safe acceptance diagnostics are local and issue no model request.
- The only approved live suite is `m6-rca`, containing SCN-001 and at most two requests with no
  retry. `m6-safety` and `m6-core` are fake-only in this approval.
- The conservative request ceiling is one third of the Approval 3 six-request ceiling. Actual token
  usage is recorded only from bounded provider metadata.
- Terraform, IAM, Cloud Run, Search, live evidence, and deployment changes remain zero.
- The approved run used two successful requests: 2,893 prompt tokens, 764 output tokens, and 3,657
  total tokens. At the same documented list rates used above, the observed cost is approximately
  USD 0.0112. No retry or safety-suite request was issued.

## M6 Approval 5 boundary

- Deterministic taxonomy implementation and offline validation issue no paid request.
- Approval 5 permits exactly one `m6-rca` Vertex execution with at most two successful or failed
  requests and no retry. The separate safety suite remains outside this approval.
- The conservative ceiling matches Approval 4; actual tokens and estimated cost are recorded only
  after the bounded execution.
- Terraform, IAM, Cloud Run, Search, live evidence, and deployment changes remain zero.
- The single run stopped after one attempted and zero successful responses with `AGENT_TIMEOUT`.
  Provider usage exposed through the bounded result was zero prompt, output, and total tokens; no
  billing amount is inferred from that metadata. The second RCA node and safety suite were not
  called.

## M6 Approval 6 boundary

- Timeout phase contracts, monotonic timing, fake-model regression, and static CI are local-only.
- The model, prompts, schemas, 20/60/200-second limits, request ceilings, and Standard PayGo
  configuration are unchanged.
- Approval 6 authorizes zero Vertex generation, Search, live-evidence, import, image, deployment,
  IAM, Terraform, or hosted model workflow calls, so its incremental cloud cost is zero.
- A later RCA diagnostic execution remains a separate approval with its own maximum request and
  cost boundary.

## M6 Approval 7 boundary

- The final approval permitted one RCA suite and, only after RCA success, one safety suite. The
  maximum was six requests with no retry and unchanged 20/60/200-second limits.
- RCA stopped on `root_cause_mismatch`, so safety issued zero requests. RCA used exactly two
  successful requests with 2,947 prompt tokens, 840 output tokens, and 3,787 total tokens.
- At the same documented list rates used for prior M6 checkpoints, observed usage is approximately
  USD 0.0120. No additional Vertex, Search, live-evidence, deployment, IAM, or Terraform operation
  followed.

## M6 Approval 8 boundary

- Evidence classification implementation and static validation are local-only and add no service,
  dependency, IAM grant, deployment, Search request, or telemetry read.
- Live acceptance permits one two-request RCA suite and, only after RCA success, one four-request
  safety suite. The total ceiling is six Standard PayGo requests with no retry.
- The model, prompt, schemas, 20/60/200-second limits, input/output bounds, and monthly KRW 50,000
  alert remain unchanged. Actual bounded token usage is recorded after execution.
- The single live RCA run stopped before safety after two attempts and one successful response.
  Reported usage was 1,246 prompt tokens, 315 output tokens, and 1,561 total tokens, approximately
  USD 0.0047 at the same documented list rates used for prior checkpoints. No retry was issued.

## M6 Approval 9 boundary

- Approval 9 changes only the local model execution budget from 20/60 to 30/75 seconds while the
  200-second suite deadline, request size, output token, and two-call case ceilings remain fixed.
- One RCA suite and, only after success, one safety suite are permitted. The aggregate ceiling is
  six Standard PayGo requests with no retry, live core suite, Search, evidence, deployment, IAM, or
  Terraform operation.
- This calibration does not increase the request or token ceiling, so the previously documented
  six-request worst-case model cost boundary remains unchanged.
- The single RCA and conditional safety executions both passed. They used six attempted and
  successful requests, 6,955 prompt tokens, 2,311 output tokens, and 10,322 total reported tokens.
- At the same documented input/output list rates used for prior M6 checkpoints, observed usage is
  approximately USD 0.0312. No retry, live core suite, Search, evidence, deployment, IAM, or
  Terraform operation followed.
