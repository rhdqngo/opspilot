# ADR-002: Bounded evidence-first orchestration

Status: implemented

## Decision

OpsPilot uses a fixed seven-node ADK graph. Only RCA drafting and report composition call the
model. Citation review, scoring, taxonomy classification, action filtering, and report admission
are deterministic code.

The model has no tools. Each model node is limited to 30 seconds, 64 KiB input, and 2,048 output
tokens. The graph is limited to 75 seconds, two model calls, concurrency one, and no retry.

## Rationale

The product must distinguish model prose from verified operational facts. Root-cause taxonomy is
therefore derived from cited supporting evidence, not from a model-provided label. The reviewer
rejects duplicate, missing, forged, and direction-mismatched citations. Prompt-injection content
is untrusted evidence and cannot change the graph or become an action.

## Consequences

- Every admitted claim has complete logical citation coverage.
- A partial source failure becomes a visible data gap; complete failure returns a safe error.
- Executable recommendations are removed and retained recommendations require approval.
- Model-origin taxonomy, acceptance suites, phase timing, and timeout-origin inference are not
  public product contracts. They were pre-release validation aids and have been removed.
- A future model-based independent reviewer is post-MVP and requires a separate decision.
