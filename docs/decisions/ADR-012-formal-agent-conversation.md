# ADR-012: Formal Incident Commander Conversation Boundary

Status: accepted for implementation; managed validation pending  
Date: 2026-08-14  
Supersedes: the production-graph and single-turn constraints in ADR-011

## Decision

OpsPilot uses one Gemini Enterprise Runtime as a thin authenticated stream adapter and one
investigation API as the authoritative intent, context, evidence, reasoning, report, and
remediation-request boundary.

The API supports the three catalog services in `dev`, `staging`, and synthetic `prod-sim`, with
bounded 1-120 minute windows and QUICK/STANDARD/DEEP evidence plans. It may retain 24 hours of
structured conversation scope keyed only by a domain-separated session hash. Raw prompts, user or
session identifiers, evidence bodies, arbitrary cloud filters, projects, and URLs are never stored
in conversation context or forwarded to the model.

Evidence-backed live signals may enter the existing ADK RCA and report graph, which remains capped
at two model calls. No-signal requests bypass the model. A model timeout, schema failure, or invalid
citation produces an inconclusive evidence-backed report.

The only conversational write outcome is creation of an approval request for an eligible
`prod-sim payment-service` rollback. The Runtime and investigation API cannot approve or execute
it. The existing M8 control API, approval identity, Workflow, and single-service executor remain
the exclusive mutation path.

## Consequences

- ADR-011 remains authoritative for persistent task, audit, trace, redaction, and idempotency
  mechanics, but no longer limits the production path to single-turn DEV investigation or excludes
  the production ADK graph.
- Real production, general chat, arbitrary GCP queries, arbitrary writes, automatic approval, and
  automatic execution remain unsupported.
- Existing DEV Terraform addresses and Firestore documents remain compatible; new fields and
  conversation documents are additive and expire without a data migration.
- Rollout is four source-bound binary plans with phase-specific address allowlists. Only the three
  named M8 IAM target changes may replace resources; every other delete/replace, public invoker,
  Runtime rename, or image/archive hash mismatch is a release stop.
