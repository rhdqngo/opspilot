# OpsPilot IAM Matrix

Status: M1 applied; M2 runtime boundary defined but not applied
Data classification: synthetic only

| Principal | Scope | Allowed in M1 | Explicitly excluded |
| --- | --- | --- | --- |
| Developer / `Edu_687` operator | Current dev project | Local read checks, local image build, and completed M1 applies | M2 image push/apply before Approval 2, destroy, billing link changes |
| GitHub CI plan identity | Dev project and state bucket | M1 reads and, after Approval 2, Cloud Run get/list/getIamPolicy; state object read | API enable, IAM write, Artifact Registry write, Cloud Run update, budget write, state write |
| Investigator identity | Dev project | Identity exists with no project role and no user-managed key | Logging, Monitoring, Run, Deploy, Secret, IAM, remediation writes |
| Order runtime identity | Not created | Planned invocation of payment and inventory only | Project roles, secrets, IAM, remediation, arbitrary Cloud Run invocation |
| Payment / inventory runtime identities | Not created | No project role planned | Cross-service invocation, secrets, IAM, remediation writes |
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
- `run.services.get` *(defined for Approval 2, not yet applied)*
- `run.services.getIamPolicy` *(defined for Approval 2, not yet applied)*
- `run.services.list` *(defined for Approval 2, not yet applied)*
- `serviceusage.services.get`
- `serviceusage.services.list`
- `storage.buckets.get`

The state bucket grants `roles/storage.objectViewer` separately. Dev remote-state plans run with
`-lock=false`; the CI identity has no state object write permissions.

GitHub admission uses immutable numeric owner and repository IDs. It does not trust a reusable
repository name, owner name, actor name, branch name, or fork-provided secret.

## Apply boundary

The repository defines resources but grants no automated apply identity. M2 Approval 2 must review
the bootstrap custom-role update separately from the dev 10-create plan. Service account keys,
`allUsers`, broad project roles, and automated apply remain prohibited.
