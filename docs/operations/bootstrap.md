# M1 Bootstrap Operations

Status: ready for static validation; no apply approved

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

## Approval 1: bootstrap

Only after an explicit bootstrap approval:

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
- `TF_PLAN_ENABLED=true`

Store `GCP_BUDGET_NOTIFICATION_EMAIL` as a GitHub repository secret, not a variable or file.

## Approval 2: dev foundation

Only after bootstrap state migration and a separate dev approval:

1. Initialize `infra/terraform/environments/dev` with the approved state bucket.
   Copy its `backend.tf.example` to ignored `backend.tf` before initialization.
2. Produce a new plan with `-lock=false` for review.
3. Confirm the plan contains only API enablement, one Docker repository, one unprivileged
   investigator service account, email notification channel, and the KRW 50,000 budget.
4. Apply only the reviewed plan.
5. Manually dispatch the hosted Terraform plan workflow and inspect its redacted text artifact.

The budget has deletion protection. Cleanup requires a deliberate policy change and a new reviewed
plan; it must never be bypassed with state editing.
