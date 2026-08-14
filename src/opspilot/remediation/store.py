"""Atomic persistence ports for remediation state and audit events."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from opspilot.domain import IncidentReport
from opspilot.remediation.contracts import (
    CallbackRegistration,
    RemediationDecision,
    RemediationEvent,
    RemediationRecord,
    RemediationStatus,
    RemediationTarget,
    VerificationEvidence,
)
from opspilot.remediation.errors import ConflictError, ExpiredError, NotFoundError


@dataclass(frozen=True)
class IdempotencyEntry:
    request_digest: str
    response: RemediationRecord
    expires_at: datetime


class RemediationStore(Protocol):
    async def get_report(
        self, incident_id: str, report_id: str, report_version: int | None = None
    ) -> IncidentReport | None: ...

    async def get_target(self, incident_id: str) -> RemediationTarget | None: ...

    async def create(
        self,
        *,
        record: RemediationRecord,
        event: RemediationEvent,
        idempotency_key: str,
        request_digest: str,
        idempotency_expires_at: datetime,
    ) -> tuple[RemediationRecord, bool]: ...

    async def get(self, remediation_id: str) -> RemediationRecord | None: ...

    async def set_workflow_execution(
        self, remediation_id: str, workflow_execution: str, now: datetime
    ) -> RemediationRecord: ...

    async def register_callback(self, registration: CallbackRegistration) -> None: ...

    async def get_callback(self, remediation_id: str) -> CallbackRegistration | None: ...

    async def expire(
        self, *, remediation_id: str, actor_hash: str, now: datetime
    ) -> RemediationRecord: ...

    async def decide(
        self,
        *,
        remediation_id: str,
        decision: RemediationDecision,
        plan_hash: str,
        actor_hash: str,
        now: datetime,
        idempotency_key: str,
        request_digest: str,
        idempotency_expires_at: datetime,
        event_factory: Callable[[RemediationRecord, RemediationRecord], RemediationEvent],
    ) -> RemediationRecord: ...

    async def begin_execution(
        self,
        *,
        remediation_id: str,
        plan_hash: str,
        attempt_id: str,
        actor_hash: str,
        now: datetime,
    ) -> tuple[RemediationRecord, bool]: ...

    async def finish_execution(
        self,
        *,
        remediation_id: str,
        attempt_id: str,
        status: RemediationStatus,
        verification: VerificationEvidence | None,
        safe_failure_code: str | None,
        actor_hash: str,
        now: datetime,
    ) -> RemediationRecord: ...

    async def list_events(self, remediation_id: str) -> list[RemediationEvent]: ...


class InMemoryRemediationStore:
    """Deterministic local store with the same atomic boundaries as Firestore."""

    def __init__(self) -> None:
        self._reports: dict[tuple[str, str], IncidentReport] = {}
        self._targets: dict[str, RemediationTarget] = {}
        self._records: dict[str, RemediationRecord] = {}
        self._events: dict[str, list[RemediationEvent]] = {}
        self._callbacks: dict[str, CallbackRegistration] = {}
        self._idempotency: dict[str, IdempotencyEntry] = {}
        self._lock = asyncio.Lock()

    async def seed_incident(self, *, report: IncidentReport, target: RemediationTarget) -> None:
        async with self._lock:
            self._reports[(report.incident_id, report.report_id)] = report.model_copy(deep=True)
            self._targets[report.incident_id] = target.model_copy(deep=True)

    async def get_report(
        self, incident_id: str, report_id: str, report_version: int | None = None
    ) -> IncidentReport | None:
        async with self._lock:
            value = self._reports.get((incident_id, report_id))
            if value is None and report_version is not None:
                value = next(
                    (
                        report
                        for (stored_incident, _), report in self._reports.items()
                        if stored_incident == incident_id
                        and report.report_version == report_version
                    ),
                    None,
                )
            return value.model_copy(deep=True) if value is not None else None

    async def get_target(self, incident_id: str) -> RemediationTarget | None:
        async with self._lock:
            value = self._targets.get(incident_id)
            return value.model_copy(deep=True) if value is not None else None

    async def create(
        self,
        *,
        record: RemediationRecord,
        event: RemediationEvent,
        idempotency_key: str,
        request_digest: str,
        idempotency_expires_at: datetime,
    ) -> tuple[RemediationRecord, bool]:
        async with self._lock:
            existing = self._active_idempotency(idempotency_key, record.created_at)
            if existing is not None:
                if existing.request_digest != request_digest:
                    raise ConflictError("idempotency key was already used with another payload")
                return existing.response.model_copy(deep=True), False
            self._records[record.remediation_id] = record.model_copy(deep=True)
            self._events[record.remediation_id] = [event.model_copy(deep=True)]
            self._idempotency[idempotency_key] = IdempotencyEntry(
                request_digest=request_digest,
                response=record.model_copy(deep=True),
                expires_at=idempotency_expires_at,
            )
            return record.model_copy(deep=True), True

    async def get(self, remediation_id: str) -> RemediationRecord | None:
        async with self._lock:
            value = self._records.get(remediation_id)
            return value.model_copy(deep=True) if value is not None else None

    async def set_workflow_execution(
        self, remediation_id: str, workflow_execution: str, now: datetime
    ) -> RemediationRecord:
        async with self._lock:
            current = self._required_record(remediation_id)
            if current.workflow_execution not in {None, workflow_execution}:
                raise ConflictError("another workflow execution is already attached")
            updated = current.model_copy(
                update={"workflow_execution": workflow_execution, "updated_at": now}
            )
            self._records[remediation_id] = updated
            return updated.model_copy(deep=True)

    async def register_callback(self, registration: CallbackRegistration) -> None:
        async with self._lock:
            record = self._records.get(registration.remediation_id)
            if record is None:
                raise NotFoundError("remediation not found")
            if registration.approval_expires_at != record.expires_at:
                raise ConflictError("callback expiration does not match the remediation plan")
            self._callbacks[registration.remediation_id] = registration.model_copy(deep=True)

    async def get_callback(self, remediation_id: str) -> CallbackRegistration | None:
        async with self._lock:
            value = self._callbacks.get(remediation_id)
            return value.model_copy(deep=True) if value is not None else None

    async def expire(
        self, *, remediation_id: str, actor_hash: str, now: datetime
    ) -> RemediationRecord:
        async with self._lock:
            current = self._required_record(remediation_id)
            if current.status is RemediationStatus.EXPIRED:
                return current.model_copy(deep=True)
            if current.status is not RemediationStatus.WAITING_APPROVAL:
                raise ConflictError("only a waiting remediation can expire")
            if now < current.expires_at:
                raise ConflictError("remediation approval window has not expired")
            updated = current.transition(RemediationStatus.EXPIRED, now=now)
            self._records[remediation_id] = updated
            self._append_transition_event(current, updated, actor_hash, "APPROVAL_TIMEOUT")
            return updated.model_copy(deep=True)

    async def decide(
        self,
        *,
        remediation_id: str,
        decision: RemediationDecision,
        plan_hash: str,
        actor_hash: str,
        now: datetime,
        idempotency_key: str,
        request_digest: str,
        idempotency_expires_at: datetime,
        event_factory: Callable[[RemediationRecord, RemediationRecord], RemediationEvent],
    ) -> RemediationRecord:
        async with self._lock:
            existing_idempotency = self._active_idempotency(idempotency_key, now)
            if existing_idempotency is not None:
                if existing_idempotency.request_digest != request_digest:
                    raise ConflictError("idempotency key was already used with another payload")
                return existing_idempotency.response.model_copy(deep=True)
            current = self._required_record(remediation_id)
            if current.plan_hash != plan_hash:
                raise ConflictError("plan hash does not match the stored remediation")
            if now >= current.expires_at:
                if current.status is RemediationStatus.WAITING_APPROVAL:
                    expired = current.transition(RemediationStatus.EXPIRED, now=now)
                    self._records[remediation_id] = expired
                    self._events[remediation_id].append(event_factory(current, expired))
                raise ExpiredError("remediation approval window expired")
            if current.status is not RemediationStatus.WAITING_APPROVAL:
                raise ConflictError("remediation is not waiting for approval")
            target_status = (
                RemediationStatus.APPROVED
                if decision is RemediationDecision.APPROVE
                else RemediationStatus.REJECTED
            )
            updated = current.transition(target_status, now=now).model_copy(
                update={
                    "approver_actor_hash": actor_hash,
                    "self_approved": actor_hash == current.requester_actor_hash,
                }
            )
            self._records[remediation_id] = updated
            self._events[remediation_id].append(event_factory(current, updated))
            self._idempotency[idempotency_key] = IdempotencyEntry(
                request_digest=request_digest,
                response=updated.model_copy(deep=True),
                expires_at=idempotency_expires_at,
            )
            return updated.model_copy(deep=True)

    async def begin_execution(
        self,
        *,
        remediation_id: str,
        plan_hash: str,
        attempt_id: str,
        actor_hash: str,
        now: datetime,
    ) -> tuple[RemediationRecord, bool]:
        async with self._lock:
            current = self._required_record(remediation_id)
            if current.plan_hash != plan_hash:
                raise ConflictError("plan hash does not match the stored remediation")
            if now >= current.expires_at:
                raise ExpiredError("approved remediation expired before execution")
            if current.status is RemediationStatus.EXECUTING:
                if current.execution_attempt_id == attempt_id:
                    return current.model_copy(deep=True), False
                raise ConflictError("another execution attempt already exists")
            if current.status in {
                RemediationStatus.SUCCEEDED,
                RemediationStatus.VERIFICATION_FAILED,
                RemediationStatus.EXECUTION_FAILED,
            }:
                if current.execution_attempt_id == attempt_id:
                    return current.model_copy(deep=True), False
                raise ConflictError("remediation execution has already completed")
            if current.status is not RemediationStatus.APPROVED:
                raise ConflictError("remediation is not approved")
            updated = current.transition(RemediationStatus.EXECUTING, now=now).model_copy(
                update={"execution_attempt_id": attempt_id}
            )
            self._records[remediation_id] = updated
            self._append_transition_event(current, updated, actor_hash)
            return updated.model_copy(deep=True), True

    async def finish_execution(
        self,
        *,
        remediation_id: str,
        attempt_id: str,
        status: RemediationStatus,
        verification: VerificationEvidence | None,
        safe_failure_code: str | None,
        actor_hash: str,
        now: datetime,
    ) -> RemediationRecord:
        if status not in {
            RemediationStatus.SUCCEEDED,
            RemediationStatus.VERIFICATION_FAILED,
            RemediationStatus.EXECUTION_FAILED,
        }:
            raise ValueError("invalid terminal execution status")
        async with self._lock:
            current = self._required_record(remediation_id)
            if current.execution_attempt_id != attempt_id:
                raise ConflictError("execution attempt does not match")
            if current.status is status:
                return current.model_copy(deep=True)
            if current.status is not RemediationStatus.EXECUTING:
                raise ConflictError("remediation is not executing")
            updated = current.transition(status, now=now).model_copy(
                update={
                    "verification_successes": (
                        verification.order_successes if verification is not None else None
                    ),
                    "verification_result": verification,
                    "safe_failure_code": safe_failure_code,
                }
            )
            self._records[remediation_id] = updated
            self._append_transition_event(current, updated, actor_hash, safe_failure_code)
            return updated.model_copy(deep=True)

    async def list_events(self, remediation_id: str) -> list[RemediationEvent]:
        async with self._lock:
            return [event.model_copy(deep=True) for event in self._events.get(remediation_id, [])]

    def _required_record(self, remediation_id: str) -> RemediationRecord:
        record = self._records.get(remediation_id)
        if record is None:
            raise NotFoundError("remediation not found")
        return record

    def _active_idempotency(self, key: str, now: datetime) -> IdempotencyEntry | None:
        value = self._idempotency.get(key)
        if value is None or now >= value.expires_at:
            return None
        return value

    def _append_transition_event(
        self,
        previous: RemediationRecord,
        updated: RemediationRecord,
        actor_hash: str,
        result_code: str | None = None,
    ) -> None:
        self._events[updated.remediation_id].append(
            RemediationEvent(
                event_id=f"EVT-{len(self._events[updated.remediation_id]) + 1:04d}",
                remediation_id=updated.remediation_id,
                occurred_at=updated.updated_at,
                event_type="STATE_TRANSITION",
                from_status=previous.status,
                to_status=updated.status,
                actor_hash=actor_hash,
                self_approved=updated.self_approved,
                plan_hash=updated.plan_hash,
                execution_attempt_id=updated.execution_attempt_id,
                result_code=result_code,
            )
        )
