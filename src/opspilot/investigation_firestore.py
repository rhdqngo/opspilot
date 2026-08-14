"""Firestore Native implementation of the investigation store contract."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from google.cloud import firestore

from opspilot.domain import IncidentReport, InvestigationRequest
from opspilot.service import (
    ConversationContext,
    IncidentRecord,
    IncidentSeed,
    IncidentState,
    InvestigationExecution,
    InvestigationRecord,
    InvestigationStatus,
)


def _key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _incident_merge_fields(
    existing: dict[str, Any],
    *,
    record: InvestigationRecord,
    request: InvestigationRequest,
) -> dict[str, Any]:
    """Add the investigation contract without discarding remediation metadata."""

    seed = IncidentRecord(
        incident_id=record.incident_id,
        services=request.services,
        opened_at=record.created_at,
        latest_investigation_id=record.investigation_id,
        assumptions=request.assumptions,
    ).model_dump(mode="python")
    return {
        key: value
        for key, value in seed.items()
        if key == "latest_investigation_id" or key not in existing
    }


class FirestoreInvestigationStore:
    """Transactions bind incident counters, immutable reports, and task leases."""

    def __init__(
        self,
        *,
        project_id: str,
        database_id: str = "opspilot-dev",
        client: firestore.Client | None = None,
    ) -> None:
        self.client = client or firestore.Client(project=project_id, database=database_id)

    async def create_investigation(
        self, record: InvestigationRecord, request: InvestigationRequest
    ) -> bool:
        investigation_ref = self.client.collection("investigations").document(
            record.investigation_id
        )
        incident_ref = self.client.collection("incidents").document(record.incident_id)

        @firestore.transactional
        def write(transaction: firestore.Transaction) -> bool:
            if investigation_ref.get(transaction=transaction).exists:
                return False
            incident_snapshot = incident_ref.get(transaction=transaction)
            transaction.create(
                investigation_ref,
                {
                    **record.model_dump(mode="python"),
                    "request": request.model_dump(mode="python"),
                },
            )
            if incident_snapshot.exists:
                transaction.set(
                    incident_ref,
                    _incident_merge_fields(
                        cast(dict[str, Any], incident_snapshot.to_dict()),
                        record=record,
                        request=request,
                    ),
                    merge=True,
                )
            else:
                transaction.create(
                    incident_ref,
                    IncidentRecord(
                        incident_id=record.incident_id,
                        services=request.services,
                        opened_at=record.created_at,
                        latest_investigation_id=record.investigation_id,
                        assumptions=request.assumptions,
                    ).model_dump(mode="python"),
                )
            return True

        return await asyncio.to_thread(write, self.client.transaction())

    async def get_record(self, investigation_id: str) -> InvestigationRecord | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("investigations").document(investigation_id).get
        )
        return InvestigationRecord.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def get_request(self, investigation_id: str) -> InvestigationRequest | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("investigations").document(investigation_id).get
        )
        if not snapshot.exists:
            return None
        payload = cast(dict[str, Any], snapshot.to_dict()).get("request")
        return InvestigationRequest.model_validate(payload) if payload is not None else None

    async def claim(
        self, investigation_id: str, *, now: datetime
    ) -> tuple[InvestigationRecord, InvestigationRequest] | None:
        ref = self.client.collection("investigations").document(investigation_id)

        @firestore.transactional
        def take(
            transaction: firestore.Transaction,
        ) -> tuple[InvestigationRecord, InvestigationRequest] | None:
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                return None
            data = cast(dict[str, Any], snapshot.to_dict())
            record = InvestigationRecord.model_validate(data)
            lease_active = record.lease_expires_at is not None and record.lease_expires_at > now
            if record.status is InvestigationStatus.RUNNING and lease_active:
                return None
            if record.status not in {InvestigationStatus.QUEUED, InvestigationStatus.RUNNING}:
                return None
            claimed = record.model_copy(
                update={
                    "status": InvestigationStatus.RUNNING,
                    "current_stage": "EVIDENCE_COLLECTION",
                    "started_at": record.started_at or now,
                    "lease_expires_at": now + timedelta(minutes=5),
                    "task_attempts": record.task_attempts + 1,
                }
            )
            transaction.update(ref, claimed.model_dump(mode="python"))
            return claimed, InvestigationRequest.model_validate(data["request"])

        return await asyncio.to_thread(take, self.client.transaction())

    async def complete(
        self, record: InvestigationRecord, execution: InvestigationExecution, *, now: datetime
    ) -> tuple[InvestigationRecord, IncidentReport]:
        investigation_ref = self.client.collection("investigations").document(
            record.investigation_id
        )
        incident_ref = self.client.collection("incidents").document(record.incident_id)

        @firestore.transactional
        def finish(
            transaction: firestore.Transaction,
        ) -> tuple[InvestigationRecord, IncidentReport]:
            investigation_snapshot = investigation_ref.get(transaction=transaction)
            incident_snapshot = incident_ref.get(transaction=transaction)
            if not investigation_snapshot.exists or not incident_snapshot.exists:
                raise RuntimeError("investigation persistence state is incomplete")
            current = InvestigationRecord.model_validate(investigation_snapshot.to_dict())
            if current.status is InvestigationStatus.COMPLETE:
                version = current.report_version
                if version is None:
                    raise RuntimeError("completed investigation has no report version")
                report_snapshot = (
                    incident_ref.collection("reports")
                    .document(f"{version:08d}")
                    .get(transaction=transaction)
                )
                return current, IncidentReport.model_validate(report_snapshot.to_dict())
            if current.status is not InvestigationStatus.RUNNING:
                raise RuntimeError("investigation lease is no longer active")
            incident = IncidentRecord.model_validate(incident_snapshot.to_dict())
            version = incident.latest_report_version + 1
            report = execution.report.model_copy(
                update={
                    "incident_id": record.incident_id,
                    "report_id": f"RPT-{record.incident_id.removeprefix('INC-')}-{version:04d}",
                    "report_version": version,
                },
                deep=True,
            )
            completed = current.model_copy(
                update={
                    "status": InvestigationStatus.COMPLETE,
                    "current_stage": "COMPLETE",
                    "completed_collectors": execution.completed_collectors,
                    "partial_failures": [error.safe_message for error in report.tool_errors],
                    "finished_at": now,
                    "lease_expires_at": None,
                    "report_version": version,
                }
            )
            transaction.create(
                incident_ref.collection("reports").document(f"{version:08d}"),
                report.model_dump(mode="python"),
            )
            transaction.update(investigation_ref, completed.model_dump(mode="python"))
            transaction.update(
                incident_ref,
                {
                    "latest_report_version": version,
                    "latest_investigation_id": record.investigation_id,
                    "services": report.affected_services,
                },
            )
            return completed, report

        return await asyncio.to_thread(finish, self.client.transaction())

    async def fail(self, record: InvestigationRecord, *, now: datetime, safe_error: str) -> None:
        failed = record.model_copy(
            update={
                "status": InvestigationStatus.FAILED,
                "current_stage": "FAILED",
                "finished_at": now,
                "lease_expires_at": None,
                "safe_error": safe_error,
            }
        )
        await asyncio.to_thread(
            self.client.collection("investigations").document(record.investigation_id).set,
            failed.model_dump(mode="python"),
            merge=True,
        )

    async def retry(self, record: InvestigationRecord, *, safe_error: str) -> None:
        ref = self.client.collection("investigations").document(record.investigation_id)

        @firestore.transactional
        def requeue(transaction: firestore.Transaction) -> None:
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                return
            current = InvestigationRecord.model_validate(snapshot.to_dict())
            if current.status is InvestigationStatus.RUNNING:
                transaction.update(
                    ref,
                    {
                        "status": InvestigationStatus.QUEUED.value,
                        "current_stage": "QUEUED",
                        "lease_expires_at": None,
                        "safe_error": safe_error,
                    },
                )

        await asyncio.to_thread(requeue, self.client.transaction())

    async def get_incident(self, incident_id: str) -> IncidentRecord | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("incidents").document(incident_id).get
        )
        return IncidentRecord.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def list_reports(self, incident_id: str) -> list[IncidentReport]:
        query = (
            self.client.collection("incidents")
            .document(incident_id)
            .collection("reports")
            .order_by("report_version")
        )
        snapshots = await asyncio.to_thread(lambda: list(query.stream()))
        return [IncidentReport.model_validate(item.to_dict()) for item in snapshots]

    async def get_report(
        self, incident_id: str, version: int | None = None
    ) -> IncidentReport | None:
        if version is None:
            incident = await self.get_incident(incident_id)
            if incident is None or incident.latest_report_version == 0:
                return None
            version = incident.latest_report_version
        snapshot = await asyncio.to_thread(
            self.client.collection("incidents")
            .document(incident_id)
            .collection("reports")
            .document(f"{version:08d}")
            .get
        )
        return IncidentReport.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def ingest_alert(
        self, seed: IncidentSeed, *, message_key: str
    ) -> tuple[IncidentRecord, bool]:
        message_ref = self.client.collection("_alert_messages").document(_key(message_key))
        index_ref = self.client.collection("_alert_index").document(
            seed.alert_key_hash.removeprefix("sha256:")
        )

        @firestore.transactional
        def ingest(transaction: firestore.Transaction) -> tuple[IncidentRecord, bool]:
            message_snapshot = message_ref.get(transaction=transaction)
            index_snapshot = index_ref.get(transaction=transaction)
            if message_snapshot.exists:
                incident_id = cast(dict[str, Any], message_snapshot.to_dict())["incident_id"]
                snapshot = (
                    self.client.collection("incidents")
                    .document(incident_id)
                    .get(transaction=transaction)
                )
                return IncidentRecord.model_validate(snapshot.to_dict()), False
            incident_id = (
                cast(dict[str, Any], index_snapshot.to_dict())["incident_id"]
                if index_snapshot.exists
                else seed.incident_id
            )
            incident_ref = self.client.collection("incidents").document(incident_id)
            incident_snapshot = incident_ref.get(transaction=transaction)
            if incident_snapshot.exists:
                incident = IncidentRecord.model_validate(incident_snapshot.to_dict())
                if seed.state is IncidentState.CLOSED:
                    incident = incident.model_copy(
                        update={"state": IncidentState.CLOSED, "closed_at": seed.closed_at}
                    )
                transaction.set(incident_ref, incident.model_dump(mode="python"), merge=True)
            else:
                incident = IncidentRecord(
                    incident_id=incident_id,
                    services=seed.services,
                    state=seed.state,
                    source=seed.source,
                    opened_at=seed.opened_at,
                    closed_at=seed.closed_at,
                    assumptions=seed.assumptions,
                )
                transaction.create(incident_ref, incident.model_dump(mode="python"))
            transaction.set(index_ref, {"incident_id": incident_id})
            transaction.create(message_ref, {"incident_id": incident_id})
            return incident, True

        return await asyncio.to_thread(ingest, self.client.transaction())

    async def get_context(self, session_hash: str) -> ConversationContext | None:
        snapshot = await asyncio.to_thread(
            self.client.collection("conversation_contexts").document(session_hash).get
        )
        if not snapshot.exists:
            return None
        context = ConversationContext.model_validate(snapshot.to_dict())
        if context.expires_at <= datetime.now(UTC):
            return None
        return context

    async def put_context(self, context: ConversationContext) -> None:
        await asyncio.to_thread(
            self.client.collection("conversation_contexts").document(context.session_hash).set,
            context.model_dump(mode="python"),
        )
