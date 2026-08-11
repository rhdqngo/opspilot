# Cloud Run Route Recovery

Status: administrator checkpoint required

This procedure diagnoses the three fixed private M2 services without printing account, project,
service URL, token, email, organization, or perimeter identifiers. It does not change Cloud Run,
IAM, VPC Service Controls, or Terraform state.

## Operator diagnostic

Run against the configured gcloud project only:

```powershell
uv run opspilot route-check --account-alias Edu_687 --format summary
```

Exit code `0` means the private route is ready. Exit code `2` means the `blocker_code` must be
resolved before remote load or hosted planning. The only blocker codes are `service_unready`,
`route_restricted`, `iam_denied`, and `unknown`.

The current expected blocked result is three Ready services with full traffic, authenticated and
unauthenticated pre-container `404` responses, no request log, `route_ready=false`, and
`blocker_code=route_restricted`.

## Administrator checklist

Share only the redacted route-check summary and ask an organization administrator to verify:

- whether the project is included in a service perimeter;
- which access level and ingress or egress rule governs the Cloud Run `run.app` endpoint;
- whether recent VPC Service Controls violations identify Cloud Run `HttpIngress`;
- whether the GitHub CI plan service account has an allowed Cloud Run Admin API read path for
  `run.services.get`, `run.services.list`, and `run.services.getIamPolicy`.

If perimeter membership is intentional, request the smallest policy change:

- connect an access level for the operator's approved network, IP, or managed device;
- allow only the three read methods above for the GitHub CI plan identity through the Admin API;
- define Cloud Run invocation access using supported network and access-level context, not only an
  IAM principal. The Cloud Run endpoint's VPC Service Controls decision does not use the caller's
  IAM identity.

If the project was included by mistake, only the administrator may remove the project from the
perimeter. The repository and operator must not add `allUsers`, disable invoker IAM checks, change
`INGRESS_TRAFFIC_ALL`, grant broad project roles, reapply, or destroy services as a workaround.

The administrator reports only `route exception active` or `route exception unavailable`; no
policy, project, perimeter, account, or network identifier is recorded in the repository.

Reference: [Cloud Run with VPC Service Controls](https://cloud.google.com/run/docs/securing/using-vpc-service-controls)

## Recovery verification

After `route exception active`, run the diagnostic after 15, 30, and 45 seconds, stopping at the
first success. A successful check has three Ready services, three unauthenticated `403` responses,
three authenticated `200` responses, and zero pre-container `404` responses.

Then:

1. Run `uv run opspilot demo load --orders 10 --concurrency 2 --auth gcloud`; require ten fulfilled
   orders.
2. Confirm request IDs and Cloud Trace correlation across all three services without inspecting or
   retaining bodies, tokens, email-like data, or card-like data.
3. Confirm request logs, structured application logs, request count, and latency points; require
   zero intentional or observed 5xx responses.
4. Recheck zero public principals, user-managed runtime keys, project runtime roles, and exactly
   the order identity's two leaf invoker grants.
5. Recheck the common image digest, revision traffic, scale-to-zero settings, probes, labels, and
   an operator Terraform zero-drift plan. Do not apply.
6. Only after these checks, configure the private image and plan gates and run the manual hosted
   read-only zero-drift workflow.

If the exception is unavailable, preserve all 24 managed resources and the disabled hosted gates.
Keep the phase `M2-deployed / remote-smoke-blocked` and prepare a separately approved personal
project migration plan.
