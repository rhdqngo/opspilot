# Verification Evidence Index

**English** | [한국어](README.ko.md)

This directory contains sanitized, source-bound release and QA records. Markdown files are the
human-readable summaries; adjacent JSON files contain the same bounded result in machine-readable
form. Cloud project identifiers, URLs, service identities, image digests, Runtime resource names,
trace/run/investigation IDs, and browser captures are intentionally excluded.

## Current source of record

| Record | Status | Purpose |
| --- | --- | --- |
| [Formal agent v3](long-spec-formal-agent-v3.md) ([JSON](long-spec-formal-agent-v3.json)) | Passed | Final positive Gemini Enterprise Preview incident detection, localization correction, backend invariants, and 278-test source-bound gate |

## Formal-agent progression

| Record | Status | Purpose |
| --- | --- | --- |
| [Formal agent v2](long-spec-formal-agent-v2.md) ([JSON](long-spec-formal-agent-v2.json)) | Passed | Final Preview regression and concise healthy-summary correction |
| [Formal agent v1](long-spec-formal-agent-v1.md) ([JSON](long-spec-formal-agent-v1.json)) | Passed | Three-environment rollout and managed conversational verification |
| [Enterprise QA v4](long-spec-enterprise-qa-v4.md) ([JSON](long-spec-enterprise-qa-v4.json)) | Passed | Preview matrix before the formal-agent expansion |
| [Pre-QA v1](long-spec-preqa-v1.md) ([JSON](long-spec-preqa-v1.json)) | Passed | Source-bound deployment, trace, audit, privacy, and idempotency readiness |

## Historical audit trail

These records are retained to show the defects and provider conditions encountered before the
passing candidates. They are not current release claims.

| Record | Historical outcome |
| --- | --- |
| [Enterprise QA v1](long-spec-enterprise-qa-v1.md) ([JSON](long-spec-enterprise-qa-v1.json)) | Blocked |
| [Enterprise QA v2](long-spec-enterprise-qa-v2.md) ([JSON](long-spec-enterprise-qa-v2.json)) | Blocked by confirmed provider streaming failure |
| [Enterprise QA v3](long-spec-enterprise-qa-v3.md) ([JSON](long-spec-enterprise-qa-v3.json)) | Blocked before Preview canary |
| [MVP cloud release v1](mvp-cloud-release-v1.md) ([JSON](mvp-cloud-release-v1.json)) | Passed historical MVP gate |
| [Portfolio release v1](portfolio-release-v1.md) ([JSON](portfolio-release-v1.json)) | Passed historical offline portfolio gate |

Raw execution evidence belongs under `.tmp` and is never versioned.
