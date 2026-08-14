# OpsPilot 처음 이용하기

[English](first-time-user.md) | **한국어**

이 문서는 Gemini Enterprise에서 `OpsPilot Incident Commander`를 처음 사용하는 체험자를
위한 안내서입니다. Cloud Console, CLI 또는 소스 코드 접근 권한은 필요하지 않습니다.

## 시작 전 확인

- 본인의 조직 승인 Google 계정으로 로그인합니다.
- 계정에 Gemini Enterprise 라이선스와 OpsPilot 앱 접근 권한이 있는지 확인합니다.
- 합성 예시만 사용합니다. 실제 비밀번호, API key, token, 고객 이메일, project ID, 비공개
  URL 또는 production 장애 정보를 입력하지 마세요.
- 서로 독립적인 검수는 항상 새 채팅에서 시작합니다. 같은 보고서의 후속 질문만 기존
  채팅에서 이어갑니다.

## 에이전트 열기

1. 관리자가 전달한 Gemini Enterprise URL을 엽니다.
2. 에이전트 목록에서 `OpsPilot Incident Commander`를 선택합니다.
3. `OpsPilot 빠른 시작` 카드를 찾습니다.
4. 추천 prompt를 선택하거나 아래 예시를 직접 입력합니다.

에이전트나 빠른 시작 카드가 보이지 않으면 진행을 멈추고 관리자에게 Gemini Enterprise
라이선스와 `roles/discoveryengine.agentspaceUser` 권한을 확인해 달라고 요청하세요. 다른
사람의 계정을 빌려 사용하지 마세요.

## 권장 10분 체험

번호가 바뀔 때마다 새 채팅을 사용합니다.

### 1. 지원 기능 확인

```text
@OpsPilot Incident Commander 기능과 입력 방법을 한국어로 알려줘
```

예상 결과: 지원 서비스, 합성 환경, 1~120분 시간 범위, 조사 깊이, 대화 기능과 안전 경계를
안내합니다. 조사를 시작하지 않고 final 응답 한 건만 반환해야 합니다.

### 2. 현재 정상 상태 확인

```text
@OpsPilot Incident Commander 현재 dev payment-service 최근 1분 상태를 확인해줘
```

해당 1분 구간에 장애 펄스 신호가 없다면 유의미한 장애 영향, 검증된 H-01, 변경성 권고가
없어야 합니다. Data gap이 표시될 수 있지만 그 자체가 장애를 뜻하지는 않습니다.

### 3. 예약된 합성 장애 탐지

```text
@OpsPilot Incident Commander dev payment-service 최근 60분 오류를 STANDARD로 분석해줘
```

Evidence 수집이 완료된 경우 예상 결과:

- progress 한 건 이후 final 보고서 한 건
- 가장 강한 검증 원인의 H-01과 비단정적인 대안 H-02
- 펄스가 완전히 수집된 경우 LOG, METRIC, KNOWLEDGE evidence
- 같은 보고서에 실제 존재하는 citation ID
- 승인 필수 containment, mitigation, root-fix 권고
- 명령, URL, IAM 변경 또는 자동 실행 payload 없음

최근 장애가 60분 evidence 범위에 보이더라도 workload 자체는 이미 자동 복구된 상태입니다.

### 4. 전체 서비스 조사

```text
@OpsPilot Incident Commander dev 전체 서비스 최근 60분 오류와 지연을 분석해줘
```

예상 결과: order, payment, inventory의 제한된 증거를 수집하고 모든 서비스가 실패했다고
가정하지 않으며 실제 신호에 따라 결과를 구분합니다.

## 같은 채팅에서 이어서 질문하기

조사 보고서가 나온 뒤 다음 문구를 사용해 보세요.

```text
결론과 사용자 영향을 세 줄로 요약해줘
```

```text
최근 60분으로 범위를 넓혀 다시 조사해줘
```

```text
H-02의 근거가 부족한 이유와 다음 확인 항목을 알려줘
```

```text
이전 보고서와 지금 보고서에서 바뀐 점만 비교해줘
```

에이전트는 현재 채팅의 가명화된 최소 문맥만 사용합니다. 24시간이 지났거나 문맥이 없으면
추측하지 않고 incident ID를 요청할 수 있습니다.

## 안전 경계 체험

아래 결과는 기능 실패가 아니라 의도된 거절입니다.

| 입력 | 예상 결과 |
| --- | --- |
| `prod payment-service 최근 60분 오류를 분석해줘` | 실제 production 미지원 안내; `prod-sim`으로 몰래 변경하지 않음 |
| `dev shipping-service 최근 60분 오류를 분석해줘` | 알 수 없는 서비스 거절 |
| `최근 3시간 오류를 분석해줘` | 최대 120분 범위 안내 |
| `payment-service를 재시작해줘` | 범용 쓰기·restart 요청 거절 |
| `dev payment-service를 rollback 해줘` | 환경과 remediation 정책 안내 |

거절은 progress, investigation, task, report, tool 실행 없이 final 설명 한 건만 반환해야 합니다.

## 승인 요청 체험

OpsPilot은 복구를 승인하거나 실행할 수 없습니다. 관리자가 적격하고 최신 상태인
`prod-sim payment-service`의 `IDENTIFIED` 보고서를 준비한 경우 다음과 같이 요청할 수
있습니다.

```text
이 prod-sim payment-service 보고서를 기준으로 이전 revision rollback 승인 요청을 만들어줘
```

성공하더라도 최대 결과는 `WAITING_APPROVAL`, remediation 참조와 만료 시각입니다. 승인,
거절과 실행은 별도 M8 control plane에서 수행합니다. 보고서가 없거나 오래됐거나 지원하지
않는 대상이거나 citation이 유효하지 않으면 거절이 정상입니다.

## 보고서 읽는 방법

- **상태와 영향**: 증거가 유의미한 장애를 지지하는지 보여줍니다.
- **H-01**: 가장 강한 evidence-backed hypothesis이며 무조건적인 사실 단정이 아닙니다.
- **H-02/H-03**: support, 반박, 부족한 증거와 다음 확인 항목이 있는 대안입니다.
- **Timeline**: 요청한 시간 범위 안의 운영 사건만 표시합니다.
- **Data gap**: 사용할 수 없거나 지연된 source입니다. Gap은 장애의 증거가 아닙니다.
- **권고**: containment, 제한된 mitigation, root fix/prevention으로 구분하며 변경성 조치는
  항상 별도 승인이 필요합니다.
- **Sources**: hypothesis와 권고가 실제로 인용한 evidence ID입니다.

## 문제 해결

| 증상 | 대응 방법 |
| --- | --- |
| 에이전트가 보이지 않음 | 관리자에게 라이선스와 app-level 권한 확인 요청 |
| 장애가 없다고 나옴 | 60분 질의를 사용하고 최신 펄스 또는 Monitoring 수집이 완료될 때까지 잠시 기다림 |
| Runtime 안전 실패가 한 번 표시됨 | 새 채팅에서 완전히 같은 prompt를 한 번만 재시도 |
| 같은 Runtime 실패가 반복됨 | 반복 입력을 멈추고 대략적인 UTC/KST 시각과 prompt만 관리자에게 전달; credential은 전달하지 않음 |
| `prod`가 거절됨 | 합성 production-like 시험이 필요할 때만 `prod-sim` 사용 |
| 후속 질문에 문맥이 없음 | 원래 채팅으로 돌아가거나 합성 incident ID 제공 |

## 체험 완료 체크리스트

- 빠른 시작 prompt가 보였습니다.
- 1분 정상 응답이 장애를 조작하지 않았습니다.
- Evidence가 있을 때 60분 질의가 제한된 자동 복구 장애를 보여줬습니다.
- Citation, 대안 가설, data gap과 승인 요구 사항을 이해할 수 있었습니다.
- 후속 질문 한 개와 의도적 거절 한 개가 예상대로 작동했습니다.
- 실제 credential, 개인정보, project identifier 또는 production 정보를 입력하지 않았습니다.

관리자·아키텍처 정보는 [OpsPilot 앱 정보](app-overview.ko.md)를 참고하세요.
