from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

ARTIFACT_SCHEMA_VERSION = "portfolio-release-v1"
README_START = "<!-- BEGIN GENERATED:PORTFOLIO_METRICS -->"
README_END = "<!-- END GENERATED:PORTFOLIO_METRICS -->"
PUBLISHED_RESULT_DIRECTORY = Path("docs/portfolio/results")


@dataclass(frozen=True)
class CommandExecution:
    returncode: int
    duration_ms: int


@dataclass(frozen=True)
class CheckDefinition:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CheckOutcome:
    name: str
    status: str
    duration_ms: int


CommandRunner = Callable[[Sequence[str], Path, Mapping[str, str]], CommandExecution]


def _run_command(
    command: Sequence[str], cwd: Path, environment: Mapping[str, str]
) -> CommandExecution:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(environment),
            check=False,
        )
        returncode = completed.returncode
    except OSError:
        returncode = 127
    return CommandExecution(
        returncode=returncode,
        duration_ms=max(0, round((time.monotonic() - started) * 1000)),
    )


def _git_output(root: Path, arguments: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    if completed.returncode != 0:
        return "unavailable"
    return completed.stdout.strip()


def discover_source_paths(root: Path) -> tuple[Path, ...]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if completed.returncode != 0:
        return ()
    paths: list[Path] = []
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        normalized = relative.as_posix()
        if normalized.startswith("docs/portfolio/results/"):
            continue
        path = root / relative
        if path.is_file():
            paths.append(relative)
    return tuple(sorted(paths, key=lambda item: item.as_posix()))


def _fingerprint_content(relative: Path, content: bytes) -> bytes:
    if relative.as_posix() != "README.md":
        return content
    text = content.decode("utf-8")
    start = text.find(README_START)
    end = text.find(README_END)
    if start < 0 or end < 0 or end < start:
        return content
    normalized = text[:start] + README_START + "\n" + README_END + text[end + len(README_END) :]
    return normalized.encode("utf-8")


def source_tree_sha256(root: Path, paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths, key=lambda item: item.as_posix()):
        path = root / relative
        if not path.is_file():
            continue
        encoded_path = relative.as_posix().encode("utf-8")
        content = _fingerprint_content(relative, path.read_bytes())
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def source_metadata(root: Path) -> dict[str, object]:
    status = _git_output(root, ["status", "--porcelain", "--untracked-files=all"])
    return {
        "git_commit": _git_output(root, ["rev-parse", "HEAD"]),
        "working_tree_dirty": status not in {"", "unavailable"},
        "source_tree_sha256": source_tree_sha256(root, discover_source_paths(root)),
    }


def _relative_output(root: Path, output: Path) -> Path:
    resolved_root = root.resolve()
    allowed = (resolved_root / ".tmp").resolve()
    destination = output.resolve() if output.is_absolute() else (resolved_root / output).resolve()
    if destination != allowed and allowed not in destination.parents:
        raise ValueError("portfolio release output must remain under .tmp")
    return destination


def build_checks(
    root: Path, run_directory: Path, include_infra: bool
) -> tuple[CheckDefinition, ...]:
    relative_run = run_directory.relative_to(root)
    pytest_xml = relative_run / "pytest.xml"
    core_output = relative_run / "core-evaluation"
    portfolio_output = relative_run / "portfolio-evaluation"
    runtime_one = relative_run / "runtime-one"
    runtime_two = relative_run / "runtime-two"
    checks = [
        CheckDefinition("git_diff_check", ("git", "diff", "--check")),
        CheckDefinition("ruff_format", ("uv", "run", "ruff", "format", "--check", ".")),
        CheckDefinition("ruff_check", ("uv", "run", "ruff", "check", ".")),
        CheckDefinition("mypy", ("uv", "run", "--extra", "agent", "mypy", "src", "tests")),
        CheckDefinition(
            "pytest",
            (
                "uv",
                "run",
                "--extra",
                "agent",
                "pytest",
                f"--junitxml={pytest_xml}",
            ),
        ),
        CheckDefinition(
            "core_evaluation",
            (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "agent",
                "eval",
                "--suite",
                "core",
                "--format",
                "summary",
                "--output",
                str(core_output),
            ),
        ),
        CheckDefinition(
            "portfolio_evaluation",
            (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "agent",
                "eval",
                "--suite",
                "portfolio",
                "--format",
                "summary",
                "--output",
                str(portfolio_output),
            ),
        ),
        CheckDefinition(
            "runtime_package_one",
            (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "agent",
                "runtime",
                "package",
                "--output",
                str(runtime_one),
            ),
        ),
        CheckDefinition(
            "runtime_package_two",
            (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "agent",
                "runtime",
                "package",
                "--output",
                str(runtime_two),
            ),
        ),
        CheckDefinition("build", ("uv", "build")),
    ]
    if include_infra:
        checks.extend(
            [
                CheckDefinition(
                    "terraform_format",
                    ("terraform", "fmt", "-check", "-recursive", "infra/terraform"),
                ),
                CheckDefinition(
                    "terraform_bootstrap_validate",
                    ("terraform", "-chdir=infra/terraform/bootstrap", "validate"),
                ),
                CheckDefinition(
                    "terraform_bootstrap_test",
                    ("terraform", "-chdir=infra/terraform/bootstrap", "test"),
                ),
                CheckDefinition(
                    "terraform_dev_validate",
                    ("terraform", "-chdir=infra/terraform/environments/dev", "validate"),
                ),
                CheckDefinition(
                    "terraform_dev_test",
                    ("terraform", "-chdir=infra/terraform/environments/dev", "test"),
                ),
            ]
        )
    return tuple(checks)


def _pytest_summary(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    root = ET.parse(path).getroot()
    suites = [root] if root.tag.endswith("testsuite") else list(root.findall("./testsuite"))
    if not suites:
        return None
    tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
    return {
        "executed": tests,
        "passed": tests - failures - errors - skipped,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
    }


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


def _number(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _evaluation_summary(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    payload = _mapping(json.loads(path.read_text(encoding="utf-8")))
    result = _mapping(payload.get("result"))
    cases = result.get("cases")
    failed_cases: list[dict[str, object]] = []
    if isinstance(cases, list):
        for raw_case in cases:
            case = _mapping(raw_case)
            if case.get("passed") is False:
                failed_cases.append(
                    {
                        "case_id": str(case.get("case_id", "unknown")),
                        "failure_reasons": case.get("failure_reasons", []),
                    }
                )
    return {
        "suite": result.get("suite"),
        "suite_version": result.get("suite_version"),
        "executed_case_count": result.get("executed_case_count"),
        "passed_case_count": result.get("passed_case_count"),
        "model_calls": result.get("model_calls"),
        "metrics": result.get("metrics", {}),
        "duration_percentiles": result.get("duration_percentiles", {}),
        "gate_failures": result.get("gate_failures", []),
        "failed_cases": failed_cases,
    }


def _runtime_summary(directory: Path) -> dict[str, object] | None:
    archive = directory / "opspilot-agent-runtime.tar.gz"
    if not archive.is_file():
        return None
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive, "r:gz") as package:
        file_count = len([member for member in package.getmembers() if member.isfile()])
    return {"file_count": file_count, "sha256": digest}


def _render_markdown(artifact: Mapping[str, object]) -> str:
    validation = _mapping(artifact.get("validation"))
    pytest_result = _mapping(validation.get("pytest"))
    core = _mapping(validation.get("core_evaluation"))
    portfolio = _mapping(validation.get("portfolio_evaluation"))
    metrics = _mapping(portfolio.get("metrics"))
    durations = _mapping(portfolio.get("duration_percentiles"))
    runtime = _mapping(validation.get("runtime_package"))
    source = _mapping(artifact.get("source"))
    checks = artifact.get("checks")
    check_lines: list[str] = []
    if isinstance(checks, list):
        for raw_check in checks:
            check = _mapping(raw_check)
            check_lines.append(
                f"| {check.get('name', 'unknown')} | {str(check.get('status', 'failed')).upper()} |"
            )
    failures = artifact.get("failures")
    failure_text = ", ".join(str(value) for value in failures) if isinstance(failures, list) else ""
    return "\n".join(
        [
            "# OpsPilot Portfolio Release Evidence",
            "",
            f"- Status: **{str(artifact.get('status', 'failed')).upper()}**",
            f"- Generated: `{artifact.get('generated_at')}`",
            f"- Source commit: `{source.get('git_commit')}`",
            f"- Working tree dirty before validation: `{source.get('working_tree_dirty')}`",
            f"- Source tree SHA-256: `{source.get('source_tree_sha256')}`",
            "",
            "## Verified results",
            "",
            "| Result | Value |",
            "| --- | ---: |",
            f"| Pytest | {pytest_result.get('passed', 0)}/{pytest_result.get('executed', 0)} |",
            (
                f"| Core evaluation | {core.get('passed_case_count', 0)}/"
                f"{core.get('executed_case_count', 0)} |"
            ),
            (
                f"| Portfolio evaluation | {portfolio.get('passed_case_count', 0)}/"
                f"{portfolio.get('executed_case_count', 0)} |"
            ),
            (
                f"| RCA top-1 / top-3 | {_number(metrics.get('rca_top1_accuracy')):.3f} / "
                f"{_number(metrics.get('rca_top3_accuracy')):.3f} |"
            ),
            f"| Required-tool recall | {_number(metrics.get('required_tool_recall')):.3f} |",
            f"| Citation coverage | {_number(metrics.get('citation_coverage')):.3f} |",
            f"| Evidence-ID validity | {_number(metrics.get('evidence_id_validity')):.3f} |",
            (
                f"| P50 / P95 fixture duration | {durations.get('p50_ms', 0)} ms / "
                f"{durations.get('p95_ms', 0)} ms |"
            ),
            (
                f"| Runtime package | {runtime.get('file_count', 0)} files / "
                f"`{runtime.get('sha256', 'unavailable')}` |"
            ),
            "",
            "## Checks",
            "",
            "| Check | Status |",
            "| --- | --- |",
            *check_lines,
            "",
            "## Failures",
            "",
            f"- {failure_text or 'None.'}",
            "",
        ]
    )


def _readme_metrics_block(artifact: Mapping[str, object]) -> str:
    validation = _mapping(artifact.get("validation"))
    pytest_result = _mapping(validation.get("pytest"))
    core = _mapping(validation.get("core_evaluation"))
    portfolio = _mapping(validation.get("portfolio_evaluation"))
    metrics = _mapping(portfolio.get("metrics"))
    durations = _mapping(portfolio.get("duration_percentiles"))
    return "\n".join(
        [
            README_START,
            (
                "Latest published verification: "
                f"**{pytest_result.get('passed', 0)}/{pytest_result.get('executed', 0)} pytest**; "
                f"core **{core.get('passed_case_count', 0)}/"
                f"{core.get('executed_case_count', 0)}**; portfolio "
                f"**{portfolio.get('passed_case_count', 0)}/"
                f"{portfolio.get('executed_case_count', 0)}**."
            ),
            (
                "RCA top-1/top-3, required-tool recall, citation coverage, and "
                "evidence-ID validity: "
                f"**{_number(metrics.get('rca_top1_accuracy')):.3f}/"
                f"{_number(metrics.get('rca_top3_accuracy')):.3f}/"
                f"{_number(metrics.get('required_tool_recall')):.3f}/"
                f"{_number(metrics.get('citation_coverage')):.3f}/"
                f"{_number(metrics.get('evidence_id_validity')):.3f}**; "
                f"fixture P50/P95 **{durations.get('p50_ms', 0)}/{durations.get('p95_ms', 0)} ms**."
            ),
            (
                "The generated [Markdown evidence]"
                "(docs/portfolio/results/portfolio-release-v1.md) and [JSON evidence]"
                "(docs/portfolio/results/portfolio-release-v1.json) are the source of record."
            ),
            README_END,
        ]
    )


def _replace_readme_block(readme: str, block: str) -> str:
    start = readme.find(README_START)
    end = readme.find(README_END)
    if start < 0 or end < 0 or end < start:
        raise ValueError("README generated metrics markers are missing or invalid")
    return readme[:start] + block + readme[end + len(README_END) :]


def publish_release_artifact(root: Path, artifact: Mapping[str, object]) -> tuple[Path, Path]:
    if artifact.get("status") != "passed":
        raise ValueError("failed release evidence cannot be published")
    readme_path = root / "README.md"
    new_readme = _replace_readme_block(
        readme_path.read_text(encoding="utf-8"), _readme_metrics_block(artifact)
    )
    destination = root / PUBLISHED_RESULT_DIRECTORY
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / f"{ARTIFACT_SCHEMA_VERSION}.json"
    markdown_path = destination / f"{ARTIFACT_SCHEMA_VERSION}.md"
    json_path.write_text(
        json.dumps(dict(artifact), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_render_markdown(artifact), encoding="utf-8")
    readme_path.write_text(new_readme, encoding="utf-8")
    return json_path, markdown_path


class PortfolioReleaseRunner:
    def __init__(
        self,
        *,
        root: Path,
        output: Path,
        include_infra: bool,
        publish: bool,
        command_runner: CommandRunner = _run_command,
    ) -> None:
        self.root = root.resolve()
        self.output = _relative_output(self.root, output)
        self.include_infra = include_infra
        self.publish = publish
        self.command_runner = command_runner

    def run(self) -> tuple[int, dict[str, object]]:
        self.output.mkdir(parents=True, exist_ok=True)
        run_directory = self.output / f"run-{uuid.uuid4().hex}"
        run_directory.mkdir(parents=True, exist_ok=False)
        environment = dict(os.environ)
        environment["UV_CACHE_DIR"] = str(
            Path(tempfile.gettempdir()) / "opspilot-portfolio-release-uv-cache"
        )
        source = source_metadata(self.root)
        outcomes: list[CheckOutcome] = []
        for check in build_checks(self.root, run_directory, self.include_infra):
            print(f"[{check.name}] {' '.join(check.command)}", flush=True)
            execution = self.command_runner(check.command, self.root, environment)
            outcomes.append(
                CheckOutcome(
                    name=check.name,
                    status="passed" if execution.returncode == 0 else "failed",
                    duration_ms=execution.duration_ms,
                )
            )

        pytest_result = _pytest_summary(run_directory / "pytest.xml")
        core = _evaluation_summary(run_directory / "core-evaluation" / "core-v1.json")
        portfolio = _evaluation_summary(
            run_directory / "portfolio-evaluation" / "portfolio-v1.json"
        )
        runtime_one = _runtime_summary(run_directory / "runtime-one")
        runtime_two = _runtime_summary(run_directory / "runtime-two")
        required_artifacts = {
            "pytest": pytest_result,
            "core_evaluation": core,
            "portfolio_evaluation": portfolio,
            "runtime_package_one": runtime_one,
            "runtime_package_two": runtime_two,
        }
        for name, value in required_artifacts.items():
            if value is None:
                outcomes.append(
                    CheckOutcome(name=f"{name}_artifact", status="failed", duration_ms=0)
                )

        deterministic = runtime_one is not None and runtime_one == runtime_two
        outcomes.append(
            CheckOutcome(
                name="runtime_determinism",
                status="passed" if deterministic else "failed",
                duration_ms=0,
            )
        )
        failures = [outcome.name for outcome in outcomes if outcome.status != "passed"]
        artifact: dict[str, object] = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "passed" if not failures else "failed",
            "source": source,
            "environment": {
                "execution_mode": "local-offline-release",
                "python": platform.python_version(),
                "operating_system": platform.system(),
            },
            "checks": [
                {"name": value.name, "status": value.status, "duration_ms": value.duration_ms}
                for value in outcomes
            ],
            "validation": {
                "pytest": pytest_result or {},
                "core_evaluation": core or {},
                "portfolio_evaluation": portfolio or {},
                "runtime_package": runtime_one if deterministic and runtime_one is not None else {},
                "terraform_included": self.include_infra,
            },
            "failures": failures,
        }
        json_path = self.output / f"{ARTIFACT_SCHEMA_VERSION}.json"
        markdown_path = self.output / f"{ARTIFACT_SCHEMA_VERSION}.md"
        json_path.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        markdown_path.write_text(_render_markdown(artifact), encoding="utf-8")
        if self.publish and not failures:
            publish_release_artifact(self.root, artifact)
        print(f"release_status: {artifact['status']}")
        print(f"release_artifact: {json_path.relative_to(self.root)}")
        return (0 if not failures else 2), artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and publish OpsPilot portfolio evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="Run the offline portfolio release gate")
    check.add_argument("--output", default=".tmp/portfolio-release")
    check.add_argument("--include-infra", action="store_true")
    check.add_argument("--publish", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        runner = PortfolioReleaseRunner(
            root=root,
            output=Path(str(args.output)),
            include_infra=bool(args.include_infra),
            publish=bool(args.publish),
        )
        return runner.run()[0]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
