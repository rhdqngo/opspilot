# ADR-010: Fixed-scope Agent Runtime and Enterprise boundary

Status: accepted for M7 Approval 1

## Decision

Deploy the existing OpsPilot graph through a separate ADK discovery entrypoint. A public async
`before_agent_callback` deterministically validates natural-language input and always returns the
final response, so no upper routing model is called. Only `payment-service` and the recent
30-minute read-only investigation are in the MVP contract.

Use workload ADC with the existing investigator service account. Add only Vertex prediction to its
existing read role. The Vertex Reasoning Engine service agent receives Token Creator on that one
service account, not at project scope. Runtime packaging is deterministic, source-inline,
identifier-free, and generated only in ignored storage.

Register into one existing global Gemini Enterprise app only after a separate deployment approval.
Registration uses one fixed display name, is plan-first and idempotent, and stops on app, runtime,
or display-name ambiguity.

## Consequences

- Existing M6 local discovery, fixture, evaluation, prompts, graph, and report contracts remain
  unchanged.
- Out-of-scope input incurs zero evidence and model calls.
- Approval 1 changes no cloud resource, IAM policy, repository variable, or Enterprise app.
- Sessions, Memory Bank, OAuth user delegation, Agent Gateway, VPC, Model Armor, alert intake,
  remediation, dashboards, and multi-project operation remain post-MVP.
