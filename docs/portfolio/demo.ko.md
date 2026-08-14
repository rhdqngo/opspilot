# OpsPilot 3~5분 데모

[English](demo.md) | **한국어**

## 준비

```powershell
uv sync --frozen --extra agent
docker build --platform linux/amd64 -t opspilot-demo:local .
```

시간을 재는 데모에서는 image만 준비하고 Compose 시작과 정리는 demo runner에 맡깁니다.

```powershell
uv run python scripts/portfolio_demo.py --dry-run
uv run python scripts/portfolio_demo.py
```

시간 제한 없는 cold build가 허용될 때만 `--build-image`를 사용합니다. Runner는 사용 중인
demo port를 거절하고 `http://127.0.0.1:8100/ready`를 기다리며, 첫 실패 phase에서 중단하고
stack을 건드렸다면 항상 `docker compose down --remove-orphans`를 시도합니다. 개인정보를
포함하지 않는 step summary는 `.tmp/portfolio-demo/summary.json`에 기록합니다.

## 녹화 순서

1. **00:00-00:25 — 경계:** README 상단에서 synthetic data, 읽기 전용 조사 identity,
   분리된 approval-gated rollback을 설명합니다.
2. **00:25-00:50 — 정상 workload:** 한정된 10건 order smoke와 aggregate success를 보여 줍니다.
3. **00:50-01:25 — 장애:** SCN-001의 고정 5 baseline / 10 incident / 5 recovery phase와
   자동 baseline 복귀를 보여 줍니다.
4. **01:25-02:00 — Evidence:** cloud identifier 없이 LOG, METRIC, CHANGE, KNOWLEDGE source
   상태를 보여 줍니다.
5. **02:00-02:40 — 조사:** core agent report에서 evidence ID, data gap, 결정론적 support
   score와 approval-required recommendation을 설명합니다.
6. **02:40-03:30 — 품질:** `portfolio-v1`의 40개 case와 release-gate metric을 보여 줍니다.
7. **03:30-04:10 — Enterprise:** 얇은 Runtime이 3개 서비스 중 하나에 대해 persistent API를
   호출하는 과정, immutable report, replay로 생성된 v2와 결정론적 비교를 보여 줍니다.
8. **04:10-04:40 — 안전과 비용:** trust boundary, alert-without-remediation 규칙,
   scale-to-zero, budget과 실행 기능이 없는 cleanup plan을 보여 줍니다.

## 명령

```powershell
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot demo load --orders 10 --concurrency 2 --auth local
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot scenario run --scenario SCN-001 --auth local --format summary
uv run opspilot evidence smoke --scenario SCN-001 --env dev --format summary
uv run --extra agent opspilot agent run --scenario SCN-001 --format markdown
uv run --extra agent opspilot agent eval --suite portfolio --format summary --output .tmp/evaluation
uv run opspilot cleanup plan --format summary
docker compose down --remove-orphans
```

개별 명령도 설명용으로 사용할 수 있지만, `scripts/portfolio_demo.py`가 재현 가능한 실행
계약입니다.
