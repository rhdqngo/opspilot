# M2 Synthetic Demo Services

Status: Approval 2 infrastructure applied; remote invocation validation blocked

## Local workflow

The same immutable-target image runs `order`, `payment`, or `inventory` according to
`OPSPILOT_DEMO_SERVICE`. Compose uses an isolated local network, in-memory state, and no cloud
credential.

```powershell
docker build --platform linux/amd64 -t opspilot-demo:local .
docker compose up -d --no-build
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot demo load --orders 10 --concurrency 2 --auth local
docker compose down --remove-orphans
```

Expected result: three healthy containers and ten fulfilled orders with ten returned request IDs.
The image runs as UID/GID `65532:65532`; the containers are read-only, drop all capabilities, and
set `no-new-privileges`.

## Runtime contracts

- order: `POST /v1/orders`
- payment: `POST /v1/payments/authorizations`
- inventory: `POST /v1/inventory/reservations`
- all roles: `GET /healthz` and `GET /readyz`

Only synthetic SKU, quantity, and KRW amount fields are accepted. `X-Request-ID` and valid Cloud
Trace context propagate across order dependencies. Structured logs never include request bodies,
authorization headers, account identifiers, or tokens.

## Approval 1 verification

- Linux/amd64 image build: pass
- Runtime user: non-root `65532:65532`
- Three health/readiness checks: pass
- Bounded load: 10 attempted, 10 succeeded, 10 request IDs
- `deploy_demo=false` remote plan: zero resource and output changes
- M2 read-only access and exact candidate-name gate: pass, conflicts 0
- Artifact Registry push and Google Cloud writes: 0

## Approval 2 execution record

- Access, billing, telemetry-read permission, candidate-name, clean `main`, and image-empty gates
  passed without printing identifiers.
- The clean Linux/amd64 image ran as `65532:65532`; local Compose completed 10/10 orders.
- One commit-SHA image tag was pushed and resolved to an immutable registry digest.
- Bootstrap applied `0 create / 1 update / 0 delete / 0 replacement`, adding only the three Cloud
  Run read permissions to the CI custom role, then returned zero drift.
- Dev applied `10 create / 0 update / 0 delete / 0 replacement`: two existing APIs entered state,
  three runtime identities and three services were created, and two leaf invoker grants applied.
- Remote dev state contains 24 managed resources and the operator plan reports zero drift.
- All three services are Ready, private, digest-pinned, scale-to-zero, and use distinct identities.
  User-managed keys, project roles for runtime identities, and public principals are all zero.

## Active blocker

- Both Cloud Run-provided URLs and the official authenticated Cloud Run proxy return Google
  frontend `404` before the request reaches a container. No Cloud Run request or structured
  application log is produced.
- The v2 service reports `defaultUriDisabled=false`, `INGRESS_TRAFFIC_ALL`, IAM enforcement active,
  and a Ready revision. Local health probes and Cloud Run startup/liveness probes pass.
- The symptoms match an inherited network or VPC Service Controls route restriction. The operator
  can detect the parent organization but cannot read its access-policy perimeter configuration.
- `TF_PLAN_ENABLED=false` remains set. `TF_M2_IMAGE_READY` and `GCP_DEMO_IMAGE_URI` remain absent,
  so hosted plan cannot run prematurely.

## Resume procedure

1. Have the organization administrator confirm whether the project or caller is inside a VPC
   Service Controls perimeter or another inherited Cloud Run ingress restriction.
2. Restore authenticated access without adding `allUsers` or broadening runtime IAM.
3. Repeat unauthenticated-denial and authenticated 10-order smoke checks.
4. Verify request/trace logs and request-count/latency metrics, then set the private image variable
   and hosted plan gates.
5. Run the manual read-only hosted zero-drift workflow and only then mark M2 complete.

Do not destroy or blindly reapply the deployed resources while this blocker is investigated.
