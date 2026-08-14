# Current Project State

**English** | [한국어](current.ko.md)

status: formal_agent_verified
phase: formal Incident Commander deployed and Gemini Enterprise Preview QA verified
updated: 2026-08-15

## Verified product scope

- OpsPilot investigates `order-service`, `payment-service`, and `inventory-service` individually or
  together in `dev`, `staging`, and synthetic `prod-sim`.
- Korean and English aliases, relative or explicit 1-120 minute windows, six symptom classes, and
  QUICK/STANDARD/DEEP depth are supported. Actual production remains explicitly rejected.
- `/internal/v2/runtime/turns` resolves investigation, refinement, concise report explanation,
  status, report-version comparison, capability guidance, and the bounded remediation-request
  intent. The legacy Runtime and public investigation contracts remain compatible.
- Firestore conversation context is pseudonymous, structured, and limited to 24 hours. Prompts,
  raw user/session identifiers, and evidence bodies are not stored in conversation context.
- Operational evidence is restricted to the requested interval. A pre-window Cloud Run revision
  may inform server-side diff calculation but never appears in Evidence, Timeline, or Sources.
- QUICK uses logs and core metrics; STANDARD/DEEP add changes and knowledge while the three-service
  path remains within the 20-tool/provider-call budget.
- Direct signals enter the bounded RCA/verification graph. No-signal and model-failure paths return
  evidence-backed healthy or inconclusive reports without fabricated hypotheses or changing
  recommendations.
- The Runtime can create one eligible `WAITING_APPROVAL` rollback request only for
  `prod-sim payment-service`. Approval and execution remain in the isolated M8 control plane.
- Gemini Enterprise publishes a Korean quick-start prompt chip. An opt-in, request-scoped SCN-001
  Job runs against `dev payment-service` at minutes 5 and 35 so a recent 60-minute investigation
  can demonstrate live synthetic detection without manual incident preparation.

## Deployment and permission boundary

- One Runtime, one private investigation API, Firestore, Cloud Tasks, and Agent Search control plane
  serve the three synthetic environments. The existing Gemini Enterprise registration still points
  to the same Runtime resource.
- The Runtime service account has a dedicated custom role containing exactly
  `resourcemanager.projects.get`. This replaces the less reliable metadata workaround required when
  that permission was absent; no broad viewer, evidence, datastore, task, or remediation permission
  was added to the Runtime.
- Runtime can invoke the investigation bridge only. Task, alert, remediation approval, and executor
  boundaries remain separate, private, and negatively tested.
- The final feature correction changed only the investigation API in place. Runtime, IAM, M8,
  registration, data schema, and synthetic workloads did not change in that cycle.
- The scheduled experience uses two dedicated identities: the runner invokes only the dev order
  workload, and the Scheduler trigger invokes only its Job. Neither receives project-wide invoker,
  Token Creator, evidence, persistence, Runtime, or remediation permissions.

## Final validation

- Initial formal-agent source-bound release: 277/277 pytest, Ruff format/check, strict mypy over 92 source files,
  package build, core 7/7, portfolio 40/40, remediation 12/12, Terraform bootstrap 1/1, and dev 8/8.
- Two 11-file Runtime packages are byte-identical. The API image is linux/amd64, non-root,
  health/ready checked, and registry-digest bound.
- Three-environment managed smoke and SCN-001 passed the expected `5/5 → 4/6 → 5/5` sequence with
  recovery and matching ground truth.
- The managed conversation matrix passed all required contracts. One multi-service turn encountered
  a provider transport transient; both prescribed same-deployment reruns passed with complete
  backend invariants, so it is retained as a documented provider transient rather than a product
  defect.
- Gemini Enterprise Preview verified a Korean single-service investigation, a three-service
  investigation, a same-session concise follow-up, localized capability guidance, and explicit
  actual-production rejection. Investigations emitted one progress and one final; immediate turns
  emitted one final only.
- A final live regression pass found and corrected the concise healthy-report summary so that it
  now returns status, localized user impact, and conclusion instead of claiming that an unrequested
  hypothesis was missing. The exact Preview phrase is covered by the 277-test source-bound gate and
  passed after an API-only in-place update.
- A subsequent positive Preview pass executed SCN-001 exactly once, verified `5/5 → 4/6 → 5/5`
  recovery, and confirmed that Preview identifies payment connection-pool exhaustion as H-01 with
  a zero-support H-02, three evidence types, three approval-gated recommendation categories, and
  valid persisted citations. One live-summary Korean copy gap found during the pass was corrected;
  the final source-bound gate now contains 278 tests.
- The final investigation linked four Runtime stages and four unique tool events to one
  investigation, one task attempt, and report version 1 with shared trace/correlation identity.
  Application payload scans found no raw sentinel, identity, project, URL, or permission error.
- Cloud Run is Ready and the final Terraform plan using the same image digest and Runtime archive
  reports `No changes`.
- GitHub portfolio documentation now uses the formal-agent release as its front-page baseline,
  separates current evidence from historical QA records, and publishes an MIT license without
  exposing raw cloud or browser identifiers.
- Korean mirrors cover the README and every portfolio document linked from its documentation table;
  English remains the canonical technical contract and both entrypoints cross-link explicitly.
- Administrator-facing app information and a first-time participant guide now document access,
  the 10-minute experience path, report interpretation, expected rejections, privacy, and recovery
  from common Preview conditions in both English and Korean.
- The scheduled experience passed manual and automatic `5/5 -> 4/6 -> 5/5` execution, a positive
  60-minute Preview investigation, a healthy one-minute regression, 289/289 pytest, Terraform dev
  10/10, and final bootstrap/dev `No changes` plans.
- Sanitized evidence: [formal-agent v3](../portfolio/results/long-spec-formal-agent-v3.md),
  [scheduled incident experience v1](../portfolio/results/long-spec-scheduled-experience-v1.md),
  and the [verification evidence index](../portfolio/results/README.md).

## External non-blocking item

- The three manual GitHub workflows remain affected by the existing hosted-runner billing or
  spending-limit condition. Local and managed-environment gates are authoritative until the hosted
  runner executes steps normally.

## Next checkpoint

- Treat the deployed formal agent as the release baseline.
- Use the root README and verification evidence index as the portfolio documentation entrypoints.
- Give reviewers the app-information and first-time-user guides instead of sharing account
  credentials or relying on verbal setup instructions.
- Keep the scheduled scenario enabled for the bounded educational demo; pause it through the
  documented runbook when the experience is not required.
- Resume only for a new requirement, a reproducible product defect, or a provider incident that
  violates the documented transient policy.
- Keep raw browser captures, cloud identifiers, and execution mappings under `.tmp` only.

## Deferred beyond this milestone

Feedback persistence, actual production connectivity, public simulation/live switching, BigQuery,
owned HTML/approval UI, Cloud Deploy rollout, Model Armor, VPC Service Controls/private networking,
multi-project/A2A/MCP, managed memory, generalized writes, dashboards, full load/cold-start suites,
presentation/video, and teardown remain deferred.

Historical checkpoints are archived in [mvp-history.md](mvp-history.md).
