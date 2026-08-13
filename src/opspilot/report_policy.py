"""Server-owned safe alternatives and advisory recommendation taxonomy."""

from __future__ import annotations

from dataclasses import dataclass

from opspilot.domain import (
    HypothesisStatus,
    RecommendedAction,
    RootCauseHypothesis,
)


@dataclass(frozen=True)
class AlternativePolicy:
    code: str
    claim: str
    mechanism: str
    missing_evidence: str
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
