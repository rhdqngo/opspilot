# OpsPilot MVP Threat Model

Status: M6 complete; M7 runtime boundary implemented and deployment remains separate

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
| Forged or missing citation | A fixed reviewer rejects duplicate draft IDs and unknown, duplicate, or direction-mismatched evidence IDs before deterministic scoring | A legitimate but weak source may still be overinterpreted |
| Hallucinated confidence | Model cannot set support score or report status; code applies source diversity and contradiction penalties | Scoring weights remain a product policy choice |
| Credential or identifier disclosure | Bounded logical evidence view strips raw records, cloud identifiers, URLs, filters, tokens, request IDs, and trace IDs | Future adapters require repeat redaction tests |
| Unbounded cost or latency | Two calls per case, 64 KiB per request, 2,048 tokens per node, 30-second node, 75-second graph, and 200-second suite deadline; attempted calls are counted before transport | Provider-side token accounting is accepted only from bounded usage metadata |
| Unauthorized remediation | No tools or write endpoint; unsafe action text is dropped; all retained actions require approval | M8 needs a separate action-policy threat review |
| Unsafe failure leakage | Exceptions normalize to fixed error categories and ADK internal trace logging is suppressed at the public boundary | Local debug mode must never be enabled in hosted output |
| Invalid advisory review output | Citation review is local deterministic code; no model response is parsed at this stage | A future model reviewer would require a separate post-MVP contract and approval |
| Semantic acceptance mismatch | The fixed suite exposes allowlisted predicate failures and stops before later cases without retry | Strict raw-code matching can reject a semantically related but unapproved taxonomy label |
| Taxonomy coercion | Canonicalization uses fixed service/source/quality-flag rules only after citation and direction verification; model labels and evidence prose are not classification inputs | Synthetic quality flags require a separate production vocabulary review after MVP |
| Timeout misclassification or diagnostic leakage | Public callbacks retain only allowlisted phase names and bounded monotonic milliseconds; timeout origin is derived from the last completed phase | A pre-response timeout cannot distinguish provider latency from framework work before the response callback |

## M7 preparation threats and controls

| Threat | Control | Residual risk |
| --- | --- | --- |
| Natural-language scope expansion | Public callback accepts exactly payment-service and a recent 30-minute read-only investigation; all other input stops before cloud/model calls | Korean/English intent vocabulary is intentionally narrow for MVP |
| User identity or prompt capture | Input is used only for deterministic scope selection; email/user ID is ignored; Runtime telemetry content capture is explicitly off | Approval 2 must verify hosted telemetry behavior |
| Runtime credential broadening | Existing investigator SA, workload ADC, eight explicit permissions, no key; Runtime service agent gets leaf Token Creator only | Project-wide telemetry read remains bounded by synthetic-only project and server-side filters |
| Package contamination | Deterministic file allowlist, pinned requirements, packaged catalog, ignored output, no archive artifact | Dependency supply-chain review remains CI/static rather than attestation-based |
| Ambiguous Enterprise registration | One global app, one fixed-name runtime, one fixed-name registration; ambiguity hard-stops and apply is process-gated | Existing app administrator must still review the Approval 2 mutation |

## Deferred reviews

Agent Runtime deployment and Gemini Enterprise registration remain deferred to Approval 2.
Sessions, Memory Bank, OAuth user delegation, Agent Gateway, VPC, Model Armor, approval state, and
remediation remain excluded. M7 Approval 1 grants no runtime identity and persists no session.
