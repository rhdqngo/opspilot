# Current Project State

status: active
phase: M7-complete / MVP-lean-runtime-update-pending
updated: 2026-08-12

## Delivered MVP

- R0–M1: Python package, private repository, remote Terraform state, WIF, and KRW 50,000 budget.
- M2: three private scale-to-zero Cloud Run demo services and authenticated order E2E.
- M3: bounded SCN-001 incident and automatic recovery.
- M4: 13-document synthetic Agent Search corpus and deterministic local retrieval.
- M5: bounded read-only Logging, Monitoring, revision, and Search evidence collection.
- M6: seven-node ADK graph, deterministic citation review, verified-evidence taxonomy, and two
  tool-free model nodes with 30/75-second limits.
- M7: managed `AdkApp` Runtime, one async-stream operation, existing Gemini Enterprise app
  registration, and successful supported-request validation.

## Active lean cut

- Remove milestone-only access, route, Search diagnostic, model acceptance, Runtime probe, and
  Enterprise registration interfaces.
- Keep the investigation API, demo workload, replay/scenario tools, corpus validation/sync/local
  retrieval, fixture evidence smoke, seven-case fake evaluation, and deterministic Runtime package.
- Package only the production Runtime dependency closure. CLI, API/demo, fixtures, tests, docs,
  Terraform, corpus sync, and diagnostic modules must not enter the archive.
- Runtime responses contain only an `IncidentReport` or one fixed safe error. Model-origin taxonomy
  and acceptance/timing diagnostics are not public output.

## Non-negotiable product boundary

- Fixed `payment-service`, recent 30-minute, read-only Runtime scope.
- No caller-supplied project, URL, token, resource name, Logging/Monitoring filter, or serving config.
- Evidence/model call limits, 30-second model timeout, and 75-second graph deadline.
- Citation integrity, deterministic verified-evidence classification, prompt-injection isolation,
  action removal, approval-required recommendations, and sensitive-data redaction.

## Deployment checkpoint

- Cloud resources, IAM, Enterprise registration, model, prompt, schema, data, and scaling remain
  unchanged.
- Current dev baseline is `36 managed / 37 addresses` and must be zero drift before deployment.
- The only permitted cloud change is one Runtime in-place update containing the new source archive
  and hash: `0 create / 1 update / 0 delete / 0 replacement`.
- After apply: state remains `36/37`, operator plan is `No changes`, and an out-of-scope request
  must stop before evidence/model work.
- One supported Enterprise Preview request is allowed. A repeated internal GaiaMint expiry is a
  Google Preview authentication-bridge blocker, not authorization to expand code or IAM.

## Validation authority

- Local ruff, strict mypy, pytest, package build, fixture eval, knowledge/evidence smoke, Compose
  E2E, and Terraform static/operator validation are authoritative.
- GitHub workflows remain `workflow_dispatch` only and `skipped-by-policy`.

## Post-MVP

VPC/perimeter controls, Model Armor, alert intake, remediation, sessions/memory, dashboard,
multi-project support, and broader evaluation remain optional and require separate approval.
