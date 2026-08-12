# OpsPilot Portfolio Release Evidence

- Status: **PASSED**
- Generated: `2026-08-12T13:35:36.274483+00:00`
- Source commit: `c4e274b92b63be5dbfe19045b8cf8374639f6066`
- Working tree dirty before validation: `False`
- Source tree SHA-256: `1363ffb79d5da0f0a0f556c741f2965145b02f5611e832000272d52f06d5cdb0`

## Verified results

| Result | Value |
| --- | ---: |
| Pytest | 143/144 |
| Core evaluation | 7/7 |
| Portfolio evaluation | 40/40 |
| RCA top-1 / top-3 | 1.000 / 1.000 |
| Required-tool recall | 1.000 |
| Citation coverage | 1.000 |
| Evidence-ID validity | 1.000 |
| P50 / P95 fixture duration | 12 ms / 14 ms |
| Runtime package | 17 files / `a1eb4b5c548fb6f88396ca506c9e5f16512e093d21e80b23ee239cd87ebaa79b` |

## Checks

| Check | Status |
| --- | --- |
| git_diff_check | PASSED |
| ruff_format | PASSED |
| ruff_check | PASSED |
| mypy | PASSED |
| pytest | PASSED |
| core_evaluation | PASSED |
| portfolio_evaluation | PASSED |
| runtime_package_one | PASSED |
| runtime_package_two | PASSED |
| build | PASSED |
| terraform_format | PASSED |
| terraform_bootstrap_validate | PASSED |
| terraform_bootstrap_test | PASSED |
| terraform_dev_validate | PASSED |
| terraform_dev_test | PASSED |
| runtime_determinism | PASSED |

## Failures

- None.
