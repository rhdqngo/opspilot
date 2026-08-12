# Current Project State

status: active
phase: M7-complete / MVP-minimum-evaluation-ready
updated: 2026-08-12

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

- M7 Approval 1 adds a separate managed-runtime entrypoint without changing the existing M6 ADK
  discovery path, seven-node graph, prompts, report schema, or local fixture/evaluation contracts.
- A deterministic public `before_agent_callback` accepts only a read-only `payment-service`
  investigation over the recent 30-minute window. Other services, windows, commands, and recovery
  requests stop before evidence or model calls; no upper routing model is used.
- The accepted runtime path uses workload ADC, the packaged service catalog, the existing bounded
  evidence layer, and the existing two-model-call graph. User email and identity are ignored.
- Deterministic Python 3.12 source packaging contains package source, catalog, and pinned runtime
  requirements only. Archives and hashes remain under ignored `.tmp` storage and are not uploaded
  as artifacts.
- Terraform defaults `deploy_agent_runtime=false`. Approval 1 applies no API, IAM, Runtime, app,
  repository variable, or other cloud change. The future enabled graph is limited to three API
  addresses, one leaf service-agent IAM grant, one Runtime, and one investigator-role update.
- Enterprise registration is plan-first, fixed-name, unique-app/runtime, idempotent, redacted, and
  process-gated. Approval 1 performed only redacted read-only inventory; no registration or paid
  runtime call occurred.
- GitHub workflows are retained as `workflow_dispatch` only and are skipped as MVP completion
  gates. Local tests and operator zero-drift plans are authoritative. M7 removes its unneeded
  hosted-reader permission diff, so bootstrap requires no apply.
- A fixed gated Runtime probe sends one unsupported-service request, requires zero evidence/model
  calls, and exposes only bounded counts and blocker codes. Runtime output carries a safe audit
  footer without project, Runtime, URL, prompt, token, or user identity values.

## Active blocker

- None for M7. The managed Runtime exposes exactly one async-stream operation,
  `streaming_agent_run_with_events`, with the required `request_json` string input.
- The reviewed Runtime update was exactly `0 create / 1 update / 0 delete / 0 replacement` and
  changed only `spec.class_methods`. Dev remains `36 managed / 37 addresses`; the final operator
  plan is `No changes`. Bootstrap source/state was unchanged and its prior operator plan remains
  zero drift.
- The fixed unsupported-service probe ran once and returned `unsupported_service` with zero
  evidence and model calls. The existing global Enterprise app has one enabled registration for
  the unique Runtime; the final registration plan is an idempotent no-op with zero conflicts.
- The fixed supported Enterprise request used the official global location endpoint and finished
  with HTTP 200 and final state `SUCCEEDED`. The accepted execution window recorded exactly two
  successful global Vertex model invocations, Runtime log entries, and Cloud Trace entries.
- The response and telemetry scans found no prompt, user identifier, email, token, or resource-path
  leakage. Runtime code and validated contracts cap evidence access at six calls, require complete
  logical citation coverage, admit no unauthorized action, and require approval on every retained
  recommendation.
- GitHub Actions remain `workflow_dispatch` only and `skipped-by-policy`; local validation and
  operator plans are the authoritative MVP gates. M7 repository gates and hosted plans were not
  enabled or run.

- M6 Approval 3 preserves the fixed Google ADK 2.5 seven-node graph but replaces the advisory model
  reviewer with a deterministic citation-review function. RCA drafting and report composition are
  the only two tool-free model nodes.
- ADK remains an optional package extra. The default fake model makes no network call and passes
  all seven scenario contracts with exactly two model calls per case. Vertex use remains
  fail-closed behind `OPSPILOT_LIVE_MODEL_ENABLED=true`.
- Model nodes receive no cloud client, credential, identifier, raw filter, URL, request/trace ID,
  or executable tool. Inputs are capped at 64 KiB; node outputs at 2,048 tokens; Approval 9
  calibrates the node timeout to 30 seconds and graph deadline to 75 seconds. Recommendations
  remain approval-required data.
- M6 Approval 1 changes no Terraform, IAM, image, workload, Search corpus, or Google Cloud state.
- The fixed sequential acceptance suite remains SCN-001, SCN-006, and SCN-007. It stops on first
  failure, permits at most six attempted requests, and rejects any model other than
  `gemini-3.5-flash` in `global`.
- Request attempts and byte limits are enforced before transport. The seven-case evaluation is
  fake-only, while live errors are reduced to fixed redacted categories without raw provider data.
- The Approval 2 Vertex batch was executed exactly once. Both provider requests completed with
  HTTP 200, but SCN-001 stopped during client-side reviewer output validation. The precise invalid
  field was not retained, no retry was made, and the process-scoped live gate was removed.
- The original acceptance summary omitted the case-level normalized error code, so the precise
  safe category was not retained. Approval 3 does not reconstruct or coerce that response; it
  removes the model reviewer from the MVP request path.
- The separately approved Approval 3 batch was executed once. SCN-001 completed both remaining
  model nodes but failed the final semantic acceptance predicate after two attempted and successful
  calls. The batch stopped before SCN-006 and SCN-007, the live gate was removed, and no retry was
  made. The summary did not retain which safe report predicate differed.
- M6 Approval 4 preserves those predicates and adds allowlisted case diagnostics for report status,
  root cause, citation coverage, hypothesis/action counts, unauthorized actions, approval flags,
  trajectory, request counts, and exact failure codes. Raw model or transport content is excluded.
- Acceptance is divided into fixed `m6-rca`, `m6-safety`, and `m6-core` suites with two, four, and
  six-request ceilings. The single approved `m6-rca` Vertex execution completed both calls and
  failed only `root_cause_mismatch`: the safe model code was `CONFIG_DB_POOL_EXHAUSTION` rather than
  the fixed `PAYMENT_DB_POOL_EXHAUSTION`. The other suites remained fake-only.
- M6 Approval 5 adds one exact, deterministic alias after citation verification. It requires at
  least two supporting source types plus verified `payment-service` scope, preserves the bounded
  model code separately, and passes only the canonical code to the composer. Fuzzy, case-variant,
  user-provided, and wrong-service mappings remain rejected. The single approved RCA rerun passed
  every preflight but stopped on its first model node with `AGENT_TIMEOUT`: one attempt, zero
  successful responses, zero reported tokens, and no composer request. The gate was removed and no
  retry was made.
- M6 Approval 6 keeps the fixed model, prompts, schemas, taxonomy, trajectory, and 20/60/200-second
  limits. Public ADK callbacks and runner events now retain only bounded monotonic phase timing for
  request validation, response receipt, node output, and graph completion.
- Timeout origin is derived from the last observed phase as response pending, structured-output
  pending, graph-completion pending, acceptance deadline, or unknown. No prompt, response, raw
  exception, wall-clock time, URL, credential, or cloud identifier enters the result.
- Approval 6 authorized no Vertex, Search, or live-evidence request and no cloud change. It created
  the timeout-observability checkpoint used by Approval 7.
- M6 Approval 7 ran one instrumented `m6-rca` suite under the unchanged limits. Both model nodes
  completed with two attempted and successful requests, and timeout origin remained `none`.
- All RCA predicates except taxonomy passed. The model returned
  `DB_CONNECTION_POOL_EXHAUSTION`, which is not the canonical code or sole approved alias, so the
  verifier preserved it and returned only `root_cause_mismatch`.
- The live gate was removed, safety issued zero requests, both Terraform states remained zero
  drift, and no retry, timeout increase, taxonomy expansion, or cloud change was made. That run
  established the former `RCA-taxonomy-blocked / safety-not-approved` checkpoint.
- M6 Approval 8 replaces the brittle model-label alias with synthetic-only canonical evidence
  rules after deterministic citation and direction validation. Payment-pool and prompt-injection
  rules use only verified service, source-type, and quality-flag facts.
- Model labels remain audit data. Scenario IDs, fixture answers, evidence prose, fuzzy matching,
  contradictory/neutral/uncited evidence, and ambiguous matches cannot choose a canonical code.
  Public CLI/schema, model, prompts, graph, budgets, IAM, and cloud resources are unchanged.
- Approval 8 static CI passed, but its one live RCA run completed only the analyst response. The
  composer stayed at `request_validated` until the 20-second boundary, producing
  `model_response_pending` with two attempts and one successful response.
- The classifier was not reached in a completed live report. The gate was removed, safety issued
  zero requests, Terraform remained zero drift, and no retry or timeout change was made. The active
  checkpoint is `evidence-classifier-ready / RCA-composer-timeout / safety-not-run`.
- M6 Approval 9 calibrated only the model-node and graph limits from 20/60 to 30/75 seconds while
  retaining the 200-second suite deadline, model, prompts, schemas, classifier, seven-node graph,
  and two-call case budget.
- The one authorized live `m6-rca` execution and the conditional one live `m6-safety` execution
  passed all three cases with six attempted and successful requests. No retry, live core, Search,
  evidence, Terraform workflow, deployment, or cloud change occurred.

- M5 Approval 1 adds typed Logging, Monitoring, Cloud Run revision, and Agent Search evidence
  contracts behind one fixture/live client boundary. The existing seven fixture reports keep their
  deterministic output while the live adapter remains source-default-off and requires an explicit
  process gate.
- Collection is capped at four concurrent sources, eight logical tool calls, ten API calls, a
  45-second deadline, and source-specific row/byte limits. Partial failure preserves remaining
  evidence, tool errors, data gaps, and observable budget usage.
- The investigator custom role, project binding, and operator leaf-SA Token Creator binding were
  applied through exact reviewed plans. The investigator has seven read/API-use permissions, no
  user-managed key, and no write, invoke, IAM, private-log, import, or Storage access.
- One live SCN-001 run and one investigator evidence batch passed. The batch used four logical
  sources and six API requests with no retry, pagination, error, data gap, or sensitive output.
- Dev state contains 31 managed resources and 32 total addresses. Bootstrap/dev operator plans and
  the manual WIF plan are zero drift; the M5 hosted gates are enabled.

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
| M5 Approval 2: investigator IAM and live acceptance | complete | Bootstrap 1-update, dev 3-create, one bounded SCN-001 evidence batch, hosted zero drift |
| M6 Approval 1: ADK orchestration | complete | Optional ADK 2.5 graph, fake model, seven-case offline evaluation, no cloud/model call |
| M6 Approval 2: live model acceptance | blocked | One approved batch stopped in SCN-001 after 2 attempts / 1 success; no retry |
| M6 Approval 3: deterministic review recovery | blocked | SCN-001 used 2/2 successful calls but failed semantic acceptance; no retry |
| M6 Approval 4: safe RCA checkpoint | blocked | Exact two-call run failed only `root_cause_mismatch`; no retry or contract change |
| M6 Approval 5: strict RCA taxonomy | blocked | Alias validated offline; one bounded run stopped at 1 attempt / 0 success with `AGENT_TIMEOUT`; no retry |
| M6 Approval 6: timeout observability | complete | Content-free phase timing and timeout-origin classification validated offline; no Vertex request |
| M6 Approval 7: final live acceptance | blocked | RCA completed 2/2 calls without timeout but failed only `root_cause_mismatch`; safety was not run |
| M6 Approval 8: evidence classification | blocked | Classifier and static CI passed; live RCA stopped at composer response timeout and safety was not run |
| M6 Approval 9: MVP latency calibration | complete | RCA 1/1 and safety 2/2 passed with 6/6 calls, no timeout, and zero cloud drift |
| M7 Approval 1: Runtime and Enterprise preparation | complete | Fixed natural-language adapter, workload ADC, deterministic package, default-off IaC, guarded registration; cloud changes 0 |
| M7 Approval 2: local-gated deployment | complete | Approved API/IAM foundation is managed; the Runtime dependency and entrypoint blockers were corrected without expanding permissions |
| M7 Approval 5: explicit operation declaration | complete | Exact one-update apply, live operation schema, safe probe, enabled Enterprise registration, supported request, telemetry, and zero drift passed |
| UI Foundation | not-applicable | M6 is API/CLI orchestration only |

## Completed major results

- Added a deployment-discoverable ADK root workflow with a fixed seven-node trajectory and two
  schema-constrained, tool-free reasoning nodes plus deterministic citation review.
- Added a deterministic fake ADK model that infers from bounded evidence rather than fixture ground
  truth; all seven scenario root-cause contracts pass with fourteen total offline model calls.
- Added deterministic citation validation, source-diversity and contradiction scoring, unsafe
  recommendation filtering, prompt-injection isolation, and logical evidence URI normalization.
- Added redacted agent run/eval CLI commands, partial-evidence handling, fail-closed Vertex gating,
  optional dependency locking, offline CI evaluation, runbook, ADR, and threat-model coverage.
- Added zero-generation Vertex readiness checks, fixed three-case `m6-core` acceptance, pre-request
  attempt and byte accounting, a 200-second aggregate deadline, model allowlisting, and safe
  provider-error normalization. The fake acceptance passes all three cases with six calls.
- Ran the approved Vertex acceptance once. It stopped on the SCN-001 reviewer stage after one
  successful response; the live gate was removed and all infrastructure remained unchanged.
- Replaced the reviewer model with fixed duplicate, existence, and evidence-direction checks while
  retaining the reviewer node name and the public report and trajectory contracts.
- Ran the separately approved deterministic-review Vertex batch once. It stopped after SCN-001
  completed two model calls but failed the final acceptance predicate; SCN-006/007 were not called.
- Added fixed RCA, safety, and core acceptance suites plus safe per-predicate diagnostics in summary
  and JSON output without prompt, response, transport, credential, or cloud identifiers.
- Ran the approved RCA-only Vertex checkpoint once. Both requests succeeded; report status,
  trajectory, citation, action, and approval checks passed, while the model root-cause code differed
  from the fixed taxonomy. The gate was removed and no retry was made.
- Added a strict root-cause canonicalizer that recognizes only the exact SCN-001 model alias after
  verified multi-source payment evidence. Public diagnostics retain model and canonical codes plus
  the normalization flag, while the composer receives no model-code provenance field.
- Ran the single approved Approval 5 RCA checkpoint after static CI, readiness, KRW budget, and both
  zero-drift gates passed. The RCA node timed out before a successful response; the safe result was
  `AGENT_TIMEOUT`, non-retryable, with one attempt and zero reported tokens. The composer and safety
  cases were not called.
- Added backward-compatible model-node timing and timeout-origin contracts using monotonic elapsed
  time and public before/after-model plus runner-event boundaries. Fake RCA, safety, core, and full
  evaluation retain their existing call budgets and complete phases.
- Added zero-generation diagnostic visibility for the unchanged 20-second node, 60-second graph,
  and 200-second acceptance limits. Approval 6 issued no live model or evidence request and made no
  infrastructure change.
- Ran the single Approval 7 RCA checkpoint. Both model responses completed in 10,328 ms and 6,047
  ms, the full trajectory and all non-taxonomy RCA predicates passed, and the exact taxonomy
  boundary rejected the unapproved `DB_CONNECTION_POOL_EXHAUSTION` label without coercion. Safety
  was not called.
- Replaced model-label aliases with fixed verified-evidence rules for payment-pool and prompt-
  injection classification. All 142 tests, seven fixtures, fake acceptance suites, container E2E,
  and Terraform static checks passed without a cloud change.
- Ran the one Approval 8 live RCA checkpoint. The analyst completed in 18,156 ms; the composer
  response exceeded the unchanged node boundary. The run stopped at 2 attempts / 1 success and
  safety was not called.
- Calibrated only the MVP execution budget to 30 seconds per model node and 75 seconds per graph;
  the 200-second suite limit and every model, schema, classifier, safety, and call-budget contract
  remained unchanged.
- Completed the single Approval 9 RCA and conditional safety executions. SCN-001, SCN-006, and
  SCN-007 all passed their fixed acceptance predicates with six attempted and successful requests,
  citation coverage 100%, unauthorized actions zero, and timeout origin `none`.

- Added strict UTC and allowlist contracts for bounded log, metric, revision, and knowledge reads.
- Added server-owned Logging/Monitoring filter builders, safe REST error normalization, PII/token
  redaction, logical evidence URIs, response caps, and project/resource identifier suppression.
- Added one `EvidenceClient` protocol with fixture and explicitly gated live implementations;
  fixture smoke completes four sources with four evidence items and zero API calls.
- Added a default-off investigator custom role and project binding with seven read/API-use
  permissions plus an operator Token Creator binding scoped only to the investigator SA. Hosted
  refresh permissions and the M5 workflow gate are applied and validated.
- Applied the exact bootstrap one-update and dev three-create IAM plans. Bootstrap remained 14/15;
  dev reached 31 managed resources and 32 total state addresses.
- Reproduced SCN-001 once and collected six payment timeout occurrences, positive error-ratio and
  latency evidence, a neutral revision snapshot, and the payment runbook through the impersonated
  investigator identity.
- Verified runtime project roles, public principals, and user-managed keys remain zero, while the
  two existing order-to-leaf invoker bindings remain unchanged.

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
| Tests | pass | 183 pytest tests, including M7 AdkApp operation discovery, local streaming rejection, fixed live-probe gating, package determinism, prior M6 acceptance, citation, budget, and redaction contracts |
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
| M5 cloud/IAM apply | pass | Bootstrap exact 1-update; dev exact 3-create; 31 managed / 32 addresses |
| M5 live evidence | pass | One SCN-001; 4 logical sources / 6 API calls; timeout count 6; metrics, neutral revision, runbook and citations accepted |
| M5 hosted plan | pass | WIF read-only; one redacted text artifact; `No changes`; identifier/credential/binary leaks 0 |
| M6 optional install | pass | `uv sync --frozen --extra agent`; ADK 2.5 lock resolved |
| M6 fake agent run | pass | SCN-001 exact seven-node trajectory; two model calls; citation coverage 100% |
| M6 offline evaluation | pass | Seven fixtures passed; fourteen fake model calls; zero cloud/model requests |
| M6 live controls | pass | Zero-call diagnostic contract; fake RCA 1/1, safety 2/2, and core 3/3 with exact two/four/six-call budgets |
| M6 Vertex acceptance | blocked | SCN-001 stopped at call 2; 2 attempted / 1 successful; 1,229 prompt, 275 output, 1,504 total tokens; no retry |
| M6 Approval 3 Vertex acceptance | blocked | SCN-001: 2 attempted / 2 successful; 2,901 prompt, 790 output, 3,691 total tokens; final predicate failed; no retry |
| M6 Approval 4 RCA acceptance | blocked | SCN-001: 2 attempted / 2 successful; 2,893 prompt, 764 output, 3,657 total tokens; only `root_cause_mismatch`; no retry |
| M6 Approval 5 taxonomy | pass | Exact alias, canonical pass-through, wrong-service, insufficient-source, unknown/case-variant, and composer-boundary contracts validated offline |
| M6 Approval 5 Vertex acceptance | blocked | SCN-001: 1 attempted / 0 successful; `AGENT_TIMEOUT`; 0 prompt/output/total tokens; no retry |
| M6 Approval 6 timeout observability | pass | Public phase callbacks, bounded monotonic timings, safe timeout origins, and backward-compatible payload defaults; live calls 0 |
| M6 Approval 7 RCA acceptance | blocked | SCN-001: 2 attempted / 2 successful; 2,947 prompt, 840 output, 3,787 total tokens; only `root_cause_mismatch`; safety calls 0 |
| M6 Approval 8 evidence classifier | pass | Verified service/source/quality rules; model labels and evidence prose excluded; all offline contracts pass |
| M6 Approval 8 Vertex acceptance | blocked | SCN-001: 2 attempted / 1 successful; composer `model_response_pending`; 1,246 prompt, 315 output, 1,561 total tokens; safety calls 0 |
| M6 Approval 9 Vertex acceptance | pass | RCA 1/1 and safety 2/2; 6 attempted / 6 successful; 6,955 prompt, 2,311 output, 10,322 total tokens; timeout origin `none` |
| M6 cloud/IAM/Terraform change | pass | Zero changes; existing M5 state and hosted gates untouched |
| M7 runtime adapter | pass | Fixed payment/30-minute intent; unsupported service/window/action stops with zero cloud/model calls |
| M7 fixture runtime smoke | pass | Existing seven-node graph; exactly two fake model calls; citation coverage 100% |
| M7 runtime package | pass | Pinned Agent Platform SDK; deterministic hash and isolated Python 3.12 SDK/Agent Engines/entrypoint imports passed with zero cloud calls |
| M7 Terraform static | pass | Default-off existing graph; enabled mock graph adds five addresses and one role update only |
| M7 hosted static CI | skipped-by-policy | All three workflows are manual-only; no hosted job or M7 repository gate is required for the MVP |
| M7 local operator gate | pass | Full Python/fixture/package regression, Linux/amd64 non-root Compose 10/10 and SCN-001, TFLint, bootstrap/dev validate and mock plans |
| M7 Runtime operation contract | pass | Official `AdkApp`; only `streaming_agent_run_with_events`; isolated streaming rejection; evidence/model calls 0 |
| M7 cloud/IAM/runtime/app change | pass | Runtime remains 36/37 zero drift; exact one-update operation apply completed, registration is enabled/no-op, supported Enterprise stream reached `SUCCEEDED` with two successful model calls |
| UI render / input | not-applicable | No end-user UI |

## Active safety decisions

- Do not add `allUsers`, broad runtime IAM, or unplanned operator bindings in later milestones.
- Keep the services private, scale-to-zero, and limited to the two order-to-leaf invoker grants.
- Do not repeat the completed recovery apply or introduce public access for later milestones.
- Real account, project, billing, state, service URL, image URI, repository numeric, and credential
  identifiers must not enter tracked files or artifacts.

## Next checkpoint

- Plan the minimum MVP evaluation over the already-deployed Runtime and synthetic dataset. Reuse
  the fixed supported investigation and existing fixture suites; do not add infrastructure or
  broaden the product surface merely to produce an evaluation score.
- Keep Sessions, Memory Bank, OAuth delegation, Agent Gateway, VPC, Model Armor, alert intake,
  remediation, dashboards, and multi-project operation outside the MVP gate.

## Related artifacts

- Master plan: `docs/plans/opspilot_ai_implementation_spec.md`
- Demo runbook: `docs/operations/demo-services.md`
- MVP endpoint recovery: `docs/operations/cloud-run-mvp-recovery.md`
- Superseded migration contingency: `docs/plans/m2_personal_project_migration.md`
- Bootstrap runbook: `docs/operations/bootstrap.md`
- Scenario runbook: `docs/operations/scenarios.md`
- Knowledge runbook: `docs/operations/knowledge.md`
- Live evidence runbook: `docs/operations/live-evidence.md`
- Agent orchestration runbook: `docs/operations/agent-orchestration.md`
- Agent Runtime runbook: `docs/operations/agent-runtime.md`
- Threat model: `docs/security/threat-model.md`
- Access gate: `docs/access-check.md`
- IAM matrix: `docs/iam-matrix.md`
- Cost model: `docs/cost-model.md`
- IaC decision: `docs/decisions/ADR-007-iac-delivery.md`
- Agent Search decision: `docs/decisions/ADR-008-agent-search-corpus.md`
- Live evidence decision: `docs/decisions/ADR-009-live-evidence-boundary.md`
- Agent Runtime decision: `docs/decisions/ADR-010-agent-runtime-enterprise.md`

## Update rules

Update this document only when the active milestone, scope, major result, blocker, validation
state, or next checkpoint changes materially. Do not edit it solely to record the end of a session.
