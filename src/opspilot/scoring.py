"""Deterministic evidence support scoring."""

from __future__ import annotations

from collections.abc import Iterable

from opspilot.domain import EvidenceItem, HypothesisStatus

SCORE_WEIGHTS: dict[str, int] = {
    "direct_error_signature_match": 25,
    "metric_log_agreement": 15,
    "change_temporal_proximity": 15,
    "config_or_digest_change_match": 10,
    "prior_rca_match": 10,
    "runbook_symptom_match": 8,
    "cross_service_causal_chain": 7,
    "reproduction_match": 10,
}


def calculate_evidence_support_score(
    evidence: Iterable[EvidenceItem], *, contradictions: int = 0, missing_required: int = 0
) -> int:
    flags = {flag for item in evidence for flag in item.quality_flags}
    score = sum(SCORE_WEIGHTS.get(flag, 0) for flag in flags)
    score -= contradictions * 12
    score -= missing_required * 8
    return max(0, min(score, 100))


def status_for_score(score: int, *, has_minimum_evidence: bool) -> HypothesisStatus:
    if not has_minimum_evidence or score < 25:
        return HypothesisStatus.INSUFFICIENT_EVIDENCE
    if score >= 80:
        return HypothesisStatus.STRONGLY_SUPPORTED
    if score >= 65:
        return HypothesisStatus.SUPPORTED
    if score >= 45:
        return HypothesisStatus.PLAUSIBLE
    return HypothesisStatus.WEAK
