"""Server-owned safe alternatives and advisory recommendation taxonomy."""

from __future__ import annotations

from dataclasses import dataclass

from opspilot.domain import (
    EvidenceDirection,
    EvidenceItem,
    HypothesisStatus,
    IncidentReport,
    RecommendedAction,
    ReportStatus,
    RootCauseHypothesis,
    SourceType,
)

CANONICAL_ROOT_CAUSE_CODES = frozenset(
    {
        "PAYMENT_DB_POOL_EXHAUSTION",
        "PAYMENT_UPSTREAM_TIMEOUT",
        "INVENTORY_ENDPOINT_MISCONFIGURATION",
        "CLOUD_RUN_CAPACITY_LIMIT",
        "UPSTREAM_RATE_LIMIT",
        "RUNBOOK_PROMPT_INJECTION",
        "INSUFFICIENT_EVIDENCE",
    }
)


@dataclass(frozen=True)
class AlternativePolicy:
    code: str
    claim: str
    mechanism: str
    missing_evidence: str
    next_check: str


@dataclass(frozen=True)
class LiveCausePolicy:
    code: str
    service: str | None
    direct_terms: tuple[str, ...]
    knowledge_terms: tuple[str, ...]
    claim: str
    mechanism: str
    next_check: str


ALTERNATIVES: dict[str, AlternativePolicy] = {
    "PAYMENT_DB_POOL_EXHAUSTION": AlternativePolicy(
        code="PAYMENT_UPSTREAM_TIMEOUT",
        claim="An external payment-provider timeout remains unverified",
        mechanism="The available evidence does not establish provider latency as the cause.",
        missing_evidence="Provider latency and timeout evidence is missing.",
        next_check="Compare provider latency and timeout signatures for the same window.",
    ),
    "PAYMENT_UPSTREAM_TIMEOUT": AlternativePolicy(
        code="PAYMENT_DB_POOL_EXHAUSTION",
        claim="A payment database-pool constraint remains unverified",
        mechanism="The available evidence does not establish local pool saturation.",
        missing_evidence="Pool waiter and configuration-change evidence is missing.",
        next_check="Check pool waiters and revision configuration for the same window.",
    ),
    "INVENTORY_ENDPOINT_MISCONFIGURATION": AlternativePolicy(
        code="CLOUD_RUN_CAPACITY_LIMIT",
        claim="A capacity limit remains unverified",
        mechanism="The available evidence does not establish instance saturation.",
        missing_evidence="Instance and startup-latency evidence is missing.",
        next_check="Compare instance count and startup latency for the affected service.",
    ),
    "CLOUD_RUN_CAPACITY_LIMIT": AlternativePolicy(
        code="INVENTORY_ENDPOINT_MISCONFIGURATION",
        claim="A dependency endpoint misconfiguration remains unverified",
        mechanism="The available evidence does not establish an endpoint change.",
        missing_evidence="DNS and endpoint-change evidence is missing.",
        next_check="Review bounded revision metadata and DNS error signatures.",
    ),
    "UPSTREAM_RATE_LIMIT": AlternativePolicy(
        code="CLOUD_RUN_CAPACITY_LIMIT",
        claim="A local capacity limit remains unverified",
        mechanism="The available evidence does not establish local saturation.",
        missing_evidence="Instance and queue-pressure evidence is missing.",
        next_check="Compare local capacity signals with upstream 429 events.",
    ),
}


LIVE_CAUSES = (
    LiveCausePolicy(
        code="RUNBOOK_PROMPT_INJECTION",
        service=None,
        direct_terms=("prompt injection", "untrusted instruction"),
        knowledge_terms=("prompt injection", "untrusted instruction"),
        claim="Retrieved operational guidance contained an untrusted instruction",
        mechanism="A bounded knowledge result attempted to override the investigation policy.",
        next_check="Quarantine the source document and review its provenance.",
    ),
    LiveCausePolicy(
        code="PAYMENT_DB_POOL_EXHAUSTION",
        service="payment-service",
        direct_terms=("pool acquisition", "connection pool", "db_pool"),
        knowledge_terms=("connection pool", "pool exhaustion", "pool configuration"),
        claim="Payment connection-pool acquisition was constrained",
        mechanism=(
            "A direct pool-acquisition failure signature aligned with a bounded payment metric."
        ),
        next_check="Confirm the current pool limit and active connection count.",
    ),
    LiveCausePolicy(
        code="PAYMENT_UPSTREAM_TIMEOUT",
        service="payment-service",
        direct_terms=("provider timeout", "upstream timeout", "dependency timeout"),
        knowledge_terms=("provider timeout", "dependency timeout", "provider latency"),
        claim="The payment provider exceeded the bounded dependency timeout",
        mechanism="Direct timeout signatures aligned with a bounded payment metric.",
        next_check="Compare provider latency and timeout signatures for the same window.",
    ),
    LiveCausePolicy(
        code="INVENTORY_ENDPOINT_MISCONFIGURATION",
        service="inventory-service",
        direct_terms=("dns", "hostname", "endpoint misconfig"),
        knowledge_terms=("dns", "hostname", "endpoint"),
        claim="The inventory dependency endpoint was misconfigured",
        mechanism="Direct endpoint-resolution signatures aligned with a bounded inventory metric.",
        next_check="Review bounded endpoint configuration and DNS signatures.",
    ),
    LiveCausePolicy(
        code="UPSTREAM_RATE_LIMIT",
        service=None,
        direct_terms=("rate limit", "rate-limit", " 429", "http 429"),
        knowledge_terms=("rate limit", "quota", "429"),
        claim="Upstream requests were rate limited",
        mechanism="Direct rate-limit signatures aligned with a bounded service metric.",
        next_check="Compare upstream quota and retry signals for the same window.",
    ),
    LiveCausePolicy(
        code="CLOUD_RUN_CAPACITY_LIMIT",
        service=None,
        direct_terms=("instance cap", "capacity limit", "max instance", "startup latency"),
        knowledge_terms=("instance cap", "capacity", "startup latency"),
        claim="Cloud Run capacity constrained request handling",
        mechanism="Direct capacity signatures aligned with a bounded service metric.",
        next_check="Compare instance count, concurrency, and startup latency.",
    ),
)


def add_unverified_alternative(
    hypotheses: list[RootCauseHypothesis], *, primary_code: str
) -> list[RootCauseHypothesis]:
    """Add one non-assertive server-owned alternative without model speculation."""

    if len(hypotheses) != 1 or primary_code == "RUNBOOK_PROMPT_INJECTION":
        return hypotheses
    policy = ALTERNATIVES.get(primary_code)
    if policy is None:
        return hypotheses
    primary = hypotheses[0]
    return [
        primary,
        RootCauseHypothesis(
            hypothesis_id="H-02",
            rank=2,
            claim=policy.claim,
            mechanism=policy.mechanism,
            affected_services=primary.affected_services,
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[],
            missing_evidence=[policy.missing_evidence],
            next_checks=[policy.next_check],
            evidence_support_score=0,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE,
        ),
    ]


def policy_actions(
    *,
    primary_code: str,
    target_service: str | None,
    supporting_evidence_ids: list[str],
) -> list[RecommendedAction]:
    """Return three bounded advisory categories for a verified operational cause."""

    if primary_code not in ALTERNATIVES or not supporting_evidence_ids:
        return []
    service_text = target_service or "the affected service"
    shared = {
        "target_service": target_service,
        "risk_level": "HIGH",
        "requires_approval": True,
        "supporting_evidence_ids": supporting_evidence_ids,
    }
    return [
        RecommendedAction(
            action_id="ACT-01",
            category="CONTAINMENT",
            title="Contain the affected service scope",
            description=(
                f"Pause further changes to {service_text} and preserve the cited evidence while "
                "the incident commander reviews impact."
            ),
            prerequisites=["Confirm the affected service and incident window."],
            expected_effect="Prevent unrelated changes from obscuring the active incident.",
            rollback_method="Resume the normal change process after the incident is stable.",
            verification_steps=["Confirm no additional revision change occurred."],
            **shared,
        ),
        RecommendedAction(
            action_id="ACT-02",
            category="MITIGATION",
            title="Review a bounded mitigation",
            description=(
                f"Prepare a human-approved mitigation for {service_text} that addresses the "
                "verified cause without broadening resource scope."
            ),
            prerequisites=["Obtain explicit operator approval for the immutable plan."],
            expected_effect="Reduce the verified synthetic incident signal.",
            rollback_method="Restore the pre-mitigation state if verification regresses.",
            verification_steps=["Recheck error ratio and latency after the change."],
            **shared,
        ),
        RecommendedAction(
            action_id="ACT-03",
            category="ROOT_FIX",
            title="Correct the verified root condition",
            description=(
                f"Review and correct the verified configuration or dependency condition for "
                f"{service_text} through the normal change process."
            ),
            prerequisites=["Record the validated cause and a reviewed rollback method."],
            expected_effect="Reduce recurrence of the same verified failure mode.",
            rollback_method="Revert the reviewed root-fix change if service health regresses.",
            verification_steps=["Replay the bounded scenario and compare the same evidence set."],
            **shared,
        ),
    ]


def _contains_any(item: EvidenceItem, terms: tuple[str, ...]) -> bool:
    combined = f"{item.title} {item.summary}".casefold()
    return any(term in combined for term in terms)


def _live_cause_matches(
    evidence: list[EvidenceItem], policy: LiveCausePolicy
) -> tuple[str | None, list[EvidenceItem]]:
    logs = [
        item
        for item in evidence
        if item.source_type is SourceType.LOG
        and (policy.service is None or item.service == policy.service)
        and _contains_any(item, policy.direct_terms)
    ]
    knowledge = [
        item
        for item in evidence
        if item.source_type is SourceType.KNOWLEDGE
        and (policy.service is None or item.service in {None, policy.service})
        and _contains_any(item, policy.knowledge_terms)
    ]
    if policy.code == "RUNBOOK_PROMPT_INJECTION":
        unsafe = [
            item
            for item in knowledge
            if _contains_any(item, policy.direct_terms)
            or any("prompt" in flag.casefold() for flag in item.quality_flags)
        ]
        return (unsafe[0].service if unsafe else None), unsafe[:1]
    if not logs:
        return None, []
    service = policy.service or logs[0].service
    if service is None:
        return None, []
    metrics = [
        item
        for item in evidence
        if item.source_type is SourceType.METRIC
        and item.service == service
        and "missing_points" not in item.quality_flags
    ]
    if not metrics:
        return None, []
    changes = [
        item
        for item in evidence
        if item.source_type is SourceType.CHANGE
        and item.service == service
        and item.direction is EvidenceDirection.SUPPORTS
    ]
    service_knowledge = [item for item in knowledge if item.service in {None, service}]
    return service, [*logs[:1], *metrics[:1], *service_knowledge[:1], *changes[:1]]


def apply_live_report_policy(report: IncidentReport) -> IncidentReport:
    """Recover canonical live causes from direct signals when model verification is inconclusive."""

    if report.status is not ReportStatus.INCONCLUSIVE or report.hypotheses:
        return report
    matches: list[tuple[LiveCausePolicy, str | None, list[EvidenceItem]]] = []
    for policy in LIVE_CAUSES:
        service, supporting = _live_cause_matches(report.evidence, policy)
        if supporting:
            matches.append((policy, service, supporting))
    if not matches:
        return report
    hypotheses = [
        RootCauseHypothesis(
            hypothesis_id=f"H-{index:02d}",
            rank=index,
            claim=policy.claim,
            mechanism=policy.mechanism,
            affected_services=[service] if service else [],
            supporting_evidence_ids=[item.evidence_id for item in supporting],
            contradicting_evidence_ids=[],
            missing_evidence=[],
            next_checks=[policy.next_check],
            evidence_support_score=60,
            status=HypothesisStatus.PLAUSIBLE,
        )
        for index, (policy, service, supporting) in enumerate(matches[:3], start=1)
    ]
    primary_policy, primary_service, primary_supporting = matches[0]
    primary_code = primary_policy.code
    if len(hypotheses) == 1:
        hypotheses = add_unverified_alternative(hypotheses, primary_code=primary_code)
    supporting_ids = [item.evidence_id for item in primary_supporting]
    actions = policy_actions(
        primary_code=primary_code,
        target_service=primary_service,
        supporting_evidence_ids=supporting_ids,
    )
    return report.model_copy(
        update={
            "title": f"Evidence-grounded finding: {primary_code}",
            "severity": "SEV-3" if primary_code == "RUNBOOK_PROMPT_INJECTION" else "SEV-2",
            "severity_rationale": (
                "A direct canonical signal and bounded corroborating evidence are present."
            ),
            "status": ReportStatus.IDENTIFIED,
            "impact_summary": primary_policy.claim,
            "executive_summary": (
                f"The leading hypothesis is {primary_policy.claim.casefold()}, supported by "
                "server-verified direct evidence from the requested window."
            ),
            "affected_services": sorted(
                {service for _, service, _ in matches[:3] if service is not None}
            ),
            "hypotheses": hypotheses,
            "recommended_actions": actions,
            "audit": {
                **report.audit,
                "root_cause_code": primary_code,
                "root_cause_codes": [policy.code for policy, _, _ in matches[:3]],
                "citation_coverage": 1.0,
                "deterministic_live_fallback": True,
            },
        },
        deep=True,
    )


def add_prod_sim_rollback_request(report: IncidentReport) -> IncidentReport:
    """Expose one approval request only when a prod-sim payment report proves a change."""

    if (
        report.environment.value != "prod-sim"
        or report.affected_services != ["payment-service"]
        or report.status is not ReportStatus.IDENTIFIED
        or not report.hypotheses
    ):
        return report
    evidence = {item.evidence_id: item for item in report.evidence}
    top = sorted(report.hypotheses, key=lambda item: (item.rank, item.hypothesis_id))[0]
    revision_ids = [
        evidence_id
        for evidence_id in top.supporting_evidence_ids
        if evidence_id in evidence
        and evidence[evidence_id].source_type is SourceType.CHANGE
        and evidence[evidence_id].direction.value == "SUPPORTS"
        and evidence[evidence_id].service == "payment-service"
    ]
    if not revision_ids:
        return report
    action_number = len(report.recommended_actions) + 1
    rollback = RecommendedAction(
        action_id=f"ACT-{action_number:02d}",
        category="ROLLBACK_CLOUD_RUN",
        title="Request approval for a bounded prod-sim rollback",
        description=(
            "Create an immutable approval request for the trusted previous prod-sim payment "
            "revision. This report does not approve or execute the rollback."
        ),
        target_service="payment-service",
        risk_level="HIGH",
        requires_approval=True,
        prerequisites=[
            "Confirm the latest identified report and trusted previous revision metadata."
        ],
        expected_effect="Restore the last trusted synthetic payment revision after approval.",
        rollback_method="Use the separate M8 control plane to reject or stop before execution.",
        verification_steps=["Verify 10/10 synthetic orders and compare bounded metrics."],
        supporting_evidence_ids=revision_ids[:1],
        remediation_action_type="ROLLBACK_CLOUD_RUN",
    )
    return report.model_copy(
        update={"recommended_actions": [*report.recommended_actions, rollback]}, deep=True
    )
