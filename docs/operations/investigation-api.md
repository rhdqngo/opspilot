# Local Investigation API

Status: Lean MVP v1 fixture boundary

The local FastAPI surface is an integration/demo API, not the managed Runtime. It preserves the
existing `POST /api/v1/investigations` request fields but accepts only a query naming exactly
`payment-service` and either no incident ID or `INC-2026-0001`.

Accepted status records expose:

```json
{
  "execution_mode": "fixture",
  "scenario_id": "SCN-001"
}
```

An `order-service`, `inventory-service`, implicit all-service, unknown service, or different
incident request returns 422 before background work. The coordinator owns an internal
`InvestigationExecutor` protocol so another approved executor can be added later without changing
the HTTP contract. Reports and status remain process-local and are lost when the API restarts.
