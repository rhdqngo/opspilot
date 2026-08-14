# OpsPilot Formal Agent Verification

Status: **PASSED**  
Verified: 2026-08-14

## Outcome

OpsPilot has completed the transition from the fixed MVP investigation flow to the bounded formal
Incident Commander defined by the long-term master specification. The deployed Gemini Enterprise
registration supports three services, three synthetic environments, bounded time/symptom/depth
scope, multi-turn report interaction, and approval-request creation at the existing M8 boundary.
Actual production connectivity and generalized write execution remain intentionally unsupported.

## Source-bound release

- The release was built from one clean `main` commit matching `origin/main`.
- Both 11-file Runtime packages were byte-identical.
- The API image passed linux/amd64, non-root, health, readiness, and registry-digest binding checks.
- The final correction used a reviewed Terraform plan with `0 add / 1 change / 0 destroy` and only
  the investigation API address. Runtime, IAM, M8, registration, workloads, and schema were
  unchanged in that cycle.

## Permission decision

Avoiding `resourcemanager.projects.get` forced an unreliable managed-Runtime metadata workaround.
The final deployment replaces that workaround with a dedicated custom role containing exactly that
single permission, bound only to the Runtime service account. No broad viewer, evidence, datastore,
task, alert, approval, or executor capability was added. Runtime still reaches only the private
investigation bridge.

## Verification results

- Local: 277/277 pytest, Ruff format/check, strict mypy over 92 source files, build, core 7/7,
  portfolio 40/40, remediation 12/12, Terraform bootstrap 1/1, and dev 8/8.
- Managed: all three environments were callable and SCN-001 passed the expected
  `5/5 → 4 fulfilled / 6 failed → 5/5` recovery sequence.
- Runtime/backend: four required Runtime stages and four unique tool events linked to one
  investigation, one task attempt, and report version 1 using the same trace/correlation identity.
- Privacy: application payloads contained no raw sentinel, user/session identity, cloud project,
  URL, or raw error. No permission error was observed in the final validation window.
- Preview: Korean single- and multi-service investigations, a same-session concise summary,
  localized capability guidance, and actual-production rejection all passed. Investigation turns
  emitted one progress and one final; immediate guidance/rejection emitted one final only.
- Timeline: the reproduced 15-minute query did not include the prior-day revision leak.
- Drift: Cloud Run is Ready, registration is stable, and the final Terraform plan reports
  `No changes` with the same immutable inputs.

## Provider transient

One managed multi-service turn encountered the previously characterized provider transport
transient. Both required reruns against the identical deployment completed successfully and all
backend idempotency, trace, report, and tool-event invariants remained intact. It is recorded as a
provider transient under the approved QA policy, not as a remaining product defect.

Cloud project identifiers, URLs, identities, image digests, Runtime resource names, execution IDs,
and browser captures are intentionally omitted. Raw evidence remains under `.tmp` and is not
versioned.
