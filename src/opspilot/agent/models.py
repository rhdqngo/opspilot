"""Model configuration and an offline deterministic ADK model for M6."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from opspilot.agent.contracts import (
    ComposeInput,
    HypothesisDraft,
    HypothesisDraftBatch,
    ModelEvidence,
    ReportNarrativeDraft,
)
from opspilot.domain import EvidenceDirection

DEFAULT_MODEL_ID = "gemini-3.5-flash"
MODEL_LOCATION = "global"
MAX_MODEL_INPUT_BYTES = 64 * 1024
MAX_MODEL_OUTPUT_TOKENS = 2_048
MODEL_CALL_LIMIT = 2
MODEL_NODE_TIMEOUT_SECONDS = 30.0
MODEL_DEADLINE_SECONDS = 75
M6_ACCEPTANCE_DEADLINE_SECONDS = 200


class FakeOpsPilotLlm(BaseLlm):
    """Return schema-valid fixture outputs without a network or fixture ground truth."""

    stage: str

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del stream
        payload = _request_payload(llm_request)
        response: HypothesisDraftBatch | ReportNarrativeDraft
        if self.stage == "rca":
            response = _fake_rca(payload)
        elif self.stage == "compose":
            response = _fake_compose(payload)
        else:
            raise ValueError("unsupported fake model stage")
        text = json.dumps(
            response.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        prompt_tokens = max(1, len(json.dumps(payload, ensure_ascii=False)) // 4)
        output_tokens = max(1, len(text) // 4)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            partial=False,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=prompt_tokens,
                candidates_token_count=output_tokens,
                total_token_count=prompt_tokens + output_tokens,
            ),
        )


def _request_payload(request: LlmRequest) -> dict[str, Any]:
    for content in reversed(request.contents):
        for part in reversed(content.parts or []):
            if part.text:
                parsed = json.loads(part.text)
                if not isinstance(parsed, dict):
                    raise ValueError("fake model input must be a JSON object")
                return parsed
    raise ValueError("fake model input is missing")


def _fake_rca(payload: dict[str, Any]) -> HypothesisDraftBatch:
    evidence = [ModelEvidence.model_validate(item) for item in payload.get("evidence", [])]
    supporting = [item for item in evidence if item.direction == EvidenceDirection.SUPPORTS.value]
    if not supporting:
        return HypothesisDraftBatch()
    combined = " ".join(f"{item.title} {item.summary}" for item in evidence).casefold()
    root_cause_code, claim, mechanism = _infer_cause(combined)
    services = sorted({item.service for item in evidence if item.service})[:3]
    return HypothesisDraftBatch(
        drafts=[
            HypothesisDraft(
                draft_id="D-01",
                root_cause_code=root_cause_code,
                claim=claim,
                mechanism=mechanism,
                affected_services=services,
                supporting_evidence_ids=[item.evidence_id for item in supporting],
                contradicting_evidence_ids=[
                    item.evidence_id
                    for item in evidence
                    if item.direction == EvidenceDirection.CONTRADICTS.value
                ],
                missing_evidence=list(payload.get("data_gaps", []))[:8],
                next_checks=["Confirm the leading hypothesis against an independent signal."],
            )
        ]
    )


def _infer_cause(combined: str) -> tuple[str, str, str]:
    if "untrusted instruction" in combined or "prompt injection" in combined:
        return (
            "RUNBOOK_PROMPT_INJECTION",
            "A runbook contains an untrusted prompt-injection instruction",
            "Retrieved operational text attempted to override policy but was isolated as evidence.",
        )
    if "429" in combined or "rate limit" in combined:
        return (
            "UPSTREAM_RATE_LIMIT",
            "Upstream requests were rate limited",
            "Provider rate limiting aligned with the observed request failures.",
        )
    if "instance cap" in combined or "capacity" in combined:
        return (
            "CLOUD_RUN_CAPACITY_LIMIT",
            "Cloud Run capacity limit delayed synthetic orders",
            "The request surge reached the bounded instance ceiling and increased latency.",
        )
    if "dns" in combined or "hostname" in combined:
        return (
            "INVENTORY_ENDPOINT_MISCONFIGURATION",
            "Inventory endpoint hostname was misconfigured",
            "A hostname change caused inventory DNS resolution failures.",
        )
    if "upstream" in combined or "provider" in combined:
        return (
            "PAYMENT_UPSTREAM_TIMEOUT",
            "External payment provider exceeded the dependency timeout",
            "Provider latency exceeded the bounded payment dependency timeout.",
        )
    return (
        "PAYMENT_DB_POOL_EXHAUSTION",
        "DB connection pool configuration was reduced",
        "Pool acquisition timeouts aligned with error and latency evidence after a "
        "configuration change.",
    )


def _fake_compose(payload: dict[str, Any]) -> ReportNarrativeDraft:
    compose = ComposeInput.model_validate(payload)
    if not compose.verified_hypotheses:
        return ReportNarrativeDraft(
            title="Inconclusive synthetic investigation",
            severity="UNCLASSIFIED",
            severity_rationale="The available evidence is insufficient to classify severity.",
            impact_summary="The impact cannot be established from the available evidence.",
            executive_summary="No root cause can be confirmed with the bounded evidence.",
        )
    top = compose.verified_hypotheses[0]
    safety_case = top.root_cause_code == "RUNBOOK_PROMPT_INJECTION"
    recommendations = []
    if not safety_case:
        recommendations = [
            {
                "category": "VERIFICATION",
                "title": "Review a bounded mitigation",
                "description": "Validate a human-approved mitigation against the cited evidence.",
                "target_service": top.affected_services[0] if top.affected_services else None,
                "risk_level": "HIGH",
                "expected_effect": (
                    "Reduce the synthetic incident signal without broadening access."
                ),
                "prerequisites": ["Obtain explicit operator approval."],
                "verification_steps": ["Recheck error ratio and latency after the change."],
                "supporting_evidence_ids": top.supporting_evidence_ids,
            }
        ]
    return ReportNarrativeDraft.model_validate(
        {
            "title": f"Evidence-grounded finding: {top.root_cause_code}",
            "severity": "SEV-3" if safety_case else "SEV-2",
            "severity_rationale": (
                "The classification is based only on verified synthetic evidence."
            ),
            "impact_summary": top.claim,
            "executive_summary": (
                f"The leading hypothesis is {top.claim}, with deterministic support "
                f"of {top.evidence_support_score}/100."
            ),
            "recommendations": recommendations,
        }
    )
