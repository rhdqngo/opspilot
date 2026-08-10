# M2 Synthetic Demo Services

Status: Approval 1 complete locally; image push and Cloud Run apply pending Approval 2

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

## Approval 2 hard gates

1. Revalidate clean `main`, account/billing, exact candidate names, empty target image path, and M2
   permissions without printing identifiers.
2. Review bootstrap plan: exactly one in-place update adding only `run.services.get`,
   `run.services.list`, and `run.services.getIamPolicy` to the CI custom role.
3. Rebuild `linux/amd64` from clean `main`, locally repeat the smoke test, authenticate Docker, push
   once to the existing repository, and resolve the registry digest without printing it.
4. Set private repository variable `GCP_DEMO_IMAGE_URI` to the digest URI and
   `TF_M2_IMAGE_READY=true`; never store either value in repository files or artifacts.
5. Review dev plan: exactly 10 creates, zero update/delete/replacement—two existing APIs entering
   state, three runtime identities, three Cloud Run services, and two order-to-leaf invoker grants.
6. Apply the two reviewed plans separately. Do not import, update, or change IAM on any existing
   non-candidate Cloud Run service.
7. Verify private invocation, request/trace propagation, Logging filters, Monitoring latency and
   status metrics, revision/image digest, service-account key absence, and hosted zero drift.

Only after all seven gates pass may the project move to `M2-complete / M3-ready-for-planning`.
