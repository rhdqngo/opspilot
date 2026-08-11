# M6 Agent Orchestration Runbook

Status: Approval 3 deterministic-review acceptance prepared

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

Expected evaluation result is seven executed fixtures, seven passes, and fourteen fake model
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

- two model calls maximum
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
- The deterministic reviewer rejects duplicate draft IDs and invalid citation structure. The next
  deterministic node checks references against immutable evidence and computes support scores.
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

The complete batch permits at most six attempted model calls and has a 200-second aggregate
deadline. Keep the gate process-scoped and remove it in a `finally` path. Do not store raw model
requests or responses. Agent Runtime deployment and Gemini Enterprise registration remain M7 work.

## Current live result

The Approval 2 batch was run once on 2026-08-11. SCN-001 stopped while validating the reviewer
response after two attempted requests and one response counted by the client workflow. Provider
usage metadata reported 1,229 prompt, 275 output, and 1,504 total tokens. Cloud Monitoring later
showed both Vertex requests completed with HTTP 200 and no provider error category. The gate was
removed and the batch was not retried.

The first summary format did not render the normalized error stored on the failed case. That output
contract is corrected locally and covered by tests, but the missing category cannot be reconstructed
without another model request. Approval 3 removes the model reviewer rather than reproducing or
coercing its output; the newly approved batch has a separate six-request ceiling.
