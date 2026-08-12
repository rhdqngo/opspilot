# Agent Runtime Runbook

Status: M7 deployed; lean archive applied; Enterprise Preview Runtime execution blocked

## Product contract

The Runtime accepts only a 3–500 character read-only investigation naming exactly
`payment-service`. A missing time window becomes the recent 30 minutes with an assumption. Other
services, windows, commands, recovery, and execution requests return a fixed safe message before
evidence or model calls.

The accepted path uses workload ADC, the packaged service catalog, bounded read-only evidence, and
the seven-node graph. It returns an `IncidentReport` or one fixed safe failure message. It does not
return acceptance audits, model-origin taxonomy, phase timing, cloud identifiers, or user identity.

## Package

```powershell
uv run --extra agent opspilot agent runtime package --output .tmp/runtime
```

The deterministic archive contains only its explicit production allowlist and pinned requirements.
It excludes CLI, API/demo code, fixtures, corpus synchronization, tests, docs, Terraform, temporary
state, and retired diagnostic/registration modules. Do not upload the archive as a CI artifact.

The entrypoint is `opspilot.agent.runtime_agent:root_agent`, an official `AdkApp` exposing exactly:

```text
streaming_agent_run_with_events
api_mode: async_stream
required input: request_json (string)
```

## Deployment

Generate a fresh package from clean `main`, verify two archives have the same hash, and create a
fresh dev plan. Apply only if the plan is exactly `0 create / 1 update / 0 delete / 0 replacement`
and the sole change is the Runtime source archive/hash. Identity, IAM, APIs, region, scaling,
telemetry, labels, class methods, and deletion policy must remain unchanged.

The lean archive was applied as the sole in-place Runtime update. Dev remains
`36 managed / 37 addresses`, and the post-apply operator plan is `No changes`. Local product tests
verify that an unsupported-service request is rejected before evidence/model work.

The single approved supported question was submitted in Gemini Enterprise Preview:

```text
payment-service 최근 30분 상태를 근거와 함께 분석해줘
```

Preview returned a generic Runtime `INTERNAL` failure. The current operator has neither project log
read nor investigator impersonation permission, so no Runtime traceback was available inside the
approved least-privilege boundary. Classify this checkpoint as `runtime_execution_blocked` until an
authorized operator can inspect the failed execution. Do not broaden IAM, expose the Runtime
publicly, repeat the request, or change the model, prompt, timeout, and product scope without a new
approved diagnostic plan. A future `GaiaMint invalid` or `mint used too late` response remains a
separate Google Preview authentication-bridge blocker.

Enterprise registration already exists. Re-registration code is intentionally absent; use the
official console procedure only if an operator explicitly needs to repair registration.
