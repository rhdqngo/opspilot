# OpsPilot 3-5 Minute Demo

## Preparation

```powershell
uv sync --frozen --extra agent
docker build --platform linux/amd64 -t opspilot-demo:local .
```

For the timed path, prepare the image but let the demo runner own Compose startup and cleanup:

```powershell
uv run python scripts/portfolio_demo.py --dry-run
uv run python scripts/portfolio_demo.py
```

Use `--build-image` when an untimed cold build is acceptable. The runner rejects occupied demo
ports, waits for `http://127.0.0.1:8100/ready`, stops on the first failed phase, and always attempts
`docker compose down --remove-orphans` after touching the stack. Its privacy-safe step summary is
written to `.tmp/portfolio-demo/summary.json`.

## Recording sequence

1. **00:00-00:25 — Boundary:** show the README hero and explain synthetic data, the read-only
   investigation identity, and the isolated approval-gated rollback.
2. **00:25-00:50 — Healthy workload:** run the bounded ten-order smoke and show aggregate success.
3. **00:50-01:25 — Incident:** run SCN-001 and show its fixed 5 baseline / 10 incident / 5 recovery
   phases and automatic return to baseline.
4. **01:25-02:00 — Evidence:** run the evidence smoke and show LOG, METRIC, CHANGE, and KNOWLEDGE
   source status without cloud identifiers.
5. **02:00-02:40 — Investigation:** run the core agent report and point to evidence IDs, data gaps,
   deterministic support score, and approval-required recommendations.
6. **02:40-03:30 — Quality:** run `portfolio-v1`, show 40 case results and release-gate metrics.
7. **03:30-04:10 — Enterprise:** show the thin Runtime calling the persistent API for one of three
   services, then show an immutable report, replay-created v2, and deterministic comparison.
8. **04:10-04:40 — Safety and cost:** show the trust boundary, alert-without-remediation rule,
   scale-to-zero policy, budget, and non-executing cleanup plan.

## Commands

```powershell
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot demo load --orders 10 --concurrency 2 --auth local
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot scenario run --scenario SCN-001 --auth local --format summary
uv run opspilot evidence smoke --scenario SCN-001 --env dev --format summary
uv run --extra agent opspilot agent run --scenario SCN-001 --format markdown
uv run --extra agent opspilot agent eval --suite portfolio --format summary --output .tmp/evaluation
uv run opspilot cleanup plan --format summary
docker compose down --remove-orphans
```

The individual commands remain useful for narration, but `scripts/portfolio_demo.py` is the
reproducible execution contract.
