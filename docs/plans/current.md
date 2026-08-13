# Current Project State

status: blocked
phase: pre-M9 MVP closure awaiting GitHub hosted runner availability
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

- Ruff format/check pass; strict mypy passes over 82 checked files; pytest passes 193/193; package
  build passes.
- Core 7/7, portfolio 40/40, remediation 12/12, knowledge validation/smoke, fixture evidence smoke,
  and non-executing cleanup plan pass.
- Two 9-file Runtime archives are byte-identical with SHA-256
  `b3c0c5559246d7ebd2db13b534459f4db7745315fbaaaf39919cc603ec132b12`; no fallback module is
  packaged.
- Terraform format/validate, bootstrap 1/1, and dev 8/8 pass.
- Clean-commit release gate and source-bound portfolio publication pass on implementation commit
  `eaea850`. The release context SHA-256 is
  `5552acb21131638ead5f5c79000a2b1931f3cb6adea37970f9bb2cf5652de42a`.
- Bootstrap updated one read-only CI role in place and returned `No changes`. Dev updated only the
  three application images and Runtime source archive in place (`0 create / 4 update / 0 destroy`),
  then returned `No changes`. All three Cloud Run services are Ready, public invoker is absent,
  and the live Runtime returned progress plus a persisted final report.
- Manual hosted runs `31675348391` (PR checks), `31675350779` (Terraform checks), and
  `31675352527` (Terraform plan) were dispatched against `eaea850`. GitHub assigned no runner and
  created zero steps because the account has a failed-payment or spending-limit condition. This is
  the only remaining validation blocker; repository code did not execute or fail in those jobs.
- Source-bound evidence is prepared for its final commit. Repository-local `.tmp`, `dist`,
  pytest/Ruff/mypy/Python caches, and both Terraform `.terraform` directories were removed after
  publication; `.venv`, tracked evidence, lockfiles, and remote state were preserved.
- After this evidence commit is pushed, the tree and `main == origin/main` are expected to be clean.
  After GitHub billing/limits are corrected, rerun the same three manual workflows; no source or
  cloud change is otherwise required.

## Deferred beyond MVP

No M9 feature is part of this checkpoint. UI/dashboard, BigQuery, feedback, managed sessions or
memory, Model Armor, generalized write actions, and multi-project operation remain deferred.

Historical checkpoints are archived in [mvp-history.md](mvp-history.md).
