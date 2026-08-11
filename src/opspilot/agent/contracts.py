"""Typed contracts passed through the M6 ADK graph."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from opspilot.domain import EvidenceItem, IncidentReport, ReportStatus, ToolError


class AgentBackend(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"


class ModelBackend(StrEnum):
    FAKE = "fake"
    VERTEX = "vertex"


class AgentAcceptanceSuite(StrEnum):
    RCA = "m6-rca"
    SAFETY = "m6-safety"
    CORE = "m6-core"


class AgentAcceptanceFailureCode(StrEnum):
    RUN_FAILED = "run_failed"
    TRAJECTORY_MISMATCH = "trajectory_mismatch"
    MODEL_CALL_BUDGET_MISMATCH = "model_call_budget_mismatch"
    CITATION_COVERAGE_INCOMPLETE = "citation_coverage_incomplete"
    UNAUTHORIZED_ACTION_PRESENT = "unauthorized_action_present"
    APPROVAL_FLAG_MISSING = "approval_flag_missing"
    ROOT_CAUSE_MISMATCH = "root_cause_mismatch"
    REPORT_STATUS_MISMATCH = "report_status_mismatch"
    HYPOTHESIS_COUNT_MISMATCH = "hypothesis_count_mismatch"
    RECOMMENDATION_COUNT_MISMATCH = "recommendation_count_mismatch"


class AgentRunStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class AgentErrorCategory(StrEnum):
    VALIDATION = "validation"
    AUTH = "auth"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    UPSTREAM = "upstream"
    INVALID_RESPONSE = "invalid_response"
    INTERNAL = "internal"


class ModelExecutionPhase(StrEnum):
    NOT_STARTED = "not_started"
    REQUEST_VALIDATED = "request_validated"
    RESPONSE_RECEIVED = "response_received"
    NODE_OUTPUT_EMITTED = "node_output_emitted"
    GRAPH_COMPLETED = "graph_completed"


class ModelTimeoutOrigin(StrEnum):
    NONE = "none"
    MODEL_RESPONSE_PENDING = "model_response_pending"
    STRUCTURED_OUTPUT_PENDING = "structured_output_pending"
    GRAPH_COMPLETION_PENDING = "graph_completion_pending"
    ACCEPTANCE_DEADLINE = "acceptance_deadline"
    UNKNOWN = "unknown"


class AgentRunError(BaseModel):
    code: str
    category: AgentErrorCategory
    safe_message: str
    retryable: bool = False


class AgentEvidenceContext(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    incident_id: str = Field(pattern=r"^INC-\d{4}-\d{4}$")
    generated_at: datetime
    correlation_id: str
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


class ModelNodeTiming(BaseModel):
    node_name: Literal["rca_analyst", "report_composer"]
    last_phase: ModelExecutionPhase = ModelExecutionPhase.NOT_STARTED
    request_to_response_ms: int | None = Field(default=None, ge=0, le=200_000)
    response_to_output_ms: int | None = Field(default=None, ge=0, le=200_000)
    total_elapsed_ms: int = Field(default=0, ge=0, le=200_000)
    completed: bool = False
    timeout_seconds: float = Field(default=20.0, ge=0.001, le=200.0)


class ModelBudgetUsage(BaseModel):
    model_calls: int = Field(default=0, ge=0, le=3)
    attempted_model_calls: int = Field(default=0, ge=0, le=3)
    successful_model_calls: int = Field(default=0, ge=0, le=3)
    prompt_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    input_bytes: int = Field(default=0, ge=0, le=64 * 1024)
    request_input_bytes: int = Field(default=0, ge=0, le=3 * 64 * 1024)
    max_request_input_bytes: int = Field(default=0, ge=0, le=64 * 1024)
    truncated: bool = False
    deadline_seconds: int = 60
    node_timings: list[ModelNodeTiming] = Field(default_factory=list, max_length=2)
    graph_elapsed_ms: int = Field(default=0, ge=0, le=200_000)
    timeout_origin: ModelTimeoutOrigin = ModelTimeoutOrigin.NONE


class AgentRunResult(BaseModel):
    status: AgentRunStatus
    succeeded: bool
    backend: AgentBackend
    model_backend: ModelBackend
    report: IncidentReport | None = None
    trajectory: list[str] = Field(default_factory=list)
    budget: ModelBudgetUsage = Field(default_factory=ModelBudgetUsage)
    errors: list[AgentRunError] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.succeeded and self.report is None:
            raise ValueError("successful agent result requires a report")
        if not self.succeeded and not self.errors:
            raise ValueError("failed agent result requires a safe error")
        return self


class AgentEvalCaseResult(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    passed: bool
    expected_root_cause_code: str
    actual_root_cause_code: str | None = None
    status: AgentRunStatus
    citation_coverage: float = Field(ge=0.0, le=1.0)
    model_calls: int = Field(ge=0, le=3)


class AgentEvalResult(BaseModel):
    suite: Literal["fixture"] = "fixture"
    model_backend: ModelBackend
    executed_case_count: int = Field(ge=0, le=7)
    passed_case_count: int = Field(ge=0, le=7)
    model_calls: int = Field(ge=0, le=21)
    cases: list[AgentEvalCaseResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.executed_case_count == 7 and self.passed_case_count == 7


class AgentDiagnosticResult(BaseModel):
    account_alias: str = Field(pattern=r"^[A-Za-z0-9_-]{3,32}$")
    account_alias_match: bool = False
    user_credentials: bool = False
    application_default_credentials: bool = False
    default_project_configured: bool = False
    project_active: bool = False
    billing_enabled: bool = False
    billing_currency_krw_confirmed: bool = False
    vertex_api_enabled: bool = False
    predict_permission: bool = False
    service_usage_permission: bool = False
    model_id_allowed: bool = False
    location_global: bool = False
    standard_paygo: bool = True
    node_timeout_seconds: float = Field(default=20.0, ge=0.001, le=200.0)
    graph_timeout_seconds: int = Field(default=60, ge=1, le=200)
    acceptance_timeout_seconds: int = Field(default=200, ge=1, le=600)
    phase_observability_ready: bool = False
    generate_content_calls: int = Field(default=0, ge=0, le=0)
    missing_permissions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    model_ready: bool = False


class AgentAcceptanceCaseResult(BaseModel):
    scenario_id: str = Field(pattern=r"^SCN-\d{3}$")
    passed: bool
    status: AgentRunStatus
    report_status: ReportStatus | None = None
    actual_root_cause_code: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    model_root_cause_code: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    canonical_root_cause_code: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )
    root_cause_normalized: bool = False
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    hypothesis_count: int = Field(default=0, ge=0)
    recommended_action_count: int = Field(default=0, ge=0)
    unauthorized_action_count: int | None = Field(default=None, ge=0)
    all_actions_require_approval: bool = True
    trajectory_matches: bool = False
    failure_codes: list[AgentAcceptanceFailureCode] = Field(default_factory=list)
    budget: ModelBudgetUsage = Field(default_factory=ModelBudgetUsage)
    errors: list[AgentRunError] = Field(default_factory=list)


class AgentAcceptanceResult(BaseModel):
    suite: AgentAcceptanceSuite = AgentAcceptanceSuite.CORE
    model_backend: ModelBackend
    executed_case_count: int = Field(default=0, ge=0, le=3)
    passed_case_count: int = Field(default=0, ge=0, le=3)
    attempted_model_calls: int = Field(default=0, ge=0, le=9)
    successful_model_calls: int = Field(default=0, ge=0, le=9)
    prompt_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    request_input_bytes: int = Field(default=0, ge=0, le=9 * 64 * 1024)
    max_request_input_bytes: int = Field(default=0, ge=0, le=64 * 1024)
    deadline_seconds: int = 200
    timeout_origin: ModelTimeoutOrigin = ModelTimeoutOrigin.NONE
    passed: bool = False
    cases: list[AgentAcceptanceCaseResult] = Field(default_factory=list, max_length=3)
    errors: list[AgentRunError] = Field(default_factory=list)
