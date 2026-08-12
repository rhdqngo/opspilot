# M7 Agent Runtime Runbook

Status: Runtime package fixed; managed entrypoint operation contract blocked

## MVP contract

The managed entrypoint accepts only a 3–500 character investigation request naming exactly
`payment-service`. An omitted window becomes the recent 30 minutes with an explicit assumption.
Other services, other time ranges, commands, recovery, and execution requests return a fixed safe
message before any evidence or model call. The upper routing model is always skipped.

The accepted path uses workload ADC, the packaged service catalog, the existing read-only evidence
client, and the existing seven-node graph. Only RCA analysis and report composition call the fixed
model. Reports retain logical citations, approval-required recommendations, and no executable
command or cloud resource path.

## Offline commands

```powershell
uv sync --frozen --extra agent
uv run --extra agent opspilot agent runtime validate --format summary
uv run --extra agent opspilot agent runtime smoke --backend fixture --format json
uv run --extra agent opspilot agent runtime probe --format json
uv run --extra agent opspilot agent runtime package --output .tmp/m7-runtime
```

Packaging writes only a deterministic tarball and SHA-256 under `.tmp`. It includes package source,
the packaged service catalog, and pinned runtime requirements; it excludes repository metadata,
environment files, tests, docs, scenario data, Terraform, and temporary state. Do not upload this
archive as a CI artifact.

The first Approval 2 deployment proved that determinism and file allowlisting alone are
insufficient. Approval 3 therefore pins `google-cloud-aiplatform[agent-engines]==1.153.1`
alongside `google-adk==2.5.0`. It intentionally does not use the SDK's `adk` extra because that
extra targets ADK 1.x. Two generated archives matched byte-for-byte, and a clean Python 3.12
environment installed their requirements and imported the SDK, Agent Engines module, and Runtime
entrypoint without a cloud call.

The probe is live and remains disabled unless `OPSPILOT_RUNTIME_PROBE_ENABLED=true` is set for one
process. It discovers only the fixed Runtime and sends one fixed unsupported-service request. Its
output contains no project, Runtime resource, URL, token, prompt, or raw response.

## Deployment gate

Source default `deploy_agent_runtime=false` preserves the current dev state. Hosted validation is
skipped during the MVP, so the bootstrap source remains zero drift and is not applied. Approval 2
reviews only the exact dev `5 create / 1 update` plan. The runtime must remain in
`asia-northeast3`, use the existing investigator service account, scale from zero to one, and
capture no prompt, response, or user identity content in telemetry.

That exact plan was applied once. The three API addresses, leaf service-agent grant, and
investigator-role update succeeded, while Runtime startup failed with a redacted
`ModuleNotFoundError` for `google.cloud.aiplatform`. Dev state is therefore `35 managed / 36
addresses`, with no Runtime in state or live inventory. Approval 3 validated the dependency fix
and reviewed an exact Runtime-only one-create plan. That single apply reached entrypoint operation
discovery but failed because the exported ADK `LlmAgent` implements none of the Runtime query or
stream-query operations. Dev remains `35 managed / 36 addresses`; Runtime, probe, registration,
and Enterprise query counts remain zero.

Do not reapply the same archive. A separate approval must wrap the existing ADK agent in a
Runtime-supported object and prove the registered-operation contract locally before another exact
one-create plan is considered.

Gemini Enterprise registration uses the fixed display name `OpsPilot Incident Commander`.
Planning is read-only. Apply additionally requires the process-scoped
`OPSPILOT_ENTERPRISE_REGISTER_ENABLED=true` gate, a unique existing global app, a unique deployed
runtime, and no conflicting registration. Identifiers are never printed.

## Approval 2 acceptance

First send one unsupported probe and require zero evidence/model calls. Then register once and send
one supported Enterprise request. Require a normal or `INCONCLUSIVE` report, citation coverage
100%, unauthorized actions zero, no captured message/user content, runtime log/trace presence, and
local operator Terraform zero drift. Do not dispatch GitHub workflows or enable Sessions, Memory
Bank, OAuth delegation, Agent Gateway, VPC, Model Armor, remediation, or dashboard work in M7.
