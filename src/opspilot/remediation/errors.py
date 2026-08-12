"""Stable, sanitized errors exposed by the remediation control plane."""

from __future__ import annotations


class RemediationError(Exception):
    status_code = 500
    code = "REMEDIATION_ERROR"

    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


class NotFoundError(RemediationError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(RemediationError):
    status_code = 409
    code = "CONFLICT"


class ExpiredError(RemediationError):
    status_code = 410
    code = "EXPIRED"


class PolicyViolationError(RemediationError):
    status_code = 422
    code = "POLICY_VIOLATION"


class AuthenticationError(RemediationError):
    status_code = 401
    code = "UNAUTHENTICATED"


class AuthorizationError(RemediationError):
    status_code = 403
    code = "FORBIDDEN"


class DependencyError(RemediationError):
    status_code = 503
    code = "DEPENDENCY_FAILURE"
