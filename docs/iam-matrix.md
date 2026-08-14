# OpsPilot IAM Matrix

Status: formal agent and prod-sim M8 boundary deployed and verified

| Principal | Allowed purpose | Explicitly excluded |
| --- | --- | --- |
| Local operator | Reviewed Terraform apply, bounded manual validation | Automatic remediation, broad runtime role |
| Terraform plan identity | Remote-state read and resource get/list needed for manual plans | Apply, API enable/disable, IAM write, import, model query |
| Runtime SA | Invoke only the private investigation API; resolve the numeric SDK project hint through one exact custom permission | Broad project role, evidence reads, Firestore, Tasks, remediation, keys, IAM write |
| Investigation API SA | Read bounded Logging/Monitoring/Run/Search evidence; create bounded tasks and investigation records | IAM write, Cloud Run update, remediation, delete permissions |
| Order runtime SA | Invoke payment and inventory Cloud Run services | Project-wide role, key, other service invocation |
| Payment/inventory runtime SAs | Run their private services | Project role, key, downstream invocation |
| Reasoning Engine service agent | Mint short-lived credentials for the investigator SA only | Project-wide Token Creator grant |
| Remediation control SA | Firestore transactions, start Workflow, send callback, bounded evidence reads, invoke order verification | Cloud Run update, IAM, image or template mutation, Runtime execution |
| Remediation Workflow SA | Invoke only control and internal executor services | Firestore, Cloud Run update, evidence, IAM |
| Remediation executor SA | Read Firestore state, read the prod-sim payment revision/service, update that exact service traffic | Firestore write, order invocation, evidence reads, other service update, IAM, image deployment, template/env mutation |
| Approver Google Group | Invoke the control API; app re-verifies token claims | Executor invocation, project role, stored email identity |

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

- Nine synthetic workload services remain private; in each environment only the order identity has
  the two leaf invoker grants.
- The managed Runtime publishes one async-stream operation. Its dedicated custom role contains
  exactly `resourcemanager.projects.get` for SDK project-hint resolution; it receives no broad
  viewer, evidence, datastore, task, Workflow, executor, or update permission.
- ADK streaming sessions remain ephemeral. Conversational continuity is a 24-hour Firestore scope
  document keyed by a domain-separated session hash; raw session/user identities and prompts are
  not persisted, and `aiplatform.sessions.create` is not granted.
- No public principal, service-account key, broad predefined runtime role, OAuth delegation,
  session/memory permission, or VPC permission exists. M8 principals remain absent until the
  separately approved `enable_remediation=true` apply.
- Existing Enterprise registration is managed through the official console; registration mutation
  code is not part of the product.

The deployed formal-agent boundary tests exact identity separation, internal executor ingress,
group invocation, and prod-sim-payment-only `run.services.update`. Runtime receives no Firestore,
Workflow, executor, or update permission.
