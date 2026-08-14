# Current Project State

status: enterprise_qa_verified
phase: Gemini Enterprise Preview and managed backend QA passed on the final source-bound candidate
updated: 2026-08-14

## Completed product scope

- Three catalog services (`order-service`, `payment-service`, `inventory-service`) and Korean or
  English relative windows from 1 to 120 minutes.
- Private persistent investigation API with Cloud Tasks, Firestore incidents/investigations,
  immutable report versions, replay/comparison, and minimal Monitoring/Pub/Sub intake.
- Gemini Enterprise Runtime as a thin authenticated API adapter with no direct evidence, model,
  Search, reporting, scoring, or Firestore fallback.
- Fixture/evaluation graph, core 7/7, portfolio 40/40, and isolated approval-gated SCN-008 rollback
  with remediation 12/12.

## Long-spec defect remediation

- FR-001 parses one incident ID, accepts dev aliases, rejects conflicting IDs and explicit
  prod/stage/qa, and records omitted dev scope as an assumption.
- FR-011 preserves the verified top cause, adds a safe non-assertive H-02 when appropriate, and
  separates cited containment, mitigation, and root-fix/prevention recommendations.
- FR-016/FR-017 propagate one run/correlation/trace identity through Runtime, API, task, executor,
  and report, with one privacy-safe structured event per logical evidence tool.
- NFR-006 uses bounded exponential full-jitter retry with deadline enforcement and requires an
  idempotency key before retrying a state-changing POST.
- NFR-011/NFR-012 retain only source-domain actor/session/query hashes and redacted query text;
  additive optional fields preserve legacy Firestore reads.

## Validation state

- Final source-bound preflight passes 237/237 pytest, Ruff format/check, strict mypy over 88 files,
  package build, core 7/7, portfolio 40/40, remediation 12/12, Terraform bootstrap 1/1, and dev 8/8.
- Two 11-file Runtime packages are byte-identical. The implementation image is linux/amd64,
  non-root, health-checked, and digest-bound to the implementation commit.
- Reviewed Terraform apply changed only the investigation API in place during the final recovery;
  the Agent Runtime resource and Gemini Enterprise registration target remained stable.
- Remote SCN-001 passed baseline 5/5, incident 4 fulfilled and 6 failed, recovery 5/5, with ground
  truth matched.
- Managed Runtime direct smoke returned exactly one progress and one final event. The persisted
  report contains H-01/H-02, all three recommendation classes, and citations contained in Sources.
- Twenty concurrent submissions with one run identity produced one investigation, one task
  attempt, and one report version. Four callers received the completed report and sixteen reached
  the bounded 12-second wait response; persisted idempotency remained intact.
- Firestore/report/log scans found no synthetic email or token sentinel. Runtime and direct API
  audit hashes, shared trace/correlation linkage, four structured tool events, and negative auth
  boundaries passed.
- Cloud Run is Ready, the Runtime is callable, public invoker is absent, and only the three intended
  service identities can invoke the investigation service.
- Gemini Enterprise admin view showed OpsPilot enabled and bound to the unchanged Runtime before
  Preview v2 began.
- Final Terraform plan with the same image digest and Runtime archive reports `No changes`.
- Sanitized evidence: [long-spec-preqa-v1.md](../portfolio/results/long-spec-preqa-v1.md).

## Gemini Enterprise Preview QA

- Chrome QA executed against the existing enabled OpsPilot registration without changing Runtime,
  IAM, M8, demo images, or Terraform configuration.
- SCN-001 passed `5/5` baseline, `4 fulfilled / 6 failed` incident, and `5/5` recovery. The English
  Preview report passed H-01/H-02, four evidence types, three recommendation classes, and citation
  containment.
- All eight unsupported-environment/service/ID/action cases were rejected before investigation or
  report creation. The accepted privacy case persisted redaction markers and domain hashes with no
  raw sentinel in Firestore, report, Runtime, or tool logs.
- QA is blocked because a healthy persisted report was not delivered after Preview progress, an
  unused incident ID produced an API 422 in the Korean flow, the persisted default-DEV assumption
  was not rendered, and tool-call events omitted `run_id`.
- Post-QA healthy orders passed `5/5`, Cloud Run remained Ready, and Terraform remained `No changes`.
- Sanitized QA evidence: [long-spec-enterprise-qa-v1.md](../portfolio/results/long-spec-enterprise-qa-v1.md).
- Iteration candidate 1 starts the handler before progress, creates valid unused incidents,
  localizes Korean narrative and assumptions, and propagates run ID into live tool audit. Its
  limited two-address deployment passed managed Runtime, privacy, idempotency, trace, audit, IAM,
  registration, and Ready gates.
- Candidate 1 passed three consecutive healthy Preview chats. Every chat emitted one progress and
  one final, persisted one investigation/task/report, and linked four Runtime stages and four tool
  events with no hypothesis or changing recommendation.
- The first managed SCN-001 attempt exposed a QA-runner cold-start defect: after an operator setup
  attempt stayed on the local default URL, the actual remote run recovered `5/5` and matched the
  `4/6` incident split but counted only `3/5` baseline orders. Preview QA stopped at that evidence.
- Iteration candidate 2 adds a bounded authenticated `/ready` warm-up before the counted SCN-001
  baseline. It passes 235/235 pytest, Ruff, strict mypy over 88 files, build, core 7/7, portfolio
  40/40, remediation 12/12, Terraform bootstrap 1/1 and dev 8/8. Its two 11-file Runtime packages
  remain byte-identical to candidate 1, so the managed Runtime is unaffected.
- Candidate 2 used a one-address Cloud Run image rollout. The first healthy Preview chat passed,
  but the next chat and both prescribed same-deployment retries remained in Preview processing.
  The final retry rendered no final even though Runtime logged `final_emitted` in 6.896 seconds and
  Firestore, Task, report, trace, and four tool events were complete and unique.
- This is the plan's confirmed provider-failure safety stop. The remaining v2 matrix was not sent.
  A reviewed one-address recovery plan restored candidate 1's last Preview-healthy image; direct
  Runtime returned two events, healthy load passed 5/5, Cloud Run is Ready, and Terraform reports
  `No changes`.
- Sanitized iterative evidence:
  [long-spec-enterprise-qa-v2.md](../portfolio/results/long-spec-enterprise-qa-v2.md).
- QA v3 stopped before its Preview canary because the direct Runtime SDK received only progress for
  45.270 seconds. Runtime still recorded `timeout` and `final_emitted`, while Firestore completed one
  task and report v1 with linked trace/correlation IDs. No browser query or deployment occurred.
- Candidate 1 remains deployed. After a scale-to-zero `3/5` first probe, warm normal traffic passed
  `5/5`; Cloud Run is Ready and Terraform remains `No changes`.
- Sanitized v3 resume evidence:
  [long-spec-enterprise-qa-v3.md](../portfolio/results/long-spec-enterprise-qa-v3.md).
- The final delivery candidate buffers the accepted investigation before emitting progress and final
  back-to-back and aligns the API, HTTP, and Runtime deadlines. Three consecutive direct SDK calls
  and the Preview canary delivered exactly one progress and one final event.
- SCN-001 now warms the authenticated end-to-end order path. The final clean cycle passed baseline
  `5/5`, incident `4 fulfilled / 6 failed`, recovery `5/5`, and matching ground truth.
- Three healthy chats, English and Korean incident cases, environment omission, privacy redaction,
  and all eight rejection boundaries passed in new Preview chats. Every final positive run persisted
  one investigation/task/report, four Runtime stages, four tool events, shared trace/correlation IDs,
  valid audit hashes, H-01/H-02, three action classes, and contained citations.
- One provider display error had a complete 3.485-second backend result; both prescribed
  same-deployment retries and the final clean privacy case passed, so it is recorded as transient.
- Normal traffic passed `5/5`, Cloud Run is Ready with private IAM, the Runtime and registration are
  stable, and the final Terraform plan reports `No changes`.
- Sanitized passing evidence:
  [long-spec-enterprise-qa-v4.md](../portfolio/results/long-spec-enterprise-qa-v4.md).

## External non-blocking item

- The three manual GitHub workflows were dispatched against the implementation commit. Each job
  ended with zero executed steps under the existing hosted-runner billing/spending-limit condition.
  The managed and local gates above are authoritative until Hosted Runner service is available.

## Next checkpoint

- Preserve the verified deployment inputs and use the v4 record as the release baseline. No product,
  Runtime, IAM, registration, M8, or Terraform change is pending for Enterprise QA.
- Re-run the three hosted workflows when the external runner billing or spending-limit condition is
  cleared; their zero-step result remains non-blocking because all local and managed gates passed.

## Deferred beyond this milestone

Feedback persistence, public simulation/live switching, BigQuery, HTML/approval UI, Cloud Deploy
rollouts, Model Armor, VPC Service Controls/private connectivity, multi-project/A2A/MCP, managed
session/memory, generalized writes, dashboards, full load/cold-start exercises, presentation/video,
and teardown remain deferred.

Historical checkpoints are archived in [mvp-history.md](mvp-history.md).
