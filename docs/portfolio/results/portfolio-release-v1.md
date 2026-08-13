# OpsPilot Portfolio Release Evidence

- Status: **PASSED**
- Generated: `2026-08-13T06:26:05.183809+00:00`
- Source commit: `eaea85038f0bbfbf58e8d43b811567c2b5bf9612`
- Working tree dirty before validation: `False`
- Source tree SHA-256: `38e42efae7df3330119da99f6787b42d69633a1abf48fa5ff593088dcdc0a53a`

## Verified results

| Result | Value |
| --- | ---: |
| Pytest | 193/193 |
| Core evaluation | 7/7 |
| Portfolio evaluation | 40/40 |
| RCA top-1 / top-3 | 1.000 / 1.000 |
| Required-tool recall | 1.000 |
| Citation coverage | 1.000 |
| Evidence-ID validity | 1.000 |
| P50 / P95 fixture duration | 11 ms / 13 ms |
| Runtime package | 9 files / `b3c0c5559246d7ebd2db13b534459f4db7745315fbaaaf39919cc603ec132b12` |

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
