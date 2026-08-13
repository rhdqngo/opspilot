# Current Project State

status: in_progress
phase: pre-M9 MVP closure and repository cleanup
updated: 2026-08-13

## Completed product scope

- Three catalog services (`order-service`, `payment-service`, `inventory-service`) and Korean or
  English relative windows from 1 to 120 minutes; omission defaults to all services and 30 minutes.
- Private persistent investigation API with Cloud Tasks dedupe, Firestore incidents/investigations,
  immutable transactional report versions, JSON/Markdown reads, replay, deterministic comparison,
  and minimal Monitoring/Pub/Sub open/close intake.
- Gemini Enterprise Runtime as a thin authenticated API adapter. Runtime has no direct evidence,
  model, Search, reporting, scoring, or Firestore fallback.
- Fixture/evaluation seven-node graph, core 7/7, portfolio 40/40, evidence/knowledge smoke, SCN-001
  workload, and canonical REST/CLI surfaces.
- Isolated M8 approval-gated SCN-008 rollback, verified in dev through approval, 100% target
  traffic, recovery/reset 10/10, IAM negative checks, and Terraform `No changes`.

## Active closure scope

- Remove confirmed dead symbols, obsolete re-exports/tests, unnecessary `noqa`, and the historical
  Runtime fallback while preserving canonical and dynamic entrypoints.
- Use one hashed release context; retain delete/replace/scope/public-IAM/digest, approval/audit,
  binary-plan SHA, lease/idempotency, target/etag/revision/traffic, citation/redaction, timeout, and
  cost gates.
- Align README, architecture, runbooks, requirements, ADR-011, hosted CI readiness, and redaction.
- Validate from a clean implementation commit, publish source-bound evidence in a second commit,
  push `main`, and require manual PR checks, Terraform checks, and hosted redacted `No changes`.
- After evidence publication, delete only exact repository-local regenerable caches/artifacts:
  `.tmp`, `dist`, pytest/Ruff/mypy/Python caches, and both Terraform `.terraform` directories.
  Preserve `.venv`, tracked evidence, lockfiles, and remote state.

## Current validation

- Ruff format/check pass; strict mypy passes over 81 source files; pytest passes 193/193; package
  build passes.
- Core 7/7, portfolio 40/40, remediation 12/12, knowledge validation/smoke, fixture evidence smoke,
  and non-executing cleanup plan pass.
- Two 9-file Runtime archives are byte-identical with SHA-256
  `b3c0c5559246d7ebd2db13b534459f4db7745315fbaaaf39919cc603ec132b12`; no fallback module is
  packaged.
- Terraform format/validate, bootstrap 1/1, and dev 8/8 pass.
- Clean-commit release gate, cloud artifact alignment, hosted workflows, final cache cleanup, clean
  tree, and `main == origin/main` remain for this closure.

## Deferred beyond MVP

No M9 feature is part of this checkpoint. UI/dashboard, BigQuery, feedback, managed sessions or
memory, Model Armor, generalized write actions, and multi-project operation remain deferred.

Historical checkpoints are archived in [mvp-history.md](mvp-history.md).
