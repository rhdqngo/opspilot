# Current Project State

status: in_progress
phase: long-master-spec defect remediation locally verified; cloud rollout pending
updated: 2026-08-13

## Completed product scope

- Three catalog services (`order-service`, `payment-service`, `inventory-service`) and Korean or
  English relative windows from 1 to 120 minutes.
- Private persistent investigation API with Cloud Tasks, Firestore incidents/investigations,
  immutable report versions, replay/comparison, and minimal Monitoring/Pub/Sub intake.
- Gemini Enterprise Runtime as a thin authenticated API adapter with no direct evidence, model,
  Search, reporting, scoring, or Firestore fallback.
- Fixture/evaluation graph, core 7/7, portfolio 40/40, and isolated approval-gated SCN-008 rollback
  with remediation 12/12.

## Defect-remediation result

- FR-001 parses one incident ID, accepts dev aliases, rejects conflicting IDs and explicit
  prod/stage/qa, and records omitted dev scope as an assumption.
- FR-011 adds a safe server-owned alternative hypothesis and separates evidence-grounded
  containment, mitigation, and root-fix recommendations. SCN-008 `ACT-01 / ROLLBACK_CLOUD_RUN`
  remains unchanged.
- FR-016/FR-017 add shared run/correlation/trace propagation and one privacy-safe structured event
  per logical evidence tool call.
- NFR-006 adds bounded exponential full-jitter retry to Evidence, Runtime API, and remediation
  transports; state-changing POST retries require an idempotency key.
- NFR-011/NFR-012 add source-domain actor/session/query hashes, verified internal caller identities,
  redaction before persistence, and additive legacy Firestore compatibility.
- Runtime run ID is the idempotency key and deterministically maps to one investigation; task and
  report creation remain deduplicated under concurrent submission/redelivery.

## Current validation

- Ruff format/check pass; strict mypy passes over 86 checked files; pytest passes 213/213; package
  build passes.
- Core 7/7, portfolio 40/40, and remediation 12/12 pass with citation and safety gates intact.
- Two 11-file Runtime archives are byte-identical with SHA-256
  `1c7f7b14a95e850a31db1b1d5b6003f2b2acff02c42216a8a7d712dbfd6eda1f`.
- Terraform format/validate, bootstrap 1/1, and dev 8/8 pass after restoring provider caches.
- Fixture replay renders H-01/H-02 and the three recommendation sections. The rebuilt local demo
  image passes 10/10 orders with two concurrent workers; containers were stopped afterward.

## Remaining release validation

- No cloud deployment, image push, Runtime update, Terraform apply/plan, or external-service write
  was performed in this change. The investigation API image and Runtime archive require the normal
  reviewed source-bound release flow.
- After rollout, verify one live Runtime turn uses the same trace/correlation IDs through persisted
  report audit, inspect the fixed `opspilot_tool_call` schema and redacted audit document, and finish
  with Terraform `No changes`.
- GitHub hosted runner workflows remain externally blocked by the previously recorded account
  billing/spending-limit condition; rerun the three manual workflows when runners are available.

## Deferred beyond this repair

Feedback persistence, public simulation/live switching, BigQuery, HTML/approval UI, Cloud Deploy
rollouts, Model Armor, VPC Service Controls/private connectivity, multi-project/A2A/MCP, managed
session/memory, generalized writes, dashboards, full load/cold-start exercises, presentation/video,
and teardown remain deferred.

Historical checkpoints are archived in [mvp-history.md](mvp-history.md).
