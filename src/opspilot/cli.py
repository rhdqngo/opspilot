"""OpsPilot command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

import uvicorn

from opspilot.access_check import render_access_summary, run_access_check
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
    access_check = subcommands.add_parser(
        "access-check", help="Run redacted read-only Google Cloud M0 checks"
    )
    access_check.add_argument("--account-alias", default="Edu_687")
    access_check.add_argument("--confirm-project", action="store_true")
    access_check.add_argument("--confirm-billing-currency-krw", action="store_true")
    access_check.add_argument("--format", choices=("json", "summary"), default="summary")
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
    raise AssertionError("unreachable command")
