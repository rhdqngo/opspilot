# OpsPilot MVP Threat Model

Status: updated for M6 Approval 2 controls

## Protected assets and trust boundaries

OpsPilot protects cloud credentials, project and resource identifiers, raw telemetry, incident
integrity, and the human approval boundary. External logs, metrics, revision metadata, retrieved
knowledge, user questions, and every model response are untrusted. Only allowlisted collectors,
typed normalizers, immutable evidence IDs, deterministic verification, and explicit operator
approval cross those boundaries.

## M6 threats and controls

| Threat | Control | Residual risk |
| --- | --- | --- |
| Prompt injection in logs or runbooks | Instructions label evidence as untrusted; model tools are empty; malicious fixture must produce no action | Model prose can still be misleading and requires human review |
| Forged or missing citation | Reviewer output is advisory; deterministic verifier rejects unknown, duplicate, or direction-mismatched evidence IDs | A legitimate but weak source may still be overinterpreted |
| Hallucinated confidence | Model cannot set support score or report status; code applies source diversity and contradiction penalties | Scoring weights remain a product policy choice |
| Credential or identifier disclosure | Bounded logical evidence view strips raw records, cloud identifiers, URLs, filters, tokens, request IDs, and trace IDs | Future adapters require repeat redaction tests |
| Unbounded cost or latency | Three calls per case, 64 KiB per request, 2,048 tokens per node, 60-second graph and 200-second three-case deadline; attempted calls are counted before transport | Provider-side token accounting is accepted only from bounded usage metadata |
| Unauthorized remediation | No tools or write endpoint; unsafe action text is dropped; all retained actions require approval | M8 needs a separate action-policy threat review |
| Unsafe failure leakage | Exceptions normalize to fixed error categories and ADK internal trace logging is suppressed at the public boundary | Local debug mode must never be enabled in hosted output |

## Deferred reviews

Agent Runtime, Gemini Enterprise registration, session persistence, approval state, and remediation
remain deferred. The M6 Vertex boundary is local operator-only, fixture-only, tool-free, and
process-gated; it does not grant a runtime identity or persist a session.
