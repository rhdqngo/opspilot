# OpsPilot MVP Threat Model

Status: active

Anonymous `RUN-…` identifiers are generated independently for each agent/Runtime invocation. They
are not derived from Enterprise user or session identifiers and cannot authorize any action.
Runtime summaries expose only source status/error codes and reasoning outcome; prompts, projects,
evidence payloads, raw exceptions, and identities remain excluded.

| Threat | Control | Residual risk |
| --- | --- | --- |
| Arbitrary cloud scope | Fixed project environment plus service/time/metric/filter allowlists; no caller project, URL, token, resource name, or raw filter | Project-level read permissions still rely on application allowlists |
| Evidence forgery | Immutable evidence IDs, direction checks, duplicate/missing reference rejection, complete citation admission | Source systems can contain incorrect synthetic data |
| Prompt injection | Knowledge text is tagged untrusted data; model has no tools; action filtering is deterministic | Model prose may still be poor, but cannot execute |
| Unsafe remediation | No remediation endpoint or write tool; executable actions removed; all retained recommendations require approval | Human operator can still make a bad manual decision |
| Sensitive-data leakage | Bounded redaction, logical `opspilot://` URIs, safe errors, telemetry content capture off | Provider-managed request metadata remains outside app control |
| Runaway cost or latency | Two model calls, bounded evidence requests, no retry, 30/75-second timeouts, scale-to-zero, KRW 50,000 alert | Budget alerts are not hard caps |
| Runtime surface expansion | One `AdkApp` async-stream operation and explicit archive allowlist | Platform behavior can change across provider versions |
| Enterprise authentication bridge failure | Preserve private IAM; classify internal expired mint as external blocker | Preview may temporarily fail despite a healthy Runtime |

The MVP deliberately excludes automatic alert intake, remediation, VPC/perimeter work, Model Armor,
sessions/memory, dashboards, and multi-project support. These require separate threat-model updates.
