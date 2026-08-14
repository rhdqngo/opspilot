# 검증 증빙 색인

[English](README.md) | **한국어**

이 directory에는 개인정보와 실제 cloud identifier를 제거한 source-bound release 및 QA
record를 보관합니다. Markdown은 사람이 읽는 summary이고, 같은 이름의 JSON은 동일한
bounded result를 machine-readable 형식으로 제공합니다. Cloud project identifier, URL,
service identity, image digest, Runtime resource name, trace/run/investigation ID와 browser
capture는 의도적으로 제외합니다.

## 현재 기준 기록

| 기록 | Status | 목적 |
| --- | --- | --- |
| [Formal agent v3](long-spec-formal-agent-v3.md) ([JSON](long-spec-formal-agent-v3.json)) | Passed | 최종 Gemini Enterprise Preview 양성 장애 탐지, localization correction, backend invariant와 278-test source-bound gate |

## Formal-agent 진행 이력

| 기록 | Status | 목적 |
| --- | --- | --- |
| [Formal agent v2](long-spec-formal-agent-v2.md) ([JSON](long-spec-formal-agent-v2.json)) | Passed | 최종 Preview regression과 concise healthy-summary correction |
| [Formal agent v1](long-spec-formal-agent-v1.md) ([JSON](long-spec-formal-agent-v1.json)) | Passed | 3환경 rollout 및 managed conversational verification |
| [Enterprise QA v4](long-spec-enterprise-qa-v4.md) ([JSON](long-spec-enterprise-qa-v4.json)) | Passed | Formal-agent 확장 전 Preview matrix |
| [Pre-QA v1](long-spec-preqa-v1.md) ([JSON](long-spec-preqa-v1.json)) | Passed | Source-bound deployment, trace, audit, privacy, idempotency readiness |

## 과거 감사 이력

다음 기록은 passing candidate 이전에 발견한 defect와 provider condition을 보여 주기 위해
보존합니다. 현재 release claim으로 사용하지 않습니다.

| 기록 | 과거 결과 |
| --- | --- |
| [Enterprise QA v1](long-spec-enterprise-qa-v1.md) ([JSON](long-spec-enterprise-qa-v1.json)) | Blocked |
| [Enterprise QA v2](long-spec-enterprise-qa-v2.md) ([JSON](long-spec-enterprise-qa-v2.json)) | Confirmed provider streaming failure로 blocked |
| [Enterprise QA v3](long-spec-enterprise-qa-v3.md) ([JSON](long-spec-enterprise-qa-v3.json)) | Preview canary 전 blocked |
| [MVP cloud release v1](mvp-cloud-release-v1.md) ([JSON](mvp-cloud-release-v1.json)) | 과거 MVP gate 통과 |
| [Portfolio release v1](portfolio-release-v1.md) ([JSON](portfolio-release-v1.json)) | 과거 offline portfolio gate 통과 |

Raw execution evidence는 `.tmp`에만 두며 version control에 포함하지 않습니다.
