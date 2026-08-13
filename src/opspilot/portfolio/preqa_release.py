"""Source-bound Gemini Enterprise pre-QA release verification."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.request import urlopen

from opspilot.portfolio.release import source_metadata

SCHEMA_VERSION = "long-spec-preqa-v1"
RELEASE_CONTEXT = "release-context.json"
PUBLISHED_DIRECTORY = Path("docs/portfolio/results")
IMAGE_ADDRESS = "google_cloud_run_v2_service.investigation_api[0]"
RUNTIME_ADDRESS = "google_vertex_ai_reasoning_engine.opspilot[0]"
ALLOWED_ADDRESSES = frozenset({IMAGE_ADDRESS, RUNTIME_ADDRESS})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}$")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _bounded_output(root: Path, output: Path) -> Path:
    resolved_root = root.resolve()
    allowed = (resolved_root / ".tmp").resolve()
    resolved = output.resolve() if output.is_absolute() else (resolved_root / output).resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError("pre-QA release output must remain under .tmp")
    return resolved


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("pre-QA artifact must be a JSON object")
    return value


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _canonical_hash(payload: Mapping[str, object]) -> str:
    return _sha256_bytes(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode())


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, object], value)


def _integer(value: object) -> int:
    return value if isinstance(value, int) else 0


def _release_context(
    source: Mapping[str, object], runtime: Mapping[str, object]
) -> dict[str, object]:
    core = {
        "schema_version": SCHEMA_VERSION,
        "source": dict(source),
        "runtime": {
            "file_count": _integer(runtime.get("file_count")),
            "sha256": str(runtime.get("sha256", "")),
        },
    }
    return {**core, "context_sha256": _canonical_hash(core)}


def _context_matches_source(context: Mapping[str, object], root: Path) -> bool:
    source = context.get("source")
    runtime = context.get("runtime")
    if not isinstance(source, dict) or not isinstance(runtime, dict):
        return False
    current = source_metadata(root)
    return (
        current.get("working_tree_dirty") is False
        and current.get("git_commit") == source.get("git_commit")
        and current.get("source_tree_sha256") == source.get("source_tree_sha256")
        and SHA256_PATTERN.fullmatch(str(runtime.get("sha256", ""))) is not None
    )


def _walk_key(value: object, key: str) -> list[object]:
    found: list[object] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key == key:
                found.append(child)
            found.extend(_walk_key(child, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_key(child, key))
    return found


def terraform_plan_summary(
    path: Path,
    *,
    expected_image_digest: str,
    expected_runtime_sha256: str,
    expected_addresses: frozenset[str] = ALLOWED_ADDRESSES,
) -> dict[str, object]:
    if DIGEST_PATTERN.fullmatch(expected_image_digest) is None:
        raise ValueError("expected investigation image digest is invalid")
    if SHA256_PATTERN.fullmatch(expected_runtime_sha256) is None:
        raise ValueError("expected Runtime SHA-256 is invalid")
    payload = _read_json(path)
    changes = payload.get("resource_changes", [])
    if not isinstance(changes, list):
        raise ValueError("Terraform plan resource_changes must be a list")
    changed: list[str] = []
    add_count = 0
    update_count = 0
    destroy_count = 0
    actions_valid = True
    image_bound = False
    runtime_bound = False
    public_iam = False
    runtime_name_stable = True
    for raw in changes:
        if not isinstance(raw, dict):
            actions_valid = False
            continue
        address = str(raw.get("address", ""))
        change = raw.get("change")
        if not isinstance(change, dict):
            actions_valid = False
            continue
        actions = change.get("actions")
        if actions == ["no-op"]:
            continue
        changed.append(address)
        if isinstance(actions, list):
            add_count += int("create" in actions)
            update_count += int(actions == ["update"])
            destroy_count += int("delete" in actions)
        if actions != ["update"]:
            actions_valid = False
        before = change.get("before")
        after = change.get("after")
        serialized_after = json.dumps(after, sort_keys=True)
        public_iam = (
            public_iam
            or "allUsers" in serialized_after
            or "allAuthenticatedUsers" in serialized_after
        )
        if address == IMAGE_ADDRESS:
            images = [str(item) for item in _walk_key(after, "image") if isinstance(item, str)]
            image_bound = any(item.endswith(f"@{expected_image_digest}") for item in images)
        if address == RUNTIME_ADDRESS:
            before_names = [
                str(item) for item in _walk_key(before, "name") if isinstance(item, str)
            ]
            after_names = [str(item) for item in _walk_key(after, "name") if isinstance(item, str)]
            if before_names and after_names:
                runtime_name_stable = before_names[0] == after_names[0]
            archives = [
                item for item in _walk_key(after, "source_archive") if isinstance(item, str)
            ]
            decoded_hashes: list[str] = []
            for archive in archives:
                try:
                    decoded_hashes.append(_sha256_bytes(base64.b64decode(archive, validate=True)))
                except (binascii.Error, ValueError):
                    continue
            runtime_bound = expected_runtime_sha256 in decoded_hashes
    if not expected_addresses or not expected_addresses.issubset(ALLOWED_ADDRESSES):
        raise ValueError("expected Terraform addresses must be a non-empty allowed subset")
    exact_scope = set(changed) == expected_addresses and len(changed) == len(expected_addresses)
    image_required = IMAGE_ADDRESS in expected_addresses
    runtime_required = RUNTIME_ADDRESS in expected_addresses
    allowed = all(
        (
            exact_scope,
            actions_valid,
            image_bound if image_required else True,
            runtime_bound if runtime_required else True,
            runtime_name_stable,
            not public_iam,
        )
    )
    return {
        "allowed": allowed,
        "add": add_count,
        "update": update_count,
        "destroy": destroy_count,
        "exact_scope": exact_scope,
        "actions_valid": actions_valid,
        "image_bound": image_bound,
        "runtime_bound": runtime_bound,
        "runtime_name_stable": runtime_name_stable,
        "public_iam_absent": not public_iam,
    }


def terraform_no_changes(path: Path) -> bool:
    payload = _read_json(path)
    changes = payload.get("resource_changes", [])
    if not isinstance(changes, list):
        return False
    for raw in changes:
        if not isinstance(raw, dict):
            return False
        change = raw.get("change")
        if isinstance(change, dict) and change.get("actions") not in (None, ["no-op"]):
            return False
    return True


def _run(command: Sequence[str], root: Path, environment: Mapping[str, str]) -> int:
    try:
        return subprocess.run(
            list(command), cwd=root, env=dict(environment), check=False, timeout=1800
        ).returncode
    except (OSError, subprocess.TimeoutExpired):
        return 127


def _status_code(url: str) -> int:
    try:
        with urlopen(url, timeout=2) as response:
            return int(response.status)
    except (OSError, URLError):
        return 0


class PreQaReleaseRunner:
    def __init__(self, *, root: Path, output: Path) -> None:
        self.root = root.resolve()
        self.output = _bounded_output(self.root, output)
        self.environment = dict(os.environ)
        self.environment["UV_CACHE_DIR"] = str(
            Path(tempfile.gettempdir()) / "opspilot-preqa-release-uv-cache"
        )

    def preflight(self) -> tuple[int, dict[str, object]]:
        self.output.mkdir(parents=True, exist_ok=True)
        local_release = self.output / "local-release"
        checks = {
            "local_release_gate": _run(
                (
                    "uv",
                    "run",
                    "python",
                    "scripts/portfolio_release.py",
                    "check",
                    "--include-infra",
                    "--output",
                    str(local_release.relative_to(self.root)),
                ),
                self.root,
                self.environment,
            )
            == 0,
            "remediation_evaluation": _run(
                (
                    "uv",
                    "run",
                    "opspilot",
                    "remediation",
                    "eval",
                    "--suite",
                    "remediation",
                    "--format",
                    "summary",
                ),
                self.root,
                self.environment,
            )
            == 0,
        }
        source = source_metadata(self.root)
        checks["clean_working_tree"] = source.get("working_tree_dirty") is False
        release = _read_json(local_release / "portfolio-release-v1.json")
        validation = release.get("validation")
        runtime = validation.get("runtime_package") if isinstance(validation, dict) else None
        if not isinstance(runtime, dict):
            runtime = {}
        checks["runtime_deterministic"] = (
            int(runtime.get("file_count", 0)) > 0
            and SHA256_PATTERN.fullmatch(str(runtime.get("sha256", ""))) is not None
        )
        context = _release_context(source, runtime)
        _write_json(self.output / RELEASE_CONTEXT, context)
        artifact = self._phase(
            "preflight", checks, {"release_context_sha256": context["context_sha256"]}
        )
        return (0 if artifact["status"] == "passed" else 2), artifact

    def image(self) -> tuple[int, dict[str, object]]:
        context = _read_json(self.output / RELEASE_CONTEXT)
        source = context.get("source")
        commit = str(source.get("git_commit", "")) if isinstance(source, dict) else ""
        local_image = self.environment.get("OPSPILOT_PREQA_LOCAL_IMAGE", "")
        registry_uri = self.environment.get("OPSPILOT_PREQA_REGISTRY_IMAGE_URI", "")
        digest = registry_uri.rsplit("@", 1)[-1] if "@" in registry_uri else ""

        def inspect_image(template: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["docker", "image", "inspect", f"--format={template}", local_image],
                cwd=self.root,
                check=False,
                capture_output=True,
                text=True,
            )

        platform_result = inspect_image("{{.Os}}/{{.Architecture}}")
        user_result = inspect_image("{{.Config.User}}")
        repo_result = inspect_image("{{json .RepoDigests}}")
        name = f"opspilot-preqa-{int(time.time())}"
        started = (
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "-p",
                    "127.0.0.1::8080",
                    "--name",
                    name,
                    local_image,
                    "serve",
                ],
                cwd=self.root,
                check=False,
                capture_output=True,
                text=True,
            ).returncode
            == 0
        )
        health = ready = False
        try:
            if started:
                for _ in range(40):
                    port = subprocess.run(
                        ["docker", "port", name, "8080/tcp"],
                        cwd=self.root,
                        check=False,
                        capture_output=True,
                        text=True,
                    ).stdout.strip()
                    match = re.search(r":([0-9]+)$", port)
                    if match:
                        base = f"http://127.0.0.1:{match.group(1)}"
                        health = _status_code(f"{base}/healthz") == 200
                        ready = _status_code(f"{base}/readyz") == 200
                        if health and ready:
                            break
                    time.sleep(0.25)
        finally:
            if started:
                subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)
        try:
            repo_digests = json.loads(repo_result.stdout)
        except json.JSONDecodeError:
            repo_digests = []
        checks = {
            "release_context_matches": _context_matches_source(context, self.root),
            "full_commit_sha_tag": local_image == f"opspilot-investigation:{commit}",
            "linux_amd64": platform_result.stdout.strip() == "linux/amd64",
            "non_root": user_result.stdout.strip() == "65532:65532",
            "healthz": health,
            "readyz": ready,
            "registry_digest_uri": DIGEST_PATTERN.fullmatch(digest) is not None,
            "local_digest_bound": isinstance(repo_digests, list)
            and any(str(item).endswith(f"@{digest}") for item in repo_digests),
        }
        return self._phase_result("image", checks, {"image_digest_present": bool(digest)})

    def terraform_plan(self) -> tuple[int, dict[str, object]]:
        context = _read_json(self.output / RELEASE_CONTEXT)
        runtime = context.get("runtime")
        if not isinstance(runtime, dict):
            raise ValueError("release context Runtime contract is missing")
        digest = self.environment.get("OPSPILOT_PREQA_IMAGE_DIGEST", "")
        raw_addresses = self.environment.get("OPSPILOT_PREQA_EXPECTED_ADDRESSES", "").strip()
        expected_addresses = (
            frozenset(item.strip() for item in raw_addresses.split(",") if item.strip())
            if raw_addresses
            else ALLOWED_ADDRESSES
        )
        summary = terraform_plan_summary(
            self.output / "terraform-plan-raw.json",
            expected_image_digest=digest,
            expected_runtime_sha256=str(runtime.get("sha256", "")),
            expected_addresses=expected_addresses,
        )
        binary = self.output / "preqa.tfplan"
        checks = {
            "release_context_matches": _context_matches_source(context, self.root),
            "terraform_plan_allowed": summary["allowed"] is True,
            "binary_plan_present": binary.is_file() and binary.stat().st_size > 0,
        }
        extra = {
            "terraform_plan": summary,
            "binary_plan_sha256": _sha256_file(binary) if binary.is_file() else "",
        }
        return self._phase_result("terraform-plan", checks, extra)

    def record(self, phase: str) -> tuple[int, dict[str, object]]:
        allowed = {
            "post-apply": {
                "api_ready",
                "runtime_ready",
                "runtime_name_stable",
                "registration_stable",
                "public_invoker_absent",
                "unexpected_iam_absent",
            },
            "smoke": {
                "scenario_recovered",
                "runtime_two_events",
                "persisted_report",
                "h01_h02",
                "classified_actions",
                "citations_valid",
                "idempotent_20",
                "redaction_verified",
                "trace_linked",
                "tool_logs_valid",
                "privacy_log_scan_clean",
                "unauthenticated_denied",
                "runtime_allowed",
                "runtime_task_denied",
                "runtime_alert_denied",
            },
            "final-plan": {"terraform_no_changes"},
            "hosted": {
                "pr_checks_recorded",
                "terraform_checks_recorded",
                "terraform_plan_recorded",
            },
        }
        input_path = self.output / f"{phase}-input.json"
        values = _read_json(input_path)
        expected = allowed[phase]
        checks = {key: values.get(key) is True for key in sorted(expected)}
        if set(values) != expected:
            checks["fixed_schema"] = False
        context = _read_json(self.output / RELEASE_CONTEXT)
        checks["release_context_matches"] = _context_matches_source(context, self.root)
        return self._phase_result(phase, checks, {})

    def publish(self) -> tuple[int, dict[str, object]]:
        phases = (
            "preflight",
            "image",
            "terraform-plan",
            "post-apply",
            "smoke",
            "final-plan",
            "hosted",
        )
        artifacts = {name: _read_json(self.output / f"{name}.json") for name in phases}
        context = _read_json(self.output / RELEASE_CONTEXT)
        passed = all(item.get("status") == "passed" for item in artifacts.values())
        plan = artifacts["terraform-plan"].get("terraform_plan", {})
        evidence = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "passed" if passed else "failed",
            "source": context.get("source"),
            "runtime": context.get("runtime"),
            "release_context_sha256": context.get("context_sha256"),
            "binary_plan_sha256_present": bool(
                artifacts["terraform-plan"].get("binary_plan_sha256")
            ),
            "terraform_plan": plan,
            "checks": {
                name: item.get("checks", {})
                for name, item in artifacts.items()
                if name in {"post-apply", "smoke", "final-plan", "hosted"}
            },
        }
        serialized = json.dumps(evidence)
        forbidden = (
            "project_id",
            "service_url",
            "actor_hash",
            "trace_id",
            "run_id",
            "investigation_id",
            "@sha256:",
        )
        if any(item in serialized for item in forbidden):
            raise ValueError("pre-QA evidence contains a prohibited identifier")
        _write_json(self.root / PUBLISHED_DIRECTORY / f"{SCHEMA_VERSION}.json", evidence)
        markdown = self._markdown(evidence)
        (self.root / PUBLISHED_DIRECTORY / f"{SCHEMA_VERSION}.md").write_text(
            markdown, encoding="utf-8"
        )
        return (0 if passed else 2), evidence

    def _phase(
        self, phase: str, checks: Mapping[str, bool], extra: Mapping[str, object]
    ) -> dict[str, object]:
        artifact = {
            "schema_version": SCHEMA_VERSION,
            "phase": phase,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": dict(checks),
            "failure_codes": [name for name, value in checks.items() if not value],
            **dict(extra),
        }
        _write_json(self.output / f"{phase}.json", artifact)
        return artifact

    def _phase_result(
        self, phase: str, checks: Mapping[str, bool], extra: Mapping[str, object]
    ) -> tuple[int, dict[str, object]]:
        artifact = self._phase(phase, checks, extra)
        return (0 if artifact["status"] == "passed" else 2), artifact

    @staticmethod
    def _markdown(evidence: Mapping[str, object]) -> str:
        source = _mapping(evidence.get("source"))
        runtime = _mapping(evidence.get("runtime"))
        return "\n".join(
            (
                "# Gemini Enterprise Pre-QA Evidence",
                "",
                f"- Status: **{str(evidence.get('status', 'failed')).upper()}**",
                f"- Source commit: `{source.get('git_commit', '')}`",
                f"- Runtime package files: `{runtime.get('file_count', 0)}`",
                "- Gemini Enterprise Preview UI queries executed: `false`",
                "- Hosted workflows: recorded as pass or external non-blocking zero-step blocker",
                "",
                "All cloud identifiers, URLs, identities, image digests, and execution "
                "identifiers are omitted.",
                "",
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Gemini Enterprise pre-QA readiness")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "image", "terraform-plan", "publish"):
        child = sub.add_parser(name)
        child.add_argument("--output", default=".tmp/preqa-release")
    record = sub.add_parser("record")
    record.add_argument(
        "--phase", choices=("post-apply", "smoke", "final-plan", "hosted"), required=True
    )
    record.add_argument("--output", default=".tmp/preqa-release")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        runner = PreQaReleaseRunner(root=root, output=Path(str(args.output)))
        if args.command == "preflight":
            return runner.preflight()[0]
        if args.command == "image":
            return runner.image()[0]
        if args.command == "terraform-plan":
            return runner.terraform_plan()[0]
        if args.command == "record":
            return runner.record(str(args.phase))[0]
        return runner.publish()[0]
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
