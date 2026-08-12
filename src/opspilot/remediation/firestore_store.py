"""Firestore Native persistence for the remediation control plane."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from google.cloud import firestore

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


def _doc_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class FirestoreRemediationStore:
    """Named-database store; every state change is a Firestore transaction."""

    def __init__(
        self,
        *,
        project_id: str,
        database_id: str = "opspilot-dev",
        client: firestore.Client | None = None,
    ) -> None:
        self.client = client or firestore.Client(project=project_id, database=database_id)

    async def save_incident(
        self,
        *,
        report: IncidentReport,
        target: RemediationTarget,
        scenario_id: str = "SCN-008",
    ) -> None:
        incident_ref = self.client.collection("incidents").document(report.incident_id)
        report_ref = incident_ref.collection("reports").document(report.report_id)
        batch = self.client.batch()
        batch.set(
            incident_ref,
            {
                "incident_id": report.incident_id,
                "scenario_id": scenario_id,
                "remediation_target": target.model_dump(mode="python"),
                "updated_at": report.generated_at,
            },
            merge=True,
        )
        batch.create(report_ref, report.model_dump(mode="python"))
        await asyncio.to_thread(batch.commit)

    async def save_recovery_target(
        self,
        *,
        incident_id: str,
        target: RemediationTarget,
        scenario_id: str,
        updated_at: datetime,
    ) -> None:
        payload = {
            "incident_id": incident_id,
            "scenario_id": scenario_id,
            "remediation_target": target.model_dump(mode="python"),
            "updated_at": updated_at,
        }
        batch = self.client.batch()
        batch.set(self.client.collection("incidents").document(incident_id), payload, merge=True)
        batch.set(self.client.collection("scenario_recovery").document(scenario_id), payload)
        await asyncio.to_thread(batch.commit)

    async def get_latest_scenario_target(
        self, scenario_id: str
    ) -> tuple[str, RemediationTarget] | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("scenario_recovery").document(scenario_id).get
        )
        if not snapshot.exists:
            return None
        data = cast(dict[str, Any], snapshot.to_dict())
        incident_id = data.get("incident_id")
        target = data.get("remediation_target")
        if not isinstance(incident_id, str) or target is None:
            return None
        return incident_id, RemediationTarget.model_validate(target)

    async def get_report(self, incident_id: str, report_id: str) -> IncidentReport | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("incidents")
            .document(incident_id)
            .collection("reports")
            .document(report_id)
            .get
        )
        if not snapshot.exists:
            return None
        return IncidentReport.model_validate(snapshot.to_dict())

    async def get_target(self, incident_id: str) -> RemediationTarget | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("incidents").document(incident_id).get
        )
        if not snapshot.exists:
            return None
        data = cast(dict[str, Any], snapshot.to_dict())
        target = data.get("remediation_target")
        return RemediationTarget.model_validate(target) if target is not None else None

    async def create(
        self,
        *,
        record: RemediationRecord,
        event: RemediationEvent,
        idempotency_key: str,
        request_digest: str,
        idempotency_expires_at: datetime,
    ) -> tuple[RemediationRecord, bool]:
        return await asyncio.to_thread(
            self._create_sync,
            record,
            event,
            idempotency_key,
            request_digest,
            idempotency_expires_at,
        )

    def _create_sync(
        self,
        record: RemediationRecord,
        event: RemediationEvent,
        idempotency_key: str,
        request_digest: str,
        idempotency_expires_at: datetime,
    ) -> tuple[RemediationRecord, bool]:
        record_ref = self.client.collection("remediations").document(record.remediation_id)
        idem_ref = self.client.collection("idempotency_keys").document(_doc_key(idempotency_key))
        event_ref = record_ref.collection("events").document(event.event_id)
        transaction = self.client.transaction()

        @firestore.transactional
        def apply(txn: Any) -> tuple[RemediationRecord, bool]:
            existing = idem_ref.get(transaction=txn)
            if existing.exists:
                data = cast(dict[str, Any], existing.to_dict())
                expires_at = cast(datetime | None, data.get("expires_at"))
                if expires_at is not None and record.created_at < expires_at:
                    if data.get("request_digest") != request_digest:
                        raise ConflictError("idempotency key was already used with another payload")
                    return RemediationRecord.model_validate(data["response"]), False
            txn.create(record_ref, record.model_dump(mode="python"))
            txn.create(event_ref, event.model_dump(mode="python"))
            # TTL deletion is asynchronous. Overwrite an expired key explicitly instead of
            # treating the document's continued existence as an active idempotency lease.
            txn.set(
                idem_ref,
                {
                    "request_digest": request_digest,
                    "response": record.model_dump(mode="python"),
                    "expires_at": idempotency_expires_at,
                },
            )
            return record, True

        return cast(tuple[RemediationRecord, bool], apply(transaction))

    async def get(self, remediation_id: str) -> RemediationRecord | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("remediations").document(remediation_id).get
        )
        if not snapshot.exists:
            return None
        return RemediationRecord.model_validate(snapshot.to_dict())

    async def get_latest_remediation_for_incident(
        self, incident_id: str
    ) -> RemediationRecord | None:
        query = self.client.collection("remediations").order_by(
            "created_at", direction=firestore.Query.DESCENDING
        )
        snapshots = await asyncio.to_thread(lambda: list(query.limit(20).stream()))
        for snapshot in snapshots:
            record = RemediationRecord.model_validate(snapshot.to_dict())
            if record.incident_id == incident_id:
                return record
        return None

    async def set_workflow_execution(
        self, remediation_id: str, workflow_execution: str, now: datetime
    ) -> RemediationRecord:
        record_ref = self.client.collection("remediations").document(remediation_id)

        def update() -> RemediationRecord:
            transaction = self.client.transaction()

            @firestore.transactional
            def apply(txn: Any) -> RemediationRecord:
                snapshot = record_ref.get(transaction=txn)
                if not snapshot.exists:
                    raise NotFoundError("remediation not found")
                current = RemediationRecord.model_validate(snapshot.to_dict())
                if current.workflow_execution not in {None, workflow_execution}:
                    raise ConflictError("another workflow execution is already attached")
                updated = current.model_copy(
                    update={"workflow_execution": workflow_execution, "updated_at": now}
                )
                txn.set(record_ref, updated.model_dump(mode="python"))
                return updated

            return cast(RemediationRecord, apply(transaction))

        return await asyncio.to_thread(update)

    async def register_callback(self, registration: CallbackRegistration) -> None:
        record_ref = self.client.collection("remediations").document(registration.remediation_id)
        callback_ref = self.client.collection("remediation_callbacks").document(
            registration.remediation_id
        )

        def update() -> None:
            transaction = self.client.transaction()

            @firestore.transactional
            def apply(txn: Any) -> None:
                snapshot = record_ref.get(transaction=txn)
                if not snapshot.exists:
                    raise NotFoundError("remediation not found")
                record = RemediationRecord.model_validate(snapshot.to_dict())
                if registration.approval_expires_at != record.expires_at:
                    raise ConflictError("callback expiration does not match the remediation plan")
                txn.set(callback_ref, registration.model_dump(mode="python"))

            apply(transaction)

        await asyncio.to_thread(update)

    async def get_callback(self, remediation_id: str) -> CallbackRegistration | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("remediation_callbacks").document(remediation_id).get
        )
        if not snapshot.exists:
            return None
        return CallbackRegistration.model_validate(snapshot.to_dict())

    async def expire(
        self, *, remediation_id: str, actor_hash: str, now: datetime
    ) -> RemediationRecord:
        record_ref = self.client.collection("remediations").document(remediation_id)

        def update() -> RemediationRecord:
            transaction = self.client.transaction()

            @firestore.transactional
            def apply(txn: Any) -> RemediationRecord:
                snapshot = record_ref.get(transaction=txn)
                if not snapshot.exists:
                    raise NotFoundError("remediation not found")
                current = RemediationRecord.model_validate(snapshot.to_dict())
                if current.status is RemediationStatus.EXPIRED:
                    return current
                if current.status is not RemediationStatus.WAITING_APPROVAL:
                    raise ConflictError("only a waiting remediation can expire")
                if now < current.expires_at:
                    raise ConflictError("remediation approval window has not expired")
                updated = current.transition(RemediationStatus.EXPIRED, now=now)
                event = self._transition_event(
                    current, updated, actor_hash, "EVT-0002", "APPROVAL_TIMEOUT"
                )
                txn.set(record_ref, updated.model_dump(mode="python"))
                txn.create(
                    record_ref.collection("events").document(event.event_id),
                    event.model_dump(mode="python"),
                )
                return updated

            return cast(RemediationRecord, apply(transaction))

        return await asyncio.to_thread(update)

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
        return await asyncio.to_thread(
            self._decide_sync,
            remediation_id,
            decision,
            plan_hash,
            actor_hash,
            now,
            idempotency_key,
            request_digest,
            idempotency_expires_at,
            event_factory,
        )

    def _decide_sync(
        self,
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
        record_ref = self.client.collection("remediations").document(remediation_id)
        idem_ref = self.client.collection("idempotency_keys").document(_doc_key(idempotency_key))
        transaction = self.client.transaction()

        @firestore.transactional
        def apply(txn: Any) -> tuple[RemediationRecord, bool]:
            existing = idem_ref.get(transaction=txn)
            if existing.exists:
                data = cast(dict[str, Any], existing.to_dict())
                expires_at = cast(datetime | None, data.get("expires_at"))
                if expires_at is not None and now < expires_at:
                    if data.get("request_digest") != request_digest:
                        raise ConflictError("idempotency key was already used with another payload")
                    return RemediationRecord.model_validate(data["response"]), False
            snapshot = record_ref.get(transaction=txn)
            if not snapshot.exists:
                raise NotFoundError("remediation not found")
            current = RemediationRecord.model_validate(snapshot.to_dict())
            if current.plan_hash != plan_hash:
                raise ConflictError("plan hash does not match the stored remediation")
            if now >= current.expires_at:
                if current.status is RemediationStatus.WAITING_APPROVAL:
                    expired = current.transition(RemediationStatus.EXPIRED, now=now)
                    txn.set(record_ref, expired.model_dump(mode="python"))
                    event = event_factory(current, expired)
                    txn.create(
                        record_ref.collection("events").document(event.event_id),
                        event.model_dump(mode="python"),
                    )
                    return expired, True
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
            event = event_factory(current, updated)
            txn.set(record_ref, updated.model_dump(mode="python"))
            txn.create(
                record_ref.collection("events").document(event.event_id),
                event.model_dump(mode="python"),
            )
            txn.set(
                idem_ref,
                {
                    "request_digest": request_digest,
                    "response": updated.model_dump(mode="python"),
                    "expires_at": idempotency_expires_at,
                },
            )
            return updated, False

        updated, expired = cast(tuple[RemediationRecord, bool], apply(transaction))
        if expired:
            # Raise only after the transaction commits the explicit EXPIRED transition.
            raise ExpiredError("remediation approval window expired")
        return updated

    async def begin_execution(
        self,
        *,
        remediation_id: str,
        plan_hash: str,
        attempt_id: str,
        actor_hash: str,
        now: datetime,
    ) -> tuple[RemediationRecord, bool]:
        record_ref = self.client.collection("remediations").document(remediation_id)

        def update() -> tuple[RemediationRecord, bool]:
            transaction = self.client.transaction()

            @firestore.transactional
            def apply(txn: Any) -> tuple[RemediationRecord, bool]:
                snapshot = record_ref.get(transaction=txn)
                if not snapshot.exists:
                    raise NotFoundError("remediation not found")
                current = RemediationRecord.model_validate(snapshot.to_dict())
                if current.plan_hash != plan_hash:
                    raise ConflictError("plan hash does not match the stored remediation")
                if now >= current.expires_at:
                    raise ExpiredError("approved remediation expired before execution")
                if current.execution_attempt_id == attempt_id and current.status in {
                    RemediationStatus.EXECUTING,
                    RemediationStatus.SUCCEEDED,
                    RemediationStatus.VERIFICATION_FAILED,
                    RemediationStatus.EXECUTION_FAILED,
                }:
                    return current, False
                if current.status is not RemediationStatus.APPROVED:
                    raise ConflictError("remediation is not approved")
                updated = current.transition(RemediationStatus.EXECUTING, now=now).model_copy(
                    update={"execution_attempt_id": attempt_id}
                )
                event = self._transition_event(current, updated, actor_hash, "EVT-0003")
                txn.set(record_ref, updated.model_dump(mode="python"))
                txn.create(
                    record_ref.collection("events").document(event.event_id),
                    event.model_dump(mode="python"),
                )
                return updated, True

            return cast(tuple[RemediationRecord, bool], apply(transaction))

        return await asyncio.to_thread(update)

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
        record_ref = self.client.collection("remediations").document(remediation_id)

        def update() -> RemediationRecord:
            transaction = self.client.transaction()

            @firestore.transactional
            def apply(txn: Any) -> RemediationRecord:
                snapshot = record_ref.get(transaction=txn)
                if not snapshot.exists:
                    raise NotFoundError("remediation not found")
                current = RemediationRecord.model_validate(snapshot.to_dict())
                if current.execution_attempt_id != attempt_id:
                    raise ConflictError("execution attempt does not match")
                if current.status is status:
                    return current
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
                event = self._transition_event(
                    current, updated, actor_hash, "EVT-0004", safe_failure_code
                )
                txn.set(record_ref, updated.model_dump(mode="python"))
                txn.create(
                    record_ref.collection("events").document(event.event_id),
                    event.model_dump(mode="python"),
                )
                return updated

            return cast(RemediationRecord, apply(transaction))

        return await asyncio.to_thread(update)

    async def list_events(self, remediation_id: str) -> list[RemediationEvent]:
        query = (
            self.client.collection("remediations")
            .document(remediation_id)
            .collection("events")
            .order_by("occurred_at")
        )
        snapshots = await asyncio.to_thread(lambda: list(query.stream()))
        return [RemediationEvent.model_validate(item.to_dict()) for item in snapshots]

    @staticmethod
    def _transition_event(
        previous: RemediationRecord,
        updated: RemediationRecord,
        actor_hash: str,
        event_id: str,
        result_code: str | None = None,
    ) -> RemediationEvent:
        return RemediationEvent(
            event_id=event_id,
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
