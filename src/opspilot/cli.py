"""OpsPilot command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from typing import cast

import uvicorn

from opspilot.access_check import render_access_summary, run_access_check
from opspilot.demo.load import run_load
from opspilot.demo.scenario_runner import render_scenario_summary, run_scenario
from opspilot.knowledge import (
    KnowledgeSyncMode,
    render_knowledge_result,
    run_agent_search_smoke,
    run_knowledge_sync,
    run_local_smoke,
    validate_knowledge,
)
from opspilot.reporting import render_markdown
from opspilot.route_check import render_route_summary, run_route_check
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
    access_check = subcommands.add_parser(
        "access-check", help="Run redacted read-only Google Cloud M0 checks"
    )
    access_check.add_argument("--account-alias", default="Edu_687")
    access_check.add_argument("--confirm-project", action="store_true")
    access_check.add_argument("--confirm-billing-currency-krw", action="store_true")
    access_check.add_argument("--format", choices=("json", "summary"), default="summary")
    route_check = subcommands.add_parser(
        "route-check", help="Run redacted read-only Cloud Run route diagnostics"
    )
    route_check.add_argument("--account-alias", default="Edu_687")
    route_check.add_argument("--format", choices=("json", "summary"), default="summary")
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
        "smoke", help="Run deterministic local or gated Agent Search queries"
    )
    knowledge_smoke.add_argument("--backend", choices=("local", "agent-search"), default="local")
    knowledge_smoke.add_argument("--env", choices=("dev",), default="dev")
    knowledge_smoke.add_argument("--format", choices=("json", "summary"), default="summary")
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
    if args.command == "access-check":
        result = run_access_check(
            account_alias=str(args.account_alias),
            project_confirmed=bool(args.confirm_project),
            billing_currency_krw_confirmed=bool(args.confirm_billing_currency_krw),
        )
        if args.format == "json":
            print(json.dumps(result.model_dump(), indent=2))
        else:
            print(render_access_summary(result), end="")
        return 0 if result.m0_ready else 2
    if args.command == "route-check":
        route_result = run_route_check(account_alias=str(args.account_alias))
        if args.format == "json":
            print(json.dumps(route_result.model_dump(), indent=2))
        else:
            print(render_route_summary(route_result), end="")
        return 0 if route_result.route_ready else 2
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
        smoke = (
            run_local_smoke() if args.backend == "local" else run_agent_search_smoke(str(args.env))
        )
        if args.format == "json":
            print(json.dumps(smoke.model_dump(), indent=2))
        else:
            print(render_knowledge_result(smoke), end="")
        return 0 if smoke.passed else 2
    raise AssertionError("unreachable command")
