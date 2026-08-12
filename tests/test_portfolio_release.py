from __future__ import annotations

import gzip
import io
import json
import tarfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from opspilot.portfolio.release import (
    ARTIFACT_SCHEMA_VERSION,
    README_END,
    README_START,
    CommandExecution,
    PortfolioReleaseRunner,
    _readme_metrics_block,
    publish_release_artifact,
    source_tree_sha256,
)


def _write_evaluation(path: Path, suite: str, cases: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "result": {
                    "suite": suite,
                    "suite_version": f"{suite}-v1",
                    "executed_case_count": cases,
                    "passed_case_count": cases,
                    "model_calls": cases * 2,
                    "metrics": {
                        "rca_top1_accuracy": 1.0,
                        "rca_top3_accuracy": 1.0,
                        "required_tool_recall": 1.0,
                        "citation_coverage": 1.0,
                        "evidence_id_validity": 1.0,
                        "unsupported_claim_count": 0,
                        "unauthorized_action_count": 0,
                        "prompt_injection_success_count": 0,
                    },
                    "duration_percentiles": {"p50_ms": 10, "p95_ms": 20},
                    "gate_failures": [],
                    "cases": [],
                }
            }
        ),
        encoding="utf-8",
    )


def _write_runtime(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / "opspilot-agent-runtime.tar.gz"
    with archive.open("wb") as destination:
        with gzip.GzipFile(fileobj=destination, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as package:
                for name in ("opspilot/__init__.py", "opspilot/agent.py"):
                    content = b"safe"
                    info = tarfile.TarInfo(name)
                    info.size = len(content)
                    info.mtime = 0
                    package.addfile(info, io.BytesIO(content))


class FakeReleaseCommands:
    def __init__(self, *, failed: set[str] | None = None) -> None:
        self.failed = failed or set()
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, command: Sequence[str], root: Path, environment: Mapping[str, str]
    ) -> CommandExecution:
        assert environment["UV_CACHE_DIR"]
        call = tuple(command)
        self.calls.append(call)
        joined = " ".join(call)
        for value in call:
            if value.startswith("--junitxml="):
                path = root / Path(value.split("=", 1)[1])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    '<testsuites name="pytest tests"><testsuite tests="3" failures="0" '
                    'errors="0" skipped="0" /></testsuites>',
                    encoding="utf-8",
                )
        if "--output" in call:
            output = root / Path(call[call.index("--output") + 1])
            if "agent eval" in joined:
                suite = call[call.index("--suite") + 1]
                _write_evaluation(output / f"{suite}-v1.json", suite, 7 if suite == "core" else 40)
            if "runtime package" in joined:
                _write_runtime(output)
        name = ""
        if "ruff format" in joined:
            name = "ruff_format"
        elif call == ("uv", "build"):
            name = "build"
        return CommandExecution(returncode=1 if name in self.failed else 0, duration_ms=1)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".tmp").mkdir()
    (root / "README.md").write_text(
        f"# Portfolio\n\n{README_START}\nold\n{README_END}\n", encoding="utf-8"
    )
    (root / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    return root


def test_release_runner_aggregates_all_checks_and_sanitizes_artifact(tmp_path: Path) -> None:
    root = _root(tmp_path)
    commands = FakeReleaseCommands()
    runner = PortfolioReleaseRunner(
        root=root,
        output=Path(".tmp/release"),
        include_infra=True,
        publish=False,
        command_runner=commands,
    )

    exit_code, artifact = runner.run()

    assert exit_code == 0
    assert artifact["status"] == "passed"
    assert len(commands.calls) == 15
    serialized = json.dumps(artifact)
    assert "run_id" not in serialized
    assert "hostname" not in serialized
    assert str(root) not in serialized
    validation = artifact["validation"]
    assert isinstance(validation, dict)
    assert validation["pytest"] == {
        "executed": 3,
        "passed": 3,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }
    assert validation["runtime_package"]["file_count"] == 2


def test_release_runner_continues_after_failures_and_returns_two(tmp_path: Path) -> None:
    root = _root(tmp_path)
    commands = FakeReleaseCommands(failed={"ruff_format", "build"})
    runner = PortfolioReleaseRunner(
        root=root,
        output=Path(".tmp/release"),
        include_infra=False,
        publish=False,
        command_runner=commands,
    )

    exit_code, artifact = runner.run()

    assert exit_code == 2
    assert artifact["status"] == "failed"
    assert artifact["failures"] == ["ruff_format", "build"]
    assert len(commands.calls) == 10


def test_publish_rejects_failed_result_without_mutating_files(tmp_path: Path) -> None:
    root = _root(tmp_path)
    readme_before = (root / "README.md").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be published"):
        publish_release_artifact(root, {"status": "failed"})

    assert (root / "README.md").read_text(encoding="utf-8") == readme_before
    assert not (root / "docs/portfolio/results").exists()


def test_publish_updates_only_generated_readme_block(tmp_path: Path) -> None:
    root = _root(tmp_path)
    artifact: dict[str, object] = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "generated_at": "2026-08-12T00:00:00+00:00",
        "status": "passed",
        "source": {
            "git_commit": "abc123",
            "working_tree_dirty": False,
            "source_tree_sha256": "0" * 64,
        },
        "checks": [],
        "validation": {
            "pytest": {"passed": 3, "executed": 3},
            "core_evaluation": {"passed_case_count": 7, "executed_case_count": 7},
            "portfolio_evaluation": {
                "passed_case_count": 40,
                "executed_case_count": 40,
                "metrics": {
                    "rca_top1_accuracy": 1.0,
                    "rca_top3_accuracy": 1.0,
                    "required_tool_recall": 1.0,
                    "citation_coverage": 1.0,
                    "evidence_id_validity": 1.0,
                },
                "duration_percentiles": {"p50_ms": 10, "p95_ms": 20},
            },
            "runtime_package": {"file_count": 2, "sha256": "1" * 64},
        },
        "failures": [],
    }

    json_path, markdown_path = publish_release_artifact(root, artifact)

    assert json_path.is_file()
    assert markdown_path.is_file()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Portfolio")
    assert "**3/3 pytest**" in readme
    assert _readme_metrics_block(artifact) in readme


def test_source_fingerprint_ignores_generated_readme_metrics(tmp_path: Path) -> None:
    root = _root(tmp_path)
    paths = (Path("README.md"), Path("source.py"))
    before = source_tree_sha256(root, paths)
    readme = (root / "README.md").read_text(encoding="utf-8")
    (root / "README.md").write_text(readme.replace("old", "new metrics"), encoding="utf-8")
    assert source_tree_sha256(root, paths) == before
    (root / "source.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert source_tree_sha256(root, paths) != before


def test_release_output_is_bounded_to_tmp(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(ValueError, match=r"must remain under \.tmp"):
        PortfolioReleaseRunner(
            root=root,
            output=Path("docs/output"),
            include_infra=False,
            publish=False,
        )


def test_manual_ci_uploads_portfolio_artifact_without_automatic_trigger() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/pr-checks.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" not in workflow
    assert "push:" not in workflow
    assert "--suite portfolio" in workflow
    assert "if: always()" in workflow
    assert "opspilot-portfolio-evaluation-${{ github.sha }}" in workflow
    assert "retention-days: 30" in workflow


def test_readme_metrics_match_published_artifact_when_present() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact_path = root / "docs/portfolio/results/portfolio-release-v1.json"
    if not artifact_path.is_file():
        pytest.skip("release evidence has not been published yet")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert _readme_metrics_block(artifact) in readme
