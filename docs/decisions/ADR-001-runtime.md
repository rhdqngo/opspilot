# ADR-001: Use Agent Runtime as the target agent host

Status: accepted for planning  
Date: 2026-08-10

## Decision

Deploy the future ADK incident commander to Agent Runtime in `asia-northeast3` when M7 access
gates pass. Keep local fixture execution as the development and CI fallback.

## Rationale

Agent Runtime provides the managed deployment and Gemini Enterprise registration path required
by the product brief. R0 intentionally carries no runtime dependency or cloud credential.

## Revisit when

The intended project lacks Agent Runtime access, Seoul support changes, or measured cost exceeds
the KRW 50,000 monthly guardrail.
