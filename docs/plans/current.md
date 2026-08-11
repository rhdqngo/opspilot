# Current Project State

status: active
phase: M2-safe-path-recovery / rollout-pending
updated: 2026-08-11

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud
  operations data.

## Delivery priority

- MVP core proceeds in order: remote workload, reproducible incident, Search, live read-only
  evidence, ADK orchestration, managed runtime/enterprise registration, and minimum evaluation.
- Advanced security/connectivity, automatic alert intake, approval execution, multi-project
  operation, and expanded dashboards are post-MVP optional work.
- Optional work cannot enter an MVP acceptance gate or Terraform plan without a separate approval.

## Active scope

- R0 local investigation, M0 access verification, and the M1 foundation are complete.
- M2 Approval 1 implements order, payment, and inventory as three isolated roles in one non-root
  Linux/amd64 image with in-memory state, structured logs, propagated request/trace IDs, and a
  bounded local load generator.
- M2 Approval 2 pushed one immutable image and applied the reviewed bootstrap update and exact
  10-create dev plan. Remote state now contains 24 managed resources and is zero drift.
- Three private Cloud Run services are Ready. The pre-container 404 is a confirmed conflict with
  Cloud Run's reserved `z`-suffix paths, not a VPC, IAM, ingress, revision, or image failure.
- A repeatable `route-check` CLI now reduces the fixed-service route state to identifier-free
  counts, booleans, HTTP status classes, and one bounded blocker code.
- One reviewed `0 create / 3 update / 0 delete / 0 replacement` revision refresh completed with
  the same image and identities. The approved recovery replaces the demo endpoints and probes with
  `/health` and `/ready`, then updates only the same three services with a new image digest.

## Milestones

| Milestone | Status | Evidence / notes |
| --- | --- | --- |
| Repository Bootstrap | complete | Python package scaffold validated from the repository root |
| R0 Local Skeleton | complete | Fixture workflow, strict validation, API/CLI baseline |
| M0 Access and decisions | complete | Redacted `Edu_687` access gate |
| Private GitHub baseline | complete | Private `opspilot/main`; no history rewrite |
| M1 Bootstrap infrastructure | complete | Protected remote state, numeric WIF, read-only plan identity |
| M1 Dev foundation | complete | 14 managed resources; operator and hosted zero drift |
| M2 Approval 1: local workload | complete | Three healthy containers; 10/10 normal orders; no cloud write |
| M2 Approval 2: Cloud Run deploy | recovery approved | Safe-path image and exact three-service update pending |
| UI Foundation | not-applicable | M2 is API, CLI, container, and infrastructure only |

## Completed major results

- Added typed synthetic order, payment authorization, and inventory reservation APIs with strict
  non-PII input contracts and safe partial downstream failures.
- Propagated bounded `X-Request-ID` and Cloud Trace context across parallel order dependencies.
- Built one Linux/amd64 image that runs as `65532:65532`; local Compose completed 10/10 orders.
- Extended the redacted M2 access gate with Logging and Monitoring read permissions.
- Applied the exact bootstrap custom-role update with three Cloud Run read permissions and no write
  permission, then verified zero drift.
- Pushed one commit-SHA image, applied the exact 10-create dev plan, and verified 24 managed
  resources with no delete, replacement, public principal, runtime key, or project runtime role.
- Verified three Ready, private, digest-pinned, scale-to-zero services with distinct identities and
  order-only invoker access to payment and inventory.
- Kept `TF_PLAN_ENABLED=false`; neither `TF_M2_IMAGE_READY` nor the private digest variable is
  configured while remote invocation is blocked.
- Corrected the Cloud Run inventory: the current project contains the three managed M2 candidates
  and no additional non-candidate service.
- Replaced the policy-specific route hypothesis with a generic endpoint diagnostic and kept
  advanced connectivity outside the active MVP implementation.
- Applied the single permitted three-service revision refresh; managed resources remained 24,
  the digest and identities were unchanged, and no IAM or other resource changed.
- Confirmed the endpoint root cause against Cloud Run's reserved-path contract: `/healthz` is
  intercepted before the container while authenticated `/health` reaches FastAPI.

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Python format / lint | pass | ruff format/check |
| Type check | pass | strict mypy over `src` and `tests` |
| Tests | pass | 52 pytest tests, including delayed-log readiness and generic endpoint classification |
| Package build | pass | sdist and wheel |
| R0 baseline | pass | SCN-001 replay; investigation API health/readiness |
| Local demo E2E | pass | Linux/amd64, non-root, three healthy roles, bounded load 10/10 |
| M2 access gate | pass | Redacted deploy and telemetry-read permissions; candidate conflicts 0 |
| Terraform static | pass | recursive fmt, validate, three mock-provider runs, TFLint 0.64.0 |
| Hosted static CI | pass | Python/container and bootstrap/dev Terraform jobs on the deployment baseline |
| Bootstrap apply | pass | Exact `0 create / 1 update / 0 delete`; operator zero drift |
| Dev apply | pass | Exact `10 create / 0 update / 0 delete`; 24 managed resources; operator zero drift |
| Controlled revision refresh | pass | Exact `0 create / 3 update / 0 delete`; same image/identities; operator zero drift |
| Runtime security | pass | Three Ready private services; digest match; keys/project roles/public principals 0 |
| Route diagnostic | recovery pending | Diagnostic now targets the Cloud Run-safe `/health` path |
| Remote smoke | recovery pending | New safe-path image and three-service rollout required |
| Hosted plan | gated | Plan gate false; image-ready and digest variables absent |
| UI render / input | not-applicable | No end-user UI |

## Blockers and decisions needed

- Do not add `allUsers`, broad runtime IAM, or unplanned operator bindings to bypass the blocker.
- Apply only a fresh exact `0 create / 3 update / 0 delete / 0 replacement` plan that changes the
  three service image digests and probe paths. No repeated apply or public access is permitted.
- Real account, project, billing, state, service URL, image URI, repository numeric, and credential
  identifiers must not enter tracked files or artifacts.

## Next checkpoint

- Validate the safe-path implementation, push one immutable image, apply the exact three-service
  plan, and complete remote smoke, telemetry, security, and hosted zero-drift acceptance.

## Related artifacts

- Master plan: `docs/plans/opspilot_ai_implementation_spec.md`
- Demo runbook: `docs/operations/demo-services.md`
- MVP endpoint recovery: `docs/operations/cloud-run-mvp-recovery.md`
- Superseded migration contingency: `docs/plans/m2_personal_project_migration.md`
- Bootstrap runbook: `docs/operations/bootstrap.md`
- Access gate: `docs/access-check.md`
- IAM matrix: `docs/iam-matrix.md`
- Cost model: `docs/cost-model.md`
- IaC decision: `docs/decisions/ADR-007-iac-delivery.md`

## Update rules

Update this document only when the active milestone, scope, major result, blocker, validation
state, or next checkpoint changes materially. Do not edit it solely to record the end of a session.
