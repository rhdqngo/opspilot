# ADR-002: Combine deterministic workflow with bounded agent reasoning

Status: implemented; deterministic reviewer selected, live acceptance blocked
Date: 2026-08-11

## Decision

Keep collection, normalization, policy, citation review, scoring, and final admission deterministic.
Use Google ADK 2.5 for a fixed seven-node graph with two reasoning nodes: RCA analyst and report
composer. The named `evidence_reviewer` node remains in the trajectory as a local function that
rejects invalid citations before scoring.

## Rationale

This preserves reproducibility, parallel collection, cost bounds, and trajectory evaluation while
preventing an LLM from constructing executable resource queries or action payloads.

## Constraints

- ADK is an optional `agent` extra; the deployed M2/M3 workload image does not gain it implicitly.
- Each model node has no tools, a 20-second timeout, and a 2,048-token output cap. The workflow is
  single-concurrency with a 60-second deadline and at most two model calls.
- Model input is capped at 64 KiB and contains only logical evidence URIs. Cloud identifiers,
  credentials, filters, URLs, raw evidence records, and resource names are prohibited.
- Model confidence is ignored. Citation integrity, minimum source diversity, contradiction penalty,
  status, and action admission are deterministic code decisions.
- Recommendations remain advisory records with `requires_approval=true`; no remediation endpoint or
  write tool is connected.
- The fixture fake model is the CI default. Vertex use remains behind
  `OPSPILOT_LIVE_MODEL_ENABLED=true`; the approved model and location are fixed to
  `gemini-3.5-flash` and `global`.
- Acceptance is divided into fixed `m6-rca`, `m6-safety`, and `m6-core` suites capped at two, four,
  and six attempted requests respectively, with a 200-second deadline and no retry. The seven-case
  evaluation remains fake-only.
- The first approved live batch produced two HTTP-successful Vertex responses but stopped while
  validating the reviewer output. The precise invalid field was not retained and is not inferred.
- A model-based independent reviewer is deferred as a post-MVP option. Restoring it requires a
  separate structured-output contract, request budget, and approval.
- The Approval 3 batch completed both SCN-001 model calls but failed its final semantic acceptance
  predicate. It stopped before SCN-006 as designed. No retry, model substitution, schema relaxation,
  or infrastructure change was made.
- Approval 4 preserves every predicate while exposing allowlisted failure codes and safe report
  facts. It authorizes only the fixed SCN-001 `m6-rca` suite; the safety cases remain a later
  approval boundary.
