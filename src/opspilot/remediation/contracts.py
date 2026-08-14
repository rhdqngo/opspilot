"""Versioned contracts for approval-gated Cloud Run remediation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from opspilot.domain import INCIDENT_ID_PATTERN

APPROVAL_TTL = timedelta(minutes=15)
IDEMPOTENCY_TTL = timedelta(hours=24)


class RemediationActionType(StrEnum):
    ROLLBACK_CLOUD_RUN = "ROLLBACK_CLOUD_RUN"


class RemediationDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class RemediationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    POLICY_REJECTED = "POLICY_REJECTED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


LEGAL_TRANSITIONS: dict[RemediationStatus, frozenset[RemediationStatus]] = {
    RemediationStatus.PROPOSED: frozenset(
        {RemediationStatus.POLICY_REJECTED, RemediationStatus.WAITING_APPROVAL}
    ),
    RemediationStatus.WAITING_APPROVAL: frozenset(
        {
            RemediationStatus.REJECTED,
            RemediationStatus.EXPIRED,
            RemediationStatus.APPROVED,
        }
    ),
    RemediationStatus.APPROVED: frozenset({RemediationStatus.EXECUTING}),
    RemediationStatus.EXECUTING: frozenset(
        {
            RemediationStatus.SUCCEEDED,
            RemediationStatus.VERIFICATION_FAILED,
            RemediationStatus.EXECUTION_FAILED,
        }
    ),
    RemediationStatus.POLICY_REJECTED: frozenset(),
    RemediationStatus.REJECTED: frozenset(),
    RemediationStatus.EXPIRED: frozenset(),
    RemediationStatus.SUCCEEDED: frozenset(),
    RemediationStatus.VERIFICATION_FAILED: frozenset(),
    RemediationStatus.EXECUTION_FAILED: frozenset(),
}


class Principal(BaseModel):
    """Verified identity with no persisted email address."""

    subject: str = Field(min_length=1, max_length=255)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", exclude=True)
    email_verified: bool

    @property
    def actor_hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.subject.encode("utf-8")).hexdigest()


class RemediationTarget(BaseModel):
    """Trusted control-plane facts that callers cannot submit."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    service: str = Field(pattern=r"^opspilot-prod-sim-payment$")
    source_revision: str = Field(min_length=1)
    target_revision: str = Field(min_length=1)
    target_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    service_etag: str = Field(min_length=1)

    @property
    def service_name(self) -> str:
        return f"projects/{self.project_id}/locations/{self.region}/services/{self.service}"


class VerificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_request_count: int = Field(default=10, ge=10, le=10)
    window_minutes: int = Field(default=10, ge=1, le=10)
    required_successes: int = Field(default=10, ge=10, le=10)
    require_target_traffic_percent: int = Field(default=100, ge=100, le=100)
    compare_metric_windows: bool = True


class RemediationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "remediation-plan-v1"
    action_type: RemediationActionType = RemediationActionType.ROLLBACK_CLOUD_RUN
    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    report_id: str = Field(min_length=1)
    action_id: str = Field(pattern=r"^ACT-\d{2}$")
    source_revision: str = Field(min_length=1)
    target_revision: str = Field(min_length=1)
    target_image_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    service_etag: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    expected_effect: str = Field(min_length=1)
    verification: VerificationPlan
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("plan timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if self.expires_at - self.created_at > APPROVAL_TTL:
            raise ValueError("approval validity cannot exceed 15 minutes")
        if self.source_revision == self.target_revision:
            raise ValueError("source and target revision must differ")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence IDs must be unique")
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @property
    def plan_hash(self) -> str:
        digest = hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


class RemediationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1)
    report_version: int | None = Field(default=None, ge=1)
    action_id: str = Field(pattern=r"^ACT-\d{2}$")
    verification_window_minutes: int = Field(default=10, ge=1, le=10)


class RemediationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: RemediationDecision
    plan_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    comment: str = Field(default="", max_length=500)


class VerificationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_traffic_percent: int = Field(ge=0, le=100)
    order_attempts: int = Field(default=10, ge=10, le=10)
    order_successes: int = Field(ge=0, le=10)
    metric_windows_recorded: bool
    metric_before_points: int = Field(ge=0)
    metric_after_points: int = Field(ge=0)
    verified_at: datetime

    @model_validator(mode="after")
    def validate_timestamp(self) -> Self:
        if self.verified_at.tzinfo is None:
            raise ValueError("verification timestamp must be timezone-aware")
        return self


class RemediationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    remediation_id: str = Field(pattern=r"^REM-[A-F0-9]{16}$")
    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    report_id: str
    action_id: str = Field(pattern=r"^ACT-\d{2}$")
    plan: RemediationPlan
    plan_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: RemediationStatus
    requester_actor_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approver_actor_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    self_approved: bool = False
    execution_attempt_id: str | None = None
    workflow_execution: str | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    verification_successes: int | None = Field(default=None, ge=0, le=10)
    verification_result: VerificationEvidence | None = None
    safe_failure_code: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.plan_hash != self.plan.plan_hash:
            raise ValueError("plan_hash does not match canonical plan")
        for value in (self.created_at, self.updated_at, self.expires_at):
            if value.tzinfo is None:
                raise ValueError("record timestamps must be timezone-aware")
        return self

    def transition(self, target: RemediationStatus, *, now: datetime) -> Self:
        if target not in LEGAL_TRANSITIONS[self.status]:
            raise ValueError(f"illegal remediation transition: {self.status} -> {target}")
        return self.model_copy(update={"status": target, "updated_at": now})


class RemediationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    remediation_id: str
    occurred_at: datetime
    event_type: str
    from_status: RemediationStatus | None = None
    to_status: RemediationStatus
    actor_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    self_approved: bool = False
    plan_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_attempt_id: str | None = None
    result_code: str | None = None


class CallbackRegistration(BaseModel):
    remediation_id: str
    callback_url: str = Field(pattern=r"^https://workflowexecutions\.googleapis\.com/")
    approval_expires_at: datetime
    expires_at: datetime


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_attempt_id: str = Field(pattern=r"^ATT-[A-Za-z0-9_-]{8,64}$")


class ExecutionOutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_attempt_id: str = Field(pattern=r"^ATT-[A-Za-z0-9_-]{8,64}$")
    traffic_update_succeeded: bool
    safe_failure_code: str | None = Field(default=None, pattern=r"^[A-Z0-9_]+$")

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.traffic_update_succeeded and self.safe_failure_code is not None:
            raise ValueError("successful traffic update cannot carry a failure code")
        if not self.traffic_update_succeeded and self.safe_failure_code is None:
            raise ValueError("failed traffic update requires a safe failure code")
        return self


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_request_digest(*, operation: str, path_id: str, payload: BaseModel) -> str:
    value = {
        "operation": operation,
        "path_id": path_id,
        "payload": payload.model_dump(mode="json"),
    }
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
