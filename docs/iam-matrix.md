# OpsPilot IAM Matrix

Status: M1 and M2 runtime boundary applied; M2 remote invocation validation blocked
Data classification: synthetic only

| Principal | Scope | Allowed in M1 | Explicitly excluded |
| --- | --- | --- | --- |
| Developer / `Edu_687` operator | Current dev project | Local read checks, image push, and completed M1/M2 applies | Destroy, billing link changes, unreviewed IAM broadening |
| GitHub CI plan identity | Dev project and state bucket | M1 reads, Cloud Run get/list/getIamPolicy, and state object read | API enable, IAM write, Artifact Registry write, Cloud Run update, budget write, state write |
| Investigator identity | Dev project | Identity exists with no project role and no user-managed key | Logging, Monitoring, Run, Deploy, Secret, IAM, remediation writes |
| Order runtime identity | Payment and inventory services | `roles/run.invoker` on the two leaf services only | Project roles, keys, secrets, IAM, remediation, arbitrary Cloud Run invocation |
| Payment / inventory runtime identities | Their own Cloud Run revisions | No IAM role or user-managed key | Cross-service invocation, project roles, secrets, IAM, remediation writes |
| Remediation identity | Not created | None | All execution permissions until M8 |

## CI plan custom role

The project custom role is limited to the following permissions:

- `artifactregistry.repositories.get`
- `artifactregistry.repositories.list`
- `billing.resourcebudgets.read`
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
`allUsers`, broad project roles, and automated apply remain prohibited. The hosted plan gate is
disabled while the private `run.app` route returns a pre-container 404. Endpoint recovery leaves
the service IAM boundary unchanged.
