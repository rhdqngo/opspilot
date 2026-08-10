# OpsPilot Cost Guardrails

Status: bootstrap applied; dev foundation not applied
Currency evidence: KRW confirmed by the operator; the source image is not stored because it
contains account and project identifiers.

| Guardrail | M1 value |
| --- | --- |
| Monthly alerts-only budget | KRW 50,000 |
| Current-spend thresholds | 50%, 80%, 100% |
| Recipients | Project-level recipients plus default billing IAM recipients |
| Budget deletion policy | Prevent |
| Cloud Run minimum instances | 0 when introduced in M2 |
| Data | Synthetic ecommerce only |
| Remediation | Disabled |

The Google Cloud budget is an alert, not a hard spending cap. Later workloads must use
scale-to-zero, bounded log and metric queries, short retention, manual demo windows, and explicit
cleanup to keep the alert from becoming the only cost control.

## Current M1 cost-bearing resources

- One regional Standard GCS bucket for Terraform state with versioning and 30-day noncurrent
  object cleanup.
- IAM, service-account, API, and WIF configuration do not directly incur resource runtime costs.

The Docker Artifact Registry repository, investigator identity, notification channel, and budget
remain unapplied until Approval 2. The hosted plan creates no cloud resources or remote dev state.

## Cleanup order

1. Disable the live Terraform plan repository variable.
2. Remove GitHub WIF repository variables.
3. Review the dev destroy plan and budget deletion protection.
4. Remove dev resources only after explicit approval.
5. Migrate bootstrap state away from GCS before any state bucket cleanup.
6. Remove WIF and CI identities only after no workflow depends on them.
7. Verify remaining budget alerts, APIs, images, objects, and state versions.
