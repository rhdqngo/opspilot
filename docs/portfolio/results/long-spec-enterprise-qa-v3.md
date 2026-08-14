# Gemini Enterprise Preview QA v3 Resume Evidence

- Status: **BLOCKED BEFORE PREVIEW CANARY**
- Source commit: `286fe06fee59eedd5fb56ce5556aff9cae7a19ab`
- Preview queries submitted: `0`
- Deployment changes: `none`

Cloud project, account, service URLs, identities, image digests, user/session values, and
trace/run/correlation/investigation IDs are omitted. Raw SDK output and managed logs remain under
ignored `.tmp/enterprise-qa-live/v3` only.

## Resume gate

The user and application-default GCP credentials were refreshed. Cloud Run was Ready with full
traffic, the investigation API had no public invoker, and Terraform reported `No changes`.

The required direct managed Runtime gate failed before any browser query was sent:

| Check | Result |
| --- | --- |
| SDK progress | received |
| SDK final | not received |
| SDK wait | 45.270 seconds |
| Runtime stages | accepted, handler started, run summary, timeout, final emitted |
| Firestore | complete |
| Task/report | one attempt, report v1 |
| Trace/correlation | linked |

The backend completed and the Runtime recorded `final_emitted`, but the SDK stream exposed only the
progress event. Because the v3 plan requires a successful direct two-event call before the Preview
canary, no Preview canary, SCN-001, candidate-2 deployment, or further QA case was attempted.

## Exit state

- The last Preview-healthy candidate remains deployed unchanged.
- A first five-order normal check encountered scale-to-zero cold start (`3/5`); the immediate warm
  verification passed `5/5` with all request IDs returned.
- Cloud Run remains Ready and Terraform remains `No changes`.

The next attempt must begin with the same direct Runtime gate. Do not submit a Preview query or
deploy candidate 2 until the SDK receives exactly one progress and one final event.
