# M6 Agent Orchestration Runbook

Status: Approval 2 controls implemented; live acceptance pending

## Purpose

M6 attaches bounded ADK reasoning to the M5 typed evidence layer. It does not expose raw cloud
clients to a model and does not execute remediation.

## Offline validation

Install the optional dependency and run the deterministic path:

```powershell
uv sync --frozen --extra agent
uv run --extra agent opspilot agent run --backend fixture --scenario SCN-001 --model fake --format summary
uv run --extra agent opspilot agent eval --suite fixture --model fake --format summary
```

Expected evaluation result is seven executed fixtures, seven passes, and twenty-one fake model
calls. The single-run trajectory is:

```text
prepare_bounded_evidence
rca_analyst
prepare_review
evidence_reviewer
verify_and_score
report_composer
finalize_report
```

## Fixed execution budget

- three model calls maximum
- 20 seconds per model node; 60 seconds total
- 64 KiB total model input view
- 2,048 output tokens per model node
- one graph execution at a time
- no model tools, retry, pagination, or remediation

Evidence is collected before the graph. A source failure produces a partial report when sufficient
independent evidence remains. Complete failure or invalid model output returns a redacted error and
exit code 2.

## Security contract

- Evidence titles, summaries, and knowledge chunks are untrusted data, not instructions.
- The model sees logical `opspilot://evidence/...` citations only.
- Project IDs, URLs, resource names, credentials, raw filters, request IDs, trace IDs, and source
  records are excluded from model inputs and public errors.
- The reviewer cannot make a citation trusted. A deterministic node checks each reference against
  immutable collected evidence and computes support scores in code.
- Suggested actions containing commands, URLs, resource paths, unknown services, or unknown
  citations are discarded. Surviving recommendations always require human approval.

## Live-model boundary

`--model vertex` is fail-closed unless `OPSPILOT_LIVE_MODEL_ENABLED=true` is set in the current
process. Only `gemini-3.5-flash` in `global` is accepted; an environment override to another model
fails before a request. The seven-case `agent eval` command is fake-only.

Run the zero-generation preflight before enabling the process gate:

```powershell
uv run --extra agent opspilot agent diagnose --account-alias Edu_687 --format summary
```

The approved live batch uses fixture evidence and exactly three fixed cases in this order:
SCN-001, SCN-006, and SCN-007. It stops after the first failed case and never retries.

```powershell
$env:OPSPILOT_LIVE_MODEL_ENABLED='true'
uv run --extra agent opspilot agent accept --suite m6-core --model vertex --format json
Remove-Item Env:OPSPILOT_LIVE_MODEL_ENABLED
```

The complete batch permits at most nine attempted model calls and has a 200-second aggregate
deadline. Keep the gate process-scoped and remove it in a `finally` path. Do not store raw model
requests or responses. Agent Runtime deployment and Gemini Enterprise registration remain M7 work.
