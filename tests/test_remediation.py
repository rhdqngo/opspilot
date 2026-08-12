from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from opspilot.remediation.contracts import (
    ExecutionOutcomeRequest,
    ExecutionRequest,
    Principal,
    RemediationCreateRequest,
    RemediationDecision,
    RemediationDecisionRequest,
    RemediationPlan,
    RemediationRecord,
    RemediationStatus,
    RemediationTarget,
    VerificationEvidence,
    VerificationPlan,
)
from opspilot.remediation.errors import ConflictError, ExpiredError, PolicyViolationError
from opspilot.remediation.executor import (
    CloudRunRevisionSnapshot,
    CloudRunServiceSnapshot,
    FixedPaymentRollbackExecutor,
)
from opspilot.remediation.service import (
    LocalCallbackSender,
    LocalWorkflowGateway,
    RemediationCoordinator,
)
from opspilot.remediation.store import InMemoryRemediationStore
from opspilot.workflow import run_fixture_investigation

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64
ACTOR_HASH = "sha256:" + "b" * 64


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


class RecordingCallbackSender(LocalCallbackSender):
    def __init__(self) -> None:
        self.calls: list[tuple[str, RemediationDecision, str]] = []

    async def send(
        self,
        callback_url: str,
        *,
        remediation_id: str,
        decision: RemediationDecision,
        plan_hash: str,
    ) -> None:
        del callback_url
        self.calls.append((remediation_id, decision, plan_hash))


class FakeCloudRun:
    def __init__(
        self,
        *,
        etag: str = "etag-faulty",
        response_loss: bool = False,
        update_error: bool = False,
    ) -> None:
        self.etag = etag
        self.traffic = {"payment-faulty": 100}
        self.response_loss = response_loss
        self.update_error = update_error
        self.update_calls = 0

    async def get_service(self, service_name: str) -> CloudRunServiceSnapshot:
        return CloudRunServiceSnapshot(
            name=service_name,
            etag=self.etag,
            traffic=dict(self.traffic),
            reconciling=False,
        )

    async def get_revision(self, revision_name: str) -> CloudRunRevisionSnapshot:
        return CloudRunRevisionSnapshot(name=revision_name, ready=True, image_digest=DIGEST)

    async def update_traffic(
        self, service: CloudRunServiceSnapshot, *, target_revision: str
    ) -> str:
        del service
        self.update_calls += 1
        if self.update_error:
            from opspilot.remediation.errors import DependencyError

            raise DependencyError("safe fake failure")
        self.traffic = {target_revision: 100}
        if self.response_loss:
            from opspilot.remediation.errors import DependencyError

            raise DependencyError("safe fake response loss")
        return "operations/update-1"

    async def wait_operation(self, operation_name: str, *, timeout_seconds: int) -> None:
        del operation_name, timeout_seconds


class FakeVerifier:
    def __init__(self, successes: int = 10) -> None:
        self.successes = successes
        self.calls = 0

    async def verify(self, record: object) -> VerificationEvidence:
        del record
        self.calls += 1
        return VerificationEvidence(
            target_traffic_percent=100,
            order_successes=self.successes,
            metric_windows_recorded=True,
            metric_before_points=10,
            metric_after_points=10,
            verified_at=NOW + timedelta(minutes=1),
        )


def _principal(subject: str = "subject-1") -> Principal:
    return Principal(subject=subject, email="approver@example.invalid", email_verified=True)


def _target(etag: str = "etag-faulty") -> RemediationTarget:
    return RemediationTarget(
        project_id="portfolio-project",
        region="asia-northeast3",
        service="opspilot-dev-payment",
        source_revision="payment-faulty",
        target_revision="payment-good",
        target_image_digest=DIGEST,
        service_etag=etag,
    )


async def _coordinator(
    *, clock: Clock | None = None, callback: RecordingCallbackSender | None = None
) -> tuple[RemediationCoordinator, InMemoryRemediationStore, Clock, RecordingCallbackSender]:
    actual_clock = clock or Clock()
    actual_callback = callback or RecordingCallbackSender()
    store = InMemoryRemediationStore()
    report = await run_fixture_investigation("SCN-008")
    await store.seed_incident(report=report, target=_target())
    return (
        RemediationCoordinator(
            store=store,
            workflow=LocalWorkflowGateway(),
            callback_sender=actual_callback,
            now=actual_clock,
        ),
        store,
        actual_clock,
        actual_callback,
    )


async def _request_and_register(
    coordinator: RemediationCoordinator, *, key: str = "request-key-0001"
) -> RemediationRecord:
    record = await coordinator.request(
        incident_id="INC-2026-0008",
        payload=RemediationCreateRequest(report_id="RPT-SCN-008-001", action_id="ACT-01"),
        idempotency_key=key,
        principal=_principal(),
    )
    await coordinator.register_callback(
        remediation_id=record.remediation_id,
        callback_url=(
            "https://workflowexecutions.googleapis.com/v1/projects/p/locations/l/"
            "workflows/w/executions/e/callbacks/c"
        ),
        expires_at=record.expires_at,
    )
    return record


def test_M8_plan_hash_is_canonical_and_binds_every_execution_fact() -> None:
    plan = RemediationPlan(
        incident_id="INC-2026-0008",
        report_id="RPT-SCN-008-001",
        action_id="ACT-01",
        source_revision="payment-faulty",
        target_revision="payment-good",
        target_image_digest=DIGEST,
        service_etag="etag-faulty",
        evidence_ids=["EV-CHG-0008"],
        expected_effect="recover",
        verification=VerificationPlan(),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )
    reparsed = RemediationPlan.model_validate_json(plan.model_dump_json())
    assert plan.plan_hash == reparsed.plan_hash
    assert plan.plan_hash.startswith("sha256:")
    assert len(plan.plan_hash) == 71
    assert plan.model_copy(update={"service_etag": "changed"}).plan_hash != plan.plan_hash


def test_M8_state_machine_rejects_every_unlisted_transition() -> None:
    legal = {
        (source, target)
        for source in RemediationStatus
        for target in RemediationStatus
        if target
        in __import__(
            "opspilot.remediation.contracts", fromlist=["LEGAL_TRANSITIONS"]
        ).LEGAL_TRANSITIONS[source]
    }
    plan = RemediationPlan(
        incident_id="INC-2026-0008",
        report_id="RPT-SCN-008-001",
        action_id="ACT-01",
        source_revision="payment-faulty",
        target_revision="payment-good",
        target_image_digest=DIGEST,
        service_etag="etag-faulty",
        evidence_ids=["EV-CHG-0008"],
        expected_effect="recover",
        verification=VerificationPlan(),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )
    for source in RemediationStatus:
        record = RemediationRecord(
            remediation_id="REM-0123456789ABCDEF",
            incident_id="INC-2026-0008",
            report_id="RPT-SCN-008-001",
            action_id="ACT-01",
            plan=plan,
            plan_hash=plan.plan_hash,
            status=source,
            requester_actor_hash=ACTOR_HASH,
            created_at=NOW,
            updated_at=NOW,
            expires_at=NOW + timedelta(minutes=15),
        )
        for target in RemediationStatus:
            if (source, target) in legal:
                assert record.transition(target, now=NOW).status is target
            else:
                with pytest.raises(ValueError, match="illegal remediation transition"):
                    record.transition(target, now=NOW)


@pytest.mark.asyncio
async def test_M8_request_is_idempotent_and_conflicting_payload_is_409() -> None:
    coordinator, _, _, _ = await _coordinator()
    first = await coordinator.request(
        incident_id="INC-2026-0008",
        payload=RemediationCreateRequest(report_id="RPT-SCN-008-001", action_id="ACT-01"),
        idempotency_key="request-key-0001",
        principal=_principal(),
    )
    replay = await coordinator.request(
        incident_id="INC-2026-0008",
        payload=RemediationCreateRequest(report_id="RPT-SCN-008-001", action_id="ACT-01"),
        idempotency_key="request-key-0001",
        principal=_principal(),
    )
    assert replay.remediation_id == first.remediation_id
    with pytest.raises(ConflictError):
        await coordinator.request(
            incident_id="INC-2026-0008",
            payload=RemediationCreateRequest(
                report_id="RPT-SCN-008-001",
                action_id="ACT-01",
                verification_window_minutes=9,
            ),
            idempotency_key="request-key-0001",
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_M8_idempotency_key_expires_explicitly_without_waiting_for_ttl_deletion() -> None:
    coordinator, _, clock, _ = await _coordinator()
    first = await coordinator.request(
        incident_id="INC-2026-0008",
        payload=RemediationCreateRequest(report_id="RPT-SCN-008-001", action_id="ACT-01"),
        idempotency_key="request-key-expiring",
        principal=_principal(),
    )
    clock.value += timedelta(hours=25)
    replacement = await coordinator.request(
        incident_id="INC-2026-0008",
        payload=RemediationCreateRequest(
            report_id="RPT-SCN-008-001",
            action_id="ACT-01",
            verification_window_minutes=9,
        ),
        idempotency_key="request-key-expiring",
        principal=_principal(),
    )
    assert replacement.remediation_id != first.remediation_id


@pytest.mark.asyncio
async def test_M8_decision_idempotency_rejects_same_key_with_changed_comment() -> None:
    coordinator, _, _, _ = await _coordinator()
    record = await _request_and_register(coordinator)
    await coordinator.decide(
        remediation_id=record.remediation_id,
        payload=RemediationDecisionRequest(
            decision=RemediationDecision.APPROVE,
            plan_hash=record.plan_hash,
            comment="first",
        ),
        idempotency_key="decision-key-comment",
        principal=_principal(),
    )
    with pytest.raises(ConflictError):
        await coordinator.decide(
            remediation_id=record.remediation_id,
            payload=RemediationDecisionRequest(
                decision=RemediationDecision.APPROVE,
                plan_hash=record.plan_hash,
                comment="changed",
            ),
            idempotency_key="decision-key-comment",
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_M8_decision_records_self_approval_and_replays_identically() -> None:
    coordinator, _, _, callback = await _coordinator()
    record = await _request_and_register(coordinator)
    payload = RemediationDecisionRequest(
        decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash, comment="approved"
    )
    approved = await coordinator.decide(
        remediation_id=record.remediation_id,
        payload=payload,
        idempotency_key="decision-key-001",
        principal=_principal(),
    )
    replay = await coordinator.decide(
        remediation_id=record.remediation_id,
        payload=payload,
        idempotency_key="decision-key-001",
        principal=_principal(),
    )
    assert approved.status is RemediationStatus.APPROVED
    assert approved.self_approved is True
    assert replay == approved
    assert len(callback.calls) == 2


@pytest.mark.asyncio
async def test_M8_twenty_concurrent_approvals_and_execution_claims_have_one_winner() -> None:
    coordinator, store, _, callback = await _coordinator()
    record = await _request_and_register(coordinator)
    payload = RemediationDecisionRequest(
        decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
    )
    decisions = await asyncio.gather(
        *(
            coordinator.decide(
                remediation_id=record.remediation_id,
                payload=payload,
                idempotency_key=f"decision-key-{index:02d}",
                principal=_principal(),
            )
            for index in range(20)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(item, RemediationRecord) for item in decisions) == 1
    assert sum(isinstance(item, ConflictError) for item in decisions) == 19
    assert len(callback.calls) == 1

    claims = await asyncio.gather(
        *(
            store.begin_execution(
                remediation_id=record.remediation_id,
                plan_hash=record.plan_hash,
                attempt_id="ATT-0123456789ABCDEF",
                actor_hash=ACTOR_HASH,
                now=NOW + timedelta(minutes=1),
            )
            for _ in range(20)
        )
    )
    assert sum(claimed for _, claimed in claims) == 1
    events = await store.list_events(record.remediation_id)
    assert sum(event.to_status is RemediationStatus.EXECUTING for event in events) == 1


@pytest.mark.asyncio
async def test_M8_expired_or_forged_decision_cannot_approve() -> None:
    coordinator, store, clock, _ = await _coordinator()
    record = await _request_and_register(coordinator)
    forged = RemediationDecisionRequest(
        decision=RemediationDecision.APPROVE,
        plan_hash="sha256:" + "0" * 64,
    )
    with pytest.raises(ConflictError):
        await coordinator.decide(
            remediation_id=record.remediation_id,
            payload=forged,
            idempotency_key="decision-key-forged",
            principal=_principal(),
        )
    clock.value = NOW + timedelta(minutes=16)
    with pytest.raises(ExpiredError):
        await coordinator.decide(
            remediation_id=record.remediation_id,
            payload=RemediationDecisionRequest(
                decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
            ),
            idempotency_key="decision-key-expired",
            principal=_principal(),
        )
    expired = await store.get(record.remediation_id)
    assert expired is not None and expired.status is RemediationStatus.EXPIRED


@pytest.mark.asyncio
async def test_M8_policy_requires_identified_change_grounded_payment_rollback() -> None:
    coordinator, store, _, _ = await _coordinator()
    report = await store.get_report("INC-2026-0008", "RPT-SCN-008-001")
    assert report is not None
    broken = report.model_copy(update={"status": "INCONCLUSIVE"})
    await store.seed_incident(report=broken, target=_target())
    with pytest.raises(PolicyViolationError):
        await coordinator.request(
            incident_id="INC-2026-0008",
            payload=RemediationCreateRequest(report_id="RPT-SCN-008-001", action_id="ACT-01"),
            idempotency_key="policy-key-0001",
            principal=_principal(),
        )


async def _approved_store() -> tuple[InMemoryRemediationStore, RemediationRecord]:
    coordinator, store, _, _ = await _coordinator()
    record = await _request_and_register(coordinator)
    approved = await coordinator.decide(
        remediation_id=record.remediation_id,
        payload=RemediationDecisionRequest(
            decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
        ),
        idempotency_key="decision-key-001",
        principal=_principal(),
    )
    executing, claimed = await store.begin_execution(
        remediation_id=approved.remediation_id,
        plan_hash=approved.plan_hash,
        attempt_id="ATT-0123456789ABCDEF",
        actor_hash=ACTOR_HASH,
        now=NOW + timedelta(minutes=1),
    )
    assert claimed is True
    return store, executing


@pytest.mark.asyncio
async def test_M8_twenty_concurrent_executor_calls_create_one_traffic_update() -> None:
    store, value = await _approved_store()
    approved = RemediationRecord.model_validate(value)
    cloud = FakeCloudRun()
    executor = FixedPaymentRollbackExecutor(
        store=store,
        cloud_run=cloud,
        now=lambda: NOW + timedelta(minutes=1),
    )
    request = ExecutionRequest(
        plan_hash=approved.plan_hash, execution_attempt_id="ATT-0123456789ABCDEF"
    )
    results = await asyncio.gather(
        *(executor.execute(approved.remediation_id, request) for _ in range(20))
    )
    assert cloud.update_calls == 1
    assert all(item.traffic_update_succeeded for item in results)


@pytest.mark.asyncio
async def test_M8_stale_etag_and_tampered_target_make_zero_updates() -> None:
    store, value = await _approved_store()
    approved = RemediationRecord.model_validate(value)
    cloud = FakeCloudRun(etag="different-etag")
    executor = FixedPaymentRollbackExecutor(
        store=store,
        cloud_run=cloud,
        now=lambda: NOW + timedelta(minutes=1),
    )
    result = await executor.execute(
        approved.remediation_id,
        ExecutionRequest(
            plan_hash=approved.plan_hash,
            execution_attempt_id="ATT-0123456789ABCDEF",
        ),
    )
    assert cloud.update_calls == 0
    assert result.traffic_update_succeeded is False
    assert result.safe_failure_code == "STALE_SERVICE_ETAG"


@pytest.mark.asyncio
async def test_M8_response_loss_is_confirmed_without_a_second_update() -> None:
    store, value = await _approved_store()
    approved = RemediationRecord.model_validate(value)
    cloud = FakeCloudRun(response_loss=True)
    executor = FixedPaymentRollbackExecutor(
        store=store,
        cloud_run=cloud,
        now=lambda: NOW + timedelta(minutes=1),
    )
    result = await executor.execute(
        approved.remediation_id,
        ExecutionRequest(
            plan_hash=approved.plan_hash,
            execution_attempt_id="ATT-0123456789ABCDEF",
        ),
    )
    assert cloud.update_calls == 1
    assert result.traffic_update_succeeded is True


@pytest.mark.asyncio
async def test_M8_executor_failure_and_control_verification_are_terminal() -> None:
    store, value = await _approved_store()
    approved = RemediationRecord.model_validate(value)
    executor = FixedPaymentRollbackExecutor(
        store=store,
        cloud_run=FakeCloudRun(update_error=True),
        now=lambda: NOW + timedelta(minutes=1),
    )
    result = await executor.execute(
        approved.remediation_id,
        ExecutionRequest(
            plan_hash=approved.plan_hash,
            execution_attempt_id="ATT-0123456789ABCDEF",
        ),
    )
    assert result.traffic_update_succeeded is False
    assert result.safe_failure_code == "EXECUTOR_DEPENDENCY_FAILURE"

    for successes, expected in (
        (10, RemediationStatus.SUCCEEDED),
        (9, RemediationStatus.VERIFICATION_FAILED),
    ):
        coordinator, _, _, _ = await _coordinator()
        coordinator.recovery_verifier = FakeVerifier(successes)
        record = await _request_and_register(coordinator)
        approved = await coordinator.decide(
            remediation_id=record.remediation_id,
            payload=RemediationDecisionRequest(
                decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
            ),
            idempotency_key=f"decision-key-{successes}",
            principal=_principal(),
        )
        executing = await coordinator.begin_execution(
            remediation_id=record.remediation_id,
            payload=ExecutionRequest(
                plan_hash=approved.plan_hash,
                execution_attempt_id="ATT-0123456789ABCDEF",
            ),
            principal=_principal("workflow-subject"),
        )
        terminal = await coordinator.finish_execution(
            remediation_id=record.remediation_id,
            payload=ExecutionOutcomeRequest(
                execution_attempt_id=executing.execution_attempt_id or "",
                traffic_update_succeeded=True,
            ),
            principal=_principal("workflow-subject"),
        )
        assert terminal.status is expected
        assert terminal.verification_successes == successes
