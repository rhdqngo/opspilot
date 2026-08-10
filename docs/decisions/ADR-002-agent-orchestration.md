# ADR-002: Combine deterministic workflow with bounded agent reasoning

Status: accepted  
Date: 2026-08-10

## Decision

Keep collection, normalization, policy, scoring, and citation validation deterministic. Introduce
ADK reasoning later only for hypothesis generation, review, and report composition.

## Rationale

This preserves reproducibility, parallel collection, cost bounds, and trajectory evaluation while
preventing an LLM from constructing executable resource queries or action payloads.
