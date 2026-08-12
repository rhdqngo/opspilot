# Agent Orchestration Runbook

Status: MVP production contract

## Offline validation

```powershell
uv sync --frozen --extra agent
uv run --extra agent opspilot agent run --scenario SCN-001 --format summary
uv run --extra agent opspilot agent eval --suite core --format summary
uv run --extra agent opspilot agent eval --suite portfolio --format summary `
  --output .tmp/evaluation
```

The evaluation must pass seven fixtures with fourteen model calls. The fixed trajectory is:

```text
prepare_bounded_evidence
rca_analyst
prepare_review
evidence_reviewer
verify_and_score
report_composer
finalize_report
```

## Execution boundary

- RCA analyst and report composer are the only model nodes; neither has tools.
- Maximum two model calls, 64 KiB input per request, and 2,048 output tokens per node.
- Each model node has 30 seconds; the graph has 75 seconds; concurrency is one; retries are zero.
- A failed source is recorded as a data gap while independent evidence remains available.
- Provider failures become one fixed safe error; raw prompt, response, URL, credential, and
  transport text are not retained.

## Verification boundary

- The deterministic reviewer rejects duplicate, missing, forged, or direction-mismatched citations.
- Support scores and root-cause taxonomy are computed from verified evidence.
- Knowledge prompt-injection text remains untrusted evidence and cannot alter control flow.
- Commands, URLs, resource paths, unknown services, and unknown citations remove a recommendation.
- Every retained recommendation has `requires_approval=true`.

Past live-acceptance suites and phase-timing diagnostics were pre-release milestone tools and are
not part of the product interface.
