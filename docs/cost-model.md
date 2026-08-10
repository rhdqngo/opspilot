# OpsPilot Cost Guardrails

Status: M1 applied; M2 local workload validated and cloud deployment pending
Currency evidence: KRW confirmed by the operator; the source image is not stored because it
contains account and project identifiers.

| Guardrail | M1 value |
| --- | --- |
| Monthly alerts-only budget | KRW 50,000 |
| Current-spend thresholds | 50%, 80%, 100% |
| Recipients | Project-level recipients plus default billing IAM recipients |
| Budget deletion policy | Prevent |
| Cloud Run minimum instances | 0 in the pending M2 configuration |
| Cloud Run maximum instances | 2 per service |
| Synthetic load | Manual, 100 orders and concurrency 10 hard maximum |
| Data | Synthetic ecommerce only |
| Remediation | Disabled |

The Google Cloud budget is an alert, not a hard spending cap. Later workloads must use
scale-to-zero, bounded log and metric queries, short retention, manual demo windows, and explicit
cleanup to keep the alert from becoming the only cost control.

## Current M1 cost-bearing resources

- One regional Standard GCS bucket for Terraform state with versioning and 30-day noncurrent
  object cleanup.
- One empty regional Standard Docker Artifact Registry repository.
- One email notification channel and one project-scoped KRW 50,000 budget. Budget APIs and email
  notifications have no configured runtime workload in M1.
- IAM, service-account, API, and WIF configuration do not directly incur resource runtime costs.

The investigator identity has no roles or user-managed keys. Artifact Registry contains no M2
image and Terraform contains no applied Cloud Run service, live telemetry workload, or remediation
resource. The local Docker image does not create Google Cloud cost. A budget is
an alert rather than a hard spending cap; email delivery remains unverified until a real threshold
is reached.

## Pending M2 controls

- Three private Cloud Run services share one digest and use request-based CPU, 1 vCPU, 256 MiB,
  min 0, max 2, concurrency 20, and a 10-second request timeout.
- There is no scheduled load, Firestore, custom metric, alert policy, fault injector, or VPC.
- Approval 2 must confirm the Artifact Registry digest and stop after bounded smoke/telemetry
  verification; no background demo window remains active.

## Cleanup order

1. Disable `TF_M2_IMAGE_READY` and the live Terraform plan gate.
2. Remove GitHub WIF repository variables.
3. Review the dev destroy plan and budget deletion protection.
4. Remove dev resources only after explicit approval.
5. Migrate bootstrap state away from GCS before any state bucket cleanup.
6. Remove WIF and CI identities only after no workflow depends on them.
7. Verify remaining budget alerts, APIs, images, objects, and state versions.
