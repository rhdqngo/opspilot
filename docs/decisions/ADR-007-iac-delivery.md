# ADR-007: Bootstrap Terraform state and GitHub WIF separately

Status: accepted
Date: 2026-08-10

## Decision

Use a local-state bootstrap stack to define the protected GCS backend, a numeric-ID-bound GitHub
OIDC provider, and a read-only CI plan identity. After an approved bootstrap apply, migrate that
stack to its own GCS prefix. Manage the dev foundation from a separate remote-state prefix.

Pull requests receive no Google Cloud credentials. A manual workflow may produce a live plan only
after bootstrap outputs have been stored as repository variables and `TF_PLAN_ENABLED` is set to
true. CI never receives an apply identity.

## Rationale

- Avoids long-lived service account keys.
- Keeps the state bootstrap dependency explicit instead of hiding it in `local-exec`.
- Restricts GitHub admission using immutable numeric owner and repository IDs.
- Keeps untrusted pull-request validation offline.
- Makes state, IAM, and billing mutations visible at separate approval gates.

## Consequences

- The first bootstrap plan and apply are local operator actions.
- Hosted live planning remains unavailable until bootstrap is applied.
- Plan jobs use state object read access and `-lock=false`; they cannot update state.
- Adding future managed services requires an explicit review of the CI custom read role.
