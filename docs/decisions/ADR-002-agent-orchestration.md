# ADR-002: Combine deterministic workflow with bounded agent reasoning

Status: implemented for offline M6
Date: 2026-08-11

## Decision

Keep collection, normalization, policy, scoring, and citation validation deterministic. Use Google
ADK 2.5 for a fixed graph with three reasoning nodes: RCA analyst, evidence reviewer, and report
composer. Function nodes bound the evidence before reasoning, reattach trusted state, reject forged
citations, compute scores, and finalize the public report.

## Rationale

This preserves reproducibility, parallel collection, cost bounds, and trajectory evaluation while
preventing an LLM from constructing executable resource queries or action payloads.

## Constraints

- ADK is an optional `agent` extra; the deployed M2/M3 workload image does not gain it implicitly.
- Each model node has no tools, a 20-second timeout, and a 2,048-token output cap. The workflow is
  single-concurrency with a 60-second deadline and at most three model calls.
- Model input is capped at 64 KiB and contains only logical evidence URIs. Cloud identifiers,
  credentials, filters, URLs, raw evidence records, and resource names are prohibited.
- Model confidence is ignored. Citation integrity, minimum source diversity, contradiction penalty,
  status, and action admission are deterministic code decisions.
- Recommendations remain advisory records with `requires_approval=true`; no remediation endpoint or
  write tool is connected.
- The fixture fake model is the CI default. Vertex use remains behind
  `OPSPILOT_LIVE_MODEL_ENABLED=true` and a separate approval.
