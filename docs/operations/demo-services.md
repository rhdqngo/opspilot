# M2 Synthetic Demo Services

Status: M2 complete; private remote workload validated

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
- all roles: `GET /health` and `GET /ready`

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
- A reviewed same-digest refresh updated only the three service revisions. All three became Ready
  with full traffic, but `/healthz` remained unavailable because it conflicts with a Cloud Run
  reserved path.
- The final recovery pushed one safe-path image and applied an exact three-service in-place plan:
  zero create/delete/replacement, 24 managed resources, and no IAM or identity change.
- All three `/health` and `/ready` endpoints return unauthenticated `403` and authenticated `200`.
  Remote load completed 10/10 orders, with ten request IDs and traces linked across all roles.
- Logging and Monitoring contain request, structured application, request-count, and latency
  evidence for all three services. Application/request 5xx and sensitive-log findings were zero.
- Operator and hosted WIF read-only plans are zero drift; the hosted artifact contained redacted
  `No changes` text and no binary plan.

## Confirmed root cause and recovery

- Cloud Run reserves some paths ending in `z` and recommends avoiding every such path. The retired
  `/healthz` request returned a Google frontend `404` before the request reached a container.
- The v2 service reports `defaultUriDisabled=false`, `INGRESS_TRAFFIC_ALL`, IAM enforcement active,
  and a Ready revision. Local health probes and Cloud Run startup/liveness probes pass.
- Authenticated `/health` reached FastAPI, proving that the URL, IAM, ingress, revision, and
  container route are functional. The replacement image exposes `/health` and `/ready` only.
- The private digest variable is configured. `TF_PLAN_ENABLED=true` and
  `TF_M2_IMAGE_READY=true` remain enabled for the manual read-only hosted plan only.
- The current Cloud Run inventory contains only the three managed M2 candidates. An earlier note
  about one non-candidate service was based on an incorrect local JSON-array count and is retired.

Run the repeatable redacted diagnostic without supplying a project identifier:

```powershell
uv run opspilot route-check --account-alias Edu_687 --format summary
```

The updated diagnostic calls `/health`. See `cloud-run-mvp-recovery.md` for the new-image rollout
and acceptance sequence.

## M3 completion

The seven offline scenario contracts and the bounded live SCN-001 contract are complete. The
reviewed M3 rollout pushed one immutable image and updated only the three existing services in
place. Three live runs each completed the fixed 5/10/5 profile and returned to a 5/5 recovery
baseline. Managed resources remain 24, private IAM and the two leaf invoker grants are unchanged,
and operator plus hosted plans are zero drift.

Scenario behavior remains request-scoped and inactive for normal traffic. Do not destroy, expose,
or broaden the deployed resources while planning M4.
