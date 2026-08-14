# Agent Runtime Runbook

Status: deployed thin adapter

The deployed formal Runtime performs only input-length and language checks and sends
all valid turns to `POST /internal/v2/runtime/turns`. The API returns whether evidence collection
actually started. Investigation/refinement turns emit one buffered progress event followed by one
final event; capability, explanation, status, comparison, clarification, and rejection turns emit
only one final event. The v1 bridge remains available for compatibility.

## Contract

The canonical entrypoint is `opspilot.agent.runtime_agent:root_agent`. It exposes one ADK streaming
operation and delegates every accepted investigation to the private persistent investigation API.
There is no direct evidence or RCA fallback in the Runtime package.

`OPSPILOT_INVESTIGATION_API_URL` is required. If it is absent, unreachable, or returns an invalid
result, Runtime emits one localized safe failure; it never changes to a different execution path.
The Runtime identity needs only permission to invoke that API. Logging, Monitoring, Cloud Run,
Search, Cloud Tasks, and Firestore access remain on API-owned identities.

Agent Engine can expose `GOOGLE_CLOUD_PROJECT` as a numeric project hint. The Runtime identity has
one dedicated custom role containing exactly `resourcemanager.projects.get`, which lets the SDK
resolve that hint without granting a broad viewer or any evidence, persistence, task, IAM, or
remediation permission. The project value is never persisted or logged.

Input supports the catalog services `order-service`, `payment-service`, and `inventory-service`
and Korean or English relative windows from 1 to 120 minutes. Missing service means all three;
missing time means 30 minutes. Commands, write requests, project IDs, URLs, tokens, raw filters,
unregistered services, and out-of-range or ambiguous windows are rejected before the API call.
Runtime creates one run ID, correlation ID, and 32-hex trace ID per invocation. It sends those IDs
with `X-Cloud-Trace-Context` and uses the run ID as the idempotency key. User and session values are
source-domain SHA-256 hashes; raw values and the raw prompt are never logged or persisted.

Runtime starts the bounded handler before emitting progress, then uses one monotonic deadline for
exactly one progress and one final event. Accepted, handler-started, summary, final, cancellation,
and timeout stages reuse the same run/correlation/trace identity.

Visible progress, failure, and persisted Markdown rendering follow Korean when the prompt contains
Hangul and English otherwise. The renderer localizes server-owned narrative and assumptions while
preserving evidence IDs and technical evidence titles.

## Packaging

```powershell
uv run --extra agent opspilot agent runtime package --output .tmp/runtime-a
uv run --extra agent opspilot agent runtime package --output .tmp/runtime-b
```

Both archives must be byte-identical. The allowlist contains only the package root, Runtime
adapter/entrypoint, parser, audit/retry contracts, catalog, domain models, service catalog resource,
and requirements.
Agent workflow/model/evidence/search/redaction/reporting/scoring modules, CLI/API/demo code,
fixtures, tests, docs, and Terraform must not be present.

## Release checks

1. Run Ruff, strict mypy, pytest, build, core/portfolio/remediation evaluations, and both package
   builds from a clean implementation commit.
2. Produce one `release-context.json` and bind later image, Terraform, and evidence records to its
   canonical hash.
3. Before Terraform planning and evidence publication, verify the current source still matches the
   context. Recheck the reviewed binary plan SHA immediately before apply.
4. A Runtime source update must be the only Runtime change; identity, IAM, region, scaling,
   registration, and environment remain fixed.
5. After apply, verify Ready state, one progress event, one final persisted report, and a final
   Terraform `No changes` plan. Do not record prompts, identities, or evidence payloads in logs.

## Safe failure triage

- Configuration failure: verify only that `OPSPILOT_INVESTIGATION_API_URL` is present on the
  deployed Runtime and points to the fixed private API.
- Authentication or transport failure: inspect pseudonymous stage/outcome logs by run,
  correlation, and trace ID plus the API request record; do not enable direct evidence access on
  Runtime. Transient 429/5xx/timeout/transport failures retry at most three times with full jitter.
- Timeout: inspect Cloud Task and investigation status. Redelivery is expected and must remain
  idempotent.
- Partial evidence: return the persisted partial/inconclusive report with data gaps and citations;
  do not synthesize missing evidence.
