# ADR-010: Minimal managed Runtime and Enterprise connection

Status: superseded by ADR-011 and ADR-012

## Decision

Deploy one `vertexai.agent_engines.AdkApp` in `asia-northeast3`, reusing the read-only investigator
service account. It exposes only `streaming_agent_run_with_events` and is registered with the
existing global Gemini Enterprise app.

The deterministic entry adapter accepts only `payment-service` over the recent 30-minute window.
Unsupported requests stop before evidence or model calls. Runtime output is an `IncidentReport` or
one fixed safe error message.

Accepted requests use a custom ADK `BaseAgent` generator. It emits one visible progress event with
`partial=true` and `turnComplete=false` before evidence work, then emits the report or fixed safe
error with `partial=false` and `turnComplete=true`. The live path uses 3-second HTTP, 4-second source,
5-second evidence-collection, 10-second RCA, and 18-second whole-Runtime bounds. The seven-node
Workflow and its 30/75-second model/graph bounds remain fixture/eval-only.

The progress content ends with two newlines because Gemini Enterprise concatenates partial and final
event text. A successful metric query with zero bounded points remains evidence but creates an
explicit data gap and makes the collection partial. Knowledge documents remain cited Sources but
are not incident Timeline events. Empty hypotheses render a deterministic fallback statement.

The public input remains unchanged, but Runtime rendering is bilingual. Input classification runs
before scope validation: any Hangul character selects `ko`, otherwise `en`. Progress, report
structure and narrative, data gaps, assumptions, rejection, configuration failure, RCA degradation,
and fixed safe failure use centralized language-specific copy. Evidence IDs, service and metric
names, and evidence titles/summaries remain verbatim. The renderer defaults to English so API, CLI,
fixture, and evaluation callers preserve their existing output.

The live investigation is a native coroutine so cancellation and deadlines reach evidence and
optional reasoning work. Only urllib transport uses bounded worker threads. Evidence quality is
computed deterministically; an RCA `LlmAgent` runs exactly once only when valid supporting
LOG/METRIC/CHANGE evidence spans two source types. With no such signal, reasoning is skipped and the
Runtime immediately renders an inconclusive report. RCA timeout, model error, or invalid output also
degrades to an evidence-backed inconclusive report; only the outer deadline or serialization failure
uses the fixed safe error.

Enterprise-supplied session IDs are accepted through an in-process `InMemorySessionService`
configured with the public `session_service_builder` hook. This prevents the single-turn MVP from
depending on Agent Platform Session creation while retaining the official `AdkApp` streaming path.
Session and user identifiers are not persisted or surfaced.

## Packaging

The Runtime archive is built from an explicit production allowlist. It contains only the entrypoint,
fixed input handling, live evidence/Search contracts, graph/model code, domain models, catalog, and
redaction/reporting support. CLI, API/demo, fixtures, corpus sync, tests, docs, Terraform,
registration, probes, and milestone acceptance code are excluded.

## Consequences

- Runtime scales from zero to one with message-content capture disabled.
- Managed Sessions, multi-turn continuity, Memory Bank, OAuth delegation, Agent Gateway, VPC,
  Model Armor, remediation, and extra operations are not part of the MVP.
- Registration is an operator console procedure, not product code.
- Accepted streams contain a progress event before the final event; rejected inputs contain only
  the final safe rejection event.
- Live zero-signal requests make zero model calls. Identified reports expose only verified
  hypotheses and next checks, never automatic execution actions.
- Optional RCA input carries `output_language`. Natural-language fields must contain Hangul for
  Korean and must not contain Hangul for English; a mismatch is invalid structured output and
  degrades to the localized evidence-backed inconclusive report.
- Runtime stages share a random process-local `RUN-…` identifier that is unrelated to user/session
  identity. One final `run_summary` records only source status/error codes and reasoning outcome.
  Prompt, user ID, session ID, project, raw evidence, and raw exception messages remain excluded.
- GitHub workflows are manual-only; local validation and operator plans are authoritative.
- A Google-internal Preview mint expiry is treated as an external authentication-bridge blocker,
  not a reason to broaden IAM or Runtime scope.
