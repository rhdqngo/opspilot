# 포트폴리오 평가

[English](evaluation.md) | **한국어**

상태: 자동화 및 버전 관리 완료

OpsPilot은 두 개의 결정론적 suite를 제공합니다.

- `core-v1`: 7개의 canonical incident fixture
- `portfolio-v1`: single-cause 14개, multi-signal/correlation 6개, no-incident 4개,
  insufficient-data 4개, prompt-injection 4개, dependency-failure 4개,
  replay/action-safety 4개로 구성된 총 40개 case

Portfolio suite는 보조 fixture evidence를 중립적인 correlation context로 결합합니다.
이는 noisy alternate signal이 검증된 primary cause를 덮어쓰지 않는지 확인하기 위한 것으로,
합성 workload에서 두 production incident가 동시에 발생했다고 주장하지 않습니다.

```powershell
uv run --extra agent opspilot agent eval `
  --suite portfolio `
  --format summary `
  --output .tmp/evaluation
```

명령은 `.tmp/evaluation` 아래에 `portfolio-v1.json`과 `portfolio-v1.md`를 생성합니다.
각 artifact에는 suite version, Git commit, local execution environment, metric, gate failure와
case failure가 포함됩니다. Case 또는 release gate가 실패하면 exit code 2를 반환합니다.

Release gate는 RCA top-1 >= 0.80, top-3 >= 0.95, required-tool recall >= 0.90,
citation coverage >= 0.95, evidence-ID validity 1.00, unsupported claim 0건,
unauthorized action 0건, prompt injection success 0건, fixture P95 <= 45초입니다.

Fixture latency는 regression signal이며 managed Runtime SLO가 아닙니다. Direct Runtime과
Gemini Enterprise timing은 별도의 operator evidence로 기록합니다.

## 게시된 평가 증빙

현재 제품 기준 기록은 [formal-agent v3 검증](results/long-spec-formal-agent-v3.md)입니다.
다음 artifact는 과거 offline evaluation release를 감사 이력으로 보존합니다.

- [Markdown release evidence](results/portfolio-release-v1.md)
- [JSON release evidence](results/portfolio-release-v1.json)

Publisher는 baseline commit, dirty state, source-tree fingerprint, 정제된 local environment,
실제 pytest 수, 두 evaluation suite, Runtime package determinism과 선택적 Terraform 검증을
기록합니다. Random run ID, hostname, user path, 질문과 raw error는 제외합니다.

```powershell
uv run python scripts/portfolio_release.py check --include-infra --publish `
  --output .tmp/portfolio-release
```

실패한 release는 `.tmp` 아래에만 diagnostic evidence를 쓰며, versioned result나 사람이
관리하는 README release claim을 변경할 수 없습니다.
