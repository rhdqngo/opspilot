# OpsPilot IAM Matrix

Status: deployed MVP boundary; no IAM change in the lean cut

| Principal | Allowed purpose | Explicitly excluded |
| --- | --- | --- |
| Local operator | Reviewed Terraform apply, bounded manual validation | Automatic remediation, broad runtime role |
| Terraform plan identity | Remote-state read and resource get/list needed for manual plans | Apply, API enable/disable, IAM write, import, model query |
| Investigator/Runtime SA | Read bounded Logging/Monitoring/Run/Search evidence; invoke the fixed Vertex model | Keys, IAM write, Cloud Run update/invoke, Search import/write, Storage object read, remediation |
| Order runtime SA | Invoke payment and inventory Cloud Run services | Project-wide role, key, other service invocation |
| Payment/inventory runtime SAs | Run their private services | Project role, key, downstream invocation |
| Reasoning Engine service agent | Mint short-lived credentials for the investigator SA only | Project-wide Token Creator grant |

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
- The managed Runtime reuses the investigator SA and publishes one async-stream operation.
- No public principal, service-account key, broad predefined runtime role, OAuth delegation,
  session/memory permission, VPC permission, or remediation principal exists.
- Existing Enterprise registration is managed through the official console; registration mutation
  code is not part of the product.

The MVP lean cut changes source packaging and pre-release interfaces only. IAM bindings, roles,
service accounts, APIs, WIF resources, and Enterprise registration remain unchanged.
