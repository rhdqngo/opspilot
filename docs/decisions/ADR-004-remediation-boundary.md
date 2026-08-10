# ADR-004: Separate investigation from remediation

Status: accepted  
Date: 2026-08-10

## Decision

The investigator remains read-only. R0 exposes no remediation route or execution tool. A later
sandbox executor must use a separate identity, immutable plan hash, expiry, idempotency, explicit
human approval, and post-action verification.

## Rationale

Untrusted prompts, logs, documents, and model output must not become a direct production write
path. Recommendations are data until a separate policy and approval boundary accepts them.
