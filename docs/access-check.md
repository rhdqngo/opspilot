# Cloud Access Check

Status: **complete**  
Checked: 2026-08-10

This document records booleans and aliases only. Do not add the real email address, project ID,
project number, OAuth client, token, or billing account identifier.

| Check | State | Evidence / next action |
| --- | --- | --- |
| Intended account alias | pass | Active gcloud account contains the user-provided `Edu_687` identifier |
| Default gcloud project | configured | Actual project identifier is intentionally not recorded here |
| User credential usable | pass | Interactive reauthentication completed; no token value was recorded |
| Application Default Credentials | pass | ADC login completed; no credential value was recorded |
| Project active | pass | Read-only project metadata reports an active project |
| Project ownership / intended use | pass | Current default project is the project previously selected by the operator |
| Billing enabled | pass | The project is linked to billing; no billing account identifier was recorded |
| Billing currency | pass | Operator-provided billing report displays costs in KRW; the image was not stored |
| Required API activation permission | pass | Read-only permission test includes API enablement |
| Project-scoped budget permission | pass | Read/write budget permissions exist for this single project |
| M1 apply permissions | pass | API, Artifact Registry, service-account, notification-channel, and project-budget writes were verified without identifiers |
| M2 deploy permissions | pass | Cloud Run create/update/read/IAM, invoke, actAs, image upload, and API enable permissions were verified without identifiers |
| M2 candidate names | pass | The three exact Terraform service names have zero conflicts; an unrelated existing service was not inspected or modified |
| Gemini Enterprise API access | pass | Global engine listing is permitted |
| Gemini Enterprise app | pass | An existing global app was detected without recording its identifier |
| Data policy | pass | Synthetic ecommerce data only |
| Monthly budget cap | applied | KRW 50,000 with 50/80/100% current-spend alerts |
| Cleanup owner | decided | Repository owner / `Edu_687` account operator |

## M0 exit commands

Run interactively outside automated logs:

```powershell
gcloud auth login
gcloud auth application-default login
```

Afterward, run redacted read-only checks for the active account, project metadata, billing state,
enabled APIs, and permissions. Stop before any cloud mutation if the project is not the intended
`Edu_687` project or billing is disabled.

```powershell
uv run opspilot access-check --confirm-project --confirm-billing-currency-krw
```

The confirmation flags assert facts checked by the operator in the signed-in console. They do not
accept or persist a project ID, billing account ID, currency value, or credential.

## M0 and M2 result

The redacted access command completed with `m0_ready=pass`. No API, IAM policy, budget, or other
Google Cloud resource was changed during the check.

The same read-only command completed with `m2_permissions_ready=pass`,
`m2_candidate_names_available=pass`, `m2_candidate_service_conflicts=0`, and
`m2_deploy_ready=pass`. These booleans authorize no deployment by themselves; Approval 2 remains
required.

## Location decisions

| Capability | Location | State |
| --- | --- | --- |
| Agent Runtime and regional workloads | `asia-northeast3` | decided |
| Agent Search and Gemini Enterprise app | `global` | verified path |
