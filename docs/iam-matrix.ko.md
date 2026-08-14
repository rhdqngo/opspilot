# OpsPilot IAM 매트릭스

[English](iam-matrix.md) | **한국어**

상태: formal agent 및 prod-sim M8 boundary 배포·검증 완료

| Principal | 허용 목적 | 명시적 제외 |
| --- | --- | --- |
| Local operator | 검토된 Terraform apply, bounded manual validation | Automatic remediation, broad runtime role |
| Terraform plan identity | Manual plan에 필요한 remote-state read와 resource get/list | Apply, API enable/disable, IAM write, import, model query |
| Runtime SA | Private investigation API만 invoke; 정확히 하나의 custom permission으로 numeric SDK project hint 해석 | Broad project role, evidence read, Firestore, Tasks, remediation, key, IAM write |
| Investigation API SA | Bounded Logging/Monitoring/Run/Search evidence read; bounded task·investigation record 생성 | IAM write, Cloud Run update, remediation, delete permission |
| Order runtime SA | Payment·inventory Cloud Run service invoke | Project-wide role, key, 다른 service invocation |
| Payment/inventory runtime SAs | 각 private service 실행 | Project role, key, downstream invocation |
| Reasoning Engine service agent | Investigator SA용 short-lived credential만 mint | Project-wide Token Creator grant |
| Remediation control SA | Firestore transaction, Workflow 시작, callback 전송, bounded evidence read, order verification invoke | Cloud Run update, IAM, image/template mutation, Runtime execution |
| Remediation Workflow SA | Control과 internal executor service만 invoke | Firestore, Cloud Run update, evidence, IAM |
| Remediation executor SA | Firestore state와 prod-sim payment revision/service read, 정확한 service traffic update | Firestore write, order invocation, evidence read, 다른 service update, IAM, image deployment, template/env mutation |
| Approver Google Group | Control API invoke; application이 token claim 재검증 | Executor invocation, project role, stored email identity |

## Investigator custom role

- `logging.logEntries.list`
- `monitoring.timeSeries.list`
- `run.services.get`
- `run.revisions.list`
- `discoveryengine.servingConfigs.search`
- `aiplatform.endpoints.predict`
- `serviceusage.services.use`
- `resourcemanager.projects.get`

Application은 고정 service, region, time, metric, filter builder로 project-level read를 더
제한합니다. Caller는 project ID, URL, token, resource name, raw Logging/Monitoring filter 또는
serving config를 전달할 수 없습니다.

## Runtime과 workload 경계

- Synthetic workload service 9개는 private이며 각 environment에서 order identity만 두 leaf
  invoker grant를 갖습니다.
- Managed Runtime은 async-stream operation 하나만 게시합니다. 전용 custom role은 SDK
  project-hint 해석을 위한 `resourcemanager.projects.get` 하나만 포함하며 broad viewer,
  evidence, datastore, task, Workflow, executor 또는 update permission을 받지 않습니다.
- ADK streaming session은 ephemeral입니다. 대화 연속성은 domain-separated session hash를
  key로 하는 24시간 Firestore scope document로 제공하며 raw session/user identity와 prompt를
  저장하지 않고 `aiplatform.sessions.create`도 부여하지 않습니다.
- Public principal, service-account key, broad predefined runtime role, OAuth delegation,
  session/memory 또는 VPC permission은 없습니다. 배포된 M8 principal은 별도 승인된
  `enable_remediation=true` input에서만 존재하고 default configuration은 이를 생략합니다.
- 기존 Enterprise registration은 공식 console에서 관리하며 registration mutation code는
  product에 포함하지 않습니다.

배포된 formal-agent boundary는 정확한 identity separation, internal executor ingress, group
invocation과 prod-sim-payment-only `run.services.update`를 검사합니다. Runtime에는 Firestore,
Workflow, executor 또는 update permission이 없습니다.
