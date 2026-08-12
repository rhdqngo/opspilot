"""OpsPilot command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import uvicorn

from opspilot.demo.load import run_load
from opspilot.demo.scenario_runner import render_scenario_summary, run_scenario
from opspilot.evidence import (
    EvidenceBackend,
    render_evidence_summary,
    run_evidence_smoke,
)
from opspilot.knowledge import (
    KnowledgeSyncMode,
    render_knowledge_result,
    run_knowledge_sync,
    run_local_smoke,
    validate_knowledge,
)
from opspilot.reporting import render_markdown
from opspilot.workflow import run_fixture_investigation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opspilot")
    subcommands = parser.add_subparsers(dest="command", required=True)
    replay = subcommands.add_parser("replay", help="Replay a synthetic incident fixture")
    replay.add_argument("--scenario", default="SCN-001")
    replay.add_argument("--format", choices=("json", "markdown"), default="json")
    serve = subcommands.add_parser("serve", help="Run the local FastAPI service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    demo = subcommands.add_parser("demo", help="Run or exercise synthetic demo services")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    demo_serve = demo_commands.add_parser("serve", help="Serve the configured demo role")
    demo_serve.add_argument("--host", default="0.0.0.0")
    demo_serve.add_argument("--port", type=int, default=None)
    demo_load = demo_commands.add_parser("load", help="Generate bounded synthetic order load")
    demo_load.add_argument("--orders", type=int, default=10)
    demo_load.add_argument("--concurrency", type=int, default=2)
    demo_load.add_argument("--auth", choices=("local", "gcloud"), default="local")
    scenario = subcommands.add_parser("scenario", help="Run bounded synthetic incidents")
    scenario_commands = scenario.add_subparsers(dest="scenario_command", required=True)
    scenario_run = scenario_commands.add_parser(
        "run", help="Run baseline, incident, and recovery phases"
    )
    scenario_run.add_argument("--scenario", default="SCN-001")
    scenario_run.add_argument("--auth", choices=("local", "gcloud"), default="local")
    scenario_run.add_argument("--format", choices=("json", "summary"), default="summary")
    knowledge = subcommands.add_parser("knowledge", help="Validate and synchronize knowledge")
    knowledge_commands = knowledge.add_subparsers(dest="knowledge_command", required=True)
    knowledge_validate = knowledge_commands.add_parser(
        "validate", help="Validate the local synthetic knowledge corpus"
    )
    knowledge_validate.add_argument("--format", choices=("json", "summary"), default="summary")
    knowledge_sync = knowledge_commands.add_parser(
        "sync", help="Plan or apply a hash-based knowledge synchronization"
    )
    knowledge_sync.add_argument("--env", choices=("dev",), default="dev")
    knowledge_sync.add_argument("--mode", choices=("plan", "apply"), default="plan")
    knowledge_sync.add_argument("--format", choices=("json", "summary"), default="summary")
    knowledge_smoke = knowledge_commands.add_parser(
        "smoke", help="Run deterministic local retrieval queries"
    )
    knowledge_smoke.add_argument("--format", choices=("json", "summary"), default="summary")
    evidence = subcommands.add_parser("evidence", help="Exercise bounded evidence collectors")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_smoke = evidence_commands.add_parser(
        "smoke", help="Run deterministic fixture evidence collection"
    )
    evidence_smoke.add_argument("--scenario", choices=("SCN-001",), default="SCN-001")
    evidence_smoke.add_argument("--env", choices=("dev",), default="dev")
    evidence_smoke.add_argument("--format", choices=("json", "summary"), default="summary")
    agent = subcommands.add_parser("agent", help="Run bounded ADK incident reasoning")
    agent_commands = agent.add_subparsers(dest="agent_command", required=True)
    agent_run = agent_commands.add_parser("run", help="Run one fixture agent case")
    agent_run.add_argument(
        "--scenario",
        choices=tuple(f"SCN-{index:03d}" for index in range(1, 8)),
        default="SCN-001",
    )
    agent_run.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    agent_eval = agent_commands.add_parser("eval", help="Run the seven-case agent fixture suite")
    agent_eval.add_argument("--format", choices=("json", "summary"), default="summary")
    agent_runtime = agent_commands.add_parser(
        "runtime", help="Package the fixed-scope Agent Runtime"
    )
    runtime_commands = agent_runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_package = runtime_commands.add_parser(
        "package", help="Create a deterministic runtime source archive under .tmp"
    )
    runtime_package.add_argument("--output", default=".tmp/m7-runtime")
    return parser


async def _replay(scenario: str, output_format: str) -> int:
    report = await run_fixture_investigation(scenario)
    if output_format == "markdown":
        print(render_markdown(report), end="")
    else:
        print(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "replay":
        return asyncio.run(_replay(str(args.scenario), str(args.format)))
    if args.command == "serve":
        uvicorn.run(
            "opspilot.api:create_app", factory=True, host=str(args.host), port=int(args.port)
        )
        return 0
    if args.command == "demo" and args.demo_command == "serve":
        port = int(args.port) if args.port is not None else int(os.environ.get("PORT", "8080"))
        uvicorn.run(
            "opspilot.demo.api:create_app",
            factory=True,
            host=str(args.host),
            port=port,
            access_log=False,
        )
        return 0
    if args.command == "demo" and args.demo_command == "load":
        summary = asyncio.run(
            run_load(
                orders=int(args.orders),
                concurrency=int(args.concurrency),
                auth=str(args.auth),
            )
        )
        print(json.dumps(summary.model_dump(), separators=(",", ":")))
        return 0 if summary.failed == 0 else 2
    if args.command == "scenario" and args.scenario_command == "run":
        scenario_result = asyncio.run(
            run_scenario(scenario_id=str(args.scenario), auth=str(args.auth))
        )
        if args.format == "json":
            print(json.dumps(scenario_result.model_dump(), separators=(",", ":")))
        else:
            print(render_scenario_summary(scenario_result), end="")
        return 0 if scenario_result.ground_truth_matched and scenario_result.recovered else 2
    if args.command == "knowledge" and args.knowledge_command == "validate":
        validation = validate_knowledge()
        if args.format == "json":
            print(json.dumps(validation.model_dump(), indent=2))
        else:
            print(render_knowledge_result(validation), end="")
        return 0 if validation.valid else 2
    if args.command == "knowledge" and args.knowledge_command == "sync":
        sync_result = run_knowledge_sync(str(args.env), cast(KnowledgeSyncMode, str(args.mode)))
        if args.format == "json":
            print(json.dumps(sync_result.model_dump(), indent=2))
        else:
            print(render_knowledge_result(sync_result), end="")
        return 0
    if args.command == "knowledge" and args.knowledge_command == "smoke":
        smoke = run_local_smoke()
        if args.format == "json":
            print(json.dumps(smoke.model_dump(), indent=2))
        else:
            print(render_knowledge_result(smoke), end="")
        return 0 if smoke.passed else 2
    if args.command == "evidence" and args.evidence_command == "smoke":
        evidence_result = asyncio.run(
            run_evidence_smoke(
                backend=EvidenceBackend.FIXTURE,
                scenario_id=str(args.scenario),
                environment=str(args.env),
            )
        )
        if args.format == "json":
            print(json.dumps(evidence_result.model_dump(mode="json"), indent=2))
        else:
            print(render_evidence_summary(evidence_result), end="")
        return 0 if evidence_result.succeeded else 2
    if args.command == "agent":
        try:
            from opspilot.agent.contracts import AgentBackend, ModelBackend
            from opspilot.agent.runner import (
                render_agent_eval,
                render_agent_result,
                run_agent_eval,
                run_agent_investigation,
            )
            from opspilot.agent.runtime import package_runtime, render_runtime_summary
        except ImportError:
            print("The agent extra is required: uv sync --extra agent")
            return 2
        if args.agent_command == "run":
            agent_result = asyncio.run(
                run_agent_investigation(
                    backend=AgentBackend.FIXTURE,
                    scenario_id=str(args.scenario),
                    model_backend=ModelBackend.FAKE,
                )
            )
            print(render_agent_result(agent_result, str(args.format)), end="")
            return 0 if agent_result.succeeded else 2
        if args.agent_command == "eval":
            eval_result = asyncio.run(run_agent_eval(model_backend=ModelBackend.FAKE))
            print(render_agent_eval(eval_result, str(args.format)), end="")
            return 0 if eval_result.passed else 2
        if args.agent_command == "runtime" and args.runtime_command == "package":
            package_result = package_runtime(Path(str(args.output)))
            print(render_runtime_summary(package_result), end="")
            return 0 if package_result.succeeded else 2
    raise AssertionError("unreachable command")
