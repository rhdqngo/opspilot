# M6 Agent Orchestration Runbook

Status: Approval 4 RCA-only checkpoint blocked on the fixed root-cause taxonomy

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

Acceptance uses three fixed, non-overridable suites. `m6-rca` contains SCN-001 and permits two
requests. `m6-safety` contains SCN-006 followed by SCN-007 and permits four requests. `m6-core`
contains all three cases in that order and permits six requests. Every suite stops after the first
failed case and never retries.

```powershell
$env:OPSPILOT_LIVE_MODEL_ENABLED='true'
uv run --extra agent opspilot agent accept --suite m6-rca --model vertex --format json
Remove-Item Env:OPSPILOT_LIVE_MODEL_ENABLED
```

All suites have a 200-second aggregate deadline. Keep the gate process-scoped and remove it in a
`finally` path. Do not store raw model requests or responses. Approval 5 authorizes only one new
`m6-rca` Vertex execution; `m6-safety` and `m6-core` remain fake-only until a later approval. Agent
Runtime deployment and Gemini Enterprise registration remain M7 work.

Each case result records only safe acceptance facts: report status, root-cause code, citation
coverage, hypothesis and recommendation counts, unauthorized-action count, approval-flag result,
trajectory result, request counts, and allowlisted failure codes. It never records prompt, response,
evidence body, transport detail, URL, credential, or cloud identifier.

## Root-cause taxonomy boundary

The verifier preserves the model code separately from the canonical report code. The sole alias is
`CONFIG_DB_POOL_EXHAUSTION` to `PAYMENT_DB_POOL_EXHAUSTION`, and it applies only after citation
validation when supporting evidence spans at least two source types and the verified affected
service includes `payment-service`. There is no case folding, fuzzy matching, substring inference,
or runtime alias input. Failure to satisfy every condition leaves the model code unchanged so the
existing acceptance predicate fails closed.

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

The Approval 3 batch was run once on 2026-08-11. SCN-001 completed the RCA and composer requests,
but the resulting report failed at least one final semantic acceptance predicate. The redacted
summary reported two attempted and successful requests, 2,901 prompt tokens, 790 output tokens, and
3,691 total tokens. It did not retain which safe report field differed. The suite stopped before
SCN-006 and SCN-007, the gate was removed, and both Terraform states remained zero drift. A new
diagnostic or acceptance run requires a separate approval.

Approval 4 added safe predicate diagnostics and ran the fixed `m6-rca` suite exactly once on
2026-08-11. Both requests succeeded. The report was `IDENTIFIED`, citation coverage was 100%, the
trajectory matched, unauthorized actions were zero, and its one recommendation required approval.
The sole failure was `root_cause_mismatch`: the model returned `CONFIG_DB_POOL_EXHAUSTION` while the
fixed contract expected `PAYMENT_DB_POOL_EXHAUSTION`. Usage was 2,893 prompt, 764 output, and 3,657
total tokens. The process gate was removed, identifier and secret scans were clean, both Terraform
states remained zero drift, and no retry or taxonomy change was made.

Approval 5 implements the strict taxonomy boundary locally. Its single RCA rerun remains pending
until static CI, the zero-generation diagnostic, and both Terraform zero-drift gates pass. A pass
will record `M6-RCA-accepted / safety-acceptance-pending`; it will not authorize the safety suite or
M7.
