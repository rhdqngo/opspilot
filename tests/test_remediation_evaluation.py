from pathlib import Path

from opspilot.remediation.evaluation import (
    load_remediation_suite,
    run_remediation_evaluation,
)


def test_M8_remediation_suite_has_twelve_reviewed_safety_cases() -> None:
    suite = load_remediation_suite()
    assert suite.suite_version == "remediation-v1"
    assert len(suite.cases) == 12
    assert {case.condition.value for case in suite.cases} == {
        "approved_success",
        "rejected",
        "expired",
        "forged_hash",
        "stale_etag",
        "wrong_service",
        "tampered_revision",
        "idempotent_replay",
        "concurrent_approval",
        "executor_403",
        "response_loss",
        "verification_failed",
    }


def test_M8_remediation_suite_passes_and_detects_expectation_tampering(
    tmp_path: Path,
) -> None:
    result = run_remediation_evaluation()
    assert result.passed is True
    assert result.passed_cases == result.executed_cases == 12

    payload = (
        Path("scenarios/evaluation/remediation-v1.json").read_text(encoding="utf-8")
    ).replace('"expected_update_count":1', '"expected_update_count":0', 1)
    (tmp_path / "remediation-v1.json").write_text(payload, encoding="utf-8")
    tampered = run_remediation_evaluation(tmp_path)
    assert tampered.passed is False
    assert tampered.passed_cases == 11
