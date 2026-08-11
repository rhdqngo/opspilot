# OpsPilot Cost Guardrails

Status: M2 Cloud Run foundation applied; remote smoke validation blocked
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
- One regional Standard Docker Artifact Registry repository containing the immutable M2 demo image.
- One email notification channel and one project-scoped KRW 50,000 budget. Budget APIs and email
  notifications have no configured runtime workload in M1.
- IAM, service-account, API, and WIF configuration do not directly incur resource runtime costs.

The investigator identity has no roles or user-managed keys. Three private Cloud Run services are
applied with scale-to-zero and no scheduled traffic. A remote route blocker prevented the bounded
smoke request from reaching a container, so request-log and request-metric cost remains zero in the
verification window. A budget is an alert rather than a hard spending cap; email delivery remains
unverified until a real threshold is reached.

The controlled refresh created new revisions for the existing services but added no managed
resource, image, scheduled traffic, minimum instance, or IAM grant. The services returned to zero
drift and scale to zero after validation.

## Applied M2 controls

- Three private Cloud Run services share one digest and use request-based CPU, 1 vCPU, 256 MiB,
  min 0, max 2, concurrency 20, and a 10-second request timeout.
- There is no scheduled load, Firestore, custom metric, alert policy, or fault injector.
- The three revisions use one immutable Artifact Registry digest. No background demo window is
active, and both hosted Terraform plan gates remain disabled until remote smoke succeeds.
Endpoint recovery must not add any cost-bearing resource without a separate plan and approval.

## Cleanup order

1. Disable `TF_M2_IMAGE_READY` and the live Terraform plan gate.
2. Remove GitHub WIF repository variables.
3. Review the dev destroy plan and budget deletion protection.
4. Remove dev resources only after explicit approval.
5. Migrate bootstrap state away from GCS before any state bucket cleanup.
6. Remove WIF and CI identities only after no workflow depends on them.
7. Verify remaining budget alerts, APIs, images, objects, and state versions.
