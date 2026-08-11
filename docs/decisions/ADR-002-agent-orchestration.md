# ADR-002: Combine deterministic workflow with bounded agent reasoning

Status: implemented; verified-evidence taxonomy selected, live acceptance pending
Date: 2026-08-12

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
- The single Approval 4 `m6-rca` run completed both requests and failed only
  `root_cause_mismatch`: `CONFIG_DB_POOL_EXHAUSTION` did not match the fixed
  `PAYMENT_DB_POOL_EXHAUSTION` taxonomy. The mismatch is recorded without coercion, retry, or prompt,
  schema, model, or acceptance-policy change.
- Approval 5 permits one exact alias only after deterministic citation validation. The alias
  requires at least two supporting source types and verified `payment-service` scope. The original
  model code remains a bounded diagnostic field, while the composer and public root-cause contract
  receive the canonical code. Fuzzy, case-insensitive, user-provided, and wrong-service mappings are
  prohibited.
- The one authorized Approval 5 rerun passed every preflight but timed out on its first model node:
  one attempt, zero successful responses, zero reported tokens, and safe code `AGENT_TIMEOUT`. The
  timeout is non-retryable under the current contract, so the taxonomy was not exercised live and
  M6 remains blocked without another request.
- Approval 6 preserves all model and timeout settings and adds content-free monotonic observations
  at the public before-model, after-model, runner-event, and graph-completion boundaries. Timeout
  origin is derived only from the last observed phase; missing evidence remains `unknown`.
- Approval 6 is zero-call and zero-cloud-change. It prepares a separately approved RCA rerun but
  does not authorize one, run the safety suite, or begin M7.
- Approval 7 used that authorization once. Both model nodes completed within 20 seconds and every
  non-taxonomy predicate passed, but `DB_CONNECTION_POOL_EXHAUSTION` is outside the canonical code
  and sole approved alias. The verifier correctly failed closed with `root_cause_mismatch`.
- Approval 8 replaces model-label aliases with two synthetic-only verified-evidence rules for the
  payment-pool and prompt-injection acceptance classes. Rules use cited supporting direction,
  service, source types, and deterministic quality flags only.
- Model labels remain bounded audit data. Scenario IDs, fixture answers, title/summary parsing,
  fuzzy matching, contradictory evidence, and user-defined taxonomy rules cannot choose the
  canonical code. Zero or multiple evidence-rule matches remain fail-closed.
