"""Versioned deterministic release gate for the bounded M8 remediation policy."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from opspilot.domain import Environment
from opspilot.remediation.contracts import (
    ExecutionOutcomeRequest,
    ExecutionRequest,
    Principal,
    RemediationCreateRequest,
    RemediationDecision,
    RemediationDecisionRequest,
    RemediationRecord,
    RemediationStatus,
    RemediationTarget,
    VerificationEvidence,
)
from opspilot.remediation.errors import ConflictError, DependencyError, ExpiredError
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


class EvaluationCondition(StrEnum):
    APPROVED_SUCCESS = "approved_success"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FORGED_HASH = "forged_hash"
    STALE_ETAG = "stale_etag"
    WRONG_SERVICE = "wrong_service"
    TAMPERED_REVISION = "tampered_revision"
    IDEMPOTENT_REPLAY = "idempotent_replay"
    CONCURRENT_APPROVAL = "concurrent_approval"
    EXECUTOR_403 = "executor_403"
    RESPONSE_LOSS = "response_loss"
    VERIFICATION_FAILED = "verification_failed"


class RemediationEvaluationCase(BaseModel):
    case_id: str = Field(pattern=r"^REM-EVAL-\d{2}$")
    condition: EvaluationCondition
    expected_status: RemediationStatus
    expected_update_count: int = Field(ge=0, le=1)


class RemediationEvaluationSuite(BaseModel):
    suite: Literal["remediation"]
    suite_version: Literal["remediation-v1"]
    cases: list[RemediationEvaluationCase] = Field(min_length=12)

    @model_validator(mode="after")
    def validate_suite(self) -> RemediationEvaluationSuite:
        if len(self.cases) != 12:
            raise ValueError("remediation-v1 must contain exactly 12 cases")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("remediation evaluation case IDs must be unique")
        return self


class RemediationEvaluationCaseResult(BaseModel):
    case_id: str
    passed: bool
    actual_status: RemediationStatus
    actual_update_count: int = Field(ge=0, le=1)


class RemediationEvaluationResult(BaseModel):
    suite: str
    suite_version: str
    executed_cases: int
    passed_cases: int
    passed: bool
    cases: list[RemediationEvaluationCaseResult]


EVAL_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
EVAL_DIGEST = "sha256:" + "a" * 64


class _EvalClock:
    def __init__(self) -> None:
        self.value = EVAL_NOW

    def __call__(self) -> datetime:
        return self.value


class _EvalCloudRun:
    def __init__(
        self,
        *,
        stale_etag: bool = False,
        wrong_service: bool = False,
        dependency_failure: bool = False,
        response_loss: bool = False,
    ) -> None:
        self.etag = "stale-etag" if stale_etag else "etag-faulty"
        self.wrong_service = wrong_service
        self.dependency_failure = dependency_failure
        self.response_loss = response_loss
        self.traffic = {"payment-faulty": 100}
        self.update_count = 0

    async def get_service(self, service_name: str) -> CloudRunServiceSnapshot:
        if self.dependency_failure:
            raise DependencyError("simulated dependency failure")
        return CloudRunServiceSnapshot(
            name=f"{service_name}-other" if self.wrong_service else service_name,
            etag=self.etag,
            traffic=dict(self.traffic),
        )

    async def get_revision(self, revision_name: str) -> CloudRunRevisionSnapshot:
        return CloudRunRevisionSnapshot(name=revision_name, ready=True, image_digest=EVAL_DIGEST)

    async def update_traffic(
        self, service: CloudRunServiceSnapshot, *, target_revision: str
    ) -> str:
        del service
        self.update_count += 1
        self.traffic = {target_revision: 100}
        if self.response_loss:
            raise DependencyError("simulated response loss")
        return "operations/eval-update"

    async def wait_operation(self, operation_name: str, *, timeout_seconds: int) -> None:
        del operation_name, timeout_seconds


class _EvalRecoveryVerifier:
    def __init__(self, successes: int = 10) -> None:
        self.successes = successes

    async def verify(self, record: RemediationRecord) -> VerificationEvidence:
        return VerificationEvidence(
            target_traffic_percent=100,
            order_successes=self.successes,
            metric_windows_recorded=True,
            metric_before_points=10,
            metric_after_points=10,
            verified_at=record.updated_at + timedelta(seconds=1),
        )


def _eval_target(*, source_revision: str = "payment-faulty") -> RemediationTarget:
    return RemediationTarget(
        project_id="portfolio-project",
        region="asia-northeast3",
        service="opspilot-prod-sim-payment",
        source_revision=source_revision,
        target_revision="payment-good",
        target_image_digest=EVAL_DIGEST,
        service_etag="etag-faulty",
    )


def _eval_principal() -> Principal:
    return Principal(
        subject="remediation-eval-subject",
        email="eval@example.invalid",
        email_verified=True,
    )


async def _evaluate_case(
    case: RemediationEvaluationCase,
) -> RemediationEvaluationCaseResult:
    clock = _EvalClock()
    store = InMemoryRemediationStore()
    report = (await run_fixture_investigation("SCN-008")).model_copy(
        update={"environment": Environment.PROD_SIM}
    )
    await store.seed_incident(report=report, target=_eval_target())
    verifier_successes = 9 if case.condition is EvaluationCondition.VERIFICATION_FAILED else 10
    coordinator = RemediationCoordinator(
        store=store,
        workflow=LocalWorkflowGateway(),
        callback_sender=LocalCallbackSender(),
        recovery_verifier=_EvalRecoveryVerifier(verifier_successes),
        now=clock,
    )
    record = await coordinator.request(
        incident_id="INC-2026-0008",
        payload=RemediationCreateRequest(report_id="RPT-SCN-008-001", action_id="ACT-01"),
        idempotency_key=f"request-{case.case_id}",
        principal=_eval_principal(),
    )
    await coordinator.register_callback(
        remediation_id=record.remediation_id,
        callback_url=(
            "https://workflowexecutions.googleapis.com/v1/projects/p/locations/l/"
            "workflows/w/executions/e/callbacks/c"
        ),
        expires_at=record.expires_at,
    )
    cloud = _EvalCloudRun(
        stale_etag=case.condition is EvaluationCondition.STALE_ETAG,
        wrong_service=case.condition is EvaluationCondition.WRONG_SERVICE,
        dependency_failure=case.condition is EvaluationCondition.EXECUTOR_403,
        response_loss=case.condition is EvaluationCondition.RESPONSE_LOSS,
    )

    if case.condition is EvaluationCondition.REJECTED:
        final = await coordinator.decide(
            remediation_id=record.remediation_id,
            payload=RemediationDecisionRequest(
                decision=RemediationDecision.REJECT, plan_hash=record.plan_hash
            ),
            idempotency_key=f"decision-{case.case_id}",
            principal=_eval_principal(),
        )
        return _case_result(case, final.status, cloud.update_count)
    if case.condition is EvaluationCondition.EXPIRED:
        clock.value += timedelta(minutes=16)
        try:
            await coordinator.decide(
                remediation_id=record.remediation_id,
                payload=RemediationDecisionRequest(
                    decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
                ),
                idempotency_key=f"decision-{case.case_id}",
                principal=_eval_principal(),
            )
        except ExpiredError:
            pass
        final = await coordinator.show(record.remediation_id)
        return _case_result(case, final.status, cloud.update_count)
    if case.condition is EvaluationCondition.FORGED_HASH:
        try:
            await coordinator.decide(
                remediation_id=record.remediation_id,
                payload=RemediationDecisionRequest(
                    decision=RemediationDecision.APPROVE,
                    plan_hash="sha256:" + "0" * 64,
                ),
                idempotency_key=f"decision-{case.case_id}",
                principal=_eval_principal(),
            )
        except ConflictError:
            pass
        final = await coordinator.show(record.remediation_id)
        return _case_result(case, final.status, cloud.update_count)

    if case.condition is EvaluationCondition.CONCURRENT_APPROVAL:
        decisions = await asyncio.gather(
            *(
                coordinator.decide(
                    remediation_id=record.remediation_id,
                    payload=RemediationDecisionRequest(
                        decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
                    ),
                    idempotency_key=f"decision-{case.case_id}-{index}",
                    principal=_eval_principal(),
                )
                for index in range(20)
            ),
            return_exceptions=True,
        )
        approved_values = [item for item in decisions if isinstance(item, RemediationRecord)]
        if len(approved_values) != 1:
            raise RuntimeError("concurrent approval evaluation did not have one winner")
        approved = approved_values[0]
    else:
        approved = await coordinator.decide(
            remediation_id=record.remediation_id,
            payload=RemediationDecisionRequest(
                decision=RemediationDecision.APPROVE, plan_hash=record.plan_hash
            ),
            idempotency_key=f"decision-{case.case_id}",
            principal=_eval_principal(),
        )
    executing = await coordinator.begin_execution(
        remediation_id=record.remediation_id,
        payload=ExecutionRequest(
            plan_hash=approved.plan_hash,
            execution_attempt_id="ATT-EVALUATION-0001",
        ),
        principal=_eval_principal(),
    )
    if case.condition is EvaluationCondition.TAMPERED_REVISION:
        await store.seed_incident(report=report, target=_eval_target(source_revision="tampered"))
    executor = FixedPaymentRollbackExecutor(
        store=store,
        cloud_run=cloud,
        now=lambda: EVAL_NOW + timedelta(minutes=1),
    )
    request = ExecutionRequest(
        plan_hash=executing.plan_hash,
        execution_attempt_id="ATT-EVALUATION-0001",
    )
    if case.condition is EvaluationCondition.CONCURRENT_APPROVAL:
        outcomes = await asyncio.gather(
            *(executor.execute(record.remediation_id, request) for _ in range(20))
        )
        outcome = outcomes[0]
    else:
        outcome = await executor.execute(record.remediation_id, request)
        if case.condition is EvaluationCondition.IDEMPOTENT_REPLAY:
            outcome = await executor.execute(record.remediation_id, request)
    final = await coordinator.finish_execution(
        remediation_id=record.remediation_id,
        payload=ExecutionOutcomeRequest(
            execution_attempt_id=outcome.execution_attempt_id,
            traffic_update_succeeded=outcome.traffic_update_succeeded,
            safe_failure_code=outcome.safe_failure_code,
        ),
        principal=_eval_principal(),
    )
    return _case_result(case, final.status, cloud.update_count)


def _case_result(
    case: RemediationEvaluationCase, status: RemediationStatus, update_count: int
) -> RemediationEvaluationCaseResult:
    return RemediationEvaluationCaseResult(
        case_id=case.case_id,
        passed=status is case.expected_status and update_count == case.expected_update_count,
        actual_status=status,
        actual_update_count=update_count,
    )


async def _evaluate_suite(
    cases: list[RemediationEvaluationCase],
) -> list[RemediationEvaluationCaseResult]:
    return list(await asyncio.gather(*(_evaluate_case(case) for case in cases)))


def load_remediation_suite(root: Path | None = None) -> RemediationEvaluationSuite:
    path = (root or Path.cwd() / "scenarios" / "evaluation") / "remediation-v1.json"
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    return RemediationEvaluationSuite.model_validate(payload)


def run_remediation_evaluation(root: Path | None = None) -> RemediationEvaluationResult:
    suite = load_remediation_suite(root)
    results = asyncio.run(_evaluate_suite(suite.cases))
    passed_cases = sum(case.passed for case in results)
    return RemediationEvaluationResult(
        suite=suite.suite,
        suite_version=suite.suite_version,
        executed_cases=len(results),
        passed_cases=passed_cases,
        passed=passed_cases == len(results),
        cases=results,
    )


def render_remediation_evaluation(result: RemediationEvaluationResult, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(result.model_dump(mode="json"), indent=2) + "\n"
    lines = [
        f"suite: {result.suite}",
        f"suite_version: {result.suite_version}",
        f"executed_cases: {result.executed_cases}",
        f"passed_cases: {result.passed_cases}",
        "gate_failures: "
        f"{'none' if result.passed else result.executed_cases - result.passed_cases}",
    ]
    lines.extend(f"{case.case_id}: {'pass' if case.passed else 'fail'}" for case in result.cases)
    return "\n".join([*lines, ""])
