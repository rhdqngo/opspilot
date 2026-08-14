"""Separate authenticated control and private executor FastAPI applications."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from opspilot import __version__
from opspilot.remediation.auth import (
    GoogleIdTokenVerifier,
    TokenVerifier,
    bearer_token,
    require_service_account,
)
from opspilot.remediation.config import RemediationSettings
from opspilot.remediation.contracts import (
    ExecutionOutcomeRequest,
    ExecutionRequest,
    Principal,
    RemediationCreateRequest,
    RemediationDecisionRequest,
    RemediationRecord,
)
from opspilot.remediation.errors import RemediationError
from opspilot.remediation.executor import (
    ExecutionOutcome,
    FixedPaymentRollbackExecutor,
    GoogleCloudRunAdmin,
    GoogleControlRecoveryVerifier,
)
from opspilot.remediation.firestore_store import FirestoreRemediationStore
from opspilot.remediation.google import GoogleCallbackSender, GoogleWorkflowGateway
from opspilot.remediation.service import RemediationCoordinator

IdempotencyHeader = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


class CallbackRegistrationRequest(BaseModel):
    callback_url: str = Field(pattern=r"^https://workflowexecutions\.googleapis\.com/")
    expires_at: str


class InternalRemediationRequest(RemediationCreateRequest):
    requester_actor_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _principal(
    request: Request,
    authorization: str | None,
    *,
    audience: str,
) -> Principal:
    verifier = cast(TokenVerifier, request.app.state.token_verifier)
    return verifier.verify(bearer_token(authorization), audience=audience)


def _install_error_handler(app: FastAPI) -> None:
    @app.exception_handler(RemediationError)
    async def remediation_error_handler(_: Request, error: RemediationError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.safe_message}},
        )


def create_app(
    coordinator: RemediationCoordinator | None = None,
    token_verifier: TokenVerifier | None = None,
    settings: RemediationSettings | None = None,
) -> FastAPI:
    runtime = settings
    if coordinator is None:
        runtime = runtime or RemediationSettings()
    app = FastAPI(title="OpsPilot remediation control API", version=__version__)
    app.state.coordinator = coordinator
    app.state.token_verifier = token_verifier or GoogleIdTokenVerifier()
    app.state.settings = runtime
    _install_error_handler(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "boundary": "remediation-control"}

    @app.post(
        "/api/v1/incidents/{incident_id}/remediations",
        response_model=RemediationRecord,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def request_remediation(
        incident_id: str,
        payload: RemediationCreateRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        principal = _principal(
            request,
            authorization,
            audience=_control_audience(request),
        )
        service = _control_coordinator(request)
        return await service.request(
            incident_id=incident_id,
            payload=payload,
            idempotency_key=idempotency_key,
            principal=principal,
        )

    @app.post(
        "/internal/v1/incidents/{incident_id}/remediation-requests",
        response_model=RemediationRecord,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def request_remediation_from_investigation(
        payload: InternalRemediationRequest,
        incident_id: str,
        request: Request,
        idempotency_key: IdempotencyHeader,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        runtime_settings = cast(RemediationSettings, request.app.state.settings)
        principal = _principal(
            request,
            authorization,
            audience=_control_audience(request),
        )
        require_service_account(
            principal,
            allowed_email=runtime_settings.investigation_service_account,
        )
        service = _control_coordinator(request)
        return await service.request(
            incident_id=incident_id,
            payload=RemediationCreateRequest(
                report_id=payload.report_id,
                report_version=payload.report_version,
                action_id=payload.action_id,
                verification_window_minutes=payload.verification_window_minutes,
            ),
            idempotency_key=idempotency_key,
            requester_actor_hash=payload.requester_actor_hash,
        )

    @app.get("/api/v1/remediations/{remediation_id}", response_model=RemediationRecord)
    async def show_remediation(
        remediation_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        _principal(request, authorization, audience=_control_audience(request))
        service = _control_coordinator(request)
        return await service.show(remediation_id)

    @app.post(
        "/api/v1/remediations/{remediation_id}/decision",
        response_model=RemediationRecord,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def decide_remediation(
        remediation_id: str,
        payload: RemediationDecisionRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        principal = _principal(request, authorization, audience=_control_audience(request))
        service = _control_coordinator(request)
        return await service.decide(
            remediation_id=remediation_id,
            payload=payload,
            idempotency_key=idempotency_key,
            principal=principal,
        )

    @app.post("/internal/v1/remediations/{remediation_id}/callback", status_code=204)
    async def register_workflow_callback(
        remediation_id: str,
        payload: CallbackRegistrationRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> None:
        runtime_settings = _required_settings(request)
        principal = _principal(request, authorization, audience=runtime_settings.control_audience)
        require_service_account(principal, allowed_email=runtime_settings.workflow_service_account)
        from datetime import datetime

        expires_at = datetime.fromisoformat(payload.expires_at.replace("Z", "+00:00"))
        service = _control_coordinator(request)
        await service.register_callback(
            remediation_id=remediation_id,
            callback_url=payload.callback_url,
            expires_at=expires_at,
        )

    @app.post(
        "/internal/v1/remediations/{remediation_id}/expire",
        response_model=RemediationRecord,
    )
    async def expire_remediation(
        remediation_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        runtime_settings = _required_settings(request)
        principal = _principal(request, authorization, audience=runtime_settings.control_audience)
        require_service_account(principal, allowed_email=runtime_settings.workflow_service_account)
        service = _control_coordinator(request)
        return await service.expire(remediation_id=remediation_id, principal=principal)

    @app.post(
        "/internal/v1/remediations/{remediation_id}/begin-execution",
        response_model=RemediationRecord,
    )
    async def begin_execution(
        remediation_id: str,
        payload: ExecutionRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        runtime_settings = _required_settings(request)
        principal = _principal(request, authorization, audience=runtime_settings.control_audience)
        require_service_account(principal, allowed_email=runtime_settings.workflow_service_account)
        service = _control_coordinator(request)
        return await service.begin_execution(
            remediation_id=remediation_id, payload=payload, principal=principal
        )

    @app.post(
        "/internal/v1/remediations/{remediation_id}/finish-execution",
        response_model=RemediationRecord,
    )
    async def finish_execution(
        remediation_id: str,
        payload: ExecutionOutcomeRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> RemediationRecord:
        runtime_settings = _required_settings(request)
        principal = _principal(request, authorization, audience=runtime_settings.control_audience)
        require_service_account(principal, allowed_email=runtime_settings.workflow_service_account)
        service = _control_coordinator(request)
        return await service.finish_execution(
            remediation_id=remediation_id, payload=payload, principal=principal
        )

    return app


def create_executor_app(
    executor: FixedPaymentRollbackExecutor | None = None,
    token_verifier: TokenVerifier | None = None,
    settings: RemediationSettings | None = None,
) -> FastAPI:
    runtime = settings
    if executor is None:
        runtime = runtime or RemediationSettings()
    app = FastAPI(title="OpsPilot private remediation executor", version=__version__)
    app.state.executor = executor
    app.state.token_verifier = token_verifier or GoogleIdTokenVerifier()
    app.state.settings = runtime
    _install_error_handler(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "boundary": "remediation-executor"}

    @app.post(
        "/internal/v1/remediations/{remediation_id}/execute",
        response_model=ExecutionOutcome,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def execute_remediation(
        remediation_id: str,
        payload: ExecutionRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> ExecutionOutcome:
        runtime_settings = _required_settings(request)
        principal = _principal(request, authorization, audience=runtime_settings.executor_audience)
        require_service_account(principal, allowed_email=runtime_settings.workflow_service_account)
        service = _rollback_executor(request)
        return await service.execute(remediation_id, payload)

    return app


def _required_settings(request: Request) -> RemediationSettings:
    runtime = request.app.state.settings
    if not isinstance(runtime, RemediationSettings):
        raise HTTPException(status_code=500, detail="remediation settings are unavailable")
    return runtime


def _control_coordinator(request: Request) -> RemediationCoordinator:
    existing = request.app.state.coordinator
    if isinstance(existing, RemediationCoordinator):
        return existing
    runtime = _required_settings(request)
    store = FirestoreRemediationStore(
        project_id=runtime.project_id, database_id=runtime.database_id
    )
    created = RemediationCoordinator(
        store=store,
        workflow=GoogleWorkflowGateway(runtime.workflow_name),
        callback_sender=GoogleCallbackSender(),
        recovery_verifier=GoogleControlRecoveryVerifier(
            store=store,
            cloud_run=GoogleCloudRunAdmin(),
            project_id=runtime.project_id,
            order_url=runtime.order_url,
            audience=runtime.order_url,
        ),
    )
    request.app.state.coordinator = created
    return created


def _rollback_executor(request: Request) -> FixedPaymentRollbackExecutor:
    existing = request.app.state.executor
    if isinstance(existing, FixedPaymentRollbackExecutor):
        return existing
    runtime = _required_settings(request)
    created = FixedPaymentRollbackExecutor(
        store=FirestoreRemediationStore(
            project_id=runtime.project_id, database_id=runtime.database_id
        ),
        cloud_run=GoogleCloudRunAdmin(),
    )
    request.app.state.executor = created
    return created


def _control_audience(request: Request) -> str:
    runtime = request.app.state.settings
    if isinstance(runtime, RemediationSettings):
        return runtime.control_audience
    return "https://control.example.invalid"
