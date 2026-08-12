"""Stable Markdown rendering for incident reports."""

from __future__ import annotations

from opspilot.domain import IncidentReport, OutputLanguage

MARKDOWN_COPY = {
    OutputLanguage.EN: {
        "summary": "Summary",
        "timeline": "Timeline",
        "hypotheses": "Root-cause hypotheses",
        "actions": "Recommended actions",
        "data_gaps": "Data gaps",
        "sources": "Sources",
        "support": "support",
        "evidence": "evidence",
        "none_verified": "None verified with the available evidence.",
        "no_action": "No action is recommended with the available evidence.",
        "none_recorded": "None recorded.",
        "approval_required": "approval required",
        "read_only": "read-only",
    },
    OutputLanguage.KO: {
        "summary": "요약",
        "timeline": "타임라인",
        "hypotheses": "근본 원인 가설",
        "actions": "권장 조치",
        "data_gaps": "데이터 공백",
        "sources": "출처",
        "support": "지지도",
        "evidence": "증거",
        "none_verified": "사용 가능한 증거로 검증된 가설이 없습니다.",
        "no_action": "사용 가능한 증거로 권장할 조치가 없습니다.",
        "none_recorded": "기록된 항목이 없습니다.",
        "approval_required": "승인 필요",
        "read_only": "읽기 전용",
    },
}


def render_markdown(
    report: IncidentReport,
    *,
    language: OutputLanguage = OutputLanguage.EN,
) -> str:
    copy = MARKDOWN_COPY[language]
    lines = [
        f"# [{report.severity}] {report.title}",
        "",
        f"## {copy['summary']}",
        "",
        report.executive_summary,
        "",
        f"## {copy['timeline']}",
        "",
    ]
    for event in report.timeline:
        evidence = ", ".join(event.evidence_ids)
        lines.append(f"- {event.timestamp.isoformat()} - {event.title} ({evidence})")
    lines.extend(["", f"## {copy['hypotheses']}", ""])
    for hypothesis in report.hypotheses:
        evidence = ", ".join(hypothesis.supporting_evidence_ids)
        lines.append(
            f"- **{hypothesis.hypothesis_id} {hypothesis.claim}** "
            f"- {copy['support']} {hypothesis.evidence_support_score}/100; "
            f"{copy['evidence']}: {evidence}"
        )
    if not report.hypotheses:
        lines.append(f"- {copy['none_verified']}")
    lines.extend(["", f"## {copy['actions']}", ""])
    if report.recommended_actions:
        for action in report.recommended_actions:
            approval = copy["approval_required"] if action.requires_approval else copy["read_only"]
            lines.append(f"- **{action.title}** - {approval}; {action.description}")
    else:
        lines.append(f"- {copy['no_action']}")
    lines.extend(["", f"## {copy['data_gaps']}", ""])
    lines.extend(f"- {gap}" for gap in report.data_gaps)
    if not report.data_gaps:
        lines.append(f"- {copy['none_recorded']}")
    lines.extend(["", f"## {copy['sources']}", ""])
    lines.extend(f"- `{item.evidence_id}` - {item.title}" for item in report.evidence)
    return "\n".join(lines) + "\n"
