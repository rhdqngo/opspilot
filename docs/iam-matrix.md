# OpsPilot IAM Matrix

Status: deployed M7 boundary; M8 roles are implemented default-off and not applied

| Principal | Allowed purpose | Explicitly excluded |
| --- | --- | --- |
| Local operator | Reviewed Terraform apply, bounded manual validation | Automatic remediation, broad runtime role |
| Terraform plan identity | Remote-state read and resource get/list needed for manual plans | Apply, API enable/disable, IAM write, import, model query |
| Runtime SA | Invoke only the private investigation API; use platform metadata for SDK bootstrap | Project role, evidence reads, Firestore, Tasks, remediation, keys, IAM write |
| Investigation API SA | Read bounded Logging/Monitoring/Run/Search evidence; create bounded tasks and investigation records | IAM write, Cloud Run update, remediation, delete permissions |
| Order runtime SA | Invoke payment and inventory Cloud Run services | Project-wide role, key, other service invocation |
| Payment/inventory runtime SAs | Run their private services | Project role, key, downstream invocation |
| Reasoning Engine service agent | Mint short-lived credentials for the investigator SA only | Project-wide Token Creator grant |
| Remediation control SA (M8 default-off) | Firestore transactions, start Workflow, send callback, bounded evidence reads, invoke order verification | Cloud Run update, IAM, image or template mutation, Runtime execution |
| Remediation Workflow SA (M8 default-off) | Invoke only control and internal executor services | Firestore, Cloud Run update, evidence, IAM |
| Remediation executor SA (M8 default-off) | Read Firestore state, read payment revision/service, update exact payment service traffic | Firestore write, order invocation, evidence reads, other service update, IAM, image deployment, template/env mutation |
| Approver Google Group (M8 default-off) | Invoke the control API; app re-verifies token claims | Executor invocation, project role, stored email identity |

## Investigator custom role

- `logging.logEntries.list`
- `monitoring.timeSeries.list`
- `run.services.get`
- `run.revisions.list`
- `discoveryengine.servingConfigs.search`
- `aiplatform.endpoints.predict`
- `serviceusage.services.use`
- `resourcemanager.projects.get`

The application further restricts these project-level reads with fixed service, region, time,
metric, and filter builders. The caller cannot pass a project ID, URL, token, resource name, raw
Logging/Monitoring filter, or serving config.

## Runtime and workload boundary

- Three Cloud Run services remain private; only the order identity has the two leaf invoker grants.
- The managed Runtime reuses the investigator SA and publishes one async-stream operation. With
  persistent investigations enabled it has no project role; numeric project metadata is normalized
  before Vertex SDK import so SDK bootstrap does not require `resourcemanager.projects.get`.
- Enterprise-supplied session IDs are handled only by an in-process `InMemorySessionService`.
  `aiplatform.sessions.create` is intentionally not granted; no session or user identity is persisted.
- No public principal, service-account key, broad predefined runtime role, OAuth delegation,
  session/memory permission, or VPC permission exists. M8 principals remain absent until the
  separately approved `enable_remediation=true` apply.
- Existing Enterprise registration is managed through the official console; registration mutation
  code is not part of the product.

The deployed M7 boundary remains unchanged. The M8 Terraform graph is default-off and tests exact
identity separation, internal executor ingress, group invocation, and payment-only conditional
`run.services.update`. Investigator/Runtime receives no Firestore, Workflow, executor, or update
permission.
