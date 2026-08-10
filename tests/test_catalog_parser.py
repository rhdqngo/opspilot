from __future__ import annotations

from datetime import UTC, datetime

import pytest

from opspilot.catalog import load_service_catalog
from opspilot.parser import parse_investigation_request


def test_FR_001_extracts_allowlisted_service_and_symptom() -> None:
    catalog = load_service_catalog()
    request = parse_investigation_request(
        "payment-service 오류율을 분석해줘",
        catalog=catalog,
        now=datetime(2026, 8, 10, 4, 30, tzinfo=UTC),
    )
    assert request.services == ["payment-service"]
    assert [symptom.value for symptom in request.symptoms] == ["ERROR_RATE"]


def test_FR_002_applies_thirty_minute_default_and_records_assumption() -> None:
    catalog = load_service_catalog()
    request = parse_investigation_request(
        "payment-service 상태를 확인해줘",
        catalog=catalog,
        now=datetime(2026, 8, 10, 4, 30, tzinfo=UTC),
    )
    assert (request.end_time - request.start_time).total_seconds() == 1_800
    assert "previous 30 minutes" in request.assumptions[0]


def test_FR_003_rejects_unknown_service_before_tool_execution() -> None:
    catalog = load_service_catalog()
    with pytest.raises(ValueError, match="not allowlisted"):
        parse_investigation_request(
            "unknown-service 오류를 분석해줘",
            catalog=catalog,
            now=datetime(2026, 8, 10, 4, 30, tzinfo=UTC),
        )
