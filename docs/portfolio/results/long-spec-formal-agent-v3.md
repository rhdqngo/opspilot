# OpsPilot Positive Incident Preview Verification

Status: **PASSED**  
Verified: 2026-08-14

## Outcome

SCN-001 was executed exactly once against the synthetic `dev` workload. The workload produced the
expected `5/5` baseline, `4 fulfilled / 6 failed` incident phase, and `5/5` recovery. Recovery and
ground truth both matched before Gemini Enterprise Preview investigation began.

The first Preview investigation immediately detected three bounded failure-log events but safely
remained inconclusive while Cloud Monitoring returned no bounded points. After provider metric
ingestion, a new Preview chat over the same 15-minute incident window returned `SEV-2` and
`IDENTIFIED` with payment connection-pool acquisition as H-01 and an unverified provider-timeout
alternative as H-02.

## Positive report contract

- H-01 was top-ranked with bounded log, metric, and knowledge citations.
- H-02 retained zero support and explicitly listed missing evidence and the next check.
- Immediate containment, bounded mitigation, and root-fix sections were present.
- Every changing recommendation required approval and contained no command, URL, IAM, or execution
  payload.
- All hypothesis and recommendation citations existed in the persisted report evidence.
- The Korean summary, impact, hypotheses, and recommendations were localized after correcting one
  live-summary copy gap observed during this QA run.

## Backend and release verification

- Runtime emitted the four required stages and four unique logical tool events.
- Trace and correlation identity matched Runtime, investigation, report, and tool events.
- Exactly one task attempt and report version 1 were persisted for the accepted final turn.
- The source-bound release passed 278/278 pytest, Ruff, strict mypy, build, core 7/7,
  portfolio 40/40, remediation 12/12, Terraform 1/1 and 8/8, and byte-identical Runtime packaging.
- The localization correction changed only the investigation API in place with
  `0 add / 1 change / 0 destroy`.
- The final Terraform plan reports `No changes`.

Cloud project identifiers, URLs, identities, image digests, Runtime resource names, scenario and
execution IDs, and browser captures are intentionally omitted. Raw evidence remains under `.tmp`
and is not versioned.
