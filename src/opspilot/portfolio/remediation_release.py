from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from opspilot.portfolio.release import source_metadata
from opspilot.remediation.client import gcloud_identity_token
from opspilot.remediation.contracts import RemediationStatus
from opspilot.remediation.executor import GoogleCloudRunAdmin
from opspilot.remediation.firestore_store import FirestoreRemediationStore
from opspilot.remediation.google import _authorized_session
from opspilot.remediation.scenario import ScenarioRecoveryRecord

ARTIFACT_SCHEMA_VERSION = "remediation-release-v1"
PUBLISHED_DIRECTORY = Path("docs/portfolio/results")
REQUIRED_TRANSITIONS = [
    "WAITING_APPROVAL",
    "APPROVED",
    "EXECUTING",
    "SUCCEEDED",
]


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str = ""


ProcessRunner = Callable[[Sequence[str], Path, Mapping[str, str]], ProcessResult]


class PhaseProbe(Protocol):
    def post_apply(self) -> dict[str, object]: ...

    def e2e(self, recovery_path: Path) -> dict[str, object]: ...


def _run_process(
    command: Sequence[str], cwd: Path, environment: Mapping[str, str]
) -> ProcessResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(environment),
            check=False,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ProcessResult(127)
    return ProcessResult(completed.returncode, completed.stdout)


def _gcloud_executable() -> str:
    return shutil.which("gcloud.cmd") or shutil.which("gcloud") or "gcloud"


def _bounded_output(root: Path, output: Path) -> Path:
    resolved_root = root.resolve()
    allowed = (resolved_root / ".tmp").resolve()
    resolved = output.resolve() if output.is_absolute() else (resolved_root / output).resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError("M8 release output must remain under .tmp")
    return resolved


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("M8 release phase artifact must be an object")
    return cast(dict[str, object], value)


def _status_code(url: str, token: str | None = None) -> int:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            response.read()
            return int(response.status)
    except HTTPError as error:
        status = error.code
        error.close()
        return status
    except (URLError, TimeoutError):
        return 0


def _safe_phase_failure(phase: str, code: str) -> dict[str, object]:
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "phase": phase,
        "status": "failed",
        "checks": {},
        "failure_codes": [code],
    }


def terraform_plan_summary(path: Path) -> dict[str, int | bool]:
    payload = _read_json(path)
    raw_changes = payload.get("resource_changes")
    if not isinstance(raw_changes, list):
        raise ValueError("Terraform plan JSON has no resource changes")
    counts = {"create": 0, "update": 0, "delete": 0, "replace": 0, "no_op": 0}
    for raw_change in raw_changes:
        if not isinstance(raw_change, dict):
            continue
        change = raw_change.get("change")
        if not isinstance(change, dict):
            continue
        raw_actions = change.get("actions")
        actions = [str(value) for value in raw_actions] if isinstance(raw_actions, list) else []
        action_set = set(actions)
        if action_set == {"create"}:
            counts["create"] += 1
        elif action_set == {"update"}:
            counts["update"] += 1
        elif action_set == {"delete"}:
            counts["delete"] += 1
        elif "create" in action_set and "delete" in action_set:
            counts["replace"] += 1
        elif action_set == {"no-op"}:
            counts["no_op"] += 1
    return {
        **counts,
        "allowed": counts["create"] > 0
        and counts["update"] == 0
        and counts["delete"] == 0
        and counts["replace"] == 0,
    }


class GoogleM8PhaseProbe:
    def __init__(
        self,
        *,
        root: Path,
        process_runner: ProcessRunner = _run_process,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.root = root
        self.process_runner = process_runner
        self.environment = dict(environment or os.environ)

    def _required(self, name: str) -> str:
        value = self.environment.get(name, "").strip()
        if not value:
            raise RuntimeError("required M8 release configuration is unavailable")
        return value

    def _process(self, command: Sequence[str]) -> ProcessResult:
        resolved = list(command)
        if resolved and resolved[0] == "gcloud":
            resolved[0] = _gcloud_executable()
        return self.process_runner(resolved, self.root, self.environment)

    def _json_process(self, command: Sequence[str]) -> dict[str, object]:
        result = self._process(command)
        if result.returncode != 0:
            raise RuntimeError("read-only cloud probe failed")
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise RuntimeError("read-only cloud probe returned invalid data")
        return cast(dict[str, object], value)

    @staticmethod
    def _ready(service: Mapping[str, object]) -> bool:
        status = service.get("status")
        if not isinstance(status, dict):
            return False
        conditions = status.get("conditions")
        if not isinstance(conditions, list):
            return False
        return any(
            isinstance(item, dict)
            and item.get("type") == "Ready"
            and str(item.get("status")).casefold() == "true"
            for item in conditions
        )

    @staticmethod
    def _service_url(service: Mapping[str, object]) -> str:
        status = service.get("status")
        if isinstance(status, dict):
            value = status.get("url") or status.get("uri")
            if isinstance(value, str):
                return value
        value = service.get("uri")
        return value if isinstance(value, str) else ""

    @staticmethod
    def _internal_ingress(service: Mapping[str, object]) -> bool:
        rendered = json.dumps(service, separators=(",", ":")).casefold()
        return (
            '"ingress":"internal"' in rendered
            or '"ingress":"ingress_traffic_internal_only"' in rendered
            or '"run.googleapis.com/ingress":"internal"' in rendered
        )

    @staticmethod
    def _invoker_members(policy: Mapping[str, object]) -> list[str]:
        bindings = policy.get("bindings")
        members: list[str] = []
        if isinstance(bindings, list):
            for binding in bindings:
                if not isinstance(binding, dict) or binding.get("role") != "roles/run.invoker":
                    continue
                raw_members = binding.get("members")
                if isinstance(raw_members, list):
                    members.extend(str(value) for value in raw_members)
        return members

    def _impersonated_token(self, account: str, audience: str) -> str:
        result = self._process(
            (
                "gcloud",
                "auth",
                "print-identity-token",
                f"--impersonate-service-account={account}",
                f"--audiences={audience}",
                "--include-email",
            )
        )
        token = result.stdout.strip()
        if result.returncode != 0 or not token:
            raise RuntimeError("negative-smoke identity token is unavailable")
        return token

    def post_apply(self) -> dict[str, object]:
        region = self._required("OPSPILOT_REMEDIATION_REGION")
        control_url = self._required("OPSPILOT_REMEDIATION_URL").rstrip("/")
        audience = self._required("OPSPILOT_REMEDIATION_CONTROL_AUDIENCE")
        control = self._json_process(
            (
                "gcloud",
                "run",
                "services",
                "describe",
                "opspilot-dev-remediation-control",
                f"--region={region}",
                "--format=json",
            )
        )
        executor = self._json_process(
            (
                "gcloud",
                "run",
                "services",
                "describe",
                "opspilot-dev-remediation-executor",
                f"--region={region}",
                "--format=json",
            )
        )
        control_policy = self._json_process(
            (
                "gcloud",
                "run",
                "services",
                "get-iam-policy",
                "opspilot-dev-remediation-control",
                f"--region={region}",
                "--format=json",
            )
        )
        executor_policy = self._json_process(
            (
                "gcloud",
                "run",
                "services",
                "get-iam-policy",
                "opspilot-dev-remediation-executor",
                f"--region={region}",
                "--format=json",
            )
        )
        database = self._json_process(
            (
                "gcloud",
                "firestore",
                "databases",
                "describe",
                "--database=opspilot-dev",
                "--format=json",
            )
        )
        workflow = self._json_process(
            (
                "gcloud",
                "workflows",
                "describe",
                "opspilot-dev-remediation",
                f"--location={region}",
                "--format=json",
            )
        )
        investigator = self._process(
            (
                "terraform",
                "-chdir=infra/terraform/environments/dev",
                "output",
                "-raw",
                "investigator_service_account_email",
            )
        )
        if investigator.returncode != 0 or not investigator.stdout.strip():
            raise RuntimeError("investigator identity output is unavailable")
        active_token = gcloud_identity_token(audience)
        denied_token = self._impersonated_token(investigator.stdout.strip(), audience)
        executor_url = self._service_url(executor).rstrip("/")
        control_members = self._invoker_members(control_policy)
        executor_members = self._invoker_members(executor_policy)
        ttl_checks = []
        for collection in ("idempotency_keys", "remediation_callbacks"):
            ttl = self._process(
                (
                    "gcloud",
                    "firestore",
                    "fields",
                    "ttls",
                    "list",
                    "--database=opspilot-dev",
                    f"--collection-group={collection}",
                    "--format=json",
                )
            )
            ttl_checks.append(ttl.returncode == 0 and bool(ttl.stdout.strip()))
        checks: dict[str, object] = {
            "control_ready": self._ready(control),
            "executor_ready": self._ready(executor),
            "executor_internal_ingress": self._internal_ingress(executor),
            "unauthenticated_control_denied": _status_code(f"{control_url}/health")
            in {401, 403, 404},
            "approver_control_allowed": _status_code(f"{control_url}/health", active_token) == 200,
            "investigator_control_denied": _status_code(f"{control_url}/health", denied_token)
            in {401, 403, 404},
            "external_executor_denied": bool(executor_url)
            and _status_code(f"{executor_url}/health", active_token) in {401, 403, 404},
            "no_public_invoker": not any(
                value in {"allUsers", "allAuthenticatedUsers"}
                for value in [*control_members, *executor_members]
            ),
            "group_control_invoker": sum(value.startswith("group:") for value in control_members)
            == 1,
            "workflow_only_executor_invoker": len(executor_members) == 1
            and executor_members[0].startswith("serviceAccount:"),
            "firestore_native": database.get("type") == "FIRESTORE_NATIVE",
            "firestore_delete_protected": database.get("deleteProtectionState")
            == "DELETE_PROTECTION_ENABLED",
            "ttl_fields_active": all(ttl_checks),
            "workflow_active": str(workflow.get("state", "")).casefold() == "active",
        }
        return checks

    async def _audit_update_count(
        self, *, start: datetime, end: datetime, service_name: str
    ) -> int:
        project_id = self._required("OPSPILOT_REMEDIATION_PROJECT_ID")
        principal = f"opspilot-dev-rem-executor@{project_id}.iam.gserviceaccount.com"
        filter_value = (
            'protoPayload.methodName="google.cloud.run.v2.Services.UpdateService" AND '
            f'protoPayload.resourceName="{service_name}" AND '
            f'protoPayload.authenticationInfo.principalEmail="{principal}" AND '
            f'timestamp>="{start.isoformat()}" AND timestamp<="{end.isoformat()}"'
        )
        session = _authorized_session()
        count = 0
        page_token: str | None = None
        while True:
            payload: dict[str, object] = {
                "resourceNames": [f"projects/{project_id}"],
                "filter": filter_value,
                "pageSize": 100,
            }
            if page_token is not None:
                payload["pageToken"] = page_token
            response = await asyncio.to_thread(
                session.post,
                "https://logging.googleapis.com/v2/entries:list",
                json=cast(Any, payload),
                timeout=20,
            )
            if response.status_code != 200:
                raise RuntimeError("audit log verification is unavailable")
            body = cast(dict[str, Any], response.json())
            entries = body.get("entries", [])
            if isinstance(entries, list):
                count += len(entries)
            raw_token = body.get("nextPageToken")
            page_token = raw_token if isinstance(raw_token, str) and raw_token else None
            if page_token is None:
                return count

    async def _e2e_async(self, recovery_path: Path) -> dict[str, object]:
        recovery = ScenarioRecoveryRecord.model_validate_json(
            recovery_path.read_text(encoding="utf-8")
        )
        project_id = self._required("OPSPILOT_REMEDIATION_PROJECT_ID")
        store = FirestoreRemediationStore(project_id=project_id, database_id="opspilot-dev")
        record = await store.get_latest_remediation_for_incident(recovery.incident_id)
        if record is None:
            raise RuntimeError("remediation evidence is unavailable")
        events = await store.list_events(record.remediation_id)
        approval = next(
            (event for event in events if event.to_status is RemediationStatus.APPROVED), None
        )
        if approval is None:
            raise RuntimeError("approval audit event is unavailable")
        cloud_run = GoogleCloudRunAdmin()
        service = await cloud_run.get_service(recovery.target.service_name)
        session = _authorized_session()
        response = await asyncio.to_thread(
            session.get,
            f"https://run.googleapis.com/v2/{recovery.target.service_name}",
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError("payment service verification is unavailable")
        service_body = cast(dict[str, Any], response.json())
        template = cast(dict[str, Any], service_body.get("template", {}))
        containers = cast(list[dict[str, Any]], template.get("containers", []))
        environment = cast(list[dict[str, str]], containers[0].get("env", [])) if containers else []
        failure_profile_absent = not any(
            item.get("name") == "OPSPILOT_PAYMENT_FAILURE_PROFILE" for item in environment
        )
        preapproval_updates = await self._audit_update_count(
            start=record.created_at,
            end=approval.occurred_at,
            service_name=recovery.target.service_name,
        )
        postapproval_updates = await self._audit_update_count(
            start=approval.occurred_at,
            end=record.updated_at,
            service_name=recovery.target.service_name,
        )
        workflow_runs = self._process(
            (
                "gcloud",
                "workflows",
                "executions",
                "list",
                "opspilot-dev-remediation",
                f"--location={self._required('OPSPILOT_REMEDIATION_REGION')}",
                "--filter=state=ACTIVE",
                "--format=json",
            )
        )
        active_workflows = (
            json.loads(workflow_runs.stdout) if workflow_runs.returncode == 0 else [1]
        )
        terraform = self._process(
            (
                "terraform",
                "-chdir=infra/terraform/environments/dev",
                "plan",
                "-detailed-exitcode",
                "-input=false",
                "-no-color",
            )
        )
        transitions = [event.to_status.value for event in events]
        checks = {
            "abort_not_used": not recovery.abort_used,
            "baseline_orders": recovery.baseline_successes == 10,
            "faulty_orders": recovery.faulty_order_successes == 0,
            "reset_orders": recovery.reset_order_successes == 10,
            "reset_recorded": recovery.reset_completed_at is not None,
            "fault_window_respected": recovery.fault_deadline_at is not None
            and record.updated_at <= recovery.fault_deadline_at,
            "terminal_succeeded": record.status is RemediationStatus.SUCCEEDED,
            "state_transitions": transitions == REQUIRED_TRANSITIONS,
            "actor_hash_present": bool(events) and all(bool(event.actor_hash) for event in events),
            "self_approved": record.self_approved,
            "single_execution_attempt": bool(record.execution_attempt_id)
            and sum(bool(event.execution_attempt_id) for event in events) == 2,
            "preapproval_updates": preapproval_updates == 0,
            "postapproval_updates": postapproval_updates == 1,
            "target_traffic": not service.reconciling
            and service.traffic.get(record.plan.target_revision) == 100,
            "verification_orders": record.verification_successes == 10,
            "metric_windows_recorded": record.verification_result is not None
            and record.verification_result.metric_windows_recorded,
            "failure_profile_absent": failure_profile_absent,
            "no_active_workflows": isinstance(active_workflows, list)
            and len(active_workflows) == 0,
            "terraform_no_changes": terraform.returncode == 0,
        }
        return {
            "checks": checks,
            "image_digest": recovery.target.target_image_digest,
            "orders": {
                "baseline_successes": recovery.baseline_successes,
                "faulty_successes": recovery.faulty_order_successes,
                "recovery_successes": record.verification_successes,
                "reset_successes": recovery.reset_order_successes,
            },
            "audit": {
                "state_transitions": transitions,
                "actor_hash_present": checks["actor_hash_present"],
                "self_approved": record.self_approved,
                "execution_attempt_count": 1 if record.execution_attempt_id else 0,
            },
            "traffic_updates": {
                "before_approval": preapproval_updates,
                "after_approval": postapproval_updates,
            },
            "verification": {
                "target_traffic_percent": (
                    record.verification_result.target_traffic_percent
                    if record.verification_result is not None
                    else 0
                ),
                "order_successes": record.verification_successes or 0,
                "metric_windows_recorded": checks["metric_windows_recorded"],
            },
        }

    def e2e(self, recovery_path: Path) -> dict[str, object]:
        return asyncio.run(self._e2e_async(recovery_path))


def _phase_artifact(phase: str, result: Mapping[str, object]) -> dict[str, object]:
    checks_value = result.get("checks", result)
    checks = checks_value if isinstance(checks_value, dict) else {}
    failures = [str(name) for name, value in checks.items() if value is not True]
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "phase": phase,
        "status": "passed" if not failures else "failed",
        **{key: value for key, value in result.items() if key != "checks"},
        "checks": checks,
        "failure_codes": failures,
    }


def _render_markdown(artifact: Mapping[str, object]) -> str:
    lines = [
        "# OpsPilot M8 Remediation Release Evidence",
        "",
        f"- Status: **{str(artifact.get('status', 'failed')).upper()}**",
        f"- Schema: `{artifact.get('schema_version')}`",
    ]
    source = artifact.get("source")
    if isinstance(source, dict):
        lines.extend(
            [
                f"- Source commit: `{source.get('git_commit')}`",
                f"- Source tree SHA-256: `{source.get('source_tree_sha256')}`",
            ]
        )
    lines.extend(["", "## Phase results", "", "| Phase | Status |", "| --- | --- |"])
    phases = artifact.get("phases")
    if isinstance(phases, dict):
        for name, value in phases.items():
            status = value.get("status") if isinstance(value, dict) else "failed"
            lines.append(f"| {name} | {str(status).upper()} |")
    lines.extend(["", "## Sanitized evidence", "", "```json"])
    lines.append(json.dumps(artifact.get("evidence", {}), indent=2, ensure_ascii=False))
    lines.extend(["```", ""])
    return "\n".join(lines)


class RemediationReleaseRunner:
    def __init__(
        self,
        *,
        root: Path,
        output: Path,
        process_runner: ProcessRunner = _run_process,
        probe: PhaseProbe | None = None,
    ) -> None:
        self.root = root.resolve()
        self.output = _bounded_output(self.root, output)
        self.process_runner = process_runner
        self.environment = dict(os.environ)
        self.environment["UV_CACHE_DIR"] = str(
            Path(tempfile.gettempdir()) / "opspilot-m8-release-uv-cache"
        )
        self.probe = probe or GoogleM8PhaseProbe(
            root=self.root,
            process_runner=process_runner,
            environment=self.environment,
        )

    def preflight(self) -> tuple[int, dict[str, object]]:
        self.output.mkdir(parents=True, exist_ok=True)
        gcloud = _gcloud_executable()
        commands = {
            "git_diff_check": ("git", "diff", "--check"),
            "local_release_gate": (
                "uv",
                "run",
                "python",
                "scripts/portfolio_release.py",
                "check",
                "--include-infra",
                "--output",
                str((self.output / "local-release").relative_to(self.root)),
            ),
            "remediation_evaluation": (
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
            "prepare_plan": (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "scenario",
                "prepare",
                "--scenario",
                "SCN-008",
                "--mode",
                "plan",
                "--auth",
                "gcloud",
            ),
            "reset_plan": (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "scenario",
                "reset",
                "--scenario",
                "SCN-008",
                "--mode",
                "plan",
                "--auth",
                "gcloud",
            ),
            "abort_plan": (
                "uv",
                "run",
                "--extra",
                "agent",
                "opspilot",
                "scenario",
                "abort",
                "--scenario",
                "SCN-008",
                "--mode",
                "plan",
                "--auth",
                "gcloud",
            ),
            "gcloud_active_account": (
                gcloud,
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ),
            "gcloud_project": (gcloud, "config", "get-value", "project"),
            "docker_daemon": ("docker", "info", "--format={{.ServerVersion}}"),
        }
        checks: dict[str, bool] = {}
        for name, command in commands.items():
            result = self.process_runner(command, self.root, self.environment)
            checks[name] = result.returncode == 0 and (
                name not in {"gcloud_active_account", "gcloud_project", "docker_daemon"}
                or bool(result.stdout.strip())
            )
        checks["required_tools"] = all(
            shutil.which(name) is not None
            for name in ("git", "uv", "terraform", "gcloud", "docker")
        )
        source = source_metadata(self.root)
        checks["clean_working_tree"] = source.get("working_tree_dirty") is False
        artifact = _phase_artifact("preflight", {"checks": checks, "source": source})
        _write_json(self.output / "preflight.json", artifact)
        return (0 if artifact["status"] == "passed" else 2), artifact

    def verify(self, phase: str) -> tuple[int, dict[str, object]]:
        self.output.mkdir(parents=True, exist_ok=True)
        try:
            if phase == "post-apply":
                plan = terraform_plan_summary(self.output / "terraform-plan.json")
                result = {
                    "checks": {
                        "terraform_plan_allowed": plan["allowed"],
                        **self.probe.post_apply(),
                    },
                    "terraform_plan": plan,
                }
            elif phase == "e2e":
                result = self.probe.e2e(self.output / "recovery.json")
            else:
                raise ValueError("unsupported M8 verification phase")
            artifact = _phase_artifact(phase, result)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError):
            artifact = _safe_phase_failure(phase, f"{phase.upper().replace('-', '_')}_FAILED")
        _write_json(self.output / f"{phase}.json", artifact)
        return (0 if artifact["status"] == "passed" else 2), artifact

    def publish(self) -> tuple[int, dict[str, object]]:
        required = {
            name: _read_json(self.output / f"{name}.json")
            for name in ("preflight", "post-apply", "e2e")
        }
        preflight = required["preflight"]
        e2e = required["e2e"]
        source = _mapping(preflight.get("source"))
        passed = all(value.get("status") == "passed" for value in required.values())
        passed = passed and source.get("working_tree_dirty") is False
        evidence: dict[str, object] = {
            key: e2e.get(key)
            for key in ("image_digest", "orders", "audit", "traffic_updates", "verification")
            if key in e2e
        }
        post_apply = required["post-apply"]
        if "terraform_plan" in post_apply:
            evidence["terraform_plan"] = post_apply["terraform_plan"]
        artifact: dict[str, object] = {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "passed" if passed else "failed",
            "source": source,
            "phases": {
                name: {
                    "status": value.get("status"),
                    "failure_codes": value.get("failure_codes", []),
                }
                for name, value in required.items()
            },
            "evidence": evidence,
            "failure_codes": [] if passed else ["M8_RELEASE_GATE_FAILED"],
        }
        _write_json(self.output / f"{ARTIFACT_SCHEMA_VERSION}.json", artifact)
        (self.output / f"{ARTIFACT_SCHEMA_VERSION}.md").write_text(
            _render_markdown(artifact), encoding="utf-8"
        )
        if not passed:
            return 2, artifact
        destination = self.root / PUBLISHED_DIRECTORY
        destination.mkdir(parents=True, exist_ok=True)
        _write_json(destination / f"{ARTIFACT_SCHEMA_VERSION}.json", artifact)
        (destination / f"{ARTIFACT_SCHEMA_VERSION}.md").write_text(
            _render_markdown(artifact), encoding="utf-8"
        )
        return 0, artifact


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify and publish sanitized M8 evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--output", default=".tmp/m8-release")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--phase", choices=("post-apply", "e2e"), required=True)
    verify.add_argument("--output", default=".tmp/m8-release")
    publish = subparsers.add_parser("publish")
    publish.add_argument("--output", default=".tmp/m8-release")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        runner = RemediationReleaseRunner(root=root, output=Path(str(args.output)))
        if args.command == "preflight":
            return runner.preflight()[0]
        if args.command == "verify":
            return runner.verify(str(args.phase))[0]
        return runner.publish()[0]
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
