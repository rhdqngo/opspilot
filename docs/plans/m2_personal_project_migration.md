# M2 Personal Project Migration Plan

Status: separate approval required

## Objective

Recreate the existing private M2 workload in a personally controlled Google Cloud project after
the current project continued returning endpoint-level `404` responses following one controlled
three-revision refresh. The current project and its remote state remain intact until the new
project passes all acceptance checks.

## Approval boundaries

1. **Project and bootstrap approval**: select and verify a personal billing project, then create a
   separate protected state bucket, WIF provider, read-only CI identity, and bootstrap state.
2. **Dev foundation approval**: apply APIs, Artifact Registry, investigator identity, budget, and
   notification channel in the new project.
3. **M2 workload approval**: rebuild the clean `main` image, push it once, pin its digest, and apply
   the three runtime identities, three private services, and two order-to-leaf invoker grants.
4. **Cutover approval**: update private GitHub repository variables only after remote acceptance;
   do not delete or repoint the current project beforehand.
5. **Old-project cleanup approval**: review a separate destroy plan only after the new hosted plan
   is zero drift and all portfolio evidence has been retained without identifiers.

Each approval uses a fresh binary Terraform plan with exact address allowlists, zero unexpected
IAM broadening, zero public principals, and no resource replacement outside its stated stage.

## Migration sequence

- Re-run the redacted access gate for the personal account and project. Require active billing,
  KRW currency, required permissions, clean `main`, and a private origin.
- Keep actual account, project, billing, numeric repository, state, image, and service identifiers
  only in process environment, ignored run directories, protected state, and repository variables.
- Apply bootstrap locally, migrate bootstrap state, configure the new read-only WIF identity, and
  prove hosted static and read-only access before continuing.
- Apply the M1 dev foundation and migrate dev state. Require the existing KRW 50,000 budget,
  deletion protection, zero investigator roles/keys, and operator/hosted zero drift.
- Build and locally verify one Linux/amd64 non-root image from the selected clean commit. Push once
  to the new registry and use only the resolved digest.
- Apply the unchanged M2 service contract: three distinct runtime identities, three private Cloud
  Run services, scale-to-zero, bounded resources, health probes, and exactly two leaf invoker
  grants.
- Run `route-check`, authenticated health checks, bounded 10-order load, correlated Logging,
  request-count/latency Monitoring, runtime security checks, operator zero drift, and hosted
  redacted `No changes` validation.
- Switch GitHub variables to the new project only after every check passes. Keep rollback values
  outside tracked files and never upload binary plans.

## Acceptance and stop conditions

- New project: three unauthenticated `403`, three authenticated `200`, ten fulfilled orders,
  correlated logs across all services, request and latency points, and zero 5xx.
- Security: zero public principals, user-managed runtime keys, project runtime roles, credential
  files, and unapproved resources.
- Terraform: expected bootstrap and dev resource counts, no drift, no delete or replacement during
  migration, and redacted hosted output.
- Cost: KRW 50,000 alerts-only budget, min instances zero, max instances two, and no scheduled
  traffic.
- If project ownership, billing currency, permissions, exact plans, or private endpoint acceptance
  fails, stop before the corresponding apply and preserve both projects unchanged.

Completing this document does not authorize project creation, apply, variable cutover, or cleanup.
