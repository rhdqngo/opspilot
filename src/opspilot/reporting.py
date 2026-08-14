"""Stable Markdown rendering for incident reports."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from opspilot.domain import IncidentReport, OutputLanguage, SourceType

MARKDOWN_COPY = {
    OutputLanguage.EN: {
        "summary": "Summary",
        "environment": "Environment",
        "window": "Requested window",
        "status": "Status",
        "impact": "Impact",
        "top_hypothesis": "Top hypothesis",
        "timeline": "Timeline",
        "hypotheses": "Root-cause hypotheses",
        "actions": "Recommended actions",
        "containment": "Immediate containment",
        "mitigation": "Bounded mitigation",
        "root_fix": "Root fix or prevention",
        "other_actions": "Other reviewed actions",
        "data_gaps": "Data gaps",
        "assumptions": "Assumptions",
        "sources": "Sources",
        "support": "support",
        "evidence": "evidence",
        "missing": "missing evidence",
        "next_check": "next check",
        "none_verified": "None verified with the available evidence.",
        "no_action": "No action is recommended with the available evidence.",
        "none_recorded": "None recorded.",
        "approval_required": "approval required",
        "read_only": "read-only",
        "no_hypothesis": "No verified hypothesis",
        "omitted_sources": "Additional evidence is summarized by type",
        "follow_up": "Ask a follow-up question to inspect omitted evidence.",
    },
    OutputLanguage.KO: {
        "summary": "요약",
        "environment": "환경",
        "window": "요청 시간 범위",
        "status": "상태",
        "impact": "영향",
        "top_hypothesis": "최상위 가설",
        "timeline": "타임라인",
        "hypotheses": "근본 원인 가설",
        "actions": "권장 조치",
        "containment": "즉시 조치",
        "mitigation": "완화 조치",
        "root_fix": "근본 개선",
        "other_actions": "기타 검토 조치",
        "data_gaps": "데이터 공백",
        "assumptions": "가정",
        "sources": "출처",
        "support": "지지도",
        "evidence": "증거",
        "missing": "부족한 증거",
        "next_check": "다음 확인",
        "none_verified": "사용 가능한 증거로 검증된 가설이 없습니다.",
        "no_action": "사용 가능한 증거로 권장할 조치가 없습니다.",
        "none_recorded": "기록된 항목이 없습니다.",
        "approval_required": "승인 필요",
        "read_only": "읽기 전용",
        "no_hypothesis": "검증된 가설 없음",
        "omitted_sources": "추가 증거 유형별 요약",
        "follow_up": "생략된 증거는 후속 질문으로 확인할 수 있습니다.",
    },
}


KOREAN_TEXT = {
    "Bounded Multi-Service Investigation": "제한된 다중 서비스 조사",
    "payment-service connection-pool constraint": "payment-service 연결 풀 제약",
    "payment-service payment failure increase": "payment-service 결제 실패 증가",
    (
        "Bounded evidence was collected from the requested allowlisted services. "
        "No model-only root cause is asserted by the production API executor."
    ): (
        "요청한 허용 서비스에서 제한된 증거를 수집했습니다. "
        "운영 API는 모델 추론만으로 근본 원인을 단정하지 않습니다."
    ),
    (
        "The leading hypothesis is a payment connection-pool acquisition constraint, "
        "supported by a direct log signature and a corresponding bounded metric series."
    ): (
        "가장 유력한 가설은 payment-service 연결 풀 획득 제약입니다. "
        "직접적인 로그 신호와 같은 구간의 제한된 메트릭이 이를 뒷받침합니다."
    ),
    "Payment connection-pool acquisition was constrained": (
        "payment-service 연결 풀 획득이 제한되었습니다"
    ),
    "DB connection pool configuration was reduced": ("DB 연결 풀 구성이 축소되었습니다"),
    (
        "A reduced connection pool saturated under payment traffic, causing acquisition "
        "timeouts and HTTP 5xx responses."
    ): (
        "축소된 연결 풀이 결제 트래픽에서 포화되어 연결 획득 timeout과 HTTP 5xx "
        "응답이 발생했습니다."
    ),
    "Confirm the current pool size and active connection count.": (
        "현재 연결 풀 크기와 활성 연결 수를 확인합니다."
    ),
    (
        "The leading hypothesis is DB connection pool configuration was reduced, supported by "
        "4 evidence items with an evidence support score of 100/100."
    ): (
        "가장 유력한 가설은 DB 연결 풀 구성 축소이며, 증거 4건과 100/100의 "
        "증거 지지도가 이를 뒷받침합니다."
    ),
    (
        "A direct pool-acquisition failure signature was observed in bounded payment logs "
        "while the corresponding error-ratio series was available for review."
    ): (
        "제한된 payment-service 로그에서 연결 풀 획득 실패 신호가 관측되었고, "
        "같은 구간의 오류 비율 메트릭도 확인할 수 있었습니다."
    ),
    "Confirm the current pool limit and active connection count.": (
        "현재 연결 풀 한도와 활성 연결 수를 확인합니다."
    ),
    "An external payment-provider timeout remains unverified": (
        "외부 결제 제공자 timeout 가능성은 확인되지 않았습니다"
    ),
    "The available evidence does not establish provider latency as the cause.": (
        "현재 증거만으로는 제공자 지연을 원인으로 확인할 수 없습니다."
    ),
    "Provider latency and timeout evidence is missing.": (
        "제공자 지연과 timeout 증거가 부족합니다."
    ),
    "Compare provider latency and timeout signatures for the same window.": (
        "같은 시간 범위의 제공자 지연과 timeout 신호를 비교합니다."
    ),
    "Contain the affected service scope": "영향받은 서비스 범위를 제한",
    (
        "Pause further changes to payment-service and preserve the cited evidence while "
        "the incident commander reviews impact."
    ): (
        "incident commander가 영향을 검토하는 동안 payment-service의 추가 변경을 "
        "중지하고 인용된 증거를 보존합니다."
    ),
    "Review a bounded mitigation": "제한된 완화 조치 검토",
    (
        "Prepare a human-approved mitigation for payment-service that addresses the verified "
        "cause without broadening resource scope."
    ): (
        "리소스 범위를 넓히지 않고 확인된 원인을 다루는 payment-service 완화 조치를 "
        "준비한 뒤 사람의 승인을 받습니다."
    ),
    "Correct the verified root condition": "확인된 근본 조건 개선",
    (
        "Review and correct the verified configuration or dependency condition for "
        "payment-service through the normal change process."
    ): (
        "정상 변경 절차를 통해 확인된 payment-service 구성 또는 의존성 조건을 검토하고 개선합니다."
    ),
    "No environment was specified; using dev.": ("환경이 지정되지 않아 DEV를 사용합니다."),
    "No explicit time range was parsed; using the previous 30 minutes.": (
        "명시적인 시간 범위가 없어 최근 30분을 사용합니다."
    ),
    "No service was specified; using the configured service allowlist.": (
        "서비스가 지정되지 않아 구성된 허용 서비스 목록을 사용합니다."
    ),
    "No meaningful incident impact was established.": "유의미한 장애 영향이 확인되지 않았습니다.",
    (
        "No meaningful incident evidence was found in the bounded window. "
        "Source delay and data gaps are listed below."
    ): (
        "제한된 시간 범위에서 유의미한 장애 근거가 확인되지 않았습니다. "
        "데이터 지연과 공백은 아래에 표시합니다."
    ),
    "Incident scope was derived from an allowlisted Monitoring alert.": (
        "허용된 Monitoring 알림에서 incident 범위를 가져왔습니다."
    ),
}


def _display_text(value: str, language: OutputLanguage) -> str:
    return localize_report_text(value, language)


def localize_report_text(value: str, language: OutputLanguage) -> str:
    """Localize stable server-owned report copy for full and concise renderers."""

    if language is OutputLanguage.KO:
        return KOREAN_TEXT.get(value, value)
    return value


def _display_title(report: IncidentReport, language: OutputLanguage) -> str:
    if language is OutputLanguage.EN:
        return report.title
    if len(report.affected_services) == 1:
        return f"{report.affected_services[0]} 장애 조사"
    if len(report.affected_services) > 1:
        return "다중 서비스 장애 조사"
    return _display_text(report.title, language)


def _display_time(value: datetime, language: OutputLanguage) -> str:
    if language is OutputLanguage.KO:
        return value.astimezone(ZoneInfo("Asia/Seoul")).isoformat() + " (KST)"
    return value.isoformat()


def _cited_evidence_ids(report: IncidentReport) -> list[str]:
    cited: list[str] = []
    for hypothesis in report.hypotheses:
        cited.extend(hypothesis.supporting_evidence_ids)
        cited.extend(hypothesis.contradicting_evidence_ids)
    for action in report.recommended_actions:
        cited.extend(action.supporting_evidence_ids)
    return list(dict.fromkeys(cited))


def render_markdown(
    report: IncidentReport,
    *,
    language: OutputLanguage = OutputLanguage.EN,
) -> str:
    copy = MARKDOWN_COPY[language]
    top_hypothesis = report.hypotheses[0].claim if report.hypotheses else copy["no_hypothesis"]
    if report.requested_start_time and report.requested_end_time:
        requested_window = (
            f"{_display_time(report.requested_start_time, language)} — "
            f"{_display_time(report.requested_end_time, language)}"
        )
    else:
        requested_window = copy["none_recorded"]
    lines = [
        f"# [{report.severity}] {_display_title(report, language)}",
        "",
        f"## {copy['summary']}",
        "",
        f"- **{copy['environment']}**: `{report.environment.value}`",
        f"- **{copy['window']}**: {requested_window}",
        f"- **{copy['status']}**: `{report.status.value}`",
        f"- **{copy['impact']}**: {_display_text(report.impact_summary, language)}",
        f"- **{copy['top_hypothesis']}**: {_display_text(top_hypothesis, language)}",
        "",
        _display_text(report.executive_summary, language),
        "",
        f"## {copy['timeline']}",
        "",
    ]
    bounded_timeline = [
        event
        for event in sorted(report.timeline, key=lambda item: item.timestamp)
        if (
            report.requested_start_time is None
            or report.requested_end_time is None
            or report.requested_start_time <= event.timestamp <= report.requested_end_time
        )
    ][:20]
    for event in bounded_timeline:
        evidence = ", ".join(event.evidence_ids)
        lines.append(f"- {_display_time(event.timestamp, language)} - {event.title} ({evidence})")
    if not bounded_timeline:
        lines.append(f"- {copy['none_recorded']}")
    lines.extend(["", f"## {copy['hypotheses']}", ""])
    for hypothesis in report.hypotheses:
        evidence = ", ".join(hypothesis.supporting_evidence_ids)
        hypothesis_line = (
            f"- **{hypothesis.hypothesis_id} {_display_text(hypothesis.claim, language)}** "
            f"- {copy['support']} {hypothesis.evidence_support_score}/100; "
            f"{copy['evidence']}: {evidence or copy['none_recorded']}"
        )
        if not hypothesis.supporting_evidence_ids:
            missing = (
                "; ".join(_display_text(item, language) for item in hypothesis.missing_evidence)
                or copy["none_recorded"]
            )
            next_check = (
                "; ".join(_display_text(item, language) for item in hypothesis.next_checks)
                or copy["none_recorded"]
            )
            hypothesis_line += f"; {copy['missing']}: {missing}; {copy['next_check']}: {next_check}"
        lines.append(hypothesis_line)
    if not report.hypotheses:
        lines.append(f"- {copy['none_verified']}")
    lines.extend(["", f"## {copy['actions']}", ""])
    if report.recommended_actions:
        groups = (
            ("containment", {"CONTAINMENT"}),
            ("mitigation", {"MITIGATION"}),
            ("root_fix", {"ROOT_FIX", "PREVENTION"}),
            (
                "other_actions",
                {
                    action.category
                    for action in report.recommended_actions
                    if action.category
                    not in {"CONTAINMENT", "MITIGATION", "ROOT_FIX", "PREVENTION"}
                },
            ),
        )
        for label, categories in groups:
            actions = [
                action for action in report.recommended_actions if action.category in categories
            ]
            if not actions:
                continue
            lines.extend([f"### {copy[label]}", ""])
            for action in actions:
                approval = (
                    copy["approval_required"] if action.requires_approval else copy["read_only"]
                )
                lines.append(
                    f"- **{_display_text(action.title, language)}** - {approval}; "
                    f"{_display_text(action.description, language)}"
                )
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    else:
        lines.append(f"- {copy['no_action']}")
    lines.extend(["", f"## {copy['data_gaps']}", ""])
    lines.extend(f"- {_display_text(gap, language)}" for gap in report.data_gaps)
    if not report.data_gaps:
        lines.append(f"- {copy['none_recorded']}")
    lines.extend(["", f"## {copy['assumptions']}", ""])
    lines.extend(f"- {_display_text(item, language)}" for item in report.assumptions)
    if not report.assumptions:
        lines.append(f"- {copy['none_recorded']}")
    lines.extend(["", f"## {copy['sources']}", ""])
    evidence_by_id = {item.evidence_id: item for item in report.evidence}
    cited_ids = _cited_evidence_ids(report)
    displayed_ids = cited_ids[:20]
    lines.extend(
        f"- `{evidence_id}` - {evidence_by_id[evidence_id].title}"
        for evidence_id in displayed_ids
        if evidence_id in evidence_by_id
    )
    uncited = [item for item in report.evidence if item.evidence_id not in displayed_ids]
    if uncited:
        counts = Counter(item.source_type for item in uncited)
        summary = ", ".join(
            f"{source_type.value}: {counts[source_type]}"
            for source_type in SourceType
            if counts[source_type]
        )
        lines.append(f"- {copy['omitted_sources']}: {summary}")
        lines.append(f"- {copy['follow_up']}")
    if not report.evidence:
        lines.append(f"- {copy['none_recorded']}")
    return "\n".join(lines) + "\n"
