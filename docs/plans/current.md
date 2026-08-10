# Current Project State

status: active
phase: M1-bootstrap-complete / dev-ready-for-apply
updated: 2026-08-10

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud
  operations data.

## Active scope

- R0 local skeleton and M0 access verification are complete.
- The M1 bootstrap is applied: protected GCS state, numeric-ID GitHub WIF, read-only CI plan
  identity, custom read role, additive IAM bindings, and required bootstrap APIs.
- Bootstrap state is migrated to the GCS `bootstrap` prefix and has no drift.
- The hosted read-only dev plan is operational and shows the approved 14 creates.
- No dev apply, dev remote state, Artifact Registry, investigator identity, notification channel,
  budget, workload, or remediation resource has been created.

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| Repository Bootstrap | complete | Python package scaffold validated from the repository root |
| R0 Local Skeleton | complete | 30 tests, strict mypy, ruff, package build, CLI replay, API health/readiness |
| M0 Access and decisions | complete | Redacted access gate passed for the `Edu_687` alias and current default project |
| Private GitHub baseline | complete | Private `opspilot` repository on `main`; no history rewrite |
| M1 Bootstrap infrastructure | complete | 14 managed resources, protected remote state, zero drift, no service-account key |
| M1 Dev foundation | ready-for-apply | Hosted redacted plan has 14 creates and zero change/destroy; Approval 2 required |
| UI Foundation | not-applicable | R0/M1 are API, CLI, and infrastructure only |

## Completed major results

- Applied the exact reviewed bootstrap binary plan after address-set and hash verification.
- Enabled the one missing bootstrap API and brought the five existing bootstrap APIs under state.
- Verified bucket public-access prevention, uniform access, versioning, lifecycle, and deletion
  protections.
- Verified the CI custom role is read-only, WIF admission uses immutable numeric IDs, and no
  user-managed service-account key exists.
- Migrated bootstrap state to GCS, confirmed 14 managed resources, and obtained a zero-drift plan.
- Stored six private GitHub variables and one budget-email secret without disclosing values.
- Verified WIF hosted dev plan run `31386038802` with 14 creates, no destructive action, and no
  actual identifier in the redacted artifact.

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Baseline run | pass | SCN-001 replay; `/healthz` and `/readyz` on a local server |
| Build | pass | `uv build` produced sdist and wheel |
| Format / lint | pass | ruff format/check; Terraform recursive format; TFLint 0.64.0 |
| Type check | pass | `uv run mypy src tests` - no issues |
| Tests | pass | `uv run pytest` - 30 passed; both Terraform mock-provider tests passed |
| Bootstrap apply | pass | Exact 14-create saved plan applied; delete/replacement 0 |
| Remote state | pass | GCS backend `bootstrap` prefix; 14 managed resources; zero drift |
| Bootstrap security | pass | Bucket controls, read-only IAM, numeric WIF, key absence, API set verified |
| Hosted dev plan | pass | Run `31386038802`; 14 create, 0 change, 0 destroy; redaction passed |
| GitHub plan gates | pass | `TF_PLAN_ENABLED=true`; `TF_DEV_STATE_READY=false`; workflow_dispatch only |
| Dev resource changes | pass | 0 resources and 0 remote dev state objects created |
| UI render / input | not-applicable | No R0/M1 end-user UI |

## Blockers and decisions needed

- Approval 1 is complete and no bootstrap blocker remains.
- Dev apply is blocked on a separate explicit Approval 2.
- `TF_DEV_STATE_READY` must remain false until an approved dev apply and state migration succeed.
- Do not store actual account, project, billing, state, app, repository numeric, or credential
  identifiers in the repository.

## Next checkpoint

- Prepare Approval 2: regenerate and review the dev plan, apply only the approved 14 resources,
  migrate dev state, then switch `TF_DEV_STATE_READY=true` and verify a hosted zero-drift plan.

## Related artifacts

- Master plan: `docs/plans/opspilot_ai_implementation_spec.md`
- Access gate: `docs/access-check.md`
- IAM matrix: `docs/iam-matrix.md`
- Cost model: `docs/cost-model.md`
- Bootstrap runbook: `docs/operations/bootstrap.md`
- IaC decision: `docs/decisions/ADR-007-iac-delivery.md`
- UI Foundation: not applicable for R0/M1

## Update rules

Update this document only when the active milestone, scope, major result, blocker, validation
state, or next checkpoint changes materially. Do not edit it solely to record the end of a session.
