# Formal Agent 배포 절차

[English](formal-agent-rollout.md) | **한국어**

상태: 4개 phase 배포 및 managed/Preview QA 검증 완료

Formal Incident Commander 배포에는 독립적으로 검토한 4개의 binary Terraform plan을
사용했습니다. 각 plan에는 해당 phase 소유 address만 포함했고, apply 시 새 plan으로
바꾸지 않고 검토한 binary plan을 그대로 재사용했습니다. 이 runbook은 향후 source-bound
update에도 같은 release contract를 적용하기 위해 보존합니다.

## Plan phase

1. `workloads`: staging과 prod-sim의 order, payment, inventory Cloud Run service와 workload
   identity, order-to-payment/inventory invoker binding만 생성합니다.
2. `investigation`: caller 전환 전에 model permission과
   `conversation_contexts.expires_at` TTL field를 추가합니다.
3. `remediation`: investigation API image와 control bridge를 원자적으로 갱신하면서 고정
   rollback target과 invocation binding을 prod-sim payment로 이동합니다. Cloud Run의
   control URL dependency 때문에 이를 나누면 phase 사이 drift가 생깁니다. 이름이 명시된
   IAM-member target 3개의 replacement만 허용한 delete/create입니다.
4. `runtime`: Runtime resource를 교체하거나 이름을 바꾸지 않고 기존 Agent Runtime source
   archive만 갱신합니다.

Verifier는 empty phase, cross-phase address, 미검토 replacement와 public invoker를 허용하지
않습니다. Remediation cutover와 Runtime phase는 정확한 image digest 및 archive SHA-256도
결합합니다.

```powershell
uv run python scripts/formal_agent_release.py .tmp/formal/workloads.json --phase workloads
uv run python scripts/formal_agent_release.py .tmp/formal/investigation.json --phase investigation
uv run python scripts/formal_agent_release.py .tmp/formal/remediation.json `
  --phase remediation --image-digest sha256:<reviewed-digest>
uv run python scripts/formal_agent_release.py .tmp/formal/runtime.json `
  --phase runtime --runtime-sha256 <reviewed-sha256>
```

Apply 전마다 binary plan SHA-256을 기록하고 `terraform show -json` 결과에 맞는 verifier를
다시 실행합니다. 예상하지 않은 add, update, replacement, delete, IAM member, Runtime name,
public invoker, source hash 또는 registration target이 있으면 중단합니다.

완료된 rollout은 9개 synthetic workload Ready, private IAM, direct Runtime conversation
smoke, 3환경 SCN-001 recovery, 실행 없는 prod-sim M8 `WAITING_APPROVAL`, Gemini Enterprise
대화형 QA와 동일 input의 최종 Terraform `No changes`를 통과했습니다. 향후 rollout도 같은
gate를 유지해야 합니다.
