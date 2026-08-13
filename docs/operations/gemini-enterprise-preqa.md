# Gemini Enterprise pre-QA release

This runbook stops immediately before the first Gemini Enterprise Preview UI query. The managed
Agent Runtime may be invoked directly for release verification, but the Enterprise agent chat is a
separate QA gate.

## Source-bound release profile

Run every phase against one clean `main` commit and one `.tmp/preqa-release` directory:

```powershell
uv run python scripts/preqa_release.py preflight --output .tmp/preqa-release
uv run python scripts/preqa_release.py image --output .tmp/preqa-release
uv run python scripts/preqa_release.py terraform-plan --output .tmp/preqa-release
uv run python scripts/preqa_release.py record --phase post-apply --output .tmp/preqa-release
uv run python scripts/preqa_release.py record --phase smoke --output .tmp/preqa-release
uv run python scripts/preqa_release.py record --phase final-plan --output .tmp/preqa-release
uv run python scripts/preqa_release.py record --phase hosted --output .tmp/preqa-release
uv run python scripts/preqa_release.py publish --output .tmp/preqa-release
```

`preflight` runs the complete offline portfolio release gate, Terraform validation/tests,
remediation evaluation, and two byte-identical Runtime package builds. It records the source commit,
source-tree hash, and Runtime SHA-256 in `release-context.json`. Later phases fail if the clean source
context changes.

The image phase requires `OPSPILOT_PREQA_LOCAL_IMAGE` and
`OPSPILOT_PREQA_REGISTRY_IMAGE_URI`. The Terraform-plan phase requires
`OPSPILOT_PREQA_IMAGE_DIGEST`. Environment values must be scoped to the current process and must not
be committed.

## Terraform boundary

The reviewed binary plan must contain exactly `0 add / 2 change / 0 destroy`, both as in-place
updates:

- `google_cloud_run_v2_service.investigation_api[0]`
- `google_vertex_ai_reasoning_engine.opspilot[0]`

The release verifier rejects create, delete, replacement, any third address, public IAM members,
an unapproved investigation image digest, a mismatched Runtime archive, or a changed Runtime resource
name. Apply only the verified `.tmp/preqa-release/preqa.tfplan`; never recreate it between review and
apply.

The default expected set is both addresses. If a failed smoke requires a source-bound recovery and
one resource already has the final bytes, set `OPSPILOT_PREQA_EXPECTED_ADDRESSES` to the exact
comma-separated non-empty subset before verification. The subset must still be drawn from the two
addresses above; a third address, empty plan, or unrequested second change is rejected.

## Post-apply evidence

Phase inputs use fixed boolean schemas and contain no cloud identifiers. Keep project IDs, URLs,
identities, image digests, trace/run/investigation IDs, questions, and raw log content only in the
operator's ephemeral session. The published `long-spec-preqa-v1` evidence includes hashes and check
outcomes, not those identifiers.

Stop and do not mark the release QA-ready if the plan scope drifts, the Runtime resource is replaced,
the Enterprise registration target changes, private text is retained, trace IDs diverge, or duplicate
tasks/reports/executor attempts are observed.

Hosted Runner zero-step failures caused by the existing billing or quota condition are recorded as an
external non-blocking result; they do not replace the local and managed-environment gates.

## Completed checkpoint

The implementation commit passed the source-bound release profile and the sanitized result is
published at [`long-spec-preqa-v1.md`](../portfolio/results/long-spec-preqa-v1.md). The existing
OpsPilot registration is enabled and still targets the unchanged Runtime. The Preview chat was not
opened and no Preview query was submitted.

## Enterprise QA handoff cases

Do not execute these in Preview during pre-QA preparation. Hand them to the QA operator with the
expected result:

| Case | Prompt shape | Expected result |
| --- | --- | --- |
| Korean normal | Korean request with `개발` and one incident ID | DEV investigation, one H-01 and one safe H-02, three recommendation classes |
| English normal | `dev payment-service last 15 minutes errors` | Persisted cited report with progress then final response |
| Environment omitted | Valid investigation without environment | DEV assumption is explicit |
| Unsupported environment | Explicit prod, production, stage, staging, or QA | Rejected; never silently changed to DEV |
| Incident ID conflict | Body and API IDs differ, or body has multiple IDs | 422 validation response |
| Alternative hypothesis | Conclusive SCN-001 result | H-01 unchanged and non-assertive H-02 present |
| Recommendation policy | Conclusive canonical cause | containment, mitigation, and root-fix/prevention sections, all cited |
| Privacy sentinel | Synthetic email and token-shaped text | Redacted storage/output; only domain-separated hashes retained |

## Executed Preview QA

The handoff cases were executed on 2026-08-13 and the sanitized record is published at
[`long-spec-enterprise-qa-v1.md`](../portfolio/results/long-spec-enterprise-qa-v1.md). English
SCN-001, privacy redaction, all eight negative boundaries, scenario recovery, and final no-drift
checks passed. The release remains blocked on healthy final delivery, the Korean unused-incident-ID
flow, visible default-DEV assumption, and missing tool-event `run_id`. No product or infrastructure
change was made during QA.

## Iterative QA remediation candidate

The next source-bound candidate starts the Runtime handler before progress, accepts valid unused
incident IDs as new user-source incidents, renders localized assumptions and canonical Korean
narrative, and propagates the stored Runtime run ID into every logical evidence-tool event. Local
gates pass 234 pytest cases, core 7/7, portfolio 40/40, remediation 12/12, strict mypy, build,
Terraform bootstrap 1/1 and dev 8/8, and two byte-identical 11-file Runtime packages. The candidate
remains blocked until the limited image/Runtime rollout and the complete Preview v2 matrix pass.
