"""Deterministic multi-turn routing for the bounded incident commander."""

from __future__ import annotations

import re
from collections.abc import Sequence

from opspilot.catalog import ServiceCatalog
from opspilot.domain import IncidentReport, OutputLanguage
from opspilot.reporting import localize_report_text
from opspilot.service import AgentTurnIntent, ConversationContext

_CAPABILITY = re.compile(
    r"\b(?:help|capabilit(?:y|ies)|what can you do|"
    r"what (?:services|environments|time ranges|actions).{0,120}\bsupport)\b|"
    r"기능|무엇을.*할 수|"
    r"지원(?:하(?:는|나요|는지)?|되(?:는|나요)?)?\s*(?:서비스|환경|시간|범위|작업)|"
    r"가능한\s*(?:작업|기능|조사)",
    re.I,
)
_COMPARE = re.compile(
    r"\b(?:compare|difference|diff|previous version)\b|비교|이전 (?:보고서|버전)",
    re.I,
)
_STATUS = re.compile(r"\b(?:status|state|progress)\b|상태|진행 상황", re.I)
_EXPLAIN = re.compile(
    r"\b(?:summari[sz]e|summary|explain|why|evidence|root cause)\b|요약|설명|왜|근거|원인",
    re.I,
)
_REFINE = re.compile(
    r"\b(?:expand|widen|deepen|refine|H-\d{2})\b|넓혀|확대|H-\d{2}",
    re.I,
)
_REMEDIATION = re.compile(
    r"\b(?:rollback|remediation request|request remediation)\b|롤백|복구 요청", re.I
)
_INCIDENT_ID = re.compile(r"\bINC-\d{4}-(?:\d{4}|[A-Fa-f0-9]{16})\b", re.I)
_ENVIRONMENT = re.compile(
    r"\b(?:dev(?:elopment)?|stage|staging|prod-sim|demo|prod(?:uction)?)\b|"
    r"\bqa\b(?!@)|개발|스테이징|운영(?:\s*모사)?",
    re.I,
)
_TIME = re.compile(
    r"(?:\b\d{1,3}\s*(?:minutes?|mins?|hours?|hrs?)\b|\d{1,3}\s*(?:분|시간)|\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}T)",
    re.I,
)
_DEPTH = re.compile(r"\b(?:quick|standard|deep)\b|간단|기본|심층", re.I)


def classify_turn(query: str) -> AgentTurnIntent:
    if _CAPABILITY.search(query):
        return AgentTurnIntent.SHOW_CAPABILITIES
    if _REMEDIATION.search(query):
        return AgentTurnIntent.CREATE_REMEDIATION_REQUEST
    if _COMPARE.search(query):
        return AgentTurnIntent.COMPARE_REPORT_VERSIONS
    if _STATUS.search(query) and not _TIME.search(query):
        return AgentTurnIntent.SHOW_STATUS
    if _REFINE.search(query):
        return AgentTurnIntent.REFINE_INVESTIGATION
    if _EXPLAIN.search(query) and not _TIME.search(query):
        return AgentTurnIntent.EXPLAIN_REPORT
    return AgentTurnIntent.INVESTIGATE


def contextualize_query(
    query: str,
    *,
    context: ConversationContext,
    catalog: ServiceCatalog,
) -> str:
    """Fill omitted follow-up scope with bounded structured context, never raw history."""

    parts = [query.strip()]
    if not _ENVIRONMENT.search(query):
        parts.append(context.environment.value)
    if not catalog.resolve_services(query):
        parts.extend(context.services)
    if not _TIME.search(query):
        parts.append(f"last {context.window_minutes} minutes")
    if not _DEPTH.search(query):
        parts.append(context.requested_depth.value)
    if not _INCIDENT_ID.search(query):
        parts.append(context.incident_id)
    return " ".join(parts)


def incident_id_from_query(query: str) -> str | None:
    values = incident_ids_from_query(query)
    return values[0] if values else None


def incident_ids_from_query(query: str) -> list[str]:
    return list(dict.fromkeys(value.upper() for value in _INCIDENT_ID.findall(query)))


def capabilities_markdown(language: OutputLanguage) -> str:
    if language is OutputLanguage.KO:
        return (
            "# OpsPilot 지원 범위\n\n"
            "- 서비스: `order-service`, `payment-service`, `inventory-service` 및 복수 서비스\n"
            "- 환경: `dev`, `staging`, `prod-sim`(합성 환경)\n"
            "- 시간: 최근 1~120분 또는 명시한 구간\n"
            "- 조사: 오류율, 지연, timeout, 가용성, 자원 고갈, 데이터 불일치\n"
            "- 후속 대화: 요약, 범위 확대, 가설 심층 조사, 보고서 버전 비교\n"
            "- 변경 요청: `prod-sim payment-service` rollback 승인 요청만 생성 가능\n\n"
            "실제 production 연결, 자동 승인·실행, 임의 프로젝트·URL·필터는 지원하지 않습니다.\n"
        )
    return (
        "# OpsPilot capabilities\n\n"
        "- Services: `order-service`, `payment-service`, `inventory-service`, "
        "including multi-service scope\n"
        "- Environments: `dev`, `staging`, and synthetic `prod-sim`\n"
        "- Time: recent 1-120 minutes or an explicit interval\n"
        "- Investigation: errors, latency, timeouts, availability, exhaustion, "
        "and data inconsistency\n"
        "- Follow-ups: summarize, widen scope, deepen a hypothesis, and compare report versions\n"
        "- Change request: create an approval request only for "
        "`prod-sim payment-service` rollback\n\n"
        "Real production, automatic approval or execution, and arbitrary projects, URLs, "
        "or filters are unsupported.\n"
    )


def rejection_markdown(code: str, language: OutputLanguage) -> str:
    messages = {
        "production_unsupported": (
            "실제 production 조사는 지원하지 않습니다. 합성 환경은 `prod-sim`으로 명시해 주세요.",
            "Real production is unsupported. Use the explicit synthetic `prod-sim` environment.",
        ),
        "unknown_service": (
            "알 수 없는 서비스입니다. 주문, 결제, 재고 서비스만 조사할 수 있습니다.",
            "The service is unknown. Only order, payment, and inventory services are supported.",
        ),
        "invalid_window": (
            "시간 범위가 충돌하거나 허용 범위인 1~120분을 벗어났습니다.",
            "The time range conflicts or is outside the allowed 1-120 minutes.",
        ),
        "multiple_incidents": (
            "한 번에 하나의 incident ID만 사용할 수 있습니다.",
            "Only one incident ID may be used per turn.",
        ),
        "missing_context": (
            "이 후속 질문을 연결할 대화 문맥이 없습니다. incident ID나 조사 범위를 명시해 주세요.",
            "No conversation context is available. Provide an incident ID or investigation scope.",
        ),
        "write_unsupported": (
            "이 쓰기 작업은 지원하지 않습니다. 조사와 복구 승인은 분리되어 있습니다.",
            "This write action is unsupported. Investigation and remediation approval "
            "are separated.",
        ),
        "m8_ineligible": (
            "M8 정책상 `prod-sim payment-service`의 적격한 rollback 승인 요청만 만들 수 있습니다.",
            "M8 only permits an eligible rollback approval request for `prod-sim payment-service`.",
        ),
        "invalid_request": (
            "요청 범위를 안전하게 해석할 수 없습니다. 서비스, 환경, 시간 범위를 명시해 주세요.",
            "The scope cannot be interpreted safely. Specify services, environment, "
            "and time range.",
        ),
    }
    korean, english = messages.get(code, messages["invalid_request"])
    return korean if language is OutputLanguage.KO else english


def classify_validation_error(message: str) -> str:
    lowered = message.lower()
    if "real production" in lowered:
        return "production_unsupported"
    if "multiple incident" in lowered or "conflicts with" in lowered:
        return "multiple_incidents"
    if "time" in lowered or "window" in lowered:
        return "invalid_window"
    if "service" in lowered:
        return "unknown_service"
    if "write" in lowered or "action" in lowered:
        return "write_unsupported"
    return "invalid_request"


def explain_report_markdown(
    report: IncidentReport,
    *,
    query: str,
    language: OutputLanguage,
) -> str:
    requested_hypothesis = re.search(r"\bH-\d{2}\b", query, re.I)
    hypotheses = report.hypotheses
    if requested_hypothesis:
        hypothesis_id = requested_hypothesis.group(0).upper()
        hypotheses = [item for item in hypotheses if item.hypothesis_id == hypothesis_id]
    impact = localize_report_text(report.impact_summary, language)
    if language is OutputLanguage.KO:
        lines = [
            f"# 보고서 {report.report_version} 요약",
            "",
            f"- 상태: `{report.status.value}`",
            f"- 사용자 영향: {impact}",
        ]
        if not hypotheses:
            conclusion = (
                f"요청한 {requested_hypothesis.group(0).upper()} 가설을 "
                "이 보고서에서 찾지 못했습니다."
                if requested_hypothesis
                else "검증된 근본 원인 가설이 없습니다."
            )
            lines.append(f"- 결론: {conclusion}")
        for item in hypotheses:
            citations = ", ".join(f"`{value}`" for value in item.supporting_evidence_ids) or "없음"
            lines.append(
                f"- 결론: **{item.hypothesis_id} {localize_report_text(item.claim, language)}** — "
                f"지지도 {item.evidence_support_score}/100; 근거 {citations}"
            )
        return "\n".join(lines) + "\n"
    lines = [
        f"# Report {report.report_version} summary",
        "",
        f"- Status: `{report.status.value}`",
        f"- User impact: {impact}",
    ]
    if not hypotheses:
        conclusion = (
            f"The requested {requested_hypothesis.group(0).upper()} hypothesis is not present."
            if requested_hypothesis
            else "No root-cause hypothesis is verified."
        )
        lines.append(f"- Conclusion: {conclusion}")
    for item in hypotheses:
        citations = ", ".join(f"`{value}`" for value in item.supporting_evidence_ids) or "none"
        lines.append(
            f"- Conclusion: **{item.hypothesis_id} {item.claim}** — "
            f"support {item.evidence_support_score}/100; evidence {citations}"
        )
    return "\n".join(lines) + "\n"


def compare_reports_markdown(reports: Sequence[IncidentReport], *, language: OutputLanguage) -> str:
    if len(reports) < 2:
        return (
            "비교할 이전 보고서가 없습니다. 먼저 동일 incident를 다시 조사해 주세요."
            if language is OutputLanguage.KO
            else "There is no previous report to compare. Re-run the same incident first."
        )
    before, after = reports[-2], reports[-1]
    before_top = before.hypotheses[0].hypothesis_id if before.hypotheses else "none"
    after_top = after.hypotheses[0].hypothesis_id if after.hypotheses else "none"
    before_evidence = {item.evidence_id for item in before.evidence}
    after_evidence = {item.evidence_id for item in after.evidence}
    added = sorted(after_evidence - before_evidence)
    removed = sorted(before_evidence - after_evidence)
    if language is OutputLanguage.KO:
        return (
            f"# 보고서 {before.report_version} → {after.report_version} 변경\n\n"
            f"- 상태: `{before.status.value}` → `{after.status.value}`\n"
            f"- 최상위 가설: `{before_top}` → `{after_top}`\n"
            f"- 추가 증거: {', '.join(added) or '없음'}\n"
            f"- 제외 증거: {', '.join(removed) or '없음'}\n"
        )
    return (
        f"# Report {before.report_version} → {after.report_version} changes\n\n"
        f"- Status: `{before.status.value}` → `{after.status.value}`\n"
        f"- Top hypothesis: `{before_top}` → `{after_top}`\n"
        f"- Evidence added: {', '.join(added) or 'none'}\n"
        f"- Evidence removed: {', '.join(removed) or 'none'}\n"
    )
