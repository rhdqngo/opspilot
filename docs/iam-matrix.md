# OpsPilot IAM Matrix

Status: M1-M5 applied and hosted zero drift; M7 runtime IAM default-off
Data classification: synthetic only

| Principal | Scope | Allowed in M1 | Explicitly excluded |
| --- | --- | --- | --- |
| Developer / `Edu_687` operator | Current dev project and the investigator SA | Local read checks, completed M1-M4 applies, bounded private invocation, and Approval 2 leaf-SA impersonation after apply | Project-wide impersonation, destroy, repeated Search smoke, unapproved import, billing model changes, unreviewed IAM broadening |
| GitHub CI plan identity | Dev project and state bucket | M1 reads, Cloud Run get/list/getIamPolicy, applied Search data store/schema/engine get/list, service usage consumption, state object read | Search/import, API enable/disable, IAM write, Artifact Registry write, Cloud Run update, budget/state write |
| Investigator identity | Dev project | Seven-permission M5 read role; one accepted bounded live collection; no user-managed key | Private logs, every Logging/Monitoring/Run/Search write, IAM, Secret, invoke, remediation operation |
| Agent Runtime service agent | Existing investigator SA only | Approval 1 source defines one future leaf Token Creator grant | Project-wide token creation, project role, key, runtime query outside Approval 2 |
| Order runtime identity | Payment and inventory services | `roles/run.invoker` on the two leaf services only | Project roles, keys, secrets, IAM, remediation, arbitrary Cloud Run invocation |
| Payment / inventory runtime identities | Their own Cloud Run revisions | No IAM role or user-managed key | Cross-service invocation, project roles, secrets, IAM, remediation writes |
| Remediation identity | Not created | None | All execution permissions until M8 |

## CI plan custom role

The project custom role is limited to the following permissions:

- `artifactregistry.repositories.get`
- `artifactregistry.repositories.list`
- `aiplatform.reasoningEngines.get`
- `aiplatform.reasoningEngines.list`
- `billing.resourcebudgets.read`
- `discoveryengine.dataStores.get`
- `discoveryengine.dataStores.list`
- `discoveryengine.engines.get`
- `discoveryengine.engines.list`
- `discoveryengine.schemas.get`
- `discoveryengine.schemas.list`
- `iam.serviceAccounts.get`
- `iam.serviceAccounts.getIamPolicy`
- `iam.serviceAccounts.list`
- `iam.roles.get`
- `monitoring.notificationChannels.get`
- `monitoring.notificationChannels.list`
- `resourcemanager.projects.get`
- `resourcemanager.projects.getIamPolicy`
- `run.services.get`
- `run.services.getIamPolicy`
- `run.services.list`
- `serviceusage.services.get`
- `serviceusage.services.list`
- `serviceusage.services.use`
- `storage.buckets.get`

The state bucket grants `roles/storage.objectViewer` separately. Dev remote-state plans run with
`-lock=false`; the CI identity has no state object write permissions. The single
`serviceusage.services.use` permission lets the identity consume quota for already enabled read
APIs; it does not grant API enable or disable permission.

GitHub admission uses immutable numeric owner and repository IDs. It does not trust a reusable
repository name, owner name, actor name, branch name, or fork-provided secret.

## Apply boundary

The repository defines resources but grants no automated apply identity. Approval 2 applied the
reviewed custom-role update separately from the exact dev 10-create plan. Service-account keys,
`allUsers`, broad project roles, and automated apply remain prohibited. Safe-path recovery changed
only the three service images and probes; runtime keys, project runtime roles, and public principals
remain zero. The manual hosted plan gate is enabled with the unchanged read-only identity.

## M3 scenario boundary

M3 added no principal, role, IAM binding, service, or job. Approval 2 reused the existing developer
ID-token path for exactly three bounded live runs and updated only the existing Cloud Run
revisions. Runtime user-managed keys, runtime project roles, public principals, and unexpected leaf
invokers remain zero. The order runtime identity retains only its two leaf `roles/run.invoker`
grants. Scenario context is strict request-scoped synthetic data; it neither authorizes a request
nor grants access, and Cloud Run IAM continues to enforce invocation.

## M4 knowledge boundary

The operator's redacted permission check covers bucket/object operations, Search data store/schema/
engine management, document import, operation status, and bounded search. The dedicated bucket,
data store, schema, and engine are now Terraform-owned; they are not candidate conflicts.

Terraform manages only four knowledge resources and no IAM binding. The existing investigator
identity remains unprivileged, and document import/search never runs in hosted Terraform. One
operator FULL import, one fixed probe, and one ten-query acceptance batch succeeded. The hosted
plan identity has the six Search get/list permissions plus the minimum service-usage consumption
permission required by Google APIs. The corrected manual plan returned zero drift. Existing Search
assets are not attached, imported, renamed, or modified.

## M5 live evidence boundary

The applied investigator custom role contains exactly:

- `discoveryengine.servingConfigs.search`
- `logging.logEntries.list`
- `monitoring.timeSeries.list`
- `resourcemanager.projects.get`
- `run.revisions.list`
- `run.services.get`
- `serviceusage.services.use`

The project binding and operator leaf-SA binding are gated by `enable_live_evidence=false` in
source and explicitly enabled in the approved live environment.
Private-log access, invoke, update, IAM, import, Storage read, key creation, and every telemetry or
Search write permission remain excluded from the investigator. The operator receives
`roles/iam.serviceAccountTokenCreator` only on the investigator service account so the live adapter
can use a short-lived OAuth token without a key. The hosted plan role adds only `iam.roles.get`,
`resourcemanager.projects.getIamPolicy`, and `iam.serviceAccounts.getIamPolicy` to refresh the three
Terraform IAM resources.

Approval 2 applied an exact bootstrap custom-role one-update followed by an exact dev three-create
plan. Dev state contains 31 managed resources and 32 total addresses. The operator minted one
short-lived investigator token path for acceptance; no key, broad predefined project role, public
principal, runtime project role, or extra leaf invoker was created. Operator and hosted plans are
zero drift.

## M6 agent boundary

M6 Approval 1 changes no principal, role, binding, API, workload, or Terraform resource. The ADK
graph consumes only the already-normalized `EvidenceCollectionResult`; model nodes receive no
Google Cloud client, token provider, tool, project identifier, URL, filter, or runtime identity.
The fake model is the only enabled CI path. A later Vertex evaluation may reuse operator ADC only
behind a process-scoped gate and separate approval; it does not expand investigator IAM.

## M7 runtime boundary

Approval 1 applies nothing. Source defaults keep Runtime resources and IAM disabled. A separately
approved deployment would add only `aiplatform.endpoints.predict` to the existing investigator
custom role and grant the Vertex Reasoning Engine service agent
`roles/iam.serviceAccountTokenCreator` on that investigator service account alone. The Runtime
reuses the same identity and receives no key, broad predefined role, invoke permission, IAM write,
Storage read, Secret access, or remediation capability.

The hosted plan identity source adds only `aiplatform.reasoningEngines.get/list`. The operator M7
check covers Runtime create/update/get/list/query, operation read, investigator actAs and leaf IAM,
plus Enterprise agent create/get/list/update. Results contain booleans, missing permission names,
and collision counts only.
