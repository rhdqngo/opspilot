# OpsPilot IAM Matrix

Status: M1-M3 applied; M4 knowledge boundary prepared but not applied
Data classification: synthetic only

| Principal | Scope | Allowed in M1 | Explicitly excluded |
| --- | --- | --- | --- |
| Developer / `Edu_687` operator | Current dev project | Local read checks, completed M1-M3 applies, bounded private invocation, M4 read-only gate | Destroy, unapproved Search creation/import, billing model changes, unreviewed IAM broadening |
| GitHub CI plan identity | Dev project and state bucket | M1 reads, Cloud Run get/list/getIamPolicy, applied Search data store/schema/engine get/list, state object read | Search/import, API enable, IAM write, Artifact Registry write, Cloud Run update, budget/state write |
| Investigator identity | Dev project | Identity exists with no project role and no user-managed key | Logging, Monitoring, Run, Deploy, Secret, IAM, remediation writes |
| Order runtime identity | Payment and inventory services | `roles/run.invoker` on the two leaf services only | Project roles, keys, secrets, IAM, remediation, arbitrary Cloud Run invocation |
| Payment / inventory runtime identities | Their own Cloud Run revisions | No IAM role or user-managed key | Cross-service invocation, project roles, secrets, IAM, remediation writes |
| Remediation identity | Not created | None | All execution permissions until M8 |

## CI plan custom role

The project custom role is limited to the following permissions:

- `artifactregistry.repositories.get`
- `artifactregistry.repositories.list`
- `billing.resourcebudgets.read`
- `discoveryengine.dataStores.get`
- `discoveryengine.dataStores.list`
- `discoveryengine.engines.get`
- `discoveryengine.engines.list`
- `discoveryengine.schemas.get`
- `discoveryengine.schemas.list`
- `iam.serviceAccounts.get`
- `iam.serviceAccounts.list`
- `monitoring.notificationChannels.get`
- `monitoring.notificationChannels.list`
- `resourcemanager.projects.get`
- `run.services.get`
- `run.services.getIamPolicy`
- `run.services.list`
- `serviceusage.services.get`
- `serviceusage.services.list`
- `storage.buckets.get`

The state bucket grants `roles/storage.objectViewer` separately. Dev remote-state plans run with
`-lock=false`; the CI identity has no state object write permissions.

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
engine management, document import, operation status, and bounded search. Candidate bucket, data
store, and engine conflicts are zero. Those permissions authorize no action until Approval 2.

Terraform prepares only four knowledge resources and no IAM binding. The existing investigator
identity remains unprivileged, the hosted plan identity receives only six Search get/list
permissions, and document import/search never runs in hosted Terraform. Existing Search assets are
not attached, imported, renamed, or modified.
