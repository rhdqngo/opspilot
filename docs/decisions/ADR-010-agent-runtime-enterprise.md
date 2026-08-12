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

During the MVP, GitHub workflows remain available only through `workflow_dispatch` and are not
acceptance gates. Local operator validation and zero-drift plans are authoritative. The existing
WIF infrastructure is preserved, but M7 adds no hosted-reader permission and performs no bootstrap
apply.

## Consequences

- Existing M6 local discovery, fixture, evaluation, prompts, graph, and report contracts remain
  unchanged.
- Out-of-scope input incurs zero evidence and model calls.
- Approval 1 changes no cloud resource, IAM policy, repository variable, or Enterprise app.
- A fixed gated rejection probe validates the deployed boundary without accepting arbitrary input
  or exposing provider response data.
- Sessions, Memory Bank, OAuth user delegation, Agent Gateway, VPC, Model Armor, alert intake,
  remediation, dashboards, and multi-project operation remain post-MVP.

## Deployment checkpoint

The source package now includes the pinned Agent Platform SDK and passes isolated Python 3.12
imports. A managed Runtime still cannot expose the raw ADK `LlmAgent` directly: operation discovery
requires a supported query-capable wrapper. The Runtime-only entrypoint therefore uses the official
`AdkApp` wrapper and publishes only `streaming_agent_run_with_events` in async-stream mode. This is
the Gemini Enterprise integration operation; session, memory, artifact, unary-query, and bidi
operations remain outside the MVP surface. The wrapper passed isolated operation discovery and
streaming rejection tests without changing the graph or deterministic input callback.

Terraform source deployments do not infer the API `classMethods` declaration from that object. The
final Runtime create succeeded but returned an empty operation schema, so Enterprise integration is
fail-closed. A separate decision may add exactly one `spec.class_methods` declaration matching the
already implemented streaming method; it must not add another operation or product capability.
