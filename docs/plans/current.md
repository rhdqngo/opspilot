# Current Project State

status: active  
phase: M0-complete / M1-baseline  
updated: 2026-08-10

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud operations data.

## Active scope

- R0 local skeleton is complete: typed contracts, deterministic SCN-001 evidence workflow, API, CLI, tests, and GitHub Actions definition.
- M0 cloud access verification for the `Edu_687` account alias and the currently configured gcloud project is complete.
- The active scope is the private GitHub baseline followed by non-applying M1 Terraform implementation.
- No cloud mutation, live telemetry, ADK, Gemini Enterprise integration, Terraform apply, or remediation execution is active.

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| Bootstrap | complete | uv package scaffold merged from isolated staging and validated from root |
| R0 Local Skeleton | complete | 19 tests, strict mypy, ruff, package build, CLI replay, API health/readiness |
| M0 Access and decisions | complete | redacted command reports ready; KRW billing, effective IAM, and existing Gemini app path verified |
| M1 Infrastructure foundation | in-progress | private GitHub baseline and static IaC implementation are active; cloud apply remains prohibited |
| UI Foundation | not-applicable | R0 is API/CLI only; Gemini Enterprise is the intended later user surface |

## Completed major results

- Added Python 3.12 packaged application with a reproducible `uv.lock`.
- Added allowlisted request parsing, typed evidence/report contracts, deterministic scoring, and secret-like value redaction.
- Added parallel fixture collectors with partial-failure reporting and SCN-001 evidence.
- Added FastAPI investigation/status/report endpoints and JSON/Markdown CLI replay.
- Added a least-privilege GitHub Actions PR workflow with no cloud credentials.

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Baseline run | pass | CLI SCN-001 replay; `/healthz` and `/readyz` on local server |
| Build | pass | `uv build` produced sdist and wheel |
| Format / lint | pass | `uv run ruff format --check .`; `uv run ruff check .` |
| Type check | pass | `uv run mypy src tests` — no issues |
| Tests | pass | `uv run pytest` — 19 passed |
| Hosted GitHub Actions | unverified | no Git remote or pushed workflow exists |
| Cloud authentication | pass | gcloud user token and ADC reauthentication completed |
| Cloud access gate | pass | redacted M0 access command reports ready |
| UI render / input | not-applicable | no R0 end-user UI |

## Blockers and decisions needed

- No M0 blocker remains.
- Terraform apply, API activation, IAM changes, and budget creation still require separate approval.
- Do not store real account, project, billing, app, or credential identifiers in the repository.

## Next checkpoint

- Create the private GitHub baseline, implement and validate static M1 Terraform, then stop at the apply approval gate.

## Related artifacts

- Master plan: `docs/plans/opspilot_ai_implementation_spec.md`
- Access gate: `docs/access-check.md`
- Decisions: `docs/decisions/ADR-001-runtime.md` through `ADR-004-remediation-boundary.md`
- UI Foundation: not applicable for R0

## Update rules

Update this document only when the active milestone, scope, major result, blocker, validation state, or next checkpoint changes materially. Do not edit it solely to record the end of a session.
