# Cloud Run MVP Safe-Path Recovery

Status: complete; retained as the safe-path recovery record

Cloud Run reserves some paths ending in `z` and recommends avoiding all such paths. The former
`/healthz` endpoint was intercepted before the request reached the container. The M2 demo uses
`/health` and `/ready`; the R0 investigation API remains a separate local contract.

References: [Cloud Run known issues](https://docs.cloud.google.com/run/docs/known-issues),
[container health checks](https://docs.cloud.google.com/run/docs/configuring/healthchecks), and
[private service testing](https://docs.cloud.google.com/run/docs/authenticating/developers).

## Redacted endpoint diagnostic

Run against the configured gcloud project only:

```powershell
uv run opspilot route-check --account-alias Edu_687 --format summary
```

The diagnostic calls `/health` on the three fixed private services. Exit code `0` requires three
Ready services with full traffic, consistent default endpoints, IAM enforcement, private policies,
operator invoke permission, unauthenticated `403`, authenticated `200`, and no pre-container 404.
Container log counts are reported as telemetry evidence but do not make route readiness depend on
Logging ingestion latency. Output never contains account, project, URL, token, email, image, or
request identifiers.

## Exact rollout gate

The completed rollout satisfied this gate. Reuse it only as an audit checklist; do not reapply the
saved plan.

1. Keep `TF_PLAN_ENABLED` and `TF_M2_IMAGE_READY` disabled.
2. Validate clean `main`, 24 remote-state resources, zero drift, and three Ready services.
3. Build the selected commit as a Linux/amd64 non-root image and complete the local 10-order E2E.
4. Push one commit-SHA tag to the existing registry and resolve it to an immutable digest.
5. Create a fresh binary plan in one ignored run directory.
6. Require exactly `0 create / 3 update / 0 delete / 0 replacement`. Only the three Cloud Run
   services may change, and only their shared image digest and `/ready` startup and `/health`
   liveness probe paths may differ.
7. Apply only the reviewed binary plan. Do not change IAM, identities, ingress, scaling, labels,
   downstream URLs, APIs, the registry, budget, or resource count.

## Remote acceptance

1. Require unauthenticated `403` and authenticated `200` for both `/health` and `/ready` on all
   three services.
2. Require `route-check` exit code `0`, `route_ready=true`, and `blocker_code=none`.
3. Run `uv run opspilot demo load --orders 10 --concurrency 2 --auth gcloud`; require ten fulfilled
   orders and ten request IDs.
4. Verify request and application logs correlate across order, payment, and inventory and contain
   no body, authorization value, token, email-like, or card-like data.
5. Verify request-count and latency points for the acceptance window and require zero 5xx.
6. Recheck zero public principals, runtime keys, and project runtime roles, plus exactly the two
   order-to-leaf invoker grants.
7. Require operator zero drift, enable the private hosted-plan gates, and require a redacted hosted
   `No changes` result.

If the exact plan differs or the safe endpoint still fails, do not repeat apply, expose, replace,
destroy, broaden IAM, or migrate automatically. Preserve the 24 managed resources, disable the
hosted gates, and record the remaining blocker.

## Completion record

- One immutable safe-path image was pushed from the validated `main` commit.
- The applied plan was exactly three in-place Cloud Run service updates with no other action.
- Three private `/health` and `/ready` endpoints, 10/10 remote orders, correlated logs/traces,
  Monitoring points, runtime security, operator zero drift, and hosted zero drift all passed.
- Managed resources remain 24; public principals, runtime keys, project runtime roles, and 5xx
  observations remain zero.
