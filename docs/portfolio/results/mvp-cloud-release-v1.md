# OpsPilot MVP Cloud Release Evidence

- Status: **PASSED**
- Verified: `2026-08-13`
- Scope: dev M8 remediation plus persistent investigation release
- Evidence policy: sanitized; no project IDs, URLs, identities, incident IDs, or image digests

## M8 remediation

| Check | Result |
| --- | ---: |
| Baseline orders | 10/10 |
| Fault orders | 0/10 |
| Approval-gated rollback | SUCCEEDED |
| Target revision traffic | 100% |
| Recovery orders | 10/10 |
| Reset orders | 10/10 |
| Public invoker | none |
| Final Terraform drift | No changes |

## Persistent investigations

| Check | Result |
| --- | ---: |
| Runtime stream | progress + final (2 events) |
| Runtime requested scope | 3 services / 15 minutes |
| Persisted report | v1 / 41 evidence items |
| API replay | v2 |
| Deterministic comparison | passed |
| Duplicate task delivery | no extra report version |
| Alert lifecycle | OPEN -> duplicate -> CLOSED |
| Alert-triggered investigations | 0 |
| Raw/user alert fields stored | none |
| Private API invokers | 3 |
| Runtime direct evidence role | absent |
| Approved API image digest | bound |

## Validation

| Check | Result |
| --- | ---: |
| Pytest | 193/193 |
| Ruff format / lint | passed |
| Strict mypy | 81 source files |
| Package build | passed |
| Core evaluation | 7/7 |
| Portfolio evaluation | 40/40 |
| Remediation evaluation | 12/12 |
| Runtime package | 9 files / deterministic |
| Terraform bootstrap tests | 1/1 |
| Terraform dev tests | 8/8 |
| Final Terraform drift | No changes |

The release retains approval, IAM separation, fixed targets, plan hash, expiry, idempotency, lease,
etag/revision/image binding, traffic verification, citation integrity, redaction, timeout, and cost
bounds. Recovery-only exact-address/count/state-move checks and duplicate plan-only preflight calls
were removed after M8 stabilization.
