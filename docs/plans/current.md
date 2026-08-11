# Current Project State

status: active
phase: M5-approval-2-code-ready / M5-live-apply-pending
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

- M5 Approval 1 adds typed Logging, Monitoring, Cloud Run revision, and Agent Search evidence
  contracts behind one fixture/live client boundary. The existing seven fixture reports keep their
  deterministic output while the live adapter remains explicitly disabled.
- Collection is capped at four concurrent sources, eight logical tool calls, ten API calls, a
  45-second deadline, and source-specific row/byte limits. Partial failure preserves remaining
  evidence, tool errors, data gaps, and observable budget usage.
- The investigator custom role, project binding, and operator leaf-SA Token Creator binding are
  defined behind `enable_live_evidence=false`; no IAM or other cloud resource has changed yet. The
  M5 hosted gate remains unset and no live evidence request has been issued in Approval 2.

- M4 recovery created only the explicit schema and Standard Search engine after hardening both the
  array-item and title-key schema contracts. Remote dev state now contains 28 managed resources and
  29 total state addresses with operator zero drift.
- One FULL import completed with 13 successes and zero failures. The protected bucket contains
  thirteen document objects, one manifest, and one current snapshot; sync plan is now a no-op.
- Approval 3 added redacted HTTP/RPC diagnostics and corrected project-number canonicalization for
  the engine-owned serving config. The zero-query diagnostic, one fixed probe, and the separate ten-
  query acceptance batch all passed without corpus, import, Terraform, or IAM changes.
- Approval 4 added only `serviceusage.services.use` to the CI plan custom role. The reviewed
  bootstrap plan was an exact one-resource in-place update, the applied permission set matches the
  source contract, and API enable/disable permissions remain absent.
- Bootstrap and dev operator plans are zero drift. The manual WIF plan succeeded on its first run
  and produced one redacted `No changes` artifact with no identifier, credential, or binary plan.

- M4 Approval 1 is complete in the repository. Thirteen synthetic knowledge documents, a
  deterministic hash catalog, ten retrieval queries, typed Search normalization, guarded sync and
  smoke commands, and a default-off four-resource Agent Search boundary are implemented.
- The M4 redacted gate confirms the operator has the required permissions and the dedicated
  knowledge resources remain Terraform-owned without modifying existing Search assets.
- `deploy_knowledge=false` remains the source default while the live environment explicitly manages
  the four approved resources. `TF_M4_KNOWLEDGE_READY=true` and `TF_PLAN_ENABLED=true` now enable
  only the manual read-only plan workflow.

- M3 is complete. Seven deterministic incident fixtures cover grounded, contradictory,
  insufficient, and malicious evidence cases.
- SCN-001 is the only live-capable MVP scenario. Its strict request-scoped 5/10/5 profile was
  reproduced three times with automatic recovery and no persistent fault state or management
  endpoint.
- The M3 rollout updated only the three existing Cloud Run services. Terraform still adds no
  scenario resource or IAM binding, and both operator and hosted plans are zero drift.
- R0 local investigation, M0 access verification, and the M1 foundation are complete.
- M2 Approval 1 implements order, payment, and inventory as three isolated roles in one non-root
  Linux/amd64 image with in-memory state, structured logs, propagated request/trace IDs, and a
  bounded local load generator.
- M2 Approval 2 pushed one immutable image and applied the reviewed bootstrap update and exact
  10-create dev plan. Remote state now contains 24 managed resources and is zero drift.
- Three private Cloud Run services are Ready and remotely accepted through Cloud Run-safe
  `/health` and `/ready` paths. The former 404 was a reserved `z`-suffix path conflict.
- A repeatable `route-check` CLI now reduces the fixed-service route state to identifier-free
  counts, booleans, HTTP status classes, and one bounded blocker code.
- The safe-path recovery pushed one immutable image and applied an exact
  `0 create / 3 update / 0 delete / 0 replacement` plan. Managed resources remain 24 and both
  operator and hosted plans are zero drift.

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
| M2 Approval 2: Cloud Run deploy | complete | Private remote E2E, telemetry, security, and hosted zero drift passed |
| M3 Approval 1: incident corpus | complete | Seven offline contracts; bounded SCN-001 local injection; no cloud write |
| M3 Approval 2: live incident | complete | Exact three-service update; three recovered live runs; telemetry and zero drift passed |
| M4 Approval 1: knowledge and IaC boundary | complete | 13 documents, 10 local retrieval contracts, guarded sync, default-off four-resource graph |
| M4 Approval 2: Search apply/import | complete | Four resources, 13-document import, fixed probe, and live retrieval 10/10 passed |
| M4 Approval 3: hosted validation | complete | Live Search accepted; Approval 4 added one quota-consumption permission and hosted plan returned `No changes` |
| M5 Approval 1: live evidence boundary | complete | Typed collectors, fixture smoke, redaction, default-off two-resource IAM graph |
| M5 Approval 2: investigator IAM and live acceptance | in progress | Bootstrap 1-update, dev 3-create, one bounded SCN-001 evidence batch |
| UI Foundation | not-applicable | M5 is API, CLI, evidence tooling, and infrastructure only |

## Completed major results

- Added strict UTC and allowlist contracts for bounded log, metric, revision, and knowledge reads.
- Added server-owned Logging/Monitoring filter builders, safe REST error normalization, PII/token
  redaction, logical evidence URIs, response caps, and project/resource identifier suppression.
- Added one `EvidenceClient` protocol with fixture and explicitly gated live implementations;
  fixture smoke completes four sources with four evidence items and zero API calls.
- Added a default-off investigator custom role and project binding with seven read/API-use
  permissions plus an operator Token Creator binding scoped only to the investigator SA. Hosted
  refresh permissions and the M5 workflow gate are prepared but unapplied.

- Added five runbooks, three prior RCAs, three architecture documents, one ownership document, and
  one malicious-instruction regression document with strict UTC metadata and logical citations.
- Added deterministic catalog hashing, ten local top-five retrieval contracts, bounded Search hit
  normalization, allowlisted filter construction, stale-document warnings, and untrusted-content
  flags.
- Added plan-by-default knowledge synchronization. Apply and live Search each require an explicit
  environment gate; import success is required before the remote snapshot advances.
- Prepared a protected regional knowledge bucket plus global data store, explicit schema, and
  Standard Search engine behind `deploy_knowledge=false`; existing Search assets are untouched.
- Extended the hosted plan identity with Search get/list only, added a false M4 workflow gate, and
  verified M4 permissions and zero candidate conflicts without identifiers or cloud mutation.
- Applied the fresh exact schema/engine two-create recovery plan. Dev state reached 28 managed
  resources and 29 addresses without changing IAM, Cloud Run, budget, network, or existing Search
  assets.
- Completed one FULL import with 13 successes, zero failures, fifteen bucket objects, and a no-op
  follow-up sync.
- Added zero-query readiness and fixed-case probe commands, bounded RPC error classification, and
  canonical serving-config validation without exposing project, query, URL, token, or raw errors.
- Completed one KQ-001 probe and an independent ten-query acceptance batch: expected document
  top-five coverage 10/10, citation metadata 100%, and malicious-content safety flag present.
- Added only `serviceusage.services.use` to the hosted plan custom role through an exact bootstrap
  in-place update. No binding, WIF, API, Search, corpus, or dev resource changed.
- Verified bootstrap and dev operator zero drift and one successful manual hosted plan with a
  single redacted `No changes` text artifact. Approval 4 issued no Search request or import.

- Added SCN-001 through SCN-007 as validated ground-truth contracts and generalized fixture replay
  so contradictions, insufficient evidence, and malicious knowledge are handled per scenario.
- Added a default-off request-scoped SCN-001 path with strict context validation and deterministic
  six-of-ten payment pool timeout behavior; baseline and recovery requests remain normal.
- Added a bounded scenario CLI, three-run Compose CI path, fixed-shape scenario logs, and a
  Terraform/GitHub gate that introduces no resource while Approval 2 is inactive.
- Pushed one immutable M3 image and applied the reviewed exact
  `0 create / 3 update / 0 delete / 0 replacement` plan; managed resources remained 24.
- Reproduced SCN-001 three times against the private workload. All runs matched the expected
  5/10/5 contract and returned to a 5/5 recovery baseline.
- Correlated 60 request IDs and traces across all three services, observed exactly 18 payment
  timeout events and 36 incident-only application 5xx entries, and found no sensitive-log or
  non-incident 5xx issue.
- Verified request-count and latency points for all services, expected 5xx points for order and
  payment, unchanged runtime security, and operator plus hosted zero drift.

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
- Configured the private immutable image variable and retained `TF_PLAN_ENABLED=true` and
  `TF_M2_IMAGE_READY=true` after hosted read-only zero-drift validation.
- Corrected the Cloud Run inventory: the current project contains the three managed M2 candidates
  and no additional non-candidate service.
- Replaced the policy-specific route hypothesis with a generic endpoint diagnostic and kept
  advanced connectivity outside the active MVP implementation.
- Applied the single permitted three-service revision refresh; managed resources remained 24,
  the digest and identities were unchanged, and no IAM or other resource changed.
- Confirmed the endpoint root cause against Cloud Run's reserved-path contract: `/healthz` is
  intercepted before the container while authenticated `/health` reaches FastAPI.
- Pushed the clean safe-path image once, applied only the three reviewed service updates, and
  verified `/health` and `/ready` as unauthenticated `403` and authenticated `200` on all roles.
- Completed 10/10 authenticated orders with ten request IDs and traces correlated across all three
  services; request/application 5xx and sensitive-log findings were zero.

## Verification state

| Check | Result | Command / evidence |
| --- | --- | --- |
| Install / restore | pass | `uv sync --frozen` |
| Python format / lint | pass | ruff format/check |
| Type check | pass | strict mypy over `src` and `tests` |
| Tests | pass | 111 pytest tests, including M5 evidence/error/redaction contracts, safe Search diagnostics, seven scenario contracts, and bounded SCN-001 execution |
| Package build | pass | sdist and wheel |
| R0 baseline | pass | SCN-001 replay; investigation API health/readiness |
| Local demo E2E | pass | Linux/amd64, non-root, three healthy roles, bounded load 10/10 |
| M2 access gate | pass | Redacted deploy and telemetry-read permissions; candidate conflicts 0 |
| Terraform static | pass | recursive fmt, validate, three mock-provider runs, TFLint 0.64.0 |
| M3 scenario Terraform | pass | Default-off gate; existing resource/IAM graph only; no cloud write |
| M3 live apply | pass | Exact `0 create / 3 update / 0 delete / 0 replacement`; 24 managed resources |
| M3 live scenario | pass | Three runs: baseline 5/5, incident 4/6, recovery 5/5; automatic recovery |
| M3 log correlation | pass | 60 request IDs/traces across three services; expected incident-only 5xx; sensitive findings 0 |
| Hosted static CI | pass | Python/container and bootstrap/dev Terraform jobs on the deployment baseline |
| Bootstrap apply | pass | Exact `0 create / 1 update / 0 delete`; operator zero drift |
| Dev apply | pass | Exact `10 create / 0 update / 0 delete`; 24 managed resources; operator zero drift |
| Controlled revision refresh | pass | Exact `0 create / 3 update / 0 delete`; same image/identities; operator zero drift |
| Runtime security | pass | Three Ready private services; digest match; keys/project roles/public principals 0 |
| Safe-path service update | pass | Exact `0 create / 3 update / 0 delete / 0 replacement`; 24 managed resources |
| Route diagnostic | pass | Three unauthenticated 403, three authenticated 200; `route_ready`; no pre-container 404 |
| Remote smoke | pass | 10/10 fulfilled; request IDs and traces correlated across three services; 5xx 0 |
| Cloud Monitoring | pass | Request-count/latency for three services; expected M3 5xx points on order/payment |
| Hosted plan | pass | WIF read-only; redacted `No changes`; identifier leaks and binary artifacts 0 |
| M4 corpus validation | pass | 13 documents, deterministic metadata/hash catalog, 10 query contracts |
| M4 local retrieval | pass | 10/10 expected documents in top five; citation metadata complete; malicious text treated as data |
| M4 access gate | pass | Required permissions; candidate bucket/data store/engine conflicts 0; identifier-free output |
| M4 Terraform static | pass | Default-off zero drift contract; enabled graph contains exactly four protected Search resources |
| M4 operator default-off plan | pass | Remote state 24 managed resources; `deploy_knowledge=false`; zero drift |
| M4 operator enabled plan | pass | Disposable read-only plan: exact `4 create / 0 update / 0 delete / 0 replacement`; plan removed |
| M4 bootstrap apply | pass | Exact read-only custom-role `0 create / 1 update / 0 delete`; 14 managed resources; zero drift |
| M4 dev recovery apply | pass | Exact schema/engine `2 create / 0 update / 0 delete / 0 replacement`; 28 managed resources; operator zero drift |
| M4 corpus import | pass | Fifteen objects; one FULL import; 13 success / 0 failure; snapshot updated; sync no-op |
| M4 live Search diagnostic | pass | Search 0; one serving config; filter-ready schema; 13 indexed; index errors 0 |
| M4 live Search probe | pass | One fixed KQ-001 request; expected document and citation metadata present |
| M4 live Search smoke | pass | Exact ten-query batch; 10/10 top-five; citation complete; malicious instruction not executed |
| M4 hosted plan | pass | Exact custom-role 1-update; first manual WIF plan returned redacted `No changes`; gates enabled |
| M5 typed evidence contracts | pass | UTC/allowlist/filter/redaction/normalization/partial-failure/call-budget tests |
| M5 fixture evidence smoke | pass | Four sources, four evidence items, four logical calls, zero API calls |
| M5 Terraform static | pass | Default-off existing graph; enabled graph adds one custom role and two bindings only |
| M5 cloud/IAM apply | not-run | Separate Approval 2 required; no live telemetry or Search request issued |
| UI render / input | not-applicable | No end-user UI |

## Active safety decisions

- Do not add `allUsers`, broad runtime IAM, or unplanned operator bindings in later milestones.
- Keep the services private, scale-to-zero, and limited to the two order-to-leaf invoker grants.
- Do not repeat the completed recovery apply or introduce public access for later milestones.
- Real account, project, billing, state, service URL, image URI, repository numeric, and credential
  identifiers must not enter tracked files or artifacts.

## Next checkpoint

- M5 Approval 2 must separately review and apply the bootstrap custom-role one-update and dev
  investigator IAM three-create plans, then impersonate the investigator without a key.
- Run one bounded live SCN-001 and exactly one log, two metric, one revision, and one Search
  collection. Require logical citations and preserve revision evidence as neutral unless actual
  configuration data supports a causal claim.
- Do not reimport knowledge, deploy an image, add custom metrics, invoke a model, or enable the M5
  hosted gate before live acceptance and operator zero drift succeed.

## Related artifacts

- Master plan: `docs/plans/opspilot_ai_implementation_spec.md`
- Demo runbook: `docs/operations/demo-services.md`
- MVP endpoint recovery: `docs/operations/cloud-run-mvp-recovery.md`
- Superseded migration contingency: `docs/plans/m2_personal_project_migration.md`
- Bootstrap runbook: `docs/operations/bootstrap.md`
- Scenario runbook: `docs/operations/scenarios.md`
- Knowledge runbook: `docs/operations/knowledge.md`
- Live evidence runbook: `docs/operations/live-evidence.md`
- Access gate: `docs/access-check.md`
- IAM matrix: `docs/iam-matrix.md`
- Cost model: `docs/cost-model.md`
- IaC decision: `docs/decisions/ADR-007-iac-delivery.md`
- Agent Search decision: `docs/decisions/ADR-008-agent-search-corpus.md`
- Live evidence decision: `docs/decisions/ADR-009-live-evidence-boundary.md`

## Update rules

Update this document only when the active milestone, scope, major result, blocker, validation
state, or next checkpoint changes materially. Do not edit it solely to record the end of a session.
