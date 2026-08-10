# ADR-003: Make evidence the report source of truth

Status: accepted  
Date: 2026-08-10

## Decision

Normalize every tool result into a typed `EvidenceItem`. Material report claims, timeline events,
hypotheses, and recommended actions may reference only evidence IDs present in the report.

## Rationale

Schema validation rejects forged and missing citations. Evidence support scores are deterministic
rule outputs rather than model confidence estimates.
