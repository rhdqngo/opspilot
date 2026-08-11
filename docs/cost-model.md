# OpsPilot Cost Guardrails

Status: M3 complete; bounded incident validated and workload scaled to zero
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

## Cleanup order

1. Disable `TF_M2_IMAGE_READY` and the live Terraform plan gate.
2. Remove GitHub WIF repository variables.
3. Review the dev destroy plan and budget deletion protection.
4. Remove dev resources only after explicit approval.
5. Migrate bootstrap state away from GCS before any state bucket cleanup.
6. Remove WIF and CI identities only after no workflow depends on them.
7. Verify remaining budget alerts, APIs, images, objects, and state versions.
