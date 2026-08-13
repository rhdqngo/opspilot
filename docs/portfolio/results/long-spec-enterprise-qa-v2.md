# Gemini Enterprise Preview Iterative QA Evidence v2

- Status: **BLOCKED — confirmed Preview provider streaming failure**
- Iterations: `2`
- Product blocker-fix commit: `b71570bdcb86a167d918a75031e80b64b690cf30`
- Scenario warm-up commit: `e3dfc1455c12a54db4ce80292c1088a984ac3f91`
- Final deployed image: restored to the last Preview-healthy product candidate

Cloud project, account, service URLs, identities, image digests, user/session values, and
trace/run/correlation/investigation IDs are omitted. Raw logs, the ID map, and the provider-failure
screen capture remain under ignored `.tmp/enterprise-qa-live` only.

## Iteration results

| Cycle | Result | Evidence |
| --- | --- | --- |
| 1 | remediated | Three consecutive healthy Preview chats passed. The managed SCN-001 request recovered `5/5` and produced the expected `4 fulfilled / 6 failed` incident split, but only `3/5` counted baseline orders survived scale-to-zero cold start. |
| 2 | blocked | Added a bounded authenticated `/ready` warm-up. All 235 tests and release gates passed; the one-address image rollout was Ready. Preview then repeatedly failed to terminate a completed stream. |

The initial cycle-1 CLI attempt omitted `OPSPILOT_ORDER_URL` and stayed on the local default. It did
not reach or alter the managed service and is excluded from the managed execution count.

## Confirmed provider boundary

| Preview case | Runtime final | Backend invariants | Final visible | Stream closed |
| --- | --- | --- | --- | --- |
| healthy-1 | 2.144 s | passed | yes | yes |
| healthy-2 | 6.999 s | passed | yes | no |
| healthy retry A | 5.972 s | passed | yes | no |
| healthy retry B | 6.896 s | passed | no | no |

For all four cycle-2 executions, Runtime logged exactly `accepted → handler_started → run_summary →
final_emitted`. Each persisted one investigation, one task attempt, one report v1, and four distinct
tool events with shared trace/correlation identities. Healthy reports contained no hypotheses or
changing recommendations. No duplicate or privacy finding occurred.

The two prescribed same-deployment retries therefore did not clear the anomaly. The final retry
had a completed persisted report and `final_emitted` log but Preview remained in its processing
state without rendering the final. This meets the plan's provider-failure safety stop; no further
Preview prompts or product modifications were made.

## Recovery and handoff

- Restored the last Preview-healthy investigation image with a reviewed `0 add / 1 update / 0
  destroy` recovery plan.
- The Agent Runtime archive and Gemini Enterprise registration never changed in cycle 2.
- Cloud Run is Ready, direct managed Runtime still returns one progress plus one final, and normal
  synthetic load passed `5/5` with all request IDs returned.
- Final Terraform plan is `No changes`.

Cycle-2 SCN-001, positive English/Korean/default-environment/privacy cases, and the eight negative
boundaries were intentionally not executed after the safety stop. FR-001, FR-017, and FR-022 remain
Partial until the full matrix can run on a healthy Gemini Enterprise Preview stream.
