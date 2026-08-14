# OpsPilot 비용 Guardrail

[English](cost-model.md) | **한국어**

상태: formal agent 배포 및 Gemini Enterprise Preview 검증 완료

`core-v1`과 `portfolio-v1` evaluation suite는 recorded synthetic evidence와 local
deterministic fake model을 사용합니다. 각각 14회와 80회의 model-node 실행은 Vertex AI,
Logging, Monitoring, Agent Search 또는 BigQuery request cost를 만들지 않습니다. Evaluation
artifact와 cleanup plan은 `.tmp` 아래 local file입니다.

| Guardrail | 값 |
| --- | --- |
| Monthly budget alert | KRW 50,000 |
| Threshold | 현재 spend의 50%, 80%, 100% |
| Cloud Run | demo service별 min 0, max 2 |
| Agent Runtime | min 0, max 1, 1 vCPU, 1 GiB, concurrency 3 |
| Model | Standard PayGo, 지원되는 investigation당 최대 2회 |
| Data | Synthetic ecommerce only |
| Remediation | Scale-to-zero, approval 필수, prod-sim payment only |

Budget은 alert이며 hard cap이 아닙니다. Scale-to-zero, bounded query, immutable image,
manual test window와 explicit approval이 실제 비용 통제입니다.

## 현재 비용이 발생할 수 있는 resource

- Versioning과 protection이 적용된 GCS Terraform-state bucket
- Immutable demo image를 보관하는 Docker Artifact Registry
- dev, staging, prod-sim의 private scale-to-zero synthetic workload service 9개
- Protected knowledge bucket과 13개 document의 Standard Agent Search corpus
- Project-scoped budget 및 email notification channel 1개
- 기존 Gemini Enterprise app에 등록된 scale-to-zero Agent Runtime 1개
- Private scale-to-zero investigation/M8 control service, Workflow path 1개, Cloud Tasks,
  bounded Firestore investigation/conversation document

IAM, service account, API enablement와 WIF configuration 자체는 always-on compute를 할당하지
않습니다. 이 lean Runtime update는 source archive/hash만 바꾸며 resource, minimum instance,
query, import 또는 model request를 추가하지 않습니다.

## 제한된 시험 사용량

- SCN-001: 실행당 request 20건
- Local fixture evaluation: paid model 또는 cloud request 없음
- 지원되는 Runtime request: evidence collection bounded, model call 최대 2회
- Scheduled load, custom metric, generalized alert intake 또는 unapproved remediation 없음
- 승인된 M8 실행: Workflow path 1개, bounded Firestore document, post-action verification order
  정확히 10건. Preview QA는 approval request만 만들고 실행하지 않음

## 정리 순서

1. 명시적 승인 후에만 manual hosted plan gate를 끄고 repository variable을 제거합니다.
2. Dev destroy plan과 deletion-protected resource를 검토합니다.
3. Export/retention 결정 후 dev workload와 Search data를 제거합니다.
4. State bucket 제거 전 Terraform state를 이전합니다.
5. 어떤 workflow도 의존하지 않을 때 WIF/CI identity를 제거합니다.
6. 남은 budget, API, image, object와 state version을 확인합니다.

VPC, Model Armor, generalized alert intake/remediation, managed sessions/memory, dashboard와
multi-project support는 향후 option이며 별도 계획 없이 비용을 추가할 수 없습니다.

## Formal-agent bounded usage

배포된 formal environment는 staging과 prod-sim에 order, payment, inventory Cloud Run service
6개를 추가하며 각각 max instance 2입니다. 3-service STANDARD/DEEP investigation은 logical
tool call 12회와 provider call 최대 18회, QUICK은 logical call 6회와 provider call 최대
9회로 제한합니다. RCA/report generation은 model call 최대 2회이며 direct incident signal이
없으면 실행하지 않습니다. Conversation context는 active session당 작은 Firestore document
하나이고 TTL은 24시간입니다. 이는 monetary estimate가 아니라 architecture boundary입니다.
