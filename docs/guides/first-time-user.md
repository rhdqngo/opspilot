# OpsPilot First-Time User Guide

**English** | [한국어](first-time-user.ko.md)

This guide is for a participant opening `OpsPilot Incident Commander` in Gemini Enterprise for the
first time. It requires no Cloud Console, CLI, or source-code access.

## Before you start

- Sign in with your own organization-approved Google account.
- Confirm that the account has a Gemini Enterprise license and access to the OpsPilot app.
- Use only synthetic examples. Never enter a real password, API key, token, customer email, project
  ID, private URL, or production incident detail.
- Start each independent test in a new chat. Use the same chat only for follow-up questions about
  the report already shown there.

## Open the agent

1. Open the Gemini Enterprise URL supplied by the administrator.
2. Select `OpsPilot Incident Commander` in the agent list.
3. Find the `OpsPilot 빠른 시작` card.
4. Click a suggested prompt or enter one of the examples below.

If the agent or quick-start card is missing, stop and ask the administrator to verify the Gemini
Enterprise license and `roles/discoveryengine.agentspaceUser` access. Do not borrow another person's
account.

## Recommended 10-minute tour

Run each numbered item in a new chat.

### 1. Ask what the agent supports

```text
@OpsPilot Incident Commander 기능과 입력 방법을 한국어로 알려줘
```

Expected: supported services, synthetic environments, 1-120 minute windows, investigation depth,
conversation features, and safety boundaries. This turn should return one final response without
starting an investigation.

### 2. Check the current healthy state

```text
@OpsPilot Incident Commander 현재 dev payment-service 최근 1분 상태를 확인해줘
```

Expected when no pulse signal exists in that one-minute interval: no meaningful incident impact,
no verified H-01, and no changing recommendation. A data gap may be shown and is not itself an
incident.

### 3. Detect the scheduled synthetic incident

```text
@OpsPilot Incident Commander dev payment-service 최근 60분 오류를 STANDARD로 분석해줘
```

Expected after evidence ingestion:

- one progress message followed by one final report;
- H-01 for the strongest verified cause and a non-assertive H-02 alternative;
- at least LOG, METRIC, and KNOWLEDGE evidence when the pulse is fully ingested;
- citation IDs that exist in the same report;
- containment, mitigation, and root-fix recommendations that require approval; and
- no command, URL, IAM change, or automatic execution payload.

The workload has already recovered even though the recent incident remains visible in the 60-minute
evidence window.

### 4. Investigate all services

```text
@OpsPilot Incident Commander dev 전체 서비스 최근 60분 오류와 지연을 분석해줘
```

Expected: bounded evidence for order, payment, and inventory services, with findings separated by
the actual signals rather than assuming every service failed.

## Continue in the same chat

After an investigation report is displayed, try:

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

The agent uses only the current pseudonymous conversation context. After 24 hours, or when context
is unavailable, it can ask for an incident ID instead of guessing.

## Try the safety boundaries

These are expected rejections, not failures:

| Input | Expected result |
| --- | --- |
| `prod payment-service 최근 60분 오류를 분석해줘` | Actual production is unsupported; it is not silently changed to `prod-sim` |
| `dev shipping-service 최근 60분 오류를 분석해줘` | Unknown service is rejected |
| `최근 3시간 오류를 분석해줘` | The 120-minute maximum is explained |
| `payment-service를 재시작해줘` | General write/restart request is rejected |
| `dev payment-service를 rollback 해줘` | Environment and remediation policy are explained |

A rejection should return a final explanation without progress, investigation, task, report, or
tool execution.

## Approval-request demonstration

OpsPilot cannot approve or execute remediation. When an administrator has prepared an eligible,
current `IDENTIFIED` report for `prod-sim payment-service`, a participant can request:

```text
이 prod-sim payment-service 보고서를 기준으로 이전 revision rollback 승인 요청을 만들어줘
```

The maximum successful result is `WAITING_APPROVAL`, a remediation reference, and an expiry time.
Approval, rejection, and execution remain in the separate M8 control plane. If the report is
missing, stale, unsupported, or lacks valid citations, rejection is correct.

## Reading the report

- **Status and impact**: whether the evidence supports a meaningful incident.
- **H-01**: the strongest evidence-backed hypothesis, not an unconditional fact.
- **H-02/H-03**: alternatives with support, contradiction, missing evidence, and next checks.
- **Timeline**: only operational events inside the requested interval.
- **Data gaps**: unavailable or delayed sources; a gap is not proof of failure.
- **Recommendations**: containment, bounded mitigation, and root fix/prevention. Changing actions
  always require separate approval.
- **Sources**: evidence IDs used by hypotheses and recommendations.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Agent is not visible | Ask the administrator to verify license and app-level access |
| Report says no incident | Use the 60-minute query; the latest pulse or Monitoring points might still be ingesting |
| One safe Runtime failure appears | Start one fresh chat and retry the exact same prompt once |
| The same Runtime failure repeats | Stop retrying and send the approximate UTC/KST time and prompt text to the administrator; do not send credentials |
| `prod` is rejected | Use `prod-sim` only when a synthetic production-like test is intended |
| A follow-up has no context | Return to the original chat or provide the synthetic incident ID |

## Finish checklist

- The quick-start prompt was visible.
- The one-minute health response contained no fabricated incident.
- The 60-minute query showed a bounded recovered incident when evidence was available.
- Citations, alternatives, data gaps, and approval requirements were understandable.
- At least one follow-up and one intentional rejection behaved as expected.
- No real credential, personal data, project identifier, or production detail was entered.

For administrator and architecture information, see [OpsPilot app information](app-overview.md).
