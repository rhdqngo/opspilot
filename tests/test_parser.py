from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from opspilot.catalog import load_service_catalog
from opspilot.domain import OutputLanguage
from opspilot.parser import MAX_QUERY_LENGTH, parse_investigation_request

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def test_parser_preserves_requested_output_language_for_the_executor() -> None:
    request = parse_investigation_request(
        "개발 결제 최근 15분 오류를 조사해줘",
        catalog=load_service_catalog(),
        output_language=OutputLanguage.KO,
        now=NOW,
    )

    assert request.output_language is OutputLanguage.KO


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


def test_parser_rejects_queries_above_the_bounded_intake_limit() -> None:
    with pytest.raises(ValueError, match="query exceeds"):
        parse_investigation_request(
            "x" * (MAX_QUERY_LENGTH + 1),
            catalog=load_service_catalog(),
            now=NOW,
        )


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


@pytest.mark.parametrize("alias", ["prod", "Production", "운영"])
def test_parser_rejects_real_production_without_coercing_to_prod_sim(alias: str) -> None:
    with pytest.raises(ValueError, match="real production is not supported"):
        parse_investigation_request(
            f"{alias} payment-service last 10 minutes errors",
            catalog=load_service_catalog(),
            now=NOW,
        )


@pytest.mark.parametrize(
    ("alias", "environment"),
    [
        ("stage", "staging"),
        ("staging", "staging"),
        ("qa", "staging"),
        ("스테이징", "staging"),
        ("prod-sim", "prod-sim"),
        ("demo", "prod-sim"),
        ("운영 모사", "prod-sim"),
        ("운영   모사", "prod-sim"),
    ],
)
def test_parser_supports_synthetic_environment_aliases(alias: str, environment: str) -> None:
    request = parse_investigation_request(
        f"{alias} payment-service last 10 minutes errors",
        catalog=load_service_catalog(),
        now=NOW,
    )

    assert request.environment.value == environment


def test_parser_does_not_treat_qa_email_local_part_as_staging() -> None:
    request = parse_investigation_request(
        "dev inventory-service last 15 minutes errors for qa@example.invalid token: synthetic",
        catalog=load_service_catalog(),
        now=NOW,
    )

    assert request.environment.value == "dev"
    assert request.services == ["inventory-service"]


@pytest.mark.parametrize(
    ("query", "services"),
    [
        ("개발 주문 최근 15분 오류", ["order-service"]),
        ("staging 결제와 재고 최근 30분 지연", ["inventory-service", "payment-service"]),
        (
            "prod-sim 전체 서비스 최근 1시간 가용성 심층 조사",
            ["inventory-service", "order-service", "payment-service"],
        ),
    ],
)
def test_parser_supports_service_aliases_and_multi_service_scope(
    query: str, services: list[str]
) -> None:
    request = parse_investigation_request(query, catalog=load_service_catalog(), now=NOW)
    assert request.services == services


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


def test_parser_supports_clock_and_iso_intervals_with_timezone_rules() -> None:
    clock = parse_investigation_request(
        "개발 payment-service 19:00부터 오류를 심층 조사해줘",
        catalog=load_service_catalog(),
        now=NOW,
    )
    assert clock.start_time.isoformat() == "2026-08-13T10:00:00+00:00"
    assert clock.end_time == NOW
    assert any("Asia/Seoul" in item for item in clock.assumptions)

    interval = parse_investigation_request(
        (
            "prod-sim order-service "
            "2026-08-13T10:00:00+09:00 2026-08-13T10:45:00+09:00 timeout QUICK"
        ),
        catalog=load_service_catalog(),
        now=NOW,
    )
    assert interval.end_time - interval.start_time == timedelta(minutes=45)
    assert interval.requested_depth.value == "QUICK"
    assert [item.value for item in interval.symptoms] == ["TIMEOUT"]


def test_parser_rejects_conflicting_environments_and_depths() -> None:
    with pytest.raises(ValueError, match="multiple environments"):
        parse_investigation_request(
            "dev staging payment-service last 15 minutes errors",
            catalog=load_service_catalog(),
            now=NOW,
        )
    with pytest.raises(ValueError, match="multiple investigation depths"):
        parse_investigation_request(
            "dev payment-service last 15 minutes QUICK DEEP errors",
            catalog=load_service_catalog(),
            now=NOW,
        )


def test_parser_extracts_one_focus_hypothesis_for_deep_follow_up() -> None:
    request = parse_investigation_request(
        "dev payment-service last 60 minutes H-02 deep investigation",
        catalog=load_service_catalog(),
        now=NOW,
    )
    assert request.focus_hypothesis_id == "H-02"

    with pytest.raises(ValueError, match="multiple hypothesis IDs"):
        parse_investigation_request(
            "dev payment-service last 60 minutes compare H-01 and H-02",
            catalog=load_service_catalog(),
            now=NOW,
        )
