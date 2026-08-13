from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from opspilot.catalog import load_service_catalog
from opspilot.parser import parse_investigation_request

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def test_parser_recognizes_service_before_a_korean_particle() -> None:
    request = parse_investigation_request(
        "order-service, payment-service, inventory-service\uc758 last 15 minutes errors",
        catalog=load_service_catalog(),
        now=NOW,
    )

    assert request.services == ["inventory-service", "order-service", "payment-service"]
    assert request.end_time - request.start_time == timedelta(minutes=15)


@pytest.mark.parametrize(
    ("query", "services", "minutes"),
    [
        ("payment-service last 1 minute errors", ["payment-service"], 1),
        ("order-service 최근 45분 지연", ["order-service"], 45),
        ("inventory-service 지난 2시간 오류", ["inventory-service"], 120),
        (
            "최근 오류 조사",
            ["inventory-service", "order-service", "payment-service"],
            30,
        ),
    ],
)
def test_parser_supports_catalog_services_and_relative_windows(
    query: str, services: list[str], minutes: int
) -> None:
    request = parse_investigation_request(query, catalog=load_service_catalog(), now=NOW)
    assert request.services == services
    assert request.end_time - request.start_time == timedelta(minutes=minutes)
    if minutes == 30 and "service" not in query:
        assert len(request.assumptions) == 3


@pytest.mark.parametrize(
    "query",
    [
        "payment-service 최근 30분 last 1 hour 오류",
        "payment-service 최근 0분 오류",
        "payment-service last 121 minutes errors",
        "unknown-service 최근 30분 오류",
    ],
)
def test_parser_rejects_ambiguous_or_out_of_scope_input(query: str) -> None:
    with pytest.raises(ValueError):
        parse_investigation_request(query, catalog=load_service_catalog(), now=NOW)


def test_parser_records_action_requests_without_executing_them() -> None:
    request = parse_investigation_request(
        "payment-service 최근 30분 분석하고 롤백해줘",
        catalog=load_service_catalog(),
        now=NOW,
    )
    assert request.requested_actions == ["롤백"]


@pytest.mark.parametrize("alias", ["dev", "Development", "개발"])
def test_FR_001_normalizes_dev_environment_aliases(alias: str) -> None:
    request = parse_investigation_request(
        f"{alias} payment-service last 10 minutes errors",
        catalog=load_service_catalog(),
        now=NOW,
    )

    assert request.environment.value == "dev"
    assert all("No environment was specified" not in item for item in request.assumptions)


@pytest.mark.parametrize("alias", ["prod", "Production", "운영", "stage", "staging", "qa"])
def test_FR_001_rejects_explicit_out_of_scope_environments(alias: str) -> None:
    with pytest.raises(ValueError, match="outside the current DEV-only scope"):
        parse_investigation_request(
            f"{alias} payment-service last 10 minutes errors",
            catalog=load_service_catalog(),
            now=NOW,
        )


def test_FR_001_extracts_one_incident_and_rejects_conflicts() -> None:
    request = parse_investigation_request(
        "Investigate INC-2026-0001 payment-service errors",
        catalog=load_service_catalog(),
        now=NOW,
        incident_id="INC-2026-0001",
    )
    assert request.incident_id == "INC-2026-0001"

    with pytest.raises(ValueError, match="conflicts"):
        parse_investigation_request(
            "Investigate INC-2026-0001 payment-service errors",
            catalog=load_service_catalog(),
            now=NOW,
            incident_id="INC-2026-0002",
        )
    with pytest.raises(ValueError, match="multiple incident IDs"):
        parse_investigation_request(
            "Compare INC-2026-0001 and INC-2026-0002 payment-service errors",
            catalog=load_service_catalog(),
            now=NOW,
        )


def test_FR_001_records_default_dev_as_an_assumption() -> None:
    request = parse_investigation_request(
        "payment-service last 10 minutes errors",
        catalog=load_service_catalog(),
        now=NOW,
    )
    assert any("No environment was specified" in item for item in request.assumptions)
