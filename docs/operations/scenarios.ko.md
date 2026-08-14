# 합성 장애 시나리오

[English](scenarios.md) | **한국어**

상태: request-scoped SCN-001 검증 완료, 선택적 30분 주기 dev 체험 지원

## 안전 모델

- Scenario 동작은 기본적으로 비활성화되며 영속 장애 상태가 없습니다.
- 영속 fault-injector 상태, 관리 endpoint, secret, custom metric, alert 또는 remediation
  identity를 만들지 않습니다.
- Live 실행은 `SCN-001`만 허용합니다. Incident phase의 10개 요청 중 6개에만 검증된
  scenario header가 붙고 baseline과 recovery 요청에는 scenario context가 없습니다.
- 고정 실행 형태는 baseline 5건, incident 10건, recovery 5건이며 concurrency는 2입니다.
- Counted baseline 전에 인증된 order `/ready`를 제한적으로 probe해 scale-to-zero revision을
  깨우며, 이 probe는 order·scenario trace 수에 포함하지 않습니다.

## 수동 실행

Local Compose에서는 다음과 같이 실행합니다.

```powershell
docker compose up -d --no-build
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot scenario run --scenario SCN-001 --auth local --format summary
docker compose down --remove-orphans
```

Managed 환경에서는 private order service URL을 `OPSPILOT_ORDER_URL`로 설정하고
`--auth gcloud`를 사용합니다. 합격 결과는 baseline `5/5`, incident `4 fulfilled / 6 failed`,
recovery `5/5`, `recovered=true`, `ground_truth_matched=true`입니다.

## 예약된 포트폴리오 체험

`enable_scheduled_scenarios=true`이면 Terraform이 전용 Cloud Run Job 하나와
`Asia/Seoul` 기준 `5,35 * * * *` Cloud Scheduler trigger를 만듭니다. Job은 다음 명령만
실행합니다.

```powershell
opspilot scenario run --scenario SCN-001 --env dev --auth workload --format json
```

Application Default Credentials가 고정 dev order URL을 audience로 하는 ID token을
발급합니다. Runner는 dev order에 대한 resource-level invoke 권한만 받고 Scheduler
identity는 해당 Job에 대한 resource-level invoke 권한만 받습니다. 실행 결과가 고정 계약과
다르면 exit code 2로 실패합니다.

운영 명령:

```powershell
gcloud run jobs execute <job> --region <region> --wait
gcloud scheduler jobs pause <scheduler-job> --location <region>
gcloud scheduler jobs resume <scheduler-job> --location <region>
gcloud run jobs executions list --job <job> --region <region> --limit 5
```

실제 resource name은 Terraform output 또는 read-only inventory에서 확인하고 versioned
evidence에는 기록하지 않습니다. 장애 주입은 incident request header에만 있으므로 Job이
중단돼도 영속 장애가 남지 않습니다. Schedule은 staging, prod-sim, M8 또는 actual
production을 호출하지 않으며 investigation이나 model call을 시작하지 않습니다.

실패 시 Job execution status와 sanitized aggregate output을 먼저 확인합니다. Recovery 실패나
고정 request count 위반이 반복될 때만 Scheduler를 pause하고, 수동 Job이 전체 계약을 다시
통과한 뒤 resume합니다.
