"""Defense-in-depth Google ID token verification for remediation services."""

from __future__ import annotations

from typing import Protocol

from google.auth.transport.requests import Request
from google.oauth2 import id_token

from opspilot.remediation.contracts import Principal
from opspilot.remediation.errors import AuthenticationError, AuthorizationError

ALLOWED_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


class TokenVerifier(Protocol):
    def verify(self, token: str, *, audience: str) -> Principal: ...


class GoogleIdTokenVerifier:
    def verify(self, token: str, *, audience: str) -> Principal:
        try:
            claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                token, Request(), audience=audience
            )
        except (ValueError, TypeError) as error:
            raise AuthenticationError("identity token could not be verified") from error
        issuer = claims.get("iss")
        subject = claims.get("sub")
        email = claims.get("email")
        if issuer not in ALLOWED_ISSUERS:
            raise AuthenticationError("identity token issuer is not allowed")
        if claims.get("aud") != audience:
            raise AuthenticationError("identity token audience does not match")
        if claims.get("email_verified") is not True:
            raise AuthenticationError("identity token email is not verified")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("identity token subject is missing")
        if not isinstance(email, str) or not email:
            raise AuthenticationError("identity token email is missing")
        return Principal(subject=subject, email=email, email_verified=True)


def bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise AuthenticationError("authorization bearer token is required")
    scheme, separator, value = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not value.strip():
        raise AuthenticationError("authorization bearer token is invalid")
    return value.strip()


def require_service_account(principal: Principal, *, allowed_email: str) -> Principal:
    if not allowed_email or principal.email != allowed_email:
        raise AuthorizationError("caller is not the configured workflow identity")
    return principal
