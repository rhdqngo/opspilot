# Current Project State

status: active
phase: M0-complete / M1-ready-for-apply
updated: 2026-08-10

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud
  operations data.

## Active scope

- R0 local skeleton is complete: typed contracts, deterministic SCN-001 workflow, API, CLI,
  tests, and package build.
- M0 access verification is complete for the `Edu_687` alias and current gcloud default project.
- M1 Terraform, offline CI, approval-gated live planning, IAM/cost documentation, and local
  non-applying plans are implemented; local and hosted static validation pass.
- No Terraform apply, API activation, IAM mutation, budget creation, state migration, or hosted
  cloud plan has been performed.

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| Bootstrap | complete | Python package scaffold validated from the repository root |
| R0 Local Skeleton | complete | 29 tests, strict mypy, ruff, package build, CLI replay, API health/readiness |
| M0 Access and decisions | complete | Redacted access check passed; KRW billing and Gemini collaboration path verified |
| Private GitHub baseline | complete | Private `opspilot` repository, `main`, baseline commit, no history rewrite |
| M1 Infrastructure foundation | ready-for-apply | Terraform 1.15.8 / Google 7.39.0, local plans, and hosted static CI pass; apply prohibited |
| UI Foundation | not-applicable | R0/M1 are API, CLI, and infrastructure only |

## Completed major results

- Split Terraform into local-state `bootstrap` and remote-state-ready `environments/dev` stacks.
- Defined protected GCS state, numeric-ID GitHub WIF, a read-only plan identity, required APIs,
  Docker Artifact Registry, an unprivileged investigator identity, and a protected KRW 50,000
  project budget.
- Added pinned, credential-free static Terraform CI and a manual live plan workflow gated by
  `TF_PLAN_ENABLED=false`.
- Added plan text redaction, Terraform contract tests, an IAM matrix, cost model, apply/state
  migration runbook, and IaC/WIF ADR.
- Produced local bootstrap and dev plans under ignored `.tmp`; both contain 14 creates and zero
  delete or replacement actions.

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Baseline run | pass | SCN-001 JSON replay; `/healthz` and `/readyz` on a local server |
| Build | pass | `uv build` produced sdist and wheel |
| Format / lint | pass | ruff format/check; Terraform recursive format; TFLint 0.64.0 |
| Type check | pass | `uv run mypy src tests` - no issues |
| Tests | pass | `uv run pytest` - 29 passed; both Terraform mock-provider tests passed |
| Terraform validate | pass | Bootstrap and dev initialized with lockfile read-only and validated |
| Local Terraform plans | pass | Bootstrap 14 creates; dev 14 creates; zero delete/replacement; redacted text reviewed |
| Hosted GitHub Actions | pass | `PR checks` run 31383948768 and `Terraform checks` run 31383949052 succeeded |
| Live Terraform plan | disabled | Repository variable `TF_PLAN_ENABLED=false`; no WIF credentials configured |
| Cloud resource changes | pass | 0 changes; plan/read operations only |
| UI render / input | not-applicable | No R0/M1 end-user UI |

## Blockers and decisions needed

- No M0 blocker remains.
- Bootstrap apply remains blocked on explicit Approval 1.
- Dev apply remains blocked on a later, separate Approval 2 after state migration.
- Do not store actual account, project, billing, app, repository numeric, or credential identifiers
  in the repository.

## Next checkpoint

- Stop at Approval 1. The next authorized change, when explicitly approved, is bootstrap apply and
  state migration only; dev apply remains a separate later approval.

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
