# ADR-010: Minimal managed Runtime and Enterprise connection

Status: implemented

## Decision

Deploy one `vertexai.agent_engines.AdkApp` in `asia-northeast3`, reusing the read-only investigator
service account. It exposes only `streaming_agent_run_with_events` and is registered with the
existing global Gemini Enterprise app.

The deterministic entry adapter accepts only `payment-service` over the recent 30-minute window.
Unsupported requests stop before evidence or model calls. Runtime output is an `IncidentReport` or
one fixed safe error message.

## Packaging

The Runtime archive is built from an explicit production allowlist. It contains only the entrypoint,
fixed input handling, live evidence/Search contracts, graph/model code, domain models, catalog, and
redaction/reporting support. CLI, API/demo, fixtures, corpus sync, tests, docs, Terraform,
registration, probes, and milestone acceptance code are excluded.

## Consequences

- Runtime scales from zero to one with message-content capture disabled.
- Sessions, Memory Bank, OAuth delegation, Agent Gateway, VPC, Model Armor, remediation, and extra
  operations are not part of the MVP.
- Registration is an operator console procedure, not product code.
- GitHub workflows are manual-only; local validation and operator plans are authoritative.
- A Google-internal Preview mint expiry is treated as an external authentication-bridge blocker,
  not a reason to broaden IAM or Runtime scope.
