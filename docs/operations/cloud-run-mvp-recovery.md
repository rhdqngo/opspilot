# Cloud Run MVP Recovery

Status: endpoint verification and controlled revision refresh

This procedure verifies the three fixed private M2 services without printing account, project,
service URL, token, email, image, or request identifiers. The MVP uses the default Cloud Run HTTPS
endpoint with IAM authentication and does not introduce additional network infrastructure.

## Endpoint diagnostic

Run against the configured gcloud project only:

```powershell
uv run opspilot route-check --account-alias Edu_687 --format summary
```

Exit code `0` means all three private endpoints are ready. Exit code `2` reports exactly one of
`service_unready`, `endpoint_not_found`, `iam_denied`, `transport_error`, `application_error`, or
`unknown`.

The diagnostic checks canonical URL agreement, Ready state, full traffic, default endpoint,
ingress, IAM enforcement, private policies, operator invoke permission, authenticated and
unauthenticated health responses, and correlated container application logs. It does not accept a
project or raw token argument and suppresses command stderr.

## Read-only recovery gate

1. Keep `TF_PLAN_ENABLED` and `TF_M2_IMAGE_READY` disabled.
2. Confirm 24 managed remote-state resources and three Ready services with full traffic.
3. Run the diagnostic up to three times. Stop immediately if all unauthenticated calls return
   `403`, all authenticated calls return `200`, and three correlated application logs are found.
4. If the blocker is not `endpoint_not_found`, resolve the reported authentication, transport,
   application, or service state problem without refreshing revisions.

## Controlled revision refresh

Only a persistent `endpoint_not_found` permits the tracked `release_phase=m2-mvp` template marker
to be planned. The fresh Terraform plan must contain exactly three in-place Cloud Run service
updates and no create, delete, replacement, IAM, API, identity, budget, registry, or image change.
Apply only the reviewed binary plan.

After apply, wait 15, 30, and 45 seconds between at most three endpoint checks. Require a new Ready
revision with 100% traffic for each service and the same immutable image digest. Do not destroy,
replace, expose, or repeatedly refresh the services if the endpoint remains unavailable.

## Remote acceptance

1. Require unauthenticated `403` and authenticated `200` from all three health endpoints.
2. Run `uv run opspilot demo load --orders 10 --concurrency 2 --auth gcloud`; require ten fulfilled
   orders and ten request IDs.
3. Verify request and application logs correlate across order, payment, and inventory and contain
   no body, authorization value, token, email-like, or card-like data.
4. Verify request count and latency points and require zero 5xx responses.
5. Recheck zero public principals, runtime keys, and project runtime roles, plus exactly the two
   order-to-leaf invoker grants.
6. Require operator zero drift, then enable the private hosted plan gates and require a redacted
   hosted `No changes` result.

If the controlled refresh does not recover the endpoint, preserve all managed resources, keep the
hosted gates disabled, retain `M2-deployed / remote-smoke-blocked`, and create a separately
approved personal-project migration plan.

References: [test a private Cloud Run service](https://docs.cloud.google.com/run/docs/authenticating/developers),
[service-to-service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service),
and [Cloud Run 404 troubleshooting](https://docs.cloud.google.com/run/docs/troubleshooting#http_404_not_found).
