# Formal Agent Rollout

Status: local candidate verified; deployment and managed QA pending

The formal Incident Commander rollout is split into four independently reviewed binary Terraform
plans. A plan may contain only the addresses owned by its phase. Every apply uses the already
reviewed binary plan; a newly generated plan is never substituted at apply time.

## Plan phases

1. `workloads`: create the staging and prod-sim order, payment, and inventory Cloud Run services,
   their workload identities, and only the order-to-payment/inventory invoker bindings.
2. `investigation`: update the investigation API image and model permission and create the
   `conversation_contexts.expires_at` TTL field.
3. `runtime`: update only the existing Agent Runtime source archive without replacing or renaming
   the Runtime resource.
4. `remediation`: move the fixed rollback target and invocation bindings to prod-sim payment and
   connect the investigation identity to the M8 control API. The three named IAM-member target
   replacements are the only reviewed delete/create actions.

The verifier accepts no empty phase, cross-phase address, unreviewed replacement, or public
invoker. The investigation and Runtime phases additionally bind the exact image digest and archive
SHA-256:

```powershell
uv run python scripts/formal_agent_release.py .tmp/formal/workloads.json --phase workloads
uv run python scripts/formal_agent_release.py .tmp/formal/investigation.json `
  --phase investigation --image-digest sha256:<reviewed-digest>
uv run python scripts/formal_agent_release.py .tmp/formal/runtime.json `
  --phase runtime --runtime-sha256 <reviewed-sha256>
uv run python scripts/formal_agent_release.py .tmp/formal/remediation.json --phase remediation
```

Before each apply, record the binary plan SHA-256 and re-run the matching verifier against
`terraform show -json` output. Stop on an unexpected add, update, replacement, delete, IAM member,
Runtime name, public invoker, source hash, or registration target.

After all four phases, require Ready checks for all nine synthetic workloads, private IAM checks,
direct Runtime conversation smoke, three-environment SCN-001 recovery, prod-sim M8
`WAITING_APPROVAL` without execution, Gemini Enterprise conversational QA, and a final plan with
the same inputs reporting `No changes`.
