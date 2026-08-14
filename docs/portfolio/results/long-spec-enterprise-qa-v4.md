# Gemini Enterprise Preview QA v4 Evidence

- Status: **PASSED**
- Final source commit: `f73c7a002b02957a65a4496a1aedd0eeb17ba019`
- Runtime package: 11 files, byte-identical across two builds
- Preview UI and managed backend cross-verification: **passed**

Cloud project, account, service URLs, identities, image digests, and
trace/run/correlation/investigation IDs are omitted. Raw browser and cloud evidence remains under
ignored `.tmp/enterprise-qa-live` only.

## Remediation and release

The managed Runtime now waits for the bounded investigation result before emitting progress and
final back-to-back. API, HTTP, and Runtime deadlines are ordered so an ordinary cold start does not
prematurely terminate an otherwise successful investigation. Three consecutive direct Vertex SDK
calls returned exactly one progress and one final event.

SCN-001 warm-up now requires two consecutive authenticated end-to-end order successes after
readiness, so the counted baseline does not absorb a downstream scale-to-zero cold request. The
final clean scenario produced baseline `5/5`, incident `4 fulfilled / 6 failed`, recovery `5/5`,
`recovered=true`, and matching ground truth.

The first limited plan changed only the investigation API and existing Agent Runtime in place. The
follow-up runner-only plan changed only the investigation API image. Both plans had zero add,
destroy, or replacement actions; IAM, registration, M8, and demo resources remained unchanged.

## Preview matrix

| Group | Result |
| --- | --- |
| Canary | Final visible and stream closed |
| Healthy chats | 3/3; one progress and final, no H-01 or changing action |
| English incident | H-01/H-02, four evidence types, three action classes |
| Korean unused incident | Korean progress/report, user-source incident, H-01/H-02 |
| Environment omitted | Explicit `No environment was specified; using dev.` assumption |
| Privacy | UI pass; persisted redaction and domain hashes; raw input absent from application logs |
| Negative boundaries | 8/8; no progress, investigation, report, or tool event |

Every final positive run persisted one investigation, one task attempt, and report v1; reused one
trace/correlation identity; emitted four Runtime stages and four logical tool events; and contained
only valid evidence citations. H-02 retained support 0 and the insufficient-evidence meaning. All
changing recommendations required approval and exposed no command, URL, IAM change, or execution
payload.

One privacy chat showed a Gemini Enterprise generic display error even though Runtime completed in
3.485 seconds and the backend was complete and unique. Two prescribed same-deployment retries and
the final clean 15-minute case passed, so it is recorded as transient rather than a product defect.

OpsPilot Firestore, reports, Runtime logs, and tool logs contain only redacted query text and
domain-separated hashes. Gemini Enterprise's own user-activity audit log retains submitted prompts
as platform audit data; it is not an OpsPilot application log and remains governed by the provider
audit-retention policy.

## Exit gate

- Normal traffic: `5/5`
- Cloud Run: Ready, 100% traffic, no public invoker
- Runtime authentication boundaries: passed
- Runtime resource and Enterprise registration: unchanged
- Final Terraform plan: `No changes`
- Local gates: pytest `237/237`, core `7/7`, portfolio `40/40`, remediation `12/12`, Ruff, strict
  mypy, build, Terraform bootstrap `1/1`, and dev `8/8`

The three manual GitHub workflows were dispatched again. Their jobs contained zero executed steps
under the existing hosted-runner billing or spending-limit condition, which remains an external
non-blocking item.
