# Current Project State

status: in_progress
phase: M8-gate-a-local-verified / image-push-approval-pending
updated: 2026-08-12

## Delivered MVP

- R0-M1: Python package, private repository, remote Terraform state, WIF, and KRW 50,000 budget.
- M2: three private scale-to-zero Cloud Run demo services and authenticated order E2E.
- M3: bounded SCN-001 incident and automatic recovery.
- M4: 13-document synthetic Agent Search corpus and deterministic local retrieval.
- M5: bounded read-only Logging, Monitoring, revision, and Search evidence collection.
- M6: seven-node ADK graph, deterministic citation review, verified-evidence taxonomy, and two
  tool-free model nodes with 30/75-second limits.
- M7: managed `AdkApp` Runtime, one async-stream operation, and existing Gemini Enterprise app
  registration.

## Completed lean cut

- Removed milestone-only access, route, Search diagnostic, model acceptance, Runtime probe, and
  Enterprise registration interfaces.
- Kept the investigation API, demo workload, replay/scenario tools, corpus validation/sync/local
  retrieval, fixture evidence smoke, seven-case fake evaluation, and deterministic Runtime package.
- The Runtime archive contains only the production dependency closure. CLI, API/demo, fixtures,
  tests, docs, Terraform, corpus sync, and diagnostic modules must not enter the archive.
- Runtime responses contain only an `IncidentReport` or one fixed safe error. Model-origin taxonomy
  and acceptance/timing diagnostics are not public output.

## Non-negotiable product boundary

- Fixed `payment-service`, recent 30-minute, read-only Runtime scope.
- No caller-supplied project, URL, token, resource name, Logging/Monitoring filter, or serving config.
- Fixture/eval retains the seven-node graph, two model calls, 30-second model timeout, and 75-second
  graph deadline.
- Live Runtime uses parallel bounded evidence, conditional one-call RCA, and 3/4/5/10/18-second
  transport/source/collection/RCA/whole-invocation limits.
- Citation integrity, deterministic verified-evidence classification, prompt-injection isolation,
  action removal, approval-required recommendations, and sensitive-data redaction.

## Enterprise session recovery checkpoint

- Runtime logs identified the previous Preview failure as `managed_session_permission_denied`:
  Enterprise supplied a session ID and the default `AdkApp` path attempted
  `aiplatform.sessions.create` three times before evidence or model work.
- The single-turn MVP now supplies ADK's supported `InMemorySessionService` through
  `session_service_builder`. Session and user identifiers stay process-local and are not stored,
  logged, or included in reports. Managed Sessions and conversation continuity remain post-MVP.
- Cloud resources, IAM, Enterprise registration, model, prompt, schema, data, operation schema, and
  scaling remain unchanged. The reviewed plan and apply were exactly one Runtime source
  archive/hash in-place update: `0 create / 1 update / 0 delete / 0 replacement`.
- Dev remains `36 managed / 37 addresses`; the Runtime is Ready and the post-apply operator plan is
  `No changes`.
- One Enterprise-shaped out-of-scope `streamQuery` with a session ID returned HTTP 200, emitted one
  safe rejection event, and produced no session permission error. Product tests prove the rejection
  path performs zero evidence and model work.
- The original Korean Gemini Enterprise Preview question was accepted after this recovery and
  returned progress followed by a complete inconclusive report.

## Enterprise zero-event recovery checkpoint

- The supported Preview question reached the Runtime three times with HTTP 200 and started bounded
  evidence/model work, but the Enterprise bridge received no event before each stream ended.
- Root cause: the prior `before_agent_callback` performed the complete investigation before ADK
  could yield its first event. This was separate from the already-fixed managed-session permission.
- The deployed Runtime now uses a custom `BaseAgent` generator. Accepted requests emit one visible
  partial progress event before the handler and one turn-complete report or fixed safe failure.
  Rejections still stop before the handler and emit one final event.
- An 18-second outer deadline and safe exception conversion prevent ordinary failures from closing
  a stream without a final safe event. Cancellation is logged after progress and propagated.
- Runtime stage logs contain only event name, stage, and elapsed time, excluding prompt, user,
  session, project, generated request identifiers, counters, status, and raw exception content.
  Concurrent-request privacy is covered by tests.
- This recovery made the first event visible, but later Preview evidence showed the live seven-node
  Workflow could still finish model generation without `graph_complete` or `final_emitted`. That
  finalization defect is closed by the live hybrid pipeline below.
- Full zero-event recovery validation passed: 107 pytest tests, ruff format/check, strict mypy, package build, Runtime
  allowlist/determinism, fixture evaluation, and Terraform format/validate/test.
- The final 17-file Runtime archive hash is
  `980a050e601a9f86db58b113ae4a5270d928458960fa1e672ff0a806d53744b5`. The saved Terraform plan
  and apply changed only the Runtime source archive: `0 create / 1 update / 0 delete / 0
  replacement`; the post-apply plan was `No changes`.
- A direct accepted `streamQuery` returned HTTP 200, emitted progress as soon as the response stream
  opened, and emitted the fixed safe final 84.9 seconds later. Logs recorded `accepted`,
  `evidence_complete`, `graph_complete`, and `final_emitted`, with no managed-session creation,
  zero-event close, or unhandled-exception pattern.
- A final deployed out-of-scope smoke returned HTTP 200 and one final rejection event; the emitted
  structured log contained only `event`, `stage`, and `elapsed_ms`.
- The user-provided Gemini Enterprise Preview response proves the original Korean question now
  receives progress and a final report, closing the zero-event failure.

## Report-quality polish checkpoint

- Progress content now ends in two newlines so concatenating clients preserve the Markdown heading.
- Successful zero-point metric queries remain evidence with `missing_points`, create explicit data
  gaps for `error_ratio` and `latency_p95`, make the collection partial, and create no tool error.
- Knowledge documents remain in Sources but are excluded from incident Timeline; empty hypotheses
  render a deterministic `None verified with the available evidence.` fallback.
- Validation passed 108 pytest tests, ruff format/check, strict mypy, build, fixture evaluation 7/7
  with 14 model calls, Runtime allowlist/determinism, and Terraform format/validate/test.
- The final 17-file archive SHA-256 is
  `50d595a35a241494e05ca448ecebf7789e08190f3a212423bb30d5d616c3c3ac`. The saved Terraform plan
  and apply changed only the Runtime source archive: `0 create / 1 update / 0 delete / 0
  replacement`; the post-apply plan was `No changes`.
- Two immediate out-of-scope smoke attempts returned HTTP 429 before the handler. Runtime logs at
  `2026-08-12T08:52:33Z` show ADK startup failed while Resource Manager returned a transient 504.
  No IAM, telemetry, registration, or Runtime configuration changed. Managed capacity recovered;
  the `2026-08-12T08:56:30Z` recheck returned HTTP 200 and one final rejection event, with no
  managed-session creation, zero-event close, or unhandled-exception pattern.
- A final Preview presentation check was not run because no authenticated Preview tab was available;
  the previously supplied Preview response remains the authoritative zero-event recovery evidence.

## Live finalization stabilization checkpoint

- The live Runtime no longer executes the seven-node Workflow. It collects LOG, METRIC, CHANGE, and
  KNOWLEDGE concurrently, computes quality deterministically, and calls one RCA model only when
  valid supporting operational evidence spans at least two source types. The zero-point live request
  is the expected zero-model path.
- Evidence and reasoning stay on native coroutines so the 18-second deadline, `CancelledError`, and
  async-generator `GeneratorExit` cancel child work. Only bounded urllib transport uses a worker
  thread.
- RCA timeout, model exception, invalid output, or failed citation verification becomes an
  evidence-backed inconclusive report. Whole-Runtime timeout or report serialization failure alone
  uses the fixed safe error. Final events remain `partial=false`, `turnComplete=true`.
- Privacy-safe stage logs are `accepted`, `evidence_complete`, `reasoning_skipped`,
  `reasoning_complete`, `reasoning_timeout`, `final_emitted`, `timeout`, and `cancelled`.
- Validation passed 114 pytest tests, ruff format/check, strict mypy, build, fixture evaluation 7/7
  with 14 model calls, Runtime allowlist/determinism, and Terraform format/validate/test. Two
  17-file archives produced SHA-256
  `b985460ccdb29aa0e97e99121d5ae0a97e87963592c341afebcd793d32b38549`.
- Terraform plan/apply changed only the existing Runtime source archive: `0 create / 1 update / 0
  delete / 0 replacement`. The post-apply operator plan returned `No changes`.
- The deployed out-of-scope warm-up returned HTTP 200. Direct accepted `streamQuery` produced the
  progress event at 0.65 seconds and the complete deterministic report at 2.25 seconds; Runtime
  `final_emitted` occurred at 1.42 seconds with `reasoning_skipped` and no model call.
- Three consecutive new-chat Preview runs showed progress at 5.29, 4.71, and 4.75 seconds and the
  final quality-correct report. Each preserved both metric data gaps, kept KNOWLEDGE out of Timeline
  and in Sources, rendered the empty-hypothesis fallback, and recommended no action. All three log
  sequences reached `final_emitted`; the third final was emitted 6.51 seconds after browser submit,
  and Gemini Enterprise recorded its `StreamAssist` answer at 8.35 seconds (insert ID
  `3250j0e6hvk9`).
- Across the three-run Preview window, managed Session creation, zero-event termination, unhandled
  exceptions, and residual model calls were all absent. The MVP is accepted as
  `enterprise-preview-stable`.

## Input-language localization checkpoint

- Runtime input classification now records an internal `OutputLanguage`: any Hangul character
  selects `ko`; every other allowed input selects `en`. Classification happens before rejection,
  while the public operation, request JSON, session behavior, region, IAM, registration, and model
  ID remain unchanged.
- Progress, report headings and narrative, data gaps, assumptions, rejection, configuration error,
  RCA degradation, and fixed safe failure are rendered in the selected language. Evidence IDs,
  service and metric names, and evidence titles/summaries remain verbatim for traceability.
- The optional RCA input carries `output_language`. Korean natural-language RCA fields must contain
  Hangul, and English fields must not; a mismatch follows the existing localized inconclusive
  fallback. CLI, API, fixture, and evaluation callers retain the default English renderer.
- Validation passed 126 pytest tests, ruff format/check, strict mypy, build, fixture evaluation 7/7
  with 14 model calls, Runtime allowlist/determinism, and Terraform format/validate/test. Two
  identical 17-file archives produced SHA-256
  `57d6bb23f9d910225673e9d6d0d88d052a31685a40233db0b981345c9cebd880`.
- Terraform plan/apply changed only the existing Runtime source archive: `0 create / 1 update / 0
  delete / 0 replacement`. The post-apply operator plan returned `No changes`.
- Direct deployed checks returned one localized Korean rejection event in 1.77 seconds, a Korean
  accepted stream with progress at 0.78 seconds and final report at 10.16 seconds, and an English
  accepted stream with progress at 0.81 seconds and final report at 2.29 seconds. Both accepted
  reports preserved the zero-point metric gaps, evidence language, Timeline/Sources boundary, and
  empty-hypothesis fallback.
- New-chat Gemini Enterprise checks matched the input language. Korean progress/final DOM appeared
  at 7.32/8.43 seconds and English at 6.96/8.52 seconds. Their Runtime `final_emitted` stages took
  1.12 and 1.69 seconds, with insert IDs `6a7c540900025452c2be2f39` and
  `6a7c543b0000bfd9d86aa039`. The window contained no managed Session creation, zero-event close,
  unhandled exception, or residual model call; only the already-scoped-out OTEL export 403 remained.
- Verification checkpoint `ko-en-output-matched` is complete. The milestone remains
  `M7-complete / enterprise-preview-stable / mvp-accepted`.

## Portfolio completeness checkpoint

- The master implementation specification is now explicitly the M0-M10 North Star. This file is
  the Lean MVP v1 plan of record, with FR-001 through FR-025 and NFR-001 through NFR-020 mapped in
  `docs/requirements-traceability.md` as implemented, partial, or deferred.
- The local investigation API no longer converts arbitrary requests into SCN-001. Its injected
  fixture executor accepts only `payment-service` and `INC-2026-0001`/SCN-001, rejects unsupported
  service or incident scope with 422, and exposes `execution_mode` and `scenario_id` in status.
- `core-v1` remains 7/7 with 14 fake model-node calls. `portfolio-v1` adds 40 versioned cases with
  the reviewed 14/6/4/4/4/4/4 category distribution and passed 40/40 with 80 calls. RCA top-1,
  top-3, required-tool recall, citation coverage, and evidence-ID validity were all 1.000; P50/P95
  fixture duration was 12/15 ms in the final recorded run and no release gate failed.
- Agent and Runtime executions now carry random anonymous `RUN-…` identifiers. Runtime stage logs
  and one terminal run summary correlate source status/error codes and reasoning outcome without
  prompt, user/session identity, project, evidence payload, or raw exception content. Twenty
  concurrent Enterprise-shaped requests remain isolated in tests.
- Portfolio documentation now includes architecture and trust-boundary diagrams, evaluation and
  demo instructions, the requirements matrix, and a non-executing cleanup plan. The cleanup command
  cannot call Terraform or cloud APIs and keeps every destructive operation separately approved.
- Validation passed 129 pytest tests, ruff format/check, strict mypy across 51 source files, package
  build, core and portfolio evaluation, deterministic 17-file Runtime packaging, and Terraform
  format/validate/test. The two Runtime archives matched SHA-256
  `a1eb4b5c548fb6f88396ca506c9e5f16512e093d21e80b23ee239cd87ebaa79b`.
- No cloud resource, IAM binding, Enterprise registration, model, public Runtime schema, or
  deployment changed. No Preview request was repeated.

## Portfolio release checkpoint

- A standard-library release runner now aggregates formatting, lint, strict typing, pytest, core
  and portfolio evaluation, deterministic Runtime packaging, build, Git whitespace checks, and
  optional Terraform validation. Failed runs remain local and cannot replace published evidence.
- The sanitized source of record is generated at
  `docs/portfolio/results/portfolio-release-v1.{json,md}` and drives the README metrics block. It
  records the baseline commit, dirty state, source-tree fingerprint, environment class, metrics,
  and named failures without random run IDs, hostnames, user paths, prompts, or raw exceptions.
- The final release run passed 143 tests with 1 policy skip, core `7/7`, portfolio `40/40`, all five primary
  quality metrics at `1.000`, two identical 17-file Runtime archives, package build, and Terraform
  format/validate/test. Exact fixture durations and the Runtime SHA-256 remain generated values in
  the published artifact rather than copied into this durable narrative.
- The cross-platform portfolio demo passed its actual Compose path: healthy load `10/10`, bounded
  SCN-001 ground truth and recovery, four-source fixture evidence, evidence-linked agent report,
  portfolio gate, non-executing cleanup plan, and guaranteed Compose teardown. Its first live run
  also exposed and closed a transient readiness disconnect handling defect.
- Manual GitHub validation remains `workflow_dispatch` only. It now evaluates both suites and
  uploads the portfolio JSON/Markdown artifact for 30 days even when the gate fails.
- Docker Desktop was started only to run the local Compose validation. No cloud deployment,
  Terraform apply, IAM mutation, Enterprise request, push, or PR was performed.
- The baseline was fixed as implementation commit `c4e274b` and evidence commit `9a6146f`.
  Published evidence intentionally names `c4e274b` as the clean source it verified.

## M8 approval-gated remediation checkpoint

- M8 is a separate control plane. The existing investigation API, Gemini Enterprise Runtime, and
  investigator identity remain read-only and receive no Firestore, Workflow, executor, or Cloud Run
  update permission.
- `opspilot.remediation.api:create_app` implements Group-IAM-backed ID-token verification, public
  request/show/decision endpoints, canonical idempotency, explicit 15-minute expiry, actor hashing,
  and development self-approval audit. Callback URLs are held only in a 24-hour TTL collection.
- The internal executor supports only `opspilot-dev-payment`, rechecks source/target revision,
  known-good digest, service etag, plan hash, approval expiry, and execution lease, and calls Cloud
  Run v2 with `updateMask=traffic`. Response loss is resolved by reading the serving target before
  any retry. It cannot invoke the order service or write terminal state.
- The control API independently finalizes execution: it confirms target traffic, runs exactly ten
  authenticated orders, records auxiliary 10-minute Monitoring-window point counts, and stores the
  terminal verification result in the Firestore remediation transaction.
- SCN-008 adds a revision-scoped `payment-failure` profile, bounded operator prepare/reset plans,
  live read-only evidence collection, a versioned report, and ten-order reproduction/recovery
  checks. Execute mode remains unauthorized until the separate cloud-change checkpoint.
- `remediation-v1` contains 12 reviewed success and safety cases and now executes the real in-memory
  coordinator/executor boundaries instead of comparing a static outcome table. Domain/API/executor
  tests cover hash binding, legal transitions, expiration, conflicting idempotency, self-approval,
  stale etag, response loss, terminal failures, and twenty concurrent approvals/execution calls
  with one lease and one traffic update.
- Terraform defaults `enable_remediation=false`. The enabled plan contains the named Native
  `opspilot-dev` database, two TTL fields, three isolated service accounts, an external IAM-protected
  control API, internal-only single-concurrency executor, 15-minute callback Workflow, approver
  Group binding, and a payment-only conditional update role. The payment resource move preserves
  state and ignores only traffic drift.
- The final local M8 release check passed: 167 pytest tests, Ruff format/check, strict mypy over 74
  source files, wheel/sdist build, core `7/7`, portfolio `40/40`, remediation `12/12`, two identical
  17-file Runtime archives with unchanged SHA-256
  `a1eb4b5c548fb6f88396ca506c9e5f16512e093d21e80b23ee239cd87ebaa79b`, Terraform
  format/validate, bootstrap
  `1/1`, and dev `7/7` tests. No generated Lean release evidence was republished.
- Actual image build/push, Terraform plan/apply, IAM negative smoke, faulty revision activation,
  approval E2E, sanitized cloud evidence, reset, and final `No changes` proof remain blocked on the
  plan's explicit user approval gates.

## M8 cloud release safeguards checkpoint

- SCN-008 now separates the captured payment image input as
  `OPSPILOT_SCN008_KNOWN_GOOD_IMAGE_URI`; `TF_VAR_remediation_image_uri` is control/executor-only.
- Prepare requires a healthy 10/10 baseline before fault activation and persists the trusted
  recovery target before faulty orders or investigation work. Reset verifies a final 10/10.
- The new caller-input-free abort path compares local and Firestore recovery facts, revalidates the
  exact service, etag, both same-digest revisions and traffic, restores known-good traffic, removes
  the failure profile, and is idempotent after successful recovery. Abort makes portfolio publish
  permanently ineligible for that run.
- Remediation request/decision commands accept stable idempotency keys and reuse them across three
  bounded transport retries. Show supports JSON polling.
- `scripts/m8_release.py` provides read-only preflight, post-apply, E2E, and publish phases. It
  rejects unsafe Terraform action summaries, aborted/incomplete E2E, non-zero drift, and sensitive
  identifiers. No cloud evidence exists until all separately approved gates pass.
- The safeguard release gate passed 181 pytest tests, Ruff format/check, strict mypy over 78 source
  files, package build, core `7/7`, portfolio `40/40`, remediation `12/12`, two identical 17-file
  Runtime archives with the unchanged SHA-256
  `a1eb4b5c548fb6f88396ca506c9e5f16512e093d21e80b23ee239cd87ebaa79b`, Terraform format/validate,
  bootstrap `1/1`, dev `7/7`, and all prepare/reset/abort plan commands.
- Safeguards are fixed in implementation commit `c01438c` plus Windows preflight and lazy-health
  corrections through `a7a4869`. The final clean preflight passed on `a7a4869`, and that source was
  also revalidated by the full 181-test gate.
- Docker Desktop was started for Gate A local validation. The Linux/amd64 image built from the
  clean source with the frozen production dependency set, ran as `65532:65532`, and returned the
  expected control and executor health boundaries without ADC or cloud calls. Temporary smoke
  containers were removed.
- Artifact Registry push is the next explicit approval checkpoint. Terraform plan/apply, faulty
  activation, approval, and cloud evidence remain separately blocked.

## Validation authority

- Local ruff, strict mypy, pytest, package build, fixture eval, knowledge/evidence smoke, Compose
  E2E, and Terraform static/operator validation are authoritative.
- GitHub workflows remain `workflow_dispatch` only and `skipped-by-policy`.

## Post-MVP

VPC/perimeter controls, Model Armor, alert intake, generalized remediation, managed Sessions/Memory,
dashboard, BigQuery, multi-project support, and broader evaluation remain M9+ and require separate
approval.
