# Gemini Enterprise Preview QA Evidence

- Status: **BLOCKED**
- QA base commit: `6bed2afd312d57a6e929bc80746d994821fdf6e4`
- Deployed implementation commit: `e7ffe615f4dac011c1a54841187628412a8aba03`
- Preview queries executed: `true`
- Infrastructure changes: `none`

Cloud project, account, service URLs, identities, image digests, session IDs, and
trace/run/correlation/investigation IDs are omitted. Raw screenshots and the identifier map remain
under ignored `.tmp/enterprise-qa` only.

## Release and recovery gates

| Check | Result |
| --- | --- |
| Clean `main` matching `origin/main` | passed |
| Initial Terraform plan | `No changes` |
| Cloud Run and Runtime registration | ready and stable |
| SCN-008 fault and active Workflow | absent |
| SCN-001 baseline / incident / recovery | `5/5`, `4 fulfilled + 6 failed`, `5/5` |
| SCN-001 ground truth and recovery | passed |
| Post-QA healthy orders | `5/5` |
| Final Terraform plan | `No changes` |

## Preview results

| Case | Result | Observation |
| --- | --- | --- |
| Healthy one-minute query | failed | Preview showed one progress response and ended without the final report; the backend persisted an inconclusive report with no hypotheses or actions. |
| English SCN-001 | passed | One progress and one final report, H-01/H-02, four evidence types, three approval-required recommendation classes, and valid citations. |
| Korean with one unused incident ID | failed | Preview showed progress then the localized safe failure; the API returned 422 and created no investigation. |
| Environment omitted | failed | The persisted request contains the DEV assumption, but the Preview report does not render it. |
| Privacy redaction | passed | The accepted report omitted raw sentinels; Firestore stored both redaction markers and valid domain hashes, and app Runtime/tool logs contained no sentinel. |
| Unsupported environment, service, multiple IDs, restart, rollback | passed | All eight cases ended without progress, task, investigation, or report creation. |

An initial synthetic privacy token accidentally began with a standalone `qa_` token and correctly
hit the unsupported-QA environment guard. It was excluded from acceptance scoring and rerun with a
non-environment nonce.

## Managed cross-checks

Four accepted Preview investigations each produced one task attempt and report version. Runtime,
investigation, report, and tool events reused the same trace and correlation identity. Every accepted
investigation emitted four fixed-schema, privacy-safe logical tool events and all citations were
contained in the corresponding report evidence.

The tool events did not contain `run_id`. This violates the complete Runtime-to-tool execution
tracking contract even though their trace, correlation, investigation, and tool-call identifiers
were present.

## Blocking findings

1. A completed healthy investigation can terminate in Preview after progress without delivering its
   persisted final report.
2. A valid Korean request with one syntactically valid but not-yet-persisted incident ID is rejected
   end to end, despite the parser accepting the ID.
3. The default DEV assumption is persisted but not exposed in the Preview Markdown response.
4. Structured tool-call events omit the Runtime `run_id`.

FR-022 remains partial and the release is not marked Enterprise-QA verified. No source fix or
deployment was attempted during this QA run.
