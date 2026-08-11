# OpsPilot Cost Guardrails

Status: M4 complete; M5 Approval 1 code-only
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

## Cleanup order

1. Disable `TF_M4_KNOWLEDGE_READY`, `TF_M3_IMAGE_READY`, `TF_M2_IMAGE_READY`, and the live plan gate.
2. Remove GitHub WIF repository variables.
3. Review the dev destroy plan and budget deletion protection.
4. Remove dev resources only after explicit approval.
5. Migrate bootstrap state away from GCS before any state bucket cleanup.
6. Remove WIF and CI identities only after no workflow depends on them.
7. Verify remaining budget alerts, APIs, images, objects, and state versions.
