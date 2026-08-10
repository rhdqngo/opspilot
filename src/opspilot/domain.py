"""Versioned domain contracts for local investigations and reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD_SIM = "prod-sim"


class RequestedDepth(StrEnum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


class Symptom(StrEnum):
    ERROR_RATE = "ERROR_RATE"
    LATENCY = "LATENCY"
    TIMEOUT = "TIMEOUT"
    AVAILABILITY = "AVAILABILITY"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    DATA_INCONSISTENCY = "DATA_INCONSISTENCY"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    LOG = "LOG"
    METRIC = "METRIC"
    CHANGE = "CHANGE"
    KNOWLEDGE = "KNOWLEDGE"
    INCIDENT = "INCIDENT"
    ACTION = "ACTION"


class EvidenceDirection(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class ToolErrorCategory(StrEnum):
    VALIDATION = "VALIDATION"
    AUTH = "AUTH"
    NOT_FOUND = "NOT_FOUND"
    QUOTA = "QUOTA"
    TIMEOUT = "TIMEOUT"
    UPSTREAM = "UPSTREAM"
    PARTIAL = "PARTIAL"
    INTERNAL = "INTERNAL"


class HypothesisStatus(StrEnum):
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    SUPPORTED = "SUPPORTED"
    PLAUSIBLE = "PLAUSIBLE"
    WEAK = "WEAK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReportStatus(StrEnum):
    INVESTIGATING = "INVESTIGATING"
    IDENTIFIED = "IDENTIFIED"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    INCONCLUSIVE = "INCONCLUSIVE"


class InvestigationRequest(BaseModel):
    incident_id: str | None = Field(default=None, pattern=r"^INC-\d{4}-\d{4}$")
    user_query: str = Field(min_length=3, max_length=2_000)
    services: list[str] = Field(default_factory=list)
    environment: Environment = Environment.DEV
    start_time: datetime
    end_time: datetime
    symptoms: list[Symptom] = Field(default_factory=lambda: [Symptom.UNKNOWN])
    requested_depth: RequestedDepth = RequestedDepth.STANDARD
    assumptions: list[str] = Field(default_factory=list)
    requested_actions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must be timezone-aware")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > timedelta(hours=2):
            raise ValueError("investigation time window cannot exceed 2 hours")
        return self


class ToolMeta(BaseModel):
    tool_name: str
    request_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    source_project: str
    source_location: str | None = None
    truncated: bool = False
    cache_hit: bool = False
    warnings: list[str] = Field(default_factory=list)


class ToolError(BaseModel):
    code: str
    category: ToolErrorCategory
    retryable: bool
    safe_message: str
    debug_reference: str | None = None


class ToolResult[T](BaseModel):
    ok: bool
    data: T | None = None
    error: ToolError | None = None
    meta: ToolMeta

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        if self.ok and (self.data is None or self.error is not None):
            raise ValueError("successful tool result requires data and no error")
        if not self.ok and self.error is None:
            raise ValueError("failed tool result requires an error")
        return self


class EvidenceItem(BaseModel):
    evidence_id: str = Field(pattern=r"^EV-(LOG|MET|CHG|KNW|INC|ACT)-\d{4}$")
    source_type: SourceType
    title: str
    service: str | None = None
    environment: str | None = None
    observed_at: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    summary: str
    value: float | str | None = None
    unit: str | None = None
    direction: EvidenceDirection = EvidenceDirection.UNKNOWN
    source_uri: str | None = None
    source_record_id: str | None = None
    raw_excerpt_hash: str | None = None
    retrieval_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_datetimes(self) -> Self:
        for value in (self.observed_at, self.period_start, self.period_end):
            if value is not None and value.tzinfo is None:
                raise ValueError("evidence datetimes must be timezone-aware")
        return self


class RootCauseHypothesis(BaseModel):
    hypothesis_id: str = Field(pattern=r"^H-\d{2}$")
    rank: int = Field(ge=1, le=3)
    claim: str
    mechanism: str
    affected_services: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    evidence_support_score: int = Field(ge=0, le=100)
    status: HypothesisStatus


class IncidentTimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    title: str
    description: str
    service: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    action_id: str = Field(pattern=r"^ACT-\d{2}$")
    category: str
    title: str
    description: str
    target_service: str | None = None
    risk_level: str
    requires_approval: bool
    prerequisites: list[str] = Field(default_factory=list)
    expected_effect: str
    rollback_method: str | None = None
    verification_steps: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)


AuditValue = str | int | float | bool | list[str]


class IncidentReport(BaseModel):
    schema_version: str = "1.0"
    report_id: str
    report_version: int = Field(ge=1)
    incident_id: str = Field(pattern=r"^INC-\d{4}-\d{4}$")
    generated_at: datetime
    correlation_id: str
    title: str
    severity: str
    severity_rationale: str
    status: ReportStatus
    impact_summary: str
    executive_summary: str
    affected_services: list[str] = Field(default_factory=list)
    timeline: list[IncidentTimelineEvent] = Field(default_factory=list)
    hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    tool_errors: list[ToolError] = Field(default_factory=list)
    approval_status: str | None = None
    audit: dict[str, AuditValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evidence_references(self) -> Self:
        ids = [item.evidence_id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be unique")
        known = set(ids)
        referenced: set[str] = set()
        for event in self.timeline:
            referenced.update(event.evidence_ids)
        for hypothesis in self.hypotheses:
            referenced.update(hypothesis.supporting_evidence_ids)
            referenced.update(hypothesis.contradicting_evidence_ids)
        for action in self.recommended_actions:
            referenced.update(action.supporting_evidence_ids)
        unknown = sorted(referenced - known)
        if unknown:
            raise ValueError(f"unknown evidence references: {unknown}")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return self
