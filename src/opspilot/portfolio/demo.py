from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class DemoCommandResult:
    returncode: int
    duration_ms: int


@dataclass(frozen=True)
class DemoStep:
    name: str
    command: tuple[str, ...]


DemoCommandRunner = Callable[[Sequence[str], Path, Mapping[str, str]], DemoCommandResult]
ReadinessProbe = Callable[[], bool]


def _run_command(
    command: Sequence[str], cwd: Path, environment: Mapping[str, str]
) -> DemoCommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(list(command), cwd=cwd, env=dict(environment), check=False)
        returncode = completed.returncode
    except OSError:
        returncode = 127
    return DemoCommandResult(
        returncode=returncode,
        duration_ms=max(0, round((time.monotonic() - started) * 1000)),
    )


def _default_readiness_probe() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8100/ready", timeout=2) as response:
            return int(response.status) == 200
    except OSError:
        return False


def _ports_are_free(ports: Sequence[int]) -> bool:
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            if client.connect_ex(("127.0.0.1", port)) == 0:
                return False
    return True


def demo_steps(output: Path, build_image: bool) -> tuple[DemoStep, ...]:
    steps: list[DemoStep] = []
    if build_image:
        steps.append(
            DemoStep(
                "build_image",
                ("docker", "build", "--platform", "linux/amd64", "-t", "opspilot-demo:local", "."),
            )
        )
    else:
        steps.append(
            DemoStep("verify_image", ("docker", "image", "inspect", "opspilot-demo:local"))
        )
    steps.extend(
        [
            DemoStep("compose_up", ("docker", "compose", "up", "-d", "--no-build")),
            DemoStep(
                "healthy_workload",
                (
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "-e",
                    "OPSPILOT_ORDER_URL=http://127.0.0.1:8080",
                    "order",
                    "opspilot",
                    "demo",
                    "load",
                    "--orders",
                    "10",
                    "--concurrency",
                    "2",
                    "--auth",
                    "local",
                ),
            ),
            DemoStep(
                "scenario_scn_001",
                (
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "-e",
                    "OPSPILOT_ORDER_URL=http://127.0.0.1:8080",
                    "order",
                    "opspilot",
                    "scenario",
                    "run",
                    "--scenario",
                    "SCN-001",
                    "--auth",
                    "local",
                    "--format",
                    "summary",
                ),
            ),
            DemoStep(
                "evidence_smoke",
                (
                    "uv",
                    "run",
                    "opspilot",
                    "evidence",
                    "smoke",
                    "--scenario",
                    "SCN-001",
                    "--env",
                    "dev",
                    "--format",
                    "summary",
                ),
            ),
            DemoStep(
                "agent_report",
                (
                    "uv",
                    "run",
                    "--extra",
                    "agent",
                    "opspilot",
                    "agent",
                    "run",
                    "--scenario",
                    "SCN-001",
                    "--format",
                    "markdown",
                ),
            ),
            DemoStep(
                "portfolio_gate",
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
                    str(output / "evaluation"),
                ),
            ),
            DemoStep(
                "cleanup_plan",
                ("uv", "run", "opspilot", "cleanup", "plan", "--format", "summary"),
            ),
        ]
    )
    return tuple(steps)


class PortfolioDemoRunner:
    def __init__(
        self,
        *,
        root: Path,
        output: Path,
        build_image: bool,
        dry_run: bool,
        command_runner: DemoCommandRunner = _run_command,
        readiness_probe: ReadinessProbe = _default_readiness_probe,
    ) -> None:
        self.root = root.resolve()
        allowed = (self.root / ".tmp").resolve()
        self.output = output.resolve() if output.is_absolute() else (self.root / output).resolve()
        if self.output != allowed and allowed not in self.output.parents:
            raise ValueError("portfolio demo output must remain under .tmp")
        self.build_image = build_image
        self.dry_run = dry_run
        self.command_runner = command_runner
        self.readiness_probe = readiness_probe

    def _wait_for_readiness(self, timeout_seconds: float = 60) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.readiness_probe():
                return True
            time.sleep(1)
        return False

    def run(self) -> int:
        self.output.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ)
        environment["UV_CACHE_DIR"] = str(
            Path(tempfile.gettempdir()) / "opspilot-portfolio-demo-uv-cache"
        )
        steps = demo_steps(self.output.relative_to(self.root), self.build_image)
        outcomes: list[dict[str, object]] = []
        status = "passed"
        stack_touched = False
        exit_code = 0
        started = time.monotonic()
        try:
            if self.dry_run:
                for step in steps:
                    print(f"[{step.name}] {' '.join(step.command)}")
                    outcomes.append({"name": step.name, "status": "planned", "duration_ms": 0})
                print("[readiness] GET http://127.0.0.1:8100/ready")
                return 0
            if shutil.which("uv") is None or shutil.which("docker") is None:
                status = "failed"
                exit_code = 2
                outcomes.append({"name": "prerequisites", "status": "failed", "duration_ms": 0})
                return exit_code
            if not _ports_are_free((8100, 8101, 8102)):
                status = "failed"
                exit_code = 2
                outcomes.append({"name": "ports", "status": "failed", "duration_ms": 0})
                return exit_code
            for step in steps:
                if step.name == "compose_up":
                    stack_touched = True
                print(f"[{step.name}] {' '.join(step.command)}", flush=True)
                result = self.command_runner(step.command, self.root, environment)
                step_status = "passed" if result.returncode == 0 else "failed"
                outcomes.append(
                    {"name": step.name, "status": step_status, "duration_ms": result.duration_ms}
                )
                if result.returncode != 0:
                    status = "failed"
                    exit_code = 2
                    break
                if step.name == "compose_up":
                    readiness_started = time.monotonic()
                    ready = self._wait_for_readiness()
                    outcomes.append(
                        {
                            "name": "readiness",
                            "status": "passed" if ready else "failed",
                            "duration_ms": max(
                                0, round((time.monotonic() - readiness_started) * 1000)
                            ),
                        }
                    )
                    if not ready:
                        status = "failed"
                        exit_code = 2
                        break
        except KeyboardInterrupt:
            status = "cancelled"
            exit_code = 130
        except Exception:
            status = "failed"
            exit_code = 2
            outcomes.append({"name": "unexpected_failure", "status": "failed", "duration_ms": 0})
        finally:
            if stack_touched and not self.dry_run:
                cleanup = self.command_runner(
                    ("docker", "compose", "down", "--remove-orphans"), self.root, environment
                )
                outcomes.append(
                    {
                        "name": "compose_down",
                        "status": "passed" if cleanup.returncode == 0 else "failed",
                        "duration_ms": cleanup.duration_ms,
                    }
                )
                if cleanup.returncode != 0 and exit_code == 0:
                    status = "failed"
                    exit_code = 2
            summary = {
                "schema_version": "portfolio-demo-v1",
                "generated_at": datetime.now(UTC).isoformat(),
                "status": status if not self.dry_run else "planned",
                "duration_ms": max(0, round((time.monotonic() - started) * 1000)),
                "steps": outcomes,
            }
            (self.output / "summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the bounded OpsPilot portfolio demo")
    parser.add_argument("--output", default=".tmp/portfolio-demo")
    parser.add_argument("--build-image", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        return PortfolioDemoRunner(
            root=root,
            output=Path(str(args.output)),
            build_image=bool(args.build_image),
            dry_run=bool(args.dry_run),
        ).run()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
