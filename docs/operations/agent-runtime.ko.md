# Agent Runtime 운영 가이드

[English](agent-runtime.md) | **한국어**

상태: deployed thin adapter

배포된 formal Runtime은 input length와 language만 확인한 뒤 유효한 모든 turn을
`POST /internal/v2/runtime/turns`로 전달합니다. API는 evidence collection이 실제로
시작됐는지 반환합니다. Investigation/refinement turn은 buffered progress 1건과 final 1건,
capability, explanation, status, comparison, clarification, rejection turn은 final 1건만
생성합니다. v1 bridge는 호환성을 위해 유지합니다.

## 계약

Canonical entrypoint는 `opspilot.agent.runtime_agent:root_agent`입니다. 하나의 ADK streaming
operation만 노출하고 accepted investigation을 private persistent investigation API에
위임합니다. Runtime package에는 직접 evidence 또는 RCA fallback이 없습니다.

`OPSPILOT_INVESTIGATION_API_URL`은 필수입니다. 값이 없거나 연결할 수 없거나 응답이
유효하지 않으면 Runtime은 localized safe failure 1건을 반환하며 다른 실행 경로로
전환하지 않습니다. Runtime identity는 해당 API invoke 권한만 필요합니다. Logging,
Monitoring, Cloud Run, Search, Cloud Tasks와 Firestore 권한은 API 소유 identity에 남습니다.

Agent Engine은 `GOOGLE_CLOUD_PROJECT`를 numeric project hint로 제공할 수 있습니다.
Runtime identity의 전용 custom role은 정확히 `resourcemanager.projects.get` 하나만 포함해
SDK가 이 hint를 해석하게 합니다. Broad viewer나 evidence, persistence, task, IAM,
remediation 권한은 추가하지 않습니다. Project 값은 저장하거나 log에 남기지 않습니다.

Input은 catalog의 `order-service`, `payment-service`, `inventory-service`와 한국어·영어
1~120분 상대 구간을 지원합니다. Service 생략은 3개 전체, time 생략은 30분입니다.
Command, write request, project ID, URL, token, raw filter, 미등록 service, 범위 밖 또는
모호한 window는 API 호출 전에 거절합니다. Runtime은 invocation마다 run ID, correlation
ID와 32-hex trace ID를 한 번 만들고 `X-Cloud-Trace-Context`와 함께 전달하며 run ID를
idempotency key로 사용합니다. User/session 값은 source-domain SHA-256 hash이고 raw 값과
raw prompt는 log 또는 persistence에 남기지 않습니다.

Runtime은 progress를 내보내기 전에 bounded handler를 시작하고 하나의 monotonic deadline
안에서 정확히 progress 1건과 final 1건을 생성합니다. Accepted, handler-started, summary,
final, cancellation, timeout stage가 같은 run/correlation/trace identity를 사용합니다.

Visible progress, failure와 persisted Markdown은 prompt에 Hangul이 있으면 한국어, 그 외에는
영어를 사용합니다. Renderer는 server-owned narrative와 assumption을 번역하되 evidence ID와
technical evidence title은 보존합니다.

## 패키징

```powershell
uv run --extra agent opspilot agent runtime package --output .tmp/runtime-a
uv run --extra agent opspilot agent runtime package --output .tmp/runtime-b
```

두 archive는 byte-identical이어야 합니다. Allowlist에는 package root, Runtime
adapter/entrypoint, parser, audit/retry contract, catalog, domain model, service catalog resource와
requirements만 포함합니다. Agent workflow/model/evidence/search/redaction/reporting/scoring,
CLI/API/demo, fixture, test, docs와 Terraform은 포함하지 않습니다.

## 릴리스 검사

1. Clean implementation commit에서 Ruff, strict mypy, pytest, build, core/portfolio/remediation
   평가와 package build 2회를 실행합니다.
2. `release-context.json` 하나를 만들고 이후 image, Terraform, evidence record를 canonical
   hash에 결합합니다.
3. Terraform plan과 evidence 게시 전에 source가 context와 일치하는지 확인하고 apply 직전
   reviewed binary plan SHA를 다시 확인합니다.
4. Runtime source update는 유일한 Runtime 변경이어야 하며 identity, IAM, region, scaling,
   registration과 environment는 고정합니다.
5. Apply 후 Ready, progress 1건, final persisted report 1건과 Terraform `No changes`를
   확인합니다. Prompt, identity 또는 evidence payload를 log에 기록하지 않습니다.

## 안전 실패 진단

- Configuration failure: 배포 Runtime의 `OPSPILOT_INVESTIGATION_API_URL`이 존재하고 고정된
  private API를 가리키는지만 확인합니다.
- Authentication/transport failure: prompt나 payload 대신 run/correlation/trace ID의
  가명화 stage/outcome log와 API request record를 확인합니다. Runtime에 직접 evidence
  권한을 추가하지 않습니다. Transient 429/5xx/timeout/transport failure는 full jitter로
  최대 3회만 retry합니다.
- Timeout: Cloud Task와 investigation status를 확인합니다. Redelivery는 예상된 동작이며
  idempotent해야 합니다.
- Partial evidence: data gap과 citation이 있는 persisted partial/inconclusive report를
  반환하고 누락 evidence를 만들어 내지 않습니다.
