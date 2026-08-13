# OpsPilot MVP Cloud Release Evidence

- Status: **PASSED**
- Verified: `2026-08-13`
- Scope: dev M8 remediation plus persistent investigation release
- Evidence policy: sanitized; no project IDs, URLs, identities, incident IDs, or image digests
- Source commit: `eaea85038f0bbfbf58e8d43b811567c2b5bf9612`
- Source tree SHA-256: `38e42efae7df3330119da99f6787b42d69633a1abf48fa5ff593088dcdc0a53a`
- Release context SHA-256: `5552acb21131638ead5f5c79000a2b1931f3cb6adea37970f9bb2cf5652de42a`

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

## Closure alignment

| Check | Result |
| --- | ---: |
| Runtime stream after source update | progress + persisted final (2 events) |
| Runtime safe failure | none |
| Runtime package | 9 files / `b3c0c5559246d7ebd2db13b534459f4db7745315fbaaaf39919cc603ec132b12` |
| Investigation container health | passed |
| Updated Cloud Run services | 3 / Ready |
| Source-only Terraform update | 4 in-place / 0 create / 0 destroy |
| Bootstrap / dev drift | No changes / No changes |
| Hosted PR checks | blocked before runner assignment (`31675348391`) |
| Hosted Terraform checks | blocked before runner assignment (`31675350779`) |
| Hosted Terraform plan | blocked before runner assignment (`31675352527`) |

The hosted jobs created zero steps because GitHub rejected runner assignment for an account billing
or spending-limit condition. This is an external hosted-validation blocker, not a repository check
failure; the equivalent local checks and both operator Terraform drift plans passed.

## Validation

| Check | Result |
| --- | ---: |
| Pytest | 193/193 |
| Ruff format / lint | passed |
| Strict mypy | 82 checked files |
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
