# OpsPilot Cost Guardrails

Status: MVP deployed; lean Runtime update applied

| Guardrail | Value |
| --- | --- |
| Monthly budget alert | KRW 50,000 |
| Thresholds | 50%, 80%, 100% of current spend |
| Cloud Run | min 0, max 2 per demo service |
| Agent Runtime | min 0, max 1, 1 vCPU, 1 GiB, concurrency 3 |
| Model | Standard PayGo, two calls per supported investigation |
| Data | Synthetic ecommerce only |
| Remediation | Disabled |

The budget is an alert, not a hard cap. Scale-to-zero, bounded queries, immutable images, manual
test windows, and explicit approvals are the actual cost controls.

## Current cost-bearing resources

- Protected versioned GCS Terraform-state bucket.
- Docker Artifact Registry with immutable demo images.
- Three private scale-to-zero Cloud Run services.
- Protected knowledge bucket and Standard Agent Search corpus with 13 documents.
- One project-scoped budget and email notification channel.
- One scale-to-zero Agent Runtime registered with the existing Gemini Enterprise app.

IAM, service accounts, API enablement, and WIF configuration do not independently allocate
always-on compute. The Runtime update in this lean cut changes only its source archive/hash and
adds no resource, minimum instance, query, import, or model request by itself.

## Bounded test usage

- SCN-001: 20 requests per run.
- Local fixture evaluation: no paid model or cloud request.
- Runtime supported request: evidence collection is bounded and model calls are capped at two.
- No retries, scheduled load, custom metric, alert intake, or automatic remediation.

The single approved Enterprise Preview request was consumed and returned a generic Runtime
`INTERNAL` failure. Do not repeat it or broaden IAM under this lean-cut scope. A future diagnostic or
acceptance request requires a separate bounded plan.

## Cleanup order

1. Disable manual hosted plan gates and remove repository variables only after explicit approval.
2. Review the dev destroy plan and deletion-protected resources.
3. Remove dev workloads and Search data only after export/retention decisions.
4. Migrate Terraform state before removing the state bucket.
5. Remove WIF/CI identities after no workflow depends on them.
6. Confirm remaining budgets, APIs, images, objects, and state versions.

VPC, Model Armor, alert intake, remediation, sessions/memory, dashboards, and multi-project support
remain post-MVP options and may not add cost without a separate plan.
