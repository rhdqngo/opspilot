from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_MVP_public_documents_do_not_describe_retired_runtime_or_recovery_contracts() -> None:
    public_documents = (
        ROOT / "README.md",
        ROOT / "docs" / "portfolio" / "architecture.md",
        ROOT / "docs" / "portfolio" / "demo.md",
        ROOT / "docs" / "requirements-traceability.md",
        ROOT / "docs" / "operations" / "agent-runtime.md",
        ROOT / "docs" / "operations" / "remediation.md",
    )
    retired_claims = (
        "not-yet-deployed",
        "not deployed or authorized",
        "fresh 22-resource",
        "exact two-create recovery",
        "fixed single-turn `payment-service`/30-minute",
        "explicitly fixture-only",
        "deployed runtime uses the smaller live hybrid",
    )

    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in public_documents)

    assert all(claim not in combined for claim in retired_claims)
