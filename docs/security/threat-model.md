# OpsPilot Formal Agent Threat Model

**English** | [한국어](threat-model.ko.md)

Status: active

Run, correlation, and trace identifiers are generated independently for each agent/Runtime
invocation and cannot authorize any action. Enterprise user/session identifiers and verified API
subjects are retained only as source-domain SHA-256 pseudonyms. The raw query is redacted before
persistence and represented in audit by a source-domain query hash. Runtime/tool summaries exclude
prompts, projects, URLs, tokens, evidence payloads, raw exceptions, and raw identities.

| Threat | Control | Residual risk |
| --- | --- | --- |
| Arbitrary cloud scope | Fixed project environment plus service/time/metric/filter allowlists; no caller project, URL, token, resource name, or raw filter | Project-level read permissions still rely on application allowlists |
| Evidence forgery | Immutable evidence IDs, direction checks, duplicate/missing reference rejection, complete citation admission | Source systems can contain incorrect synthetic data |
| Prompt injection | Knowledge text is tagged untrusted data; model has no tools; action filtering is deterministic | Model prose may still be poor, but cannot execute |
| Unsafe remediation | Runtime investigation authority remains read-only; separate M8 control API requires report/change evidence, canonical plan hash, 15-minute approval, transaction, exact service/revision/digest/etag revalidation, and one traffic-only executor | An authorized approver can still approve a poor but policy-valid rollback |
| Callback theft or replay | Callback URL is stored only in a 24-hour TTL collection, never returned or logged, requires `workflows.callbacks.send`, and every decision checks explicit plan expiry | TTL deletion is asynchronous; explicit expiry checks remain authoritative |
| Concurrent or lost responses | Atomic idempotency and one execution lease; executor concurrency is one; already-recovered traffic is idempotent success after response loss | Provider reconciliation or verification can still end in a safe terminal failure |
| Identity confusion | Cloud Run IAM plus issuer/audience/subject checks; Runtime, task, alert, direct API, and M8 identities are endpoint-scoped and source-domain hashed; audit never stores email | Group and service-account lifecycle remains an external administrative control |
| Sensitive-data leakage | Redact before persistence, source-domain query/user/session hashes, fixed tool-event allowlist, logical `opspilot://` URIs, safe errors, telemetry content capture off | Provider-managed request metadata remains outside app control |
| Runaway cost or latency | Two model calls, bounded evidence requests, maximum-three jittered transient retries inside deadlines, scale-to-zero, KRW 50,000 alert | Budget alerts are not hard caps |
| Runtime surface expansion | One `AdkApp` async-stream operation and explicit archive allowlist | Platform behavior can change across provider versions |
| Enterprise authentication bridge failure | Preserve private IAM; classify internal expired mint as external blocker | Preview may temporarily fail despite a healthy Runtime |

Formal-agent context adds no raw memory: `conversation_contexts` stores only a pseudonymous session
hash and structured scope/report references with a 24-hour TTL. The model receives only bounded,
sanitized evidence with logical URIs and remains tool-free. Revision snapshots outside the requested
window may be used only for server-side key-difference calculation and are removed before report or
model input.

M8 remains approval-gated and supports only prod-sim payment revision rollback. Runtime can request a
`WAITING_APPROVAL` record only through the authenticated investigation-to-control bridge; it cannot
approve, reject, or execute. DEV, staging, order/inventory, restart, and real-production writes are
policy rejected.

Automatic remediation
from alerts, general remediation, VPC/perimeter work, Model Armor, sessions/memory, dashboards,
BigQuery, and multi-project support remain excluded.
