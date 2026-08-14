"""Typed contracts passed through the M6 ADK graph."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from opspilot.audit import new_trace_id
from opspilot.domain import (
    INCIDENT_ID_PATTERN,
    EvidenceItem,
    IncidentReport,
    OutputLanguage,
    ReportStatus,
    SourceType,
    ToolError,
)


class AgentBackend(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"


class ModelBackend(StrEnum):
    FAKE = "fake"
    VERTEX = "vertex"


class AgentRunStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class AgentErrorCategory(StrEnum):
    VALIDATION = "validation"
    AUTH = "auth"
    TIMEOUT = "timeout"
    MODEL = "model"
    INTERNAL = "internal"


class AgentRunError(BaseModel):
    code: str
    category: AgentErrorCategory
    safe_message: str
    retryable: bool = False


class AgentEvidenceContext(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    generated_at: datetime
    correlation_id: str
    trace_id: str = Field(default_factory=new_trace_id, pattern=r"^[0-9a-f]{32}$")
    output_language: OutputLanguage = OutputLanguage.EN
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_errors: list[ToolError] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("agent evidence IDs must be unique")
        return self


class ModelEvidence(BaseModel):
    evidence_id: str = Field(pattern=r"^EV-(LOG|MET|CHG|KNW|INC|ACT)-\d{4}$")
    source_type: str
    title: str
    service: str | None = None
    observed_at: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    summary: str
    value: float | str | None = None
    unit: str | None = None
    direction: str
    source_uri: str
    quality_flags: list[str] = Field(default_factory=list)


class RcaInput(BaseModel):
    scenario_id: str
    output_language: OutputLanguage = OutputLanguage.EN
    evidence: list[ModelEvidence] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class HypothesisDraft(BaseModel):
    draft_id: str = Field(pattern=r"^D-\d{2}$")
    root_cause_code: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    claim: str = Field(min_length=3, max_length=500)
    mechanism: str = Field(min_length=3, max_length=1_000)
    affected_services: list[str] = Field(default_factory=list, max_length=3)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list, max_length=8)
    next_checks: list[str] = Field(default_factory=list, max_length=8)


class HypothesisDraftBatch(BaseModel):
    drafts: list[HypothesisDraft] = Field(default_factory=list, max_length=3)


class ReviewInput(BaseModel):
    evidence: list[ModelEvidence] = Field(default_factory=list)
    drafts: list[HypothesisDraft] = Field(default_factory=list, max_length=3)
    data_gaps: list[str] = Field(default_factory=list)


class HypothesisReview(BaseModel):
    draft_id: str = Field(pattern=r"^D-\d{2}$")
    decision: Literal["ACCEPT", "REJECT", "INSUFFICIENT"]
    rationale: str = Field(min_length=3, max_length=500)
    unsupported_evidence_ids: list[str] = Field(default_factory=list)


class HypothesisReviewBatch(BaseModel):
    reviews: list[HypothesisReview] = Field(default_factory=list, max_length=3)


class VerifiedHypothesis(BaseModel):
    root_cause_code: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    claim: str
    mechanism: str
    affected_services: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    evidence_support_score: int = Field(ge=0, le=100)
    source_type_count: int = Field(ge=0)


class RootCauseResolution(BaseModel):
    model_root_cause_code: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    canonical_root_cause_code: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    root_cause_normalized: bool = False


class ComposeInput(BaseModel):
    scenario_id: str
    evidence: list[ModelEvidence] = Field(default_factory=list)
    verified_hypotheses: list[VerifiedHypothesis] = Field(default_factory=list, max_length=3)
    data_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class RecommendationDraft(BaseModel):
    category: Literal["CONTAINMENT", "MITIGATION", "ROOT_FIX", "PREVENTION", "VERIFICATION"]
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=1_000)
    target_service: str | None = None
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
    expected_effect: str = Field(min_length=3, max_length=500)
    prerequisites: list[str] = Field(default_factory=list, max_length=8)
    rollback_method: str | None = Field(default=None, max_length=500)
    verification_steps: list[str] = Field(default_factory=list, max_length=8)
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class ReportNarrativeDraft(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    severity: Literal["SEV-2", "SEV-3", "UNCLASSIFIED"]
    severity_rationale: str = Field(min_length=3, max_length=500)
    impact_summary: str = Field(min_length=3, max_length=1_000)
    executive_summary: str = Field(min_length=3, max_length=1_500)
    recommendations: list[RecommendationDraft] = Field(default_factory=list, max_length=3)


class ModelBudgetUsage(BaseModel):
    model_calls: int = Field(default=0, ge=0, le=2)
    attempted_model_calls: int = Field(default=0, ge=0, le=2)
    successful_model_calls: int = Field(default=0, ge=0, le=2)
    prompt_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    input_bytes: int = Field(default=0, ge=0, le=64 * 1024)
    request_input_bytes: int = Field(default=0, ge=0, le=2 * 64 * 1024)
    max_request_input_bytes: int = Field(default=0, ge=0, le=64 * 1024)
    truncated: bool = False
    deadline_seconds: int = 75


class AgentRunResult(BaseModel):
    status: AgentRunStatus
    succeeded: bool
    backend: AgentBackend
    model_backend: ModelBackend
    report: IncidentReport | None = None
    trajectory: list[str] = Field(default_factory=list)
    budget: ModelBudgetUsage = Field(default_factory=ModelBudgetUsage)
    errors: list[AgentRunError] = Field(default_factory=list)
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{16}$")
    trace_id: str = Field(default_factory=new_trace_id, pattern=r"^[0-9a-f]{32}$")
    duration_ms: int = Field(default=0, ge=0)
    collection_trajectory: list[str] = Field(default_factory=list)
    source_status: dict[str, bool] = Field(default_factory=dict)
    source_error_codes: dict[str, str] = Field(default_factory=dict)
    reasoning_outcome: Literal["complete", "partial", "failed"] = "complete"

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.succeeded and self.report is None:
            raise ValueError("successful agent result requires a report")
        if not self.succeeded and not self.errors:
            raise ValueError("failed agent result requires a safe error")
        return self


class EvaluationCategory(StrEnum):
    SINGLE_CAUSE = "single_cause"
    MULTI_CAUSE = "multi_cause"
    NO_INCIDENT = "no_incident"
    INSUFFICIENT_DATA = "insufficient_data"
    PROMPT_INJECTION = "prompt_injection"
    DEPENDENCY_FAILURE = "dependency_failure"
    REPLAY_ACTION_SAFETY = "replay_action_safety"


class EvaluationCase(BaseModel):
    case_id: str = Field(pattern=r"^EVAL-[A-Z0-9-]+$")
    category: EvaluationCategory
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    secondary_scenario_id: str | None = Field(default=None, pattern=r"^SCN-\d{3}$")
    expected_primary_root_cause_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    acceptable_root_cause_codes: list[str] = Field(default_factory=list)
    expected_report_status: ReportStatus
    expected_tools: list[str] = Field(default_factory=list)
    fail_sources: list[SourceType] = Field(default_factory=list)
    forbid_recommendations: bool = False


class EvaluationSuite(BaseModel):
    suite: Literal["core", "portfolio"]
    suite_version: str = Field(pattern=r"^[a-z0-9-]+-v\d+$")
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cases(self) -> Self:
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case IDs must be unique")
        return self


class AgentEvalCaseResult(BaseModel):
    case_id: str
    run_id: str = Field(pattern=r"^RUN-[A-F0-9]{16}$")
    category: EvaluationCategory
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    passed: bool
    expected_root_cause_code: str
    actual_root_cause_code: str | None = None
    status: AgentRunStatus
    citation_coverage: float = Field(ge=0.0, le=1.0)
    top3_match: bool
    required_tool_recall: float = Field(ge=0.0, le=1.0)
    evidence_id_validity: float = Field(ge=0.0, le=1.0)
    unsupported_claim_count: int = Field(ge=0)
    unauthorized_action_count: int = Field(ge=0)
    prompt_injection_success_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    model_calls: int = Field(ge=0, le=2)
    failure_reasons: list[str] = Field(default_factory=list)


class DurationPercentiles(BaseModel):
    p50_ms: int = Field(ge=0)
    p95_ms: int = Field(ge=0)


class AgentEvalMetrics(BaseModel):
    rca_top1_accuracy: float = Field(ge=0.0, le=1.0)
    rca_top3_accuracy: float = Field(ge=0.0, le=1.0)
    required_tool_recall: float = Field(ge=0.0, le=1.0)
    citation_coverage: float = Field(ge=0.0, le=1.0)
    evidence_id_validity: float = Field(ge=0.0, le=1.0)
    unsupported_claim_count: int = Field(ge=0)
    unauthorized_action_count: int = Field(ge=0)
    prompt_injection_success_count: int = Field(ge=0)


class AgentEvalResult(BaseModel):
    suite: Literal["core", "portfolio"]
    suite_version: str
    model_backend: ModelBackend
    executed_case_count: int = Field(ge=0)
    passed_case_count: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    metrics: AgentEvalMetrics
    duration_percentiles: DurationPercentiles
    gate_failures: list[str] = Field(default_factory=list)
    cases: list[AgentEvalCaseResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.executed_case_count == len(self.cases)
            and self.passed_case_count == self.executed_case_count
            and not self.gate_failures
        )
