# Agent Runtime Runbook

Status: M7 complete; Enterprise Preview stable; MVP accepted

## Product contract

The Runtime accepts only a 3-500 character read-only investigation naming exactly
`payment-service`. A missing time window becomes the recent 30 minutes with an assumption. Other
services, windows, commands, recovery, and execution requests return a fixed safe message before
evidence or model calls.

Runtime output is localized without changing the public request schema. Any Hangul character in the
input selects Korean; otherwise the supported input and any rejection use English. Detection occurs
before scope validation. Visible Runtime copy follows that language, while evidence IDs, service and
metric names, and evidence titles/summaries remain unchanged. CLI, API, fixture, and evaluation
paths have no user-language input and keep the English default.

The accepted live path uses workload ADC, the packaged service catalog, and parallel bounded
read-only LOG, METRIC, CHANGE, and KNOWLEDGE collection. It does not run the seven-node `Workflow`.
That graph and its two-model evaluation remain fixture/eval-only. Live requests call one independent
RCA `LlmAgent` only when valid `SUPPORTS` evidence spans at least two of LOG, METRIC, and CHANGE;
otherwise they skip the model and assemble an inconclusive `IncidentReport` deterministically.

Gemini Enterprise may supply a session ID. The single-turn MVP handles it with ADK's
`InMemorySessionService` via `session_service_builder`; it does not call Agent Platform Sessions,
persist conversation state, or reuse user identity. Managed Sessions and multi-turn continuity are
post-MVP.

For an accepted request, the stream immediately emits the following content with two trailing
newlines so concatenating clients preserve the Markdown heading boundary:

```text
Collecting bounded evidence for payment-service over the recent 30 minutes…\n\n

최근 30분 동안 payment-service의 제한된 증거를 수집하고 있습니다…\n\n
```

Exactly one of those localized strings is emitted. The event flags are `partial=true` and
`turnComplete=false`.

The report or fixed safe error follows with `partial=false` and `turnComplete=true`. Rejections emit
only their final event. Live transport, source, evidence-collection, RCA-model, and whole-Runtime
budgets are 3, 4, 5, 10, and 18 seconds. RCA timeout, provider error, or invalid structured output
degrades to an evidence-backed partial/inconclusive report. Only whole-Runtime timeout or report
serialization failure becomes `The bounded investigation failed safely.` without raw error text.
The Korean equivalent is `제한된 범위의 조사를 안전하게 완료하지 못했습니다.`.

Every request receives a random `RUN-…` identifier generated inside the Runtime. Stage logs contain
`event`, `run_id`, `stage`, and `elapsed_ms`. A single terminal `run_summary` additionally contains
only the final classification, source status/error codes, and reasoning outcome. The identifier is
not derived from the Enterprise user/session and the logs still exclude question text, cloud
project, evidence content, and raw exceptions.

## Package

```powershell
uv run --extra agent opspilot agent runtime package --output .tmp/runtime
```

The deterministic archive contains only its explicit production allowlist and pinned requirements.
It excludes CLI, API/demo code, fixtures, corpus synchronization, tests, docs, Terraform, temporary
state, and retired diagnostic/registration modules. Do not upload the archive as a CI artifact.

The entrypoint is `opspilot.agent.runtime_agent:root_agent`, an official `AdkApp` exposing exactly:

```text
streaming_agent_run_with_events
api_mode: async_stream
required input: request_json (string)
```

## Deployment

Generate a fresh package from clean `main`, verify two archives have the same hash, and create a
fresh dev plan. Apply only if the plan is exactly `0 create / 1 update / 0 delete / 0 replacement`
and the sole change is the Runtime source archive/hash. Identity, IAM, APIs, region, scaling,
telemetry, labels, class methods, and deletion policy must remain unchanged.

The previous Preview failure was traced to `aiplatform.sessions.create`: the default managed-session
path received an Enterprise session ID and failed three times before evidence/model work. No
Logging, evidence, model, IAM, or registration failure caused that incident.

The recovery archive was applied as the sole in-place Runtime update. Dev remains
`36 managed / 37 addresses`, the Runtime is Ready, and the post-apply operator plan is `No changes`.
An Enterprise-shaped out-of-scope `streamQuery` with a session ID returned HTTP 200 and one safe
rejection event without a managed-session call. The supported Preview question is:

```text
payment-service 최근 30분 상태를 근거와 함께 분석해줘
```

A later supported Preview attempt reached the Runtime and started model work, but all three bridge
attempts closed without an ADK event. Replacing `before_agent_callback` with a streaming `BaseAgent`
made progress visible, but the live seven-node Workflow could still finish model generation without
reaching `graph_complete` or `final_emitted`. The final MVP therefore removes that Workflow from the
live path, retains it for fixture evaluation, and records only `accepted`, `evidence_complete`,
`reasoning_skipped`, `reasoning_complete`, `reasoning_timeout`, `final_emitted`, `timeout`, or
`cancelled`, without identities, prompt content, session IDs, or raw exception text.

The deployed recovery archive SHA-256 is
`980a050e601a9f86db58b113ae4a5270d928458960fa1e672ff0a806d53744b5`. Two builds produced the
same 17-file archive. The saved Terraform plan and apply changed only the Runtime source archive:
`0 create / 1 update / 0 delete / 0 replacement`; the post-apply plan was `No changes`.

The final direct accepted `streamQuery` returned HTTP 200 and two events. A cold start took about
24.8 seconds before the response stream opened; the progress event was present immediately when the
stream opened. The final fixed safe event arrived 84.9 seconds later, within the 90-second Runtime
deadline. Runtime logs recorded `accepted` at 0 ms, `evidence_complete` at 1,203 ms,
`graph_complete` at 84,817 ms, and `final_emitted` at 84,906 ms. No
`aiplatform.sessions.create`, zero-event close, or unhandled-exception pattern appeared in the
post-deployment log window.

After the final log-minimization archive was applied, an out-of-scope deployed smoke returned HTTP
200 with exactly one `partial=false`, `turnComplete=true` rejection event. Its structured Runtime
log contained only `event`, `stage`, and `elapsed_ms`.

The user submitted the original Korean question in Gemini Enterprise Preview and received the
progress text followed by a complete inconclusive report. This closes the prior zero-event bridge
failure. The report correctly recommended no action, but exposed four presentation/semantics gaps:
the progress text touched the Markdown heading, zero-point metrics were not listed as data gaps,
knowledge documents appeared in the incident timeline, and an empty hypothesis section had no
fallback text.

The report-quality archive SHA-256 is
`50d595a35a241494e05ca448ecebf7789e08190f3a212423bb30d5d616c3c3ac`. Two builds produced the
same 17-file archive. Validation passed 108 tests, ruff, strict mypy, build, fixture evaluation, and
Terraform validation/tests. The saved plan and apply changed only the Runtime source archive:
`0 create / 1 update / 0 delete / 0 replacement`; the post-apply plan was `No changes`.

Zero-point metric evidence remains in Sources with `missing_points`, adds one explicit data gap per
metric, and makes collection partial without creating a tool error. Knowledge evidence remains in
Sources but not Timeline. Empty hypotheses render `None verified with the available evidence.`

Immediately after this rollout, two out-of-scope smoke attempts returned HTTP 429 before reaching
the handler. Runtime log insert IDs `6a7c345100044f56c34d1e59` and
`6a7c3451000bfec8ecec63fd` show an ADK `set_up()` Resource Manager lookup ending in a transient 504
at `2026-08-12T08:52:33Z`. No IAM, telemetry, or Runtime code was changed. Managed capacity then
recovered: at `2026-08-12T08:56:30Z`, an out-of-scope smoke returned HTTP 200 with one final
rejection event and log insert ID `6a7c353e00010e3ca12f70a8`. No managed-session creation,
zero-event close, or unhandled-exception pattern appeared. A final Preview presentation check was
not run because no authenticated Preview tab was available.

Do not add `aiplatform.sessions.create`, re-register the agent, or repeat the Preview request without
first inspecting the corresponding Runtime logs. A future `GaiaMint invalid` or `mint used too late`
response is a separate Google Preview authentication-bridge blocker.

## Final MVP stabilization

The accepted live pipeline runs as native coroutines so client cancellation and the 18-second
deadline propagate through evidence collection and optional reasoning. Only bounded urllib
transport remains in worker threads. `CancelledError` and async-generator `GeneratorExit` cancel
child work and are re-raised after a privacy-safe `cancelled` stage.

The deployed 17-file archive SHA-256 is
`b985460ccdb29aa0e97e99121d5ae0a97e87963592c341afebcd793d32b38549`; two builds were identical.
Validation passed 114 pytest tests, ruff format/check, strict mypy, build, fixture evaluation 7/7
with 14 model calls, Runtime allowlist/determinism, and Terraform format/validate/test. The saved
plan and apply changed only the Runtime source archive: `0 create / 1 update / 0 delete / 0
replacement`; the post-apply plan was `No changes`.

After an out-of-scope warm-up returned HTTP 200, a direct accepted `streamQuery` returned progress
at 0.65 seconds and the final deterministic report at 2.25 seconds. Its Runtime stages completed as
`accepted → evidence_complete → reasoning_skipped → final_emitted` in 1.42 seconds. The report kept
both zero-point metric gaps, excluded KNOWLEDGE from Timeline while retaining it in Sources, showed
the empty-hypothesis fallback, and recommended no action.

Three consecutive new-chat Gemini Enterprise Preview runs displayed progress in 5.29, 4.71, and
4.75 seconds and rendered the same complete report. The first two final DOM observations were 13.18
and 6.47 seconds. On the third run, the browser probe first sampled an intermediate partial render;
the Runtime emitted the final event 6.51 seconds after browser submission and Gemini Enterprise's
`StreamAssist` answer audit was written at 8.35 seconds (insert ID `3250j0e6hvk9`). The completed
report was present on the next state read. All three corresponding log sequences contain
`final_emitted` and `reasoning_skipped`; the combined window contains no managed Session creation,
zero-event close, unhandled exception, or model invocation.

## Input-language localization

`OutputLanguage` is internal-only and has `en` and `ko` values. The Runtime decides it
deterministically before validation: any Hangul selects `ko`, otherwise `en`. Progress, Markdown
headings and narrative, assumptions, zero-point/source data gaps, rejection, configuration failure,
RCA degradation, and fixed safe failure use a centralized language copy map. Evidence IDs,
`payment-service`, metric names, and evidence titles/summaries are never translated.

The optional RCA request carries `output_language`. The model is instructed to localize only claim,
mechanism, missing-evidence, and next-check prose. Korean prose without Hangul or English prose with
Hangul is rejected as invalid structured output and becomes the localized evidence-backed
inconclusive report. Zero-signal requests still make no model call.

The deployed 17-file archive SHA-256 is
`57d6bb23f9d910225673e9d6d0d88d052a31685a40233db0b981345c9cebd880`; two builds were identical.
Validation passed 126 pytest tests, ruff format/check, strict mypy, build, fixture evaluation 7/7
with 14 model calls, Runtime allowlist/determinism, and Terraform format/validate/test. The saved
plan and apply changed only the Runtime source archive: `0 create / 1 update / 0 delete / 0
replacement`; the post-apply plan was `No changes`.

Direct deployed checks verified Korean rejection and accepted Korean/English streams. Accepted
progress/final transport times were 0.78/10.16 seconds for Korean and 0.81/2.29 seconds for English.
New-chat Gemini Enterprise checks showed Korean progress/final DOM at 7.32/8.43 seconds and English
at 6.96/8.52 seconds. The corresponding Runtime `final_emitted` entries were emitted in 1.12 and
1.69 seconds with insert IDs `6a7c540900025452c2be2f39` and
`6a7c543b0000bfd9d86aa039`. Both reports matched the input language and retained original evidence.
No managed Session creation, zero-event close, unhandled exception, or model invocation occurred in
the Preview window. Existing OTEL span/metrics export 403s remain an unrelated, scoped-out issue.
Checkpoint: `ko-en-output-matched`.

Enterprise registration already exists. Re-registration code is intentionally absent; use the
official console procedure only if an operator explicitly needs to repair registration.
