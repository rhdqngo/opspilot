from __future__ import annotations

import pytest
from google.auth.credentials import AnonymousCredentials
from vertexai import init as vertexai_init


def pytest_configure(config: pytest.Config) -> None:
    """Keep test collection independent from local or CI Google credentials."""

    del config
    vertexai_init(
        project="opspilot-test-project",
        location="asia-northeast3",
        credentials=AnonymousCredentials(),  # type: ignore[no-untyped-call]
    )
