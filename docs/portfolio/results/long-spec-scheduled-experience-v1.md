# OpsPilot Scheduled Incident Experience Verification

Status: **PASSED**  
Verified: 2026-08-15

## Outcome

Gemini Enterprise now exposes a Korean `OpsPilot 빠른 시작` prompt chip with four bounded starter
prompts. A dedicated Cloud Run Job runs request-scoped SCN-001 traffic against synthetic
`dev payment-service` at `5,35 * * * *` in `Asia/Seoul`. Each run is limited to one task with no
Job or Scheduler retry and automatically returns the workload to its healthy state.

The manual release execution and the next scheduled execution both completed successfully. The
scenario produced the expected `5/5 baseline -> 4 fulfilled / 6 failed incident -> 5/5 recovery`
sequence, reported recovery, and matched ground truth. The Scheduler attempt was correlated with a
completed Job execution without storing the raw execution identifier in this record.

## Preview verification

- A 60-minute Korean Preview investigation detected payment connection-pool exhaustion as H-01.
- H-02 remained an explicitly unsupported alternative, and LOG, METRIC, and KNOWLEDGE evidence
  supported the report.
- Containment, mitigation, and root-fix recommendations were present, approval-gated, and cited
  evidence that existed in the persisted report.
- The first turn returned a safe Runtime failure. The same unchanged deployment passed two required
  fresh-chat reruns, while a direct bounded executor reproduction also passed, so the observation is
  retained as a provider/Runtime transient rather than hidden as a product success.
- A separate one-minute query returned no meaningful incident impact, no verified hypothesis, and
  no changing recommendation.

## IAM and infrastructure boundary

- The scenario runner can invoke only the synthetic dev order workload.
- The Scheduler trigger can invoke only the dedicated Job.
- Public or project-wide invoker, Token Creator, Firestore, evidence-read, Runtime, and remediation
  permissions were not added to either new identity.
- The initial plan added exactly seven scheduled-experience addresses. A Cloud Run minimum-memory
  validation was corrected to `512Mi`; the bounded recovery plan added only the remaining three
  addresses.
- Cloud Scheduler's omitted `retryCount` is its documented zero default. The Terraform source uses
  that default to preserve no-retry behavior without a perpetual zero-versus-null drift.
- Final bootstrap and dev Terraform plans both report `No changes`.

## Source-bound validation

The source-bound gate passed 289/289 pytest, Ruff format/check, strict mypy, package build, core
7/7, portfolio 40/40, remediation 12/12, Terraform bootstrap 1/1 and dev 10/10, and two
byte-identical Runtime packages.

Cloud project identifiers, URLs, identities, image digests, Job/Scheduler identifiers, Runtime
resource names, trace/run/investigation IDs, and browser captures are intentionally omitted. Raw
release and UI evidence remains under `.tmp` and is not versioned.
