"""Policy, idempotency, and approval orchestration for M8 remediation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from opspilot.domain import (
    EvidenceDirection,
    IncidentReport,
    RecommendedAction,
    ReportStatus,
    SourceType,
)
from opspilot.remediation.contracts import (
    APPROVAL_TTL,
    IDEMPOTENCY_TTL,
    CallbackRegistration,
    ExecutionOutcomeRequest,
    ExecutionRequest,
    Principal,
    RemediationCreateRequest,
    RemediationDecision,
    RemediationDecisionRequest,
    RemediationEvent,
    RemediationPlan,
    RemediationRecord,
    RemediationStatus,
    RemediationTarget,
    VerificationEvidence,
    VerificationPlan,
    canonical_request_digest,
    utc_now,
)
from opspilot.remediation.errors import (
    ConflictError,
    DependencyError,
    NotFoundError,
    PolicyViolationError,
)
from opspilot.remediation.store import RemediationStore


class WorkflowGateway(Protocol):
    async def start(self, remediation_id: str, expires_at: datetime) -> str: ...


class CallbackSender(Protocol):
    async def send(
        self,
        callback_url: str,
        *,
        remediation_id: str,
        decision: RemediationDecision,
        plan_hash: str,
    ) -> None: ...


class RecoveryVerifier(Protocol):
    async def verify(self, record: RemediationRecord) -> VerificationEvidence: ...


class LocalWorkflowGateway:
    """Non-cloud workflow stand-in used only by injected local/test apps."""

    async def start(self, remediation_id: str, expires_at: datetime) -> str:
        del expires_at
        return f"local-workflow/{remediation_id}"


class LocalCallbackSender:
    async def send(
        self,
        callback_url: str,
        *,
        remediation_id: str,
        decision: RemediationDecision,
        plan_hash: str,
    ) -> None:
        del callback_url, remediation_id, decision, plan_hash


class RemediationCoordinator:
    def __init__(
        self,
        *,
        store: RemediationStore,
        workflow: WorkflowGateway,
        callback_sender: CallbackSender,
        recovery_verifier: RecoveryVerifier | None = None,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.store = store
        self.workflow = workflow
        self.callback_sender = callback_sender
        self.recovery_verifier = recovery_verifier
        self.now = now

    async def request(
        self,
        *,
        incident_id: str,
        payload: RemediationCreateRequest,
        idempotency_key: str,
        principal: Principal | None = None,
        requester_actor_hash: str | None = None,
    ) -> RemediationRecord:
        actor_hash = requester_actor_hash or (principal.actor_hash if principal else None)
        if actor_hash is None or not actor_hash.startswith("sha256:"):
            raise PolicyViolationError("a pseudonymous requester identity is required")
        report = await self.store.get_report(incident_id, payload.report_id, payload.report_version)
        if report is None:
            raise NotFoundError("incident report not found")
        target = await self.store.get_target(incident_id)
        if target is None:
            raise PolicyViolationError("incident has no trusted rollback target")
        action = next(
            (item for item in report.recommended_actions if item.action_id == payload.action_id),
            None,
        )
        if action is None:
            raise NotFoundError("report action not found")
        self._validate_policy(
            report_status=report.status,
            action=action,
            report=report,
            target=target,
        )

        now = self.now()
        expires_at = now + APPROVAL_TTL
        plan = RemediationPlan(
            incident_id=incident_id,
            report_id=report.report_id,
            action_id=action.action_id,
            source_revision=target.source_revision,
            target_revision=target.target_revision,
            target_image_digest=target.target_image_digest,
            service_etag=target.service_etag,
            evidence_ids=sorted(action.supporting_evidence_ids),
            expected_effect=action.expected_effect,
            verification=VerificationPlan(window_minutes=payload.verification_window_minutes),
            created_at=now,
            expires_at=expires_at,
        )
        remediation_id = f"REM-{uuid4().hex[:16].upper()}"
        record = RemediationRecord(
            remediation_id=remediation_id,
            incident_id=incident_id,
            report_id=report.report_id,
            action_id=action.action_id,
            plan=plan,
            plan_hash=plan.plan_hash,
            status=RemediationStatus.WAITING_APPROVAL,
            requester_actor_hash=actor_hash,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        event = RemediationEvent(
            event_id="EVT-0001",
            remediation_id=remediation_id,
            occurred_at=now,
            event_type="POLICY_ACCEPTED",
            from_status=RemediationStatus.PROPOSED,
            to_status=RemediationStatus.WAITING_APPROVAL,
            actor_hash=actor_hash,
            plan_hash=plan.plan_hash,
        )
        digest = canonical_request_digest(operation="request", path_id=incident_id, payload=payload)
        stored, created = await self.store.create(
            record=record,
            event=event,
            idempotency_key=f"request:{idempotency_key}",
            request_digest=digest,
            idempotency_expires_at=now + IDEMPOTENCY_TTL,
        )
        if not created:
            return stored
        workflow_execution = await self.workflow.start(stored.remediation_id, stored.expires_at)
        return await self.store.set_workflow_execution(
            stored.remediation_id, workflow_execution, self.now()
        )

    async def show(self, remediation_id: str) -> RemediationRecord:
        record = await self.store.get(remediation_id)
        if record is None:
            raise NotFoundError("remediation not found")
        return record

    async def register_callback(
        self,
        *,
        remediation_id: str,
        callback_url: str,
        expires_at: datetime,
    ) -> None:
        await self.store.register_callback(
            CallbackRegistration(
                remediation_id=remediation_id,
                callback_url=callback_url,
                approval_expires_at=expires_at,
                expires_at=self.now() + IDEMPOTENCY_TTL,
            )
        )

    async def decide(
        self,
        *,
        remediation_id: str,
        payload: RemediationDecisionRequest,
        idempotency_key: str,
        principal: Principal,
    ) -> RemediationRecord:
        callback = await self.store.get_callback(remediation_id)
        if callback is None:
            raise ConflictError("approval workflow callback is not ready")
        now = self.now()
        digest = canonical_request_digest(
            operation="decision", path_id=remediation_id, payload=payload
        )

        def event_factory(
            previous: RemediationRecord, updated: RemediationRecord
        ) -> RemediationEvent:
            expired = updated.status is RemediationStatus.EXPIRED
            return RemediationEvent(
                event_id="EVT-0002",
                remediation_id=remediation_id,
                occurred_at=now,
                event_type="APPROVAL_TIMEOUT" if expired else "APPROVAL_DECISION",
                from_status=previous.status,
                to_status=updated.status,
                actor_hash=principal.actor_hash,
                self_approved=updated.self_approved,
                plan_hash=updated.plan_hash,
                result_code="APPROVAL_TIMEOUT" if expired else payload.decision.value,
            )

        updated = await self.store.decide(
            remediation_id=remediation_id,
            decision=payload.decision,
            plan_hash=payload.plan_hash,
            actor_hash=principal.actor_hash,
            now=now,
            idempotency_key=f"decision:{idempotency_key}",
            request_digest=digest,
            idempotency_expires_at=now + IDEMPOTENCY_TTL,
            event_factory=event_factory,
        )
        await self.callback_sender.send(
            callback.callback_url,
            remediation_id=remediation_id,
            decision=payload.decision,
            plan_hash=payload.plan_hash,
        )
        return updated

    async def expire(self, *, remediation_id: str, principal: Principal) -> RemediationRecord:
        return await self.store.expire(
            remediation_id=remediation_id,
            actor_hash=principal.actor_hash,
            now=self.now(),
        )

    async def begin_execution(
        self,
        *,
        remediation_id: str,
        payload: ExecutionRequest,
        principal: Principal,
    ) -> RemediationRecord:
        record, _ = await self.store.begin_execution(
            remediation_id=remediation_id,
            plan_hash=payload.plan_hash,
            attempt_id=payload.execution_attempt_id,
            actor_hash=principal.actor_hash,
            now=self.now(),
        )
        return record

    async def finish_execution(
        self,
        *,
        remediation_id: str,
        payload: ExecutionOutcomeRequest,
        principal: Principal,
    ) -> RemediationRecord:
        status = RemediationStatus.EXECUTION_FAILED
        verification: VerificationEvidence | None = None
        failure_code = payload.safe_failure_code
        if payload.traffic_update_succeeded:
            current = await self.show(remediation_id)
            if (
                current.status is not RemediationStatus.EXECUTING
                or current.execution_attempt_id != payload.execution_attempt_id
            ):
                raise ConflictError("execution attempt does not match the active lease")
            if self.recovery_verifier is None:
                status = RemediationStatus.VERIFICATION_FAILED
                failure_code = "RECOVERY_VERIFIER_NOT_CONFIGURED"
            else:
                try:
                    verification = await self.recovery_verifier.verify(current)
                except (DependencyError, TimeoutError):
                    status = RemediationStatus.VERIFICATION_FAILED
                    failure_code = "RECOVERY_VERIFICATION_UNAVAILABLE"
                else:
                    recovered = (
                        verification.target_traffic_percent == 100
                        and verification.order_attempts == 10
                        and verification.order_successes == 10
                    )
                    status = (
                        RemediationStatus.SUCCEEDED
                        if recovered
                        else RemediationStatus.VERIFICATION_FAILED
                    )
                    failure_code = None if recovered else "RECOVERY_VERIFICATION_FAILED"
        return await self.store.finish_execution(
            remediation_id=remediation_id,
            attempt_id=payload.execution_attempt_id,
            status=status,
            verification=verification,
            safe_failure_code=failure_code,
            actor_hash=principal.actor_hash,
            now=self.now(),
        )

    @staticmethod
    def _validate_policy(
        *,
        report_status: ReportStatus,
        action: RecommendedAction,
        report: IncidentReport,
        target: RemediationTarget,
    ) -> None:
        if report_status is not ReportStatus.IDENTIFIED:
            raise PolicyViolationError("report must be identified before remediation")
        if action.category != "ROLLBACK_CLOUD_RUN" or not action.requires_approval:
            raise PolicyViolationError("action is not an approval-gated Cloud Run rollback")
        if (
            report.environment.value != "prod-sim"
            or action.target_service != "payment-service"
            or target.service != "opspilot-prod-sim-payment"
        ):
            raise PolicyViolationError("only the prod-sim payment service can be remediated")
        evidence = {item.evidence_id: item for item in report.evidence}
        supporting_change = any(
            evidence_id in evidence
            and evidence[evidence_id].source_type is SourceType.CHANGE
            and evidence[evidence_id].direction is EvidenceDirection.SUPPORTS
            and evidence[evidence_id].service == "payment-service"
            for evidence_id in action.supporting_evidence_ids
        )
        if not supporting_change:
            raise PolicyViolationError("rollback requires supporting payment revision evidence")
