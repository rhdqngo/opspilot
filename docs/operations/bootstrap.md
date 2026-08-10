# M1 Bootstrap Operations

Status: M1 bootstrap and dev foundation complete

## Approval 1 execution record

- Applied the reviewed bootstrap plan with 14 managed resources and no delete or replacement.
- Migrated bootstrap state to the protected GCS `bootstrap` prefix and verified a zero-drift plan.
- Configured numeric-ID GitHub WIF and the read-only CI plan identity without service-account keys.
- Verified hosted dev plan run `31386038802`: 14 creates, zero changes, zero destroys, and no
  identifier leakage in the redacted artifact.

## Approval 2 execution record

- Applied the exact reviewed 14-create dev plan with no delete or replacement.
- Enabled the one missing Budget API and brought nine existing APIs under dev state.
- Created one empty regional Docker repository, one unprivileged investigator identity, one email
  notification channel, and one protected project-scoped KRW 50,000 budget.
- Verified the investigator has no project role or user-managed key.
- Migrated dev state to the protected `environments/dev` prefix, preserved lineage, and verified an
  operator zero-drift plan before removing local state and binary plans.
- Kept the API default ownership scope because `OWNERSHIP_SCOPE_UNSPECIFIED` is equivalent to
  `ALL_USERS`; explicitly setting the equivalent enum caused perpetual provider drift for this
  project-level budget.
- Set `TF_DEV_STATE_READY=true` and retained `TF_PLAN_ENABLED=true`.
- Verified final hosted run `31389847460` from the normalized `main`: remote-state WIF succeeded,
  the redacted artifact reported no changes, identifier leakage was zero, and no binary plan was
  uploaded.

## M2 read-only plan preparation

M2 Approval 1 adds three Cloud Run read permissions to the existing CI custom-role definition.
They are not applied in Approval 1. Approval 2 must first review a bootstrap plan with exactly one
in-place custom-role update and no create/delete/replacement, then review the separate dev plan.

The live dev workflow now also requires `TF_M2_IMAGE_READY=true`. Approval 1 does not create this
variable or `GCP_DEMO_IMAGE_URI`, so a manual dispatch cannot run with a missing image digest.

## Safety invariants

- Use only the current gcloud default project verified by `opspilot access-check`.
- Never commit `backend.hcl`, `*.tfvars`, state, plan binaries, account IDs, or project IDs.
- Review bootstrap and dev plans separately.
- Bootstrap apply and dev apply require separate approvals.
- Do not run destroy as part of bootstrap or validation.

## Local inputs

Inject actual values only in the current shell or ignored local files:

```powershell
$env:TF_VAR_project_id = '<current-default-project-id>'
$env:TF_VAR_billing_account_id = '<linked-billing-account-id>'
$env:TF_VAR_budget_notification_email = '<budget-alert-recipient>'
$env:TF_VAR_github_owner_id = '<numeric-owner-id>'
$env:TF_VAR_github_repository_id = '<numeric-repository-id>'
```

The repository examples contain placeholders only.

## Static validation

```powershell
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/bootstrap init -backend=false -input=false
terraform -chdir=infra/terraform/bootstrap validate
terraform -chdir=infra/terraform/bootstrap test
terraform -chdir=infra/terraform/environments/dev init -backend=false -input=false
terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/environments/dev test
```

Static validation uses mock provider data and makes no Google Cloud changes.

## Approval 1: bootstrap (completed)

The completed procedure was:

1. Produce and save a local bootstrap plan under ignored `.tmp/`.
2. Review API enablement, state bucket, custom role, CI service account, WIF pool/provider, and
   additive IAM members.
3. Reject any delete, replacement, broad predefined write role, service account key, or unexpected
   resource.
4. Apply the reviewed bootstrap plan.
5. Copy `backend.tf.example` to ignored `backend.tf`.
6. Write the returned bucket name to ignored `backend.hcl` and run
   `terraform init -migrate-state -backend-config=backend.hcl`.
7. Store the sensitive Terraform outputs as GitHub repository variables, not repository files.

Expected repository variables after bootstrap:

- `GCP_PROJECT_ID`
- `GCP_PROJECT_NUMBER`
- `GCP_BILLING_ACCOUNT_ID`
- `GCP_WIF_PROVIDER`
- `GCP_TERRAFORM_PLAN_SERVICE_ACCOUNT`
- `TF_STATE_BUCKET`
- `TF_DEV_STATE_READY=true`
- `TF_PLAN_ENABLED=true`

Store `GCP_BUDGET_NOTIFICATION_EMAIL` as a GitHub repository secret, not a variable or file.

## Approval 2: dev foundation (completed locally)

The completed procedure was:

1. Copy the committed dev configuration to an ignored run directory and initialize local state.
2. Produce a new binary plan with `-lock=false` for review.
3. Confirm the plan contains only API enablement, one Docker repository, one unprivileged
   investigator service account, email notification channel, and the KRW 50,000 budget.
4. Apply only the reviewed plan.
5. Verify all resources, migrate state to the `environments/dev` prefix, and obtain an operator
   zero-drift plan.
6. Remove local state and plan material only after remote state and lineage verification.
7. Set `TF_DEV_STATE_READY=true`, manually dispatch the hosted Terraform plan workflow, and inspect
   its redacted text artifact.

The budget has deletion protection. Cleanup requires a deliberate policy change and a new reviewed
plan; it must never be bypassed with state editing.
