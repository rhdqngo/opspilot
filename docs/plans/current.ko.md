# 현재 프로젝트 상태

[English](current.md) | **한국어**

status: formal_agent_verified
phase: formal Incident Commander 배포 및 Gemini Enterprise Preview QA 검증 완료
updated: 2026-08-14

## 검증된 제품 범위

- OpsPilot은 `dev`, `staging`, 합성 `prod-sim`에서 `order-service`, `payment-service`,
  `inventory-service`를 개별 또는 함께 조사합니다.
- 한국어·영어 별칭, 상대·절대 1~120분 구간, 6개 symptom class,
  QUICK/STANDARD/DEEP depth를 지원합니다. 실제 production은 명시적으로 거절합니다.
- `/internal/v2/runtime/turns`가 investigation, refinement, concise report explanation,
  status, report-version comparison, capability guidance와 bounded remediation-request intent를
  판정합니다. Legacy Runtime과 public investigation contract는 호환됩니다.
- Firestore conversation context는 가명화·구조화되어 있고 24시간으로 제한합니다. Prompt,
  raw user/session identifier와 evidence body는 저장하지 않습니다.
- Operational evidence는 요청 interval로 제한합니다. Window 이전 Cloud Run revision은
  server-side diff 계산에 사용할 수 있지만 Evidence, Timeline, Sources에는 나타나지 않습니다.
- QUICK은 log와 core metric을 사용하고 STANDARD/DEEP은 change와 knowledge를 추가하며,
  3-service 경로도 20회 tool/provider-call budget 안에 유지합니다.
- Direct signal은 bounded RCA/verification graph로 전달됩니다. No-signal과 model-failure
  경로는 hypothesis 또는 changing recommendation을 조작하지 않고 evidence-backed
  healthy/inconclusive report를 반환합니다.
- Runtime은 `prod-sim payment-service`에 대해서만 적격한 `WAITING_APPROVAL` rollback 요청
  하나를 만들 수 있습니다. Approval과 execution은 isolated M8 control plane에 남습니다.

## 배포 및 권한 경계

- Runtime 1개, private investigation API 1개, Firestore, Cloud Tasks와 Agent Search control
  plane 하나가 3개 합성 환경을 제공합니다. 기존 Gemini Enterprise registration은 같은
  Runtime resource를 계속 가리킵니다.
- Runtime service account의 전용 custom role은 정확히
  `resourcemanager.projects.get` 하나만 포함합니다. Permission이 없을 때 사용한 불안정한
  metadata workaround를 대체하며 broad viewer, evidence, datastore, task 또는 remediation
  permission은 Runtime에 추가하지 않았습니다.
- Runtime은 investigation bridge만 invoke할 수 있습니다. Task, alert, remediation approval,
  executor boundary는 분리·비공개 상태이며 negative test를 통과했습니다.
- 최종 feature correction은 investigation API만 in-place로 변경했습니다. Runtime, IAM, M8,
  registration, data schema와 synthetic workload는 해당 cycle에서 변경하지 않았습니다.

## 최종 검증

- 초기 formal-agent source-bound release: pytest 277/277, Ruff format/check, 92개 source file
  strict mypy, package build, core 7/7, portfolio 40/40, remediation 12/12, Terraform bootstrap
  1/1 및 dev 8/8
- 11-file Runtime package 2개가 byte-identical입니다. API image는 linux/amd64, non-root,
  health/ready 확인 및 registry-digest binding을 통과했습니다.
- 3환경 managed smoke와 SCN-001은 예상한 `5/5 -> 4/6 -> 5/5` sequence, recovery와 ground
  truth 일치를 통과했습니다.
- Managed conversation matrix가 모든 required contract를 통과했습니다. Multi-service turn
  1건에 provider transport transient가 있었지만 같은 deployment에서 규정대로 재실행한
  2건 모두 완전한 backend invariant와 함께 통과해 product defect가 아닌 documented
  provider transient로 보존합니다.
- Gemini Enterprise Preview에서 한국어 단일-service 조사, 3-service 조사, same-session
  concise follow-up, localized capability guidance와 명시적 actual-production rejection을
  검증했습니다. Investigation은 progress 1건과 final 1건, immediate turn은 final 1건만
  생성했습니다.
- 최종 live regression에서 요청하지 않은 hypothesis가 없다고 잘못 표시하던 concise
  healthy-report summary를 수정해 status, localized user impact와 conclusion을 반환하도록
  했습니다. 정확한 Preview phrase는 277-test source-bound gate에 포함됐고 API-only in-place
  update 뒤 통과했습니다.
- 이후 positive Preview pass에서 SCN-001을 정확히 한 번 실행하고 `5/5 -> 4/6 -> 5/5`
  recovery를 검증했습니다. Preview는 payment connection-pool exhaustion을 H-01, support 0의
  H-02, 3개 evidence 유형, 3개 approval-gated recommendation category와 유효한 persisted
  citation으로 식별했습니다. 이 과정에서 발견한 live-summary 한국어 문구 공백도 수정해
  최종 source-bound gate는 278개 test를 포함합니다.
- 최종 investigation은 Runtime stage 4개와 unique tool event 4개를 하나의 investigation,
  task attempt 1건, report version 1에 동일 trace/correlation identity로 연결했습니다.
  Application payload scan에서는 raw sentinel, identity, project, URL 또는 permission error가
  발견되지 않았습니다.
- Cloud Run은 Ready이며 동일 image digest와 Runtime archive를 사용하는 최종 Terraform
  plan은 `No changes`입니다.
- GitHub portfolio 문서는 formal-agent release를 첫 화면 baseline으로 사용하고 current
  evidence와 historical QA record를 분리하며 raw cloud/browser identifier 없이 MIT license를
  게시합니다.
- README와 documentation table의 모든 portfolio 문서에 한국어 mirror를 제공하고,
  English를 canonical technical contract로 유지하면서 두 진입점을 명시적으로 연결합니다.
- 정제된 증빙: [formal-agent v3](../portfolio/results/long-spec-formal-agent-v3.md),
  [한국어 검증 증빙 색인](../portfolio/results/README.ko.md)

## 외부 비차단 항목

- 수동 GitHub workflow 3개는 기존 hosted-runner billing 또는 spending-limit 조건의 영향을
  받습니다. Runner가 정상적으로 step을 실행할 때까지 local 및 managed-environment gate가
  권위 있는 결과입니다.

## 다음 checkpoint

- 배포된 formal agent를 release baseline으로 취급합니다.
- Root README와 verification evidence index를 portfolio documentation 진입점으로 사용합니다.
- 새 요구사항, 재현 가능한 product defect 또는 documented transient policy를 위반한
  provider incident가 있을 때만 작업을 재개합니다.
- Raw browser capture, cloud identifier와 execution mapping은 `.tmp`에만 보관합니다.

## 이 milestone 이후로 연기한 범위

Feedback persistence, actual production connectivity, public simulation/live switching, BigQuery,
owned HTML/approval UI, Cloud Deploy rollout, Model Armor, VPC Service Controls/private
networking, multi-project/A2A/MCP, managed memory, generalized write, dashboard, full
load/cold-start suite, presentation/video와 teardown은 연기된 범위입니다.

과거 checkpoint는 [mvp-history.md](mvp-history.md)에 보관합니다.
