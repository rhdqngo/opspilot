# M7 Agent Runtime Runbook

Status: M7 complete; Runtime and Enterprise Preview path accepted

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

The Runtime entrypoint is an official Agent Platform `AdkApp` around the existing fixed-scope ADK
agent. It registers only the asynchronous `streaming_agent_run_with_events` operation required by
Gemini Enterprise; session, memory, artifact, unary-query, and bidi operations are not published.
The packaged object passed isolated operation discovery and a local streaming rejection test.

The probe is live and remains disabled unless `OPSPILOT_RUNTIME_PROBE_ENABLED=true` is set for one
process. It discovers only the fixed Runtime and sends one fixed unsupported-service request to
the streaming operation. Its total response is capped at 64 KiB and its output contains no project,
Runtime resource, URL, token, prompt, user identifier, or raw response.

## Deployed boundary

Source default `deploy_agent_runtime=false` remains fail-closed. The managed environment explicitly
enables it with an immutable deterministic archive. The Runtime remains in `asia-northeast3`, uses
the existing investigator service account, scales from zero to one, and captures no message or user
identity content in telemetry. Dev contains `36 managed / 37 addresses` and the operator plan is
zero drift.

The public Runtime schema contains exactly one method:

```text
streaming_agent_run_with_events
api_mode: async_stream
required input: request_json (string)
```

The exact in-place declaration plan changed only that schema: `0 create / 1 update / 0 delete / 0
replacement`. Runtime source, identity, IAM, APIs, scaling, telemetry, labels, region, and deletion
policy were unchanged.

Gemini Enterprise registration uses the fixed display name `OpsPilot Incident Commander` and the
existing unique global app. Registration is enabled for the same unique Runtime; subsequent plans
are no-op. The supported request must use the global location endpoint. Do not add
`actionDisabled` to a direct Agent-mode request: the Runtime itself publishes no action operation,
and disabling actions at the outer request can suppress the registered-agent invocation.

## Live acceptance evidence

- The fixed unsupported-service probe returned the expected rejection with evidence/model calls
  both zero.
- The registered supported request finished with HTTP 200 and final Enterprise state `SUCCEEDED`.
- Vertex metrics for the bounded execution window recorded exactly two successful global model
  invocations.
- Runtime logs were present and contained no detected prompt, email, bearer token, or exception
  class. Cloud Trace entries were observable in the same bounded window.
- The deployed code caps evidence access at six calls, requires complete logical citations, filters
  unauthorized actions, and marks every retained recommendation as approval-required. These
  contracts are covered by the full local Runtime and agent regression suite.
- Enterprise registration and dev Terraform both finish no-op/zero drift. GitHub workflows remain
  manual-only and `skipped-by-policy`.

Do not enable Sessions, Memory Bank, OAuth delegation, Agent Gateway, VPC, Model Armor,
remediation, or dashboard work as part of M7.
