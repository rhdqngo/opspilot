"""Privacy-safe audit and correlation contracts."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
HASH_PATTERN = r"^[0-9a-f]{64}$"


def audit_hash(namespace: str, value: str) -> str:
    """Return a domain-separated pseudonymous fingerprint."""

    normalized = " ".join(value.strip().split())
    return hashlib.sha256(f"opspilot:{namespace}:v1:{normalized}".encode()).hexdigest()


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_correlation_id() -> str:
    return f"COR-{uuid4().hex[:16].upper()}"


def extract_trace_id(value: str | None) -> str | None:
    """Extract the trace ID from the Cloud Trace context header without retaining raw input."""

    if value is None:
        return None
    candidate = value.split("/", maxsplit=1)[0].strip().lower()
    return candidate if TRACE_ID_PATTERN.fullmatch(candidate) else None


class InvestigationAudit(BaseModel):
    source: Literal["enterprise", "direct_api", "monitoring", "replay", "fixture"]
    actor_hash: str | None = Field(default=None, pattern=HASH_PATTERN)
    session_hash: str | None = Field(default=None, pattern=HASH_PATTERN)
    query_hash: str = Field(pattern=HASH_PATTERN)
    run_id: str | None = Field(default=None, pattern=r"^RUN-[A-F0-9]{16}$")
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")


class ToolCallAuditEvent(BaseModel):
    event: Literal["opspilot_tool_call"] = "opspilot_tool_call"
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    correlation_id: str
    investigation_id: str | None = None
    run_id: str | None = None
    tool_call_id: str
    tool_name: str
    environment: str
    service_count: int = Field(ge=1)
    window_seconds: int = Field(ge=1)
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    status: Literal["OK", "ERROR"]
    api_call_count: int = Field(ge=0)
    result_count: int = Field(ge=0)
    result_bytes: int = Field(ge=0)
    truncated: bool
    cache_hit: bool
    error_code: str | None = None
    error_category: str | None = None
    retryable: bool | None = None


class ToolAuditContext(BaseModel):
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    correlation_id: str
    investigation_id: str | None = None
    run_id: str | None = None


def log_tool_call(logger: logging.Logger, event: ToolCallAuditEvent) -> None:
    payload = json.dumps(event.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)
    if os.getenv("K_SERVICE"):
        print(payload, flush=True)
        return
    logger.info("%s", payload)
