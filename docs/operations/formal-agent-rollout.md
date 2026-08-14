# Formal Agent Rollout

Status: all four phases deployed and managed/Preview QA verified

The formal Incident Commander rollout used four independently reviewed binary Terraform plans.
Each plan contained only the addresses owned by its phase, and every apply reused the reviewed
binary plan rather than generating a substitute. This runbook preserves that release contract for
future source-bound updates.

## Plan phases

1. `workloads`: create the staging and prod-sim order, payment, and inventory Cloud Run services,
   their workload identities, and only the order-to-payment/inventory invoker bindings.
2. `investigation`: add the model permission and create the
   `conversation_contexts.expires_at` TTL field before either caller is cut over.
3. `remediation`: atomically update the investigation API image and control bridge while moving
   the fixed rollback target and invocation bindings to prod-sim payment. Cloud Run makes the
   control URL a dependency of the investigation service, so splitting these changes would create
   a temporary cross-phase drift. The three named IAM-member target replacements are the only
   reviewed delete/create actions.
4. `runtime`: update only the existing Agent Runtime source archive without replacing or renaming
   the Runtime resource.

The verifier accepts no empty phase, cross-phase address, unreviewed replacement, or public
invoker. The remediation cutover and Runtime phases additionally bind the exact image digest and
archive SHA-256:

```powershell
uv run python scripts/formal_agent_release.py .tmp/formal/workloads.json --phase workloads
uv run python scripts/formal_agent_release.py .tmp/formal/investigation.json --phase investigation
uv run python scripts/formal_agent_release.py .tmp/formal/remediation.json `
  --phase remediation --image-digest sha256:<reviewed-digest>
uv run python scripts/formal_agent_release.py .tmp/formal/runtime.json `
  --phase runtime --runtime-sha256 <reviewed-sha256>
```

Before each apply, record the binary plan SHA-256 and re-run the matching verifier against
`terraform show -json` output. Stop on an unexpected add, update, replacement, delete, IAM member,
Runtime name, public invoker, source hash, or registration target.

The completed rollout passed Ready checks for all nine synthetic workloads, private IAM checks,
direct Runtime conversation smoke, three-environment SCN-001 recovery, prod-sim M8
`WAITING_APPROVAL` without execution, Gemini Enterprise conversational QA, and a final plan with
the same inputs reporting `No changes`. Future rollouts must retain the same gates.
