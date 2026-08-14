# OpsPilot Cost Guardrails

**English** | [한국어](cost-model.ko.md)

Status: formal agent deployed; Gemini Enterprise Preview verified

The `core-v1` and `portfolio-v1` evaluation suites use recorded synthetic evidence and the local
deterministic fake model. Their 14 and 80 model-node executions create no Vertex AI, Logging,
Monitoring, Agent Search, or BigQuery request cost. Evaluation artifacts and cleanup plans are local
files under `.tmp`.

| Guardrail | Value |
| --- | --- |
| Monthly budget alert | KRW 50,000 |
| Thresholds | 50%, 80%, 100% of current spend |
| Cloud Run | min 0, max 2 per demo service |
| Agent Runtime | min 0, max 1, 1 vCPU, 1 GiB, concurrency 3 |
| Model | Standard PayGo, two calls per supported investigation |
| Data | Synthetic ecommerce only |
| Remediation | Scale-to-zero; approval required; prod-sim payment only |

The budget is an alert, not a hard cap. Scale-to-zero, bounded queries, immutable images, manual
test windows, and explicit approvals are the actual cost controls.

## Current cost-bearing resources

- Protected versioned GCS Terraform-state bucket.
- Docker Artifact Registry with immutable demo images.
- Nine private scale-to-zero synthetic workload services across dev, staging, and prod-sim.
- Protected knowledge bucket and Standard Agent Search corpus with 13 documents.
- One project-scoped budget and email notification channel.
- One scale-to-zero Agent Runtime registered with the existing Gemini Enterprise app.
- Private scale-to-zero investigation and M8 control services, one Workflow path, Cloud Tasks, and
  bounded Firestore investigation/conversation documents.

IAM, service accounts, API enablement, and WIF configuration do not independently allocate
always-on compute. The Runtime update in this lean cut changes only its source archive/hash and
adds no resource, minimum instance, query, import, or model request by itself.

## Bounded test usage

- SCN-001: 20 requests per run.
- Local fixture evaluation: no paid model or cloud request.
- Runtime supported request: evidence collection is bounded and model calls are capped at two.
- No scheduled load, custom metric, generalized alert intake, or unapproved remediation.
- An approved M8 execution uses one Workflow path, bounded Firestore documents, and exactly ten
  post-action verification orders. Preview QA creates approval requests only and does not execute
  them.

## Cleanup order

1. Disable manual hosted plan gates and remove repository variables only after explicit approval.
2. Review the dev destroy plan and deletion-protected resources.
3. Remove dev workloads and Search data only after export/retention decisions.
4. Migrate Terraform state before removing the state bucket.
5. Remove WIF/CI identities after no workflow depends on them.
6. Confirm remaining budgets, APIs, images, objects, and state versions.

VPC, Model Armor, generalized alert intake/remediation, managed sessions/memory, dashboards, and
multi-project support remain future options and may not add cost without a separate plan.

## Formal-agent bounded usage

The deployed formal environment adds six scale-to-zero Cloud Run services: order, payment, and
inventory in staging and prod-sim, each capped at two instances. A three-service STANDARD or DEEP
investigation remains bounded to 12 logical tool calls and at most 18 provider calls; QUICK remains at six logical calls
and at most nine provider calls. RCA/report generation remains capped at two model calls and is
skipped when no direct incident signal exists. Conversation context is one small Firestore document
per active session with a 24-hour TTL. These are architectural bounds, not a monetary estimate.
