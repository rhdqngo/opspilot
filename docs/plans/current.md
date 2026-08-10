# Current Project State

status: active
phase: M2-deployed / remote-smoke-blocked
updated: 2026-08-11

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud
  operations data.

## Active scope

- R0 local investigation, M0 access verification, and the M1 foundation are complete.
- M2 Approval 1 implements order, payment, and inventory as three isolated roles in one non-root
  Linux/amd64 image with in-memory state, structured logs, propagated request/trace IDs, and a
  bounded local load generator.
- M2 Approval 2 pushed one immutable image and applied the reviewed bootstrap update and exact
  10-create dev plan. Remote state now contains 24 managed resources and is zero drift.
- Three private Cloud Run services are Ready, but their default URLs and the authenticated Cloud
  Run proxy return a pre-container 404. Remote E2E, request telemetry, and hosted plan remain gated.

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
| M2 Approval 2: Cloud Run deploy | blocked after apply | Infrastructure applied; inherited route restriction blocks remote smoke |
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

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Python format / lint | pass | ruff format/check |
| Type check | pass | strict mypy over `src` and `tests` |
| Tests | pass | 43 pytest tests |
| Package build | pass | sdist and wheel |
| R0 baseline | pass | SCN-001 replay; investigation API health/readiness |
| Local demo E2E | pass | Linux/amd64, non-root, three healthy roles, bounded load 10/10 |
| M2 access gate | pass | Redacted deploy and telemetry-read permissions; candidate conflicts 0 |
| Terraform static | pass | recursive fmt, validate, three mock-provider runs, TFLint 0.64.0 |
| Hosted static CI | pass | Python/container and bootstrap/dev Terraform jobs on the deployment baseline |
| Bootstrap apply | pass | Exact `0 create / 1 update / 0 delete`; operator zero drift |
| Dev apply | pass | Exact `10 create / 0 update / 0 delete`; 24 managed resources; operator zero drift |
| Runtime security | pass | Three Ready private services; digest match; keys/project roles/public principals 0 |
| Remote smoke | blocked | Google frontend 404 before container; request logs and metrics absent |
| Hosted plan | gated | Plan gate false; image-ready and digest variables absent |
| UI render / input | not-applicable | No end-user UI |

## Blockers and decisions needed

- The organization-level access-policy perimeter cannot be read by the current operator. An
  administrator must confirm inherited VPC Service Controls or Cloud Run route restrictions.
- Do not add `allUsers`, broad runtime IAM, or unplanned operator bindings to bypass the blocker.
- The existing non-candidate Cloud Run service remained outside Terraform scope.
- Real account, project, billing, state, service URL, image URI, repository numeric, and credential
  identifiers must not enter tracked files or artifacts.

## Next checkpoint

- Resolve the inherited Cloud Run route restriction, then run authenticated 10-order E2E,
  request/trace and latency metrics checks, configure the private GitHub image variables, and run
  hosted read-only zero drift before marking M2 complete.

## Related artifacts

- Master plan: `docs/plans/opspilot_ai_implementation_spec.md`
- Demo runbook: `docs/operations/demo-services.md`
- Bootstrap runbook: `docs/operations/bootstrap.md`
- Access gate: `docs/access-check.md`
- IAM matrix: `docs/iam-matrix.md`
- Cost model: `docs/cost-model.md`
- IaC decision: `docs/decisions/ADR-007-iac-delivery.md`

## Update rules

Update this document only when the active milestone, scope, major result, blocker, validation
state, or next checkpoint changes materially. Do not edit it solely to record the end of a session.
