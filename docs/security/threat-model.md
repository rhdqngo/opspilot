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
| Unsafe remediation | M7 Runtime remains read-only; separate M8 control API requires report/change evidence, canonical plan hash, 15-minute approval, transaction, exact service/revision/digest/etag revalidation, and one traffic-only executor | An authorized approver can still approve a poor but policy-valid rollback |
| Callback theft or replay | Callback URL is stored only in a 24-hour TTL collection, never returned or logged, requires `workflows.callbacks.send`, and every decision checks explicit plan expiry | TTL deletion is asynchronous; explicit expiry checks remain authoritative |
| Concurrent or lost responses | Atomic idempotency and one execution lease; executor concurrency is one; already-recovered traffic is idempotent success after response loss | Provider reconciliation or verification can still end in a safe terminal failure |
| Identity confusion | Cloud Run Group Invoker plus issuer/audience/verified-email/subject checks; audit stores actor hash and `self_approved`, never email | Group lifecycle remains an external administrative control |
| Sensitive-data leakage | Bounded redaction, logical `opspilot://` URIs, safe errors, telemetry content capture off | Provider-managed request metadata remains outside app control |
| Runaway cost or latency | Two model calls, bounded evidence requests, no retry, 30/75-second timeouts, scale-to-zero, KRW 50,000 alert | Budget alerts are not hard caps |
| Runtime surface expansion | One `AdkApp` async-stream operation and explicit archive allowlist | Platform behavior can change across provider versions |
| Enterprise authentication bridge failure | Preserve private IAM; classify internal expired mint as external blocker | Preview may temporarily fail despite a healthy Runtime |

M8 remains default-off and supports only SCN-008 payment revision rollback. Automatic alert intake,
general remediation, VPC/perimeter work, Model Armor, sessions/memory, dashboards, BigQuery, and
multi-project support remain excluded.
