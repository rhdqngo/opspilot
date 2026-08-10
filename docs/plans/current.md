# Current Project State

status: active
phase: M1-complete / M2-ready-for-planning
updated: 2026-08-10

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud
  operations data.

## Active scope

- R0 local skeleton and M0 access verification are complete.
- The M1 bootstrap is applied: protected GCS state, numeric-ID GitHub WIF, read-only CI plan
  identity, custom read role, additive IAM bindings, and required bootstrap APIs.
- Bootstrap state is migrated to the GCS `bootstrap` prefix and has no drift.
- The exact reviewed dev plan was applied and its 14 managed resources were migrated to the GCS
  `environments/dev` prefix with preserved lineage and operator zero drift.
- The dev foundation contains ten managed APIs, an empty regional Docker repository, an
  unprivileged investigator identity, an active email channel, and a protected KRW 50,000 budget.
- No workload, investigator permission, service-account key, image, or remediation resource exists.

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| Repository Bootstrap | complete | Python package scaffold validated from the repository root |
| R0 Local Skeleton | complete | 30 tests, strict mypy, ruff, package build, CLI replay, API health/readiness |
| M0 Access and decisions | complete | Redacted access gate passed for the `Edu_687` alias and current default project |
| Private GitHub baseline | complete | Private `opspilot` repository on `main`; no history rewrite |
| M1 Bootstrap infrastructure | complete | 14 managed resources, protected remote state, zero drift, no service-account key |
| M1 Dev foundation | complete | Exact 14-create plan applied and migrated; operator and hosted plans have zero drift |
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
- Applied the exact saved dev plan after config/address/hash/redaction checks and verified 14
  managed resources with no replacement or delete.
- Enabled the Budget API, created the bounded four-resource dev foundation, and verified the
  investigator has no project role or user-managed key.
- Normalized the project-level budget ownership field to the API default, which is semantically
  equivalent to `ALL_USERS`, eliminating a perpetual one-field drift without another cloud write.
- Migrated dev state to GCS, preserved lineage, obtained operator zero drift, and removed all local
  state, plan, and recovery files from the run directory.
- Verified final hosted run `31389847460`: WIF remote-state read succeeded, the redacted artifact
  reported no changes, actual identifier leakage was zero, and no binary plan was uploaded.

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
| Dev apply | pass | Exact 14-create plan; update/delete/replacement 0 |
| Dev resources | pass | API 10/10; repository empty; investigator roles/keys 0; channel and budget contracts pass |
| Dev remote state | pass | GCS `environments/dev`; 14 managed resources; lineage preserved; operator zero drift |
| Hosted dev plan | pass | Run `31389847460`; remote state, no changes, redaction pass, binary plan absent |
| GitHub plan gates | pass | `TF_PLAN_ENABLED=true`; `TF_DEV_STATE_READY=true`; workflow_dispatch only |
| UI render / input | not-applicable | No R0/M1 end-user UI |

## Blockers and decisions needed

- Approval 1 and Approval 2 are complete; no M1 blocker remains.
- M2 requires a new plan and explicit approval before adding a demo workload.
- Do not store actual account, project, billing, state, app, repository numeric, or credential
  identifiers in the repository.

## Next checkpoint

- Plan M2: a scale-to-zero synthetic demo service, image build path, runtime identity boundary,
  observability defaults, and separate apply approval.

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
