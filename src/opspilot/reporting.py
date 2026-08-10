"""Stable Markdown rendering for incident reports."""

from __future__ import annotations

from opspilot.domain import IncidentReport


def render_markdown(report: IncidentReport) -> str:
    lines = [
        f"# [{report.severity}] {report.title}",
        "",
        "## Summary",
        "",
        report.executive_summary,
        "",
        "## Timeline",
        "",
    ]
    for event in report.timeline:
        evidence = ", ".join(event.evidence_ids)
        lines.append(f"- {event.timestamp.isoformat()} - {event.title} ({evidence})")
    lines.extend(["", "## Root-cause hypotheses", ""])
    for hypothesis in report.hypotheses:
        evidence = ", ".join(hypothesis.supporting_evidence_ids)
        lines.append(
            f"- **{hypothesis.hypothesis_id} {hypothesis.claim}** "
            f"- support {hypothesis.evidence_support_score}/100; evidence: {evidence}"
        )
    lines.extend(["", "## Recommended actions", ""])
    if report.recommended_actions:
        for action in report.recommended_actions:
            approval = "approval required" if action.requires_approval else "read-only"
            lines.append(f"- **{action.title}** - {approval}; {action.description}")
    else:
        lines.append("- No action is recommended with the available evidence.")
    lines.extend(["", "## Data gaps", ""])
    lines.extend(f"- {gap}" for gap in report.data_gaps)
    if not report.data_gaps:
        lines.append("- None recorded.")
    lines.extend(["", "## Sources", ""])
    lines.extend(f"- `{item.evidence_id}` - {item.title}" for item in report.evidence)
    return "\n".join(lines) + "\n"
