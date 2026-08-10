# OpsPilot IAM Matrix

Status: bootstrap applied; dev foundation not applied
Data classification: synthetic only

| Principal | Scope | Allowed in M1 | Explicitly excluded |
| --- | --- | --- | --- |
| Developer / `Edu_687` operator | Current dev project | Local read checks and separately approved Terraform apply | Unapproved apply, destroy, billing link changes |
| GitHub CI plan identity | Dev project and state bucket | M1 get/list custom role; state object read | API enable, IAM write, Artifact Registry write, budget write, state write |
| Investigator identity | Not created | None until Approval 2 | Logging, Monitoring, Run, Deploy, Secret, IAM, remediation writes |
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
- `serviceusage.services.get`
- `serviceusage.services.list`
- `storage.buckets.get`

The state bucket grants `roles/storage.objectViewer` separately. Before dev state exists, the
hosted workflow uses an ephemeral local state. Later remote-state plans run with `-lock=false`;
the CI identity has no state object write permissions.

GitHub admission uses immutable numeric owner and repository IDs. It does not trust a reusable
repository name, owner name, actor name, branch name, or fork-provided secret.

## Apply boundary

The repository defines resources but grants no automated apply identity. Bootstrap and dev apply
use the authenticated operator only after separate approvals. Service account keys are prohibited.
