# Current Project State

status: active
phase: M2-code-complete / M2-ready-for-deploy-approval
updated: 2026-08-10

## Objective

- Build OpsPilot as an evidence-grounded AI incident commander for synthetic Google Cloud
  operations data.

## Active scope

- R0 local investigation and M0 access verification are complete.
- M1 bootstrap and dev foundation remain applied in protected GCS state with zero drift.
- M2 Approval 1 implements order, payment, and inventory as three isolated roles in one non-root
  Linux/amd64 image with in-memory state, structured logs, propagated request/trace IDs, and a
  bounded local load generator.
- Cloud Run IaC is prepared behind `deploy_demo=false`. With the gate disabled, the remote dev plan
  has zero resource and output changes.
- No M2 image, Cloud Run service, runtime identity, invoker grant, Firestore resource, fault
  injector, custom metric, alert, workload, or remediation resource has been created.

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
| M2 Approval 2: Cloud Run deploy | pending approval | Image push, two reviewed plans, apply, telemetry and hosted drift checks |
| UI Foundation | not-applicable | M2 is API, CLI, container, and infrastructure only |

## Completed major results

- Added typed synthetic order, payment authorization, and inventory reservation APIs with strict
  non-PII input contracts and safe partial downstream failures.
- Propagated bounded `X-Request-ID` and Cloud Trace context across parallel order dependencies.
- Added fixed-shape structured stdout logs without request bodies, authorization headers, tokens,
  or user identifiers.
- Built one digest-pinned-base Linux/amd64 image that runs as `65532:65532`; Compose applies a
  read-only filesystem, no capabilities, and `no-new-privileges`.
- Verified all three health/readiness endpoints and a bounded run of 10 attempted, 10 fulfilled,
  and 10 correlated orders.
- Added gated Cloud Run v2 IaC for two existing API state entries, three runtime identities, three
  scale-to-zero services, and two order-to-leaf invoker grants.
- Kept the M1 investigator identity separate and defined no service-account keys, `allUsers`, broad
  project role, data store, scheduled load, fault injection, or remediation resource.
- Extended the redacted access check: M2 permissions pass, candidate-name check pass, conflicts 0.
- Added Cloud Run get/list/getIamPolicy to the CI custom-role definition only; the update is not
  applied and requires an exact Approval 2 bootstrap plan.
- Gated the manual hosted plan on `TF_M2_IMAGE_READY=true`; neither that variable nor the private
  digest URI has been configured.

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Python format / lint | pass | ruff format/check |
| Type check | pass | strict mypy over `src` and `tests` |
| Tests | pass | 43 pytest tests |
| Package build | pass | sdist and wheel |
| R0 baseline | pass | SCN-001 replay; investigation API health/readiness |
| Demo image | pass | Linux/amd64; non-root `65532:65532`; pinned Python and uv bases |
| Demo E2E | pass | Three healthy roles; bounded load 10/10 with 10 request IDs |
| M2 access gate | pass | Redacted permissions and exact candidate-name conflicts 0 |
| Terraform static | pass | recursive fmt, validate, three mock-provider runs, TFLint 0.64.0 |
| Dev gate disabled | pass | Remote state read; zero resource/output changes; temp plan removed |
| Cloud mutation | pass | API/IAM/Artifact Registry/Cloud Run changes 0 |
| UI render / input | not-applicable | No end-user UI |

## Blockers and decisions needed

- M2 Approval 2 is required before any image push, GitHub image variable, CI role update, or Cloud
  Run apply.
- Approval 2 must review the bootstrap custom-role plan (`0 create / 1 update / 0 delete`) separately
  from the dev workload plan (`10 create / 0 update / 0 delete / 0 replacement`).
- Any collision on the three exact candidate names, destructive action, image tag without digest,
  project/billing change, or permission loss is a hard stop.
- An existing non-candidate Cloud Run service is outside Terraform scope and must remain untouched.
- Real account, project, billing, state, service URL, image URI, repository numeric, and credential
  identifiers must not enter tracked files or artifacts.

## Next checkpoint

- Plan and explicitly approve M2 Approval 2: rebuild and local smoke from clean `main`, one operator
  image push, digest capture, exact bootstrap/dev plans, separate applies, private remote E2E,
  Logging/Monitoring verification, hosted zero drift, and cleanup confirmation.

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
