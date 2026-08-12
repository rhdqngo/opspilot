# Agent Runtime Runbook

Status: M7 deployed; lean archive update pending

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

After apply, require `36 managed / 37 addresses`, Runtime Ready, and an operator `No changes` plan.
An unsupported-service request must be rejected before evidence/model work. Run one supported
question in Gemini Enterprise Preview:

```text
payment-service 최근 30분 상태를 근거와 함께 분석해줘
```

A repeated `GaiaMint invalid` or `mint used too late` result is a Google Preview authentication
bridge blocker. Do not broaden IAM, expose the Runtime publicly, retry indefinitely, or change the
model, prompt, timeout, and product scope in response.

Enterprise registration already exists. Re-registration code is intentionally absent; use the
official console procedure only if an operator explicitly needs to repair registration.
