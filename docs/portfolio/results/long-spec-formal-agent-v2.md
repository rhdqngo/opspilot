# OpsPilot Final Preview Regression Verification

Status: **PASSED**  
Verified: 2026-08-14

## Outcome

A final live Gemini Enterprise Preview pass exercised capability guidance, a three-service
investigation, a same-session concise summary, and actual-production rejection. The pass exposed
one deterministic presentation defect: a healthy report with no hypotheses incorrectly said that
a requested hypothesis was missing. The concise renderer now returns exactly the report status,
localized user impact, and conclusion unless a specific hypothesis ID was actually requested.

## Release and validation

- The exact failing Preview phrase is covered by a regression test.
- The source-bound gate passed 277/277 pytest, Ruff format/check, strict mypy over 92 source files,
  package build, core 7/7, portfolio 40/40, remediation 12/12, Terraform bootstrap 1/1 and dev 8/8.
- Both 11-file Runtime packages remained byte-identical. Runtime itself did not require deployment.
- The reviewed Terraform plan contained `0 add / 1 change / 0 destroy` and changed only the
  investigation API in place.
- Post-deployment Preview returned a bounded three-service report and then a three-item Korean
  summary containing status, user impact, and conclusion. Capability guidance and the localized
  actual-production rejection also passed.
- The three-service turn produced four Runtime stages and twelve service-scoped tool events across
  four unique tools. Trace/correlation linkage, one task attempt, and report version 1 all passed.
- Cloud Run is Ready and the final Terraform plan reports `No changes`.

## Provider transient

The first capability-guidance attempt ended in the managed provider's safe-failure path. Two
required same-deployment reruns returned the correct immediate guidance, and the post-fix release
also passed the same Preview case. This remains a provider transient rather than a product defect.

Cloud project identifiers, URLs, identities, image digests, Runtime resource names, execution IDs,
and browser captures are intentionally omitted. Raw evidence remains under `.tmp` and is not
versioned.
