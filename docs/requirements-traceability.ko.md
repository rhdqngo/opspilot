# Lean MVP v1 요구사항 추적표

[English](requirements-traceability.md) | **한국어**

상태: formal Incident Commander / Gemini Enterprise Preview QA 검증 완료

이 표는 M0~M10 North Star 명세와 배포된 MVP 조사 plane 및 approval-gated M8 control
plane을 비교합니다. `Implemented`는 현재 test 또는 operator record가 해당 요구사항을
검증한다는 뜻입니다. `Partial`은 MVP가 제한된 일부만 구현했음을, `Deferred`는 누락이
아니라 의도적인 product boundary임을 뜻합니다.

Source-bound managed-environment 검증은
[`long-spec-preqa-v1.md`](portfolio/results/long-spec-preqa-v1.md)에 게시되어 있습니다.
실행된 Preview 결과는
[`long-spec-enterprise-qa-v1.md`](portfolio/results/long-spec-enterprise-qa-v1.md),
provider 차단 상태에서 반복한 v2는
[`long-spec-enterprise-qa-v2.md`](portfolio/results/long-spec-enterprise-qa-v2.md),
pre-canary 재개 실패는
[`long-spec-enterprise-qa-v3.md`](portfolio/results/long-spec-enterprise-qa-v3.md)입니다.
최종 통과 기록은
[`long-spec-enterprise-qa-v4.md`](portfolio/results/long-spec-enterprise-qa-v4.md)이며,
source-bound formal-agent release와 최종 대화형 QA는
[`long-spec-formal-agent-v3.md`](portfolio/results/long-spec-formal-agent-v3.md)에 게시했습니다.

## 기능 요구사항

| ID | Status | Lean MVP 증거 또는 경계 |
| --- | --- | --- |
| FR-001 | Implemented | [`parser.py`](../src/opspilot/parser.py)는 incident ID 하나, 3개 서비스와 별칭, `dev`/`staging`/`prod-sim`, 상대·절대 1~120분 구간, 6개 증상, 3개 깊이를 파싱합니다. 실제 production과 충돌하는 scope는 명시적으로 거절하며 3환경 관리형 및 양성 Preview QA는 [formal-agent 기록](portfolio/results/long-spec-formal-agent-v3.md)에서 통과했습니다. |
| FR-002 | Implemented | Service 생략 시 3개 전체, 시간 생략 시 30분을 기본값으로 사용하고 두 가정을 모두 기록합니다. |
| FR-003 | Implemented | 범위가 제한된 Logging filter/client와 live evidence test를 제공합니다. |
| FR-004 | Implemented | Zero-point gap을 포함한 bounded error-ratio 및 latency Monitoring query를 제공합니다. |
| FR-005 | Implemented | 명세는 Cloud Run revision 또는 Cloud Deploy rollout 수집을 허용하며, bounded Cloud Run revision 경로를 구현하고 검증했습니다. |
| FR-006 | Implemented | Agent Search corpus, sync plan, 10개 retrieval case와 live search normalization을 제공합니다. |
| FR-007 | Implemented | 4개 source를 모두 versioned `EvidenceItem` record로 정규화합니다. |
| FR-008 | Implemented | Operational evidence는 시간순으로 정렬하고 knowledge는 incident Timeline에서 제외합니다. |
| FR-009 | Implemented | ADK contract는 최대 3개 hypothesis와 결정론적 검증·순위를 허용합니다. [`report_policy.py`](../src/opspilot/report_policy.py)는 operational cause가 하나만 식별되면 비단정적 H-02 하나를 추가합니다. |
| FR-010 | Implemented | 위조·누락·중복·방향 불일치 evidence reference를 거절합니다. |
| FR-011 | Implemented | [`report_policy.py`](../src/opspilot/report_policy.py)는 evidence-grounded containment, mitigation, root-fix recommendation을 각각 최대 하나 생성하고 [`reporting.py`](../src/opspilot/reporting.py)는 별도 section으로 출력합니다. [Managed Runtime smoke](portfolio/results/long-spec-preqa-v1.md)는 H-01/H-02, 3개 분류와 유효 citation을 검증합니다. 범용 실행은 의도적인 경계입니다. |
| FR-012 | Implemented | Investigator identity와 public surface는 읽기 전용입니다. |
| FR-013 | Implemented | 격리된 M8 API는 canonical SCN-008 payment rollback만 지원하며 합성 `prod-sim payment-service`를 대상으로 배포되었습니다. |
| FR-014 | Implemented | Firestore transaction, 15분 Workflow callback, hash-bound approval, TTL cleanup과 actor audit를 end-to-end로 검증했습니다. |
| FR-015 | Implemented | 정확한 target traffic, revision/digest binding, metric window와 10/10 recovery를 합성 prod-sim target에서 검증했습니다. |
| FR-016 | Implemented | [`audit.py`](../src/opspilot/audit.py), Runtime, API, task worker, executor와 report audit가 하나의 trace/correlation identity를 재사용합니다. Concurrent run-ID idempotency는 [`test_investigation_service.py`](../tests/test_investigation_service.py)와 [20-submit managed smoke](portfolio/results/long-spec-preqa-v1.md)로 검증합니다. |
| FR-017 | Implemented | 각 logical evidence tool은 scope, timing, result, truncation/cache, safe error field를 가진 고정 privacy-safe `ToolCallAuditEvent` schema를 기록합니다. 최종 양성 Preview run은 각각 Runtime `run_id`와 공통 trace/correlation ID가 있는 4개 event를 기록했고, 거절 run은 event를 만들지 않았습니다. |
| FR-018 | Implemented | Versioned core 7-case와 portfolio 40-case suite가 결정론적 gate를 강제합니다. |
| FR-019 | Deferred | User feedback persistence는 post-MVP입니다. |
| FR-020 | Implemented | 7개 fixture scenario, SCN-001 workload 실행과 SCN-008 prepare/approve/execute/reset/abort를 검증합니다. |
| FR-021 | Deferred | Public backend switching은 제거했으며 각 surface는 고정되고 문서화된 execution mode를 사용합니다. |
| FR-022 | Implemented | 변경되지 않은 Gemini Enterprise registration이 Runtime v2를 가리킵니다. [Formal-agent 기록](portfolio/results/long-spec-formal-agent-v3.md)은 Preview에서 양성 장애 식별, 단일·복수 서비스 조사, 수정된 same-session 설명, 기능 안내와 final-only 거절을 검증합니다. |
| FR-023 | Implemented | Incident, investigation과 immutable JSON/Markdown report를 Firestore에 저장합니다. |
| FR-024 | Implemented | Transactional report version과 결정론적 version comparison을 API로 제공합니다. |
| FR-025 | Implemented | 영속 incident replay는 새 investigation과 report version을 생성하며 fixture CLI replay도 유지합니다. |

### 정식 전환 수용 항목

| ID | Status | 증거 또는 경계 |
| --- | --- | --- |
| FA-001 | Implemented | [`conversation.py`](../src/opspilot/conversation.py), Runtime v2와 Firestore `conversation_contexts`는 원문 질문이나 evidence body를 저장하지 않고 refine, explain, status, report comparison turn을 위한 24시간 가명화 구조 문맥을 제공합니다. Managed·Preview conversation 검증은 [formal-agent 기록](portfolio/results/long-spec-formal-agent-v3.md)에서 통과했습니다. |
| FA-002 | Implemented | 적격한 `prod-sim payment-service` report는 authenticated internal bridge를 통해 정확히 하나의 M8 `WAITING_APPROVAL` 요청을 생성합니다. Runtime은 이를 승인하거나 실행할 수 없습니다. 3환경 managed smoke와 remediation 12/12가 통과했습니다. |

## 비기능 요구사항

| ID | Status | Lean MVP 증거 또는 경계 |
| --- | --- | --- |
| NFR-001 | Implemented | Runtime은 API만 호출할 수 있고 API 소유 identity가 bounded read·persistence 권한을 가집니다. |
| NFR-002 | Implemented | 격리된 M8 control, Workflow, payment-only executor identity가 cloud IAM negative check를 통과했습니다. |
| NFR-003 | Implemented | Project, resource, filter, metric과 URL 입력을 allowlist로부터 서버가 생성합니다. |
| NFR-004 | Implemented | 악성 knowledge content는 evidence로만 남고 tool authority를 갖지 않습니다. |
| NFR-005 | Implemented | Source failure와 zero-point metric은 partial/inconclusive report를 생성합니다. |
| NFR-006 | Implemented | [`retry.py`](../src/opspilot/retry.py)는 deadline 안에서 최대 3회의 exponential full-jitter retry를 제공합니다. Evidence, Runtime API와 remediation client는 transient failure만 retry하고 state-changing POST에는 idempotency key를 요구합니다. [Managed pre-QA 기록](portfolio/results/long-spec-preqa-v1.md)이 bounded Runtime/API 동작을 검증합니다. |
| NFR-007 | Implemented | LOG, METRIC, CHANGE, KNOWLEDGE 수집은 병렬입니다. |
| NFR-008 | Implemented | Log, metric, revision, knowledge, model input과 output size를 제한합니다. |
| NFR-009 | Implemented | Demo service와 Runtime은 scale-to-zero 경계를 사용합니다. |
| NFR-010 | Deferred | BigQuery는 Lean MVP v1에 포함하지 않습니다. |
| NFR-011 | Implemented | `InvestigationAudit`는 raw identifier를 보존하지 않고 source, 가명화 actor/session/query hash, run ID, trace ID를 연결합니다. Internal caller는 issuer/audience/identity를 확인하고 source-domain hash로 기록합니다. Live 연결은 [managed pre-QA evidence](portfolio/results/long-spec-preqa-v1.md)에 기록했습니다. |
| NFR-012 | Implemented | Runtime은 user/session identifier를 hash하고 API는 redacted query와 source-domain query hash만 저장합니다. Log는 prompt/identity/URL/project/raw error를 제외하며 legacy record는 additive optional field로 읽습니다. Firestore, report, log sentinel scan은 [managed pre-QA evidence](portfolio/results/long-spec-preqa-v1.md)에서 통과했습니다. |
| NFR-013 | Implemented | Provider transport/client adapter와 domain normalization을 분리합니다. |
| NFR-014 | Implemented | HTTP normalization, auth/error mapping, mock, fixture, Terraform contract를 검증합니다. |
| NFR-015 | Implemented | Terraform, deterministic package, knowledge sync와 문서화된 명령으로 환경을 재구축할 수 있습니다. |
| NFR-016 | Deferred | Lean MVP는 자체 HTML report 또는 approval UI를 제공하지 않습니다. |
| NFR-017 | Implemented | Model/project/store 설정은 주입하지만 region, catalog, provider filter와 resource scope는 서버 정책으로 유지합니다. |
| NFR-018 | Implemented | Hypothesis는 supporting evidence와 contradicting evidence를 구분합니다. |
| NFR-019 | Implemented | Support score와 product taxonomy를 검증된 evidence로부터 코드에서 계산합니다. |
| NFR-020 | Implemented | Pydantic validation과 고정 safe failure가 structured output을 보호합니다. |

## 검증 명령

```powershell
uv run --extra agent pytest
uv run ruff format --check .
uv run ruff check .
uv run --extra agent mypy src tests
uv run --extra agent opspilot agent eval --suite core --format summary
uv run --extra agent opspilot agent eval --suite portfolio --format summary --output .tmp/evaluation
uv run opspilot remediation eval --suite remediation --format summary
uv run --extra agent opspilot scenario prepare --scenario SCN-008 --mode plan --auth gcloud
uv run --extra agent opspilot scenario abort --scenario SCN-008 --mode plan --auth gcloud
uv run python scripts/m8_release.py preflight --output .tmp/m8-release
uv run python scripts/m8_release.py verify --phase image --output .tmp/m8-release
uv run python scripts/m8_release.py verify --phase terraform-plan --output .tmp/m8-release
uv run python scripts/formal_agent_release.py <plan-json> --phase <phase> <phase-hash-arguments>
uv run opspilot cleanup plan --format summary
```
