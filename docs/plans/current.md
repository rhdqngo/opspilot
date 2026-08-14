# Current Project State

status: formal_agent_verified
phase: formal Incident Commander deployed and Gemini Enterprise Preview QA verified
updated: 2026-08-14

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

## Final validation

- Source-bound local release: 277/277 pytest, Ruff format/check, strict mypy over 92 source files,
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
- The final investigation linked four Runtime stages and four unique tool events to one
  investigation, one task attempt, and report version 1 with shared trace/correlation identity.
  Application payload scans found no raw sentinel, identity, project, URL, or permission error.
- Cloud Run is Ready and the final Terraform plan using the same image digest and Runtime archive
  reports `No changes`.
- Sanitized evidence: [long-spec-formal-agent-v2.md](../portfolio/results/long-spec-formal-agent-v2.md).

## External non-blocking item

- The three manual GitHub workflows remain affected by the existing hosted-runner billing or
  spending-limit condition. Local and managed-environment gates are authoritative until the hosted
  runner executes steps normally.

## Next checkpoint

- Treat the deployed formal agent as the release baseline.
- Resume only for a new requirement, a reproducible product defect, or a provider incident that
  violates the documented transient policy.
- Keep raw browser captures, cloud identifiers, and execution mappings under `.tmp` only.

## Deferred beyond this milestone

Feedback persistence, actual production connectivity, public simulation/live switching, BigQuery,
owned HTML/approval UI, Cloud Deploy rollout, Model Armor, VPC Service Controls/private networking,
multi-project/A2A/MCP, managed memory, generalized writes, dashboards, full load/cold-start suites,
presentation/video, and teardown remain deferred.

Historical checkpoints are archived in [mvp-history.md](mvp-history.md).
