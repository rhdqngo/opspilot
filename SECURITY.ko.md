# 보안 정책

[English](SECURITY.md) | **한국어**

## 지원 버전

보안 수정은 `main`의 최신 commit을 대상으로 합니다. 과거 portfolio snapshot과 이미 배포된
demo revision은 별도 지원 버전으로 유지하지 않습니다.

## 취약점 제보

의심되는 취약점은 [GitHub 비공개 취약점 제보](https://github.com/rhdqngo/opspilot/security/advisories/new)를
사용해 주세요. Credential, 개인정보, 비공개 cloud identifier 또는 exploit 세부사항을 공개
issue에 작성하지 마세요.

가능하면 영향받는 component, 재현 조건, 예상 영향과 안전한 최소 proof of concept를
포함해 주세요. 이 portfolio project는 best-effort로 검토하며 production SLA를 제공하지
않습니다.

민감정보를 노출하지 않는 일반 defect는 공개 issue로 제보할 수 있습니다.

## 범위

이 정책은 저장소의 source, 합성 demo service, infrastructure 정의와 GitHub workflow에
적용됩니다. 이 프로젝트는 실제 production 연결을 의도적으로 거절하며, 본인이 소유하지
않은 제3자 또는 Google Cloud system에 대한 테스트를 허가하지 않습니다.
