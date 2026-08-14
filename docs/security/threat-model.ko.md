# OpsPilot Formal Agent 위협 모델

[English](threat-model.md) | **한국어**

상태: active

Run, correlation, trace identifier는 agent/Runtime invocation마다 독립적으로 생성하며 어떤
action도 authorize할 수 없습니다. Enterprise user/session identifier와 검증된 API subject는
source-domain SHA-256 pseudonym으로만 보존합니다. Raw query는 persistence 전에 redact하고
audit에는 source-domain query hash로 표현합니다. Runtime/tool summary는 prompt, project,
URL, token, evidence payload, raw exception과 raw identity를 제외합니다.

| 위협 | 통제 | 잔여 위험 |
| --- | --- | --- |
| 임의 cloud scope | 고정 project environment와 service/time/metric/filter allowlist; caller project, URL, token, resource name, raw filter를 받지 않음 | Project-level read permission은 application allowlist에 계속 의존함 |
| Evidence 위조 | Immutable evidence ID, direction check, duplicate/missing reference rejection, complete citation admission | Source system이 잘못된 synthetic data를 포함할 수 있음 |
| Prompt injection | Knowledge text를 untrusted data로 표시하고 model은 tool을 갖지 않으며 action filtering은 결정론적임 | Model prose 품질은 낮을 수 있지만 실행은 불가능함 |
| 안전하지 않은 remediation | Runtime 조사 권한은 읽기 전용; 별도 M8 control API는 report/change evidence, canonical plan hash, 15분 approval, transaction, 정확한 service/revision/digest/etag 재검증과 traffic-only executor 하나를 요구함 | Authorized approver가 policy-valid하지만 좋지 않은 rollback을 승인할 수 있음 |
| Callback 탈취·replay | Callback URL은 24시간 TTL collection에만 저장하고 반환·log하지 않으며 `workflows.callbacks.send`가 필요하고 모든 decision이 plan expiry를 확인함 | TTL 삭제는 비동기이므로 명시적 expiry check가 계속 권위 있음 |
| Concurrent 또는 유실 응답 | Atomic idempotency, execution lease 하나, executor concurrency 1; 응답 유실 뒤 이미 복구된 traffic은 idempotent success | Provider reconciliation 또는 verification이 safe terminal failure로 끝날 수 있음 |
| Identity 혼동 | Cloud Run IAM과 issuer/audience/subject check; Runtime, task, alert, direct API, M8 identity를 endpoint별로 제한하고 source-domain hash로 기록하며 audit에 email을 저장하지 않음 | Group·service-account lifecycle은 외부 관리 통제로 남음 |
| 민감정보 유출 | Persistence 전 redaction, source-domain query/user/session hash, 고정 tool-event allowlist, logical `opspilot://` URI, safe error, telemetry content capture off | Provider-managed request metadata는 application 통제 밖임 |
| 비용·latency 폭주 | Model call 2회, bounded evidence request, deadline 내 maximum-three jittered transient retry, scale-to-zero, KRW 50,000 alert | Budget alert는 hard cap이 아님 |
| Runtime surface 확장 | `AdkApp` async-stream operation 하나와 명시적 archive allowlist | Provider version에 따라 platform 동작이 바뀔 수 있음 |
| Enterprise authentication bridge 실패 | Private IAM을 유지하고 internal expired mint를 external blocker로 분류 | Runtime이 정상이어도 Preview가 일시적으로 실패할 수 있음 |

Formal-agent context는 raw memory를 추가하지 않습니다. `conversation_contexts`는
pseudonymous session hash와 structured scope/report reference만 24시간 TTL로 저장합니다.
Model은 logical URI가 있는 bounded sanitized evidence만 받고 tool을 갖지 않습니다. 요청
window 밖의 revision snapshot은 server-side key-difference 계산에만 사용할 수 있으며 report
또는 model input 전에 제거합니다.

M8은 approval-gated이며 prod-sim payment revision rollback만 지원합니다. Runtime은
authenticated investigation-to-control bridge를 통해 `WAITING_APPROVAL` record만 요청할 수
있고 approve, reject, execute는 할 수 없습니다. DEV, staging, order/inventory, restart와
real-production write는 policy가 거절합니다.

Alert 기반 automatic remediation, general remediation, VPC/perimeter, Model Armor,
sessions/memory, dashboard, BigQuery와 multi-project support는 범위에서 제외합니다.
