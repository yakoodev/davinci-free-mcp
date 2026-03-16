"""Autonomous live Resolve runner for embedded-executor smoke flows."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LiveResolveRunnerError(RuntimeError):
    """Raised when live Resolve automation cannot complete."""


@dataclass(slots=True)
class LiveRunnerConfig:
    project_name: str
    command: str
    resolve_timeout_seconds: int = 45
    executor_timeout_seconds: int = 120
    project_timeout_seconds: int = 30
    fresh_within_seconds: int = 90
    resolve_path: str = r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
    container_name: str = "davinci-free-mcp"
    reinstall_bootstrap: bool = False
    repo_root: Path = Path.cwd()


@dataclass(slots=True)
class ExecutorSnapshot:
    available: bool
    running: bool
    resolve_connected: bool
    age_seconds: float | None
    raw_status: dict[str, Any] | None
    status_present: bool
    lock_present: bool

    def is_healthy(self, fresh_within_seconds: int) -> bool:
        if not self.available or not self.running or not self.resolve_connected:
            return False
        if self.age_seconds is None:
            return False
        return self.age_seconds <= fresh_within_seconds


class LiveResolveRunner:
    """Host-side orchestrator for backend + Resolve + embedded executor."""

    def __init__(
        self,
        config: LiveRunnerConfig,
        *,
        container_checker=None,
        process_lister=None,
        status_loader=None,
        script_runner=None,
        bootstrap_launcher=None,
        backend_invoker=None,
        command_runner=None,
        logger=None,
    ) -> None:
        self.config = config
        self.repo_root = config.repo_root
        self.status_path = self.repo_root / "runtime" / "status" / "executor_status.json"
        self.lock_path = self.repo_root / "runtime" / "status" / "executor.lock.json"
        self.scripts_dir = self.repo_root / "scripts"
        self._container_checker = container_checker or self._default_container_checker
        self._process_lister = process_lister or self._default_process_lister
        self._status_loader = status_loader or self._default_status_loader
        self._script_runner = script_runner or self._default_script_runner
        self._bootstrap_launcher = bootstrap_launcher or self._default_bootstrap_launcher
        self._backend_invoker = backend_invoker or self._default_backend_invoker
        self._command_runner = command_runner or self._default_command_runner
        self._logger = logger or self._default_logger

    def run(self) -> int:
        self._ensure_backend_container()
        if self.config.reinstall_bootstrap:
            self._log("Reinstalling Resolve bootstrap.")
            self._run_script("dev_install_executor.ps1")

        snapshot = self._load_snapshot()
        if snapshot.is_healthy(self.config.fresh_within_seconds):
            self._log("Healthy executor detected, reusing current Resolve session.")
        else:
            self._prepare_healthy_executor(snapshot)

        self._ensure_project_open(self.config.project_name, self.config.project_timeout_seconds)
        self._log("Running agent command.")
        exit_code = self._command_runner(self.config.command)
        if exit_code != 0:
            raise LiveResolveRunnerError(f"Agent command failed with exit code {exit_code}.")
        self._log("Live run completed successfully.")
        return exit_code

    def _prepare_healthy_executor(self, snapshot: ExecutorSnapshot) -> None:
        resolve_running = self._is_resolve_running()
        if not resolve_running and (snapshot.status_present or snapshot.lock_present):
            self._log("Recovering host runtime before live run.")
            self._run_script("dev_kill_davinci.ps1")
            self._run_script("dev_reset_runtime.ps1", "-IncludeLock")
            snapshot = self._load_snapshot()

        if not resolve_running:
            self._log("Starting Resolve with Python-aware helper.")
            self._run_script("dev_start_resolve_with_python.ps1", "-ResolvePath", self.config.resolve_path)
            self._wait_for_condition(
                lambda: self._is_resolve_running(),
                self.config.resolve_timeout_seconds,
                f"Resolve did not start within {self.config.resolve_timeout_seconds} seconds.",
            )
            self._log(f"Opening target project '{self.config.project_name}' through startup helper.")
            self._run_script(
                "dev_agent_project_start.ps1",
                "-TargetMode",
                "existing",
                "-ProjectName",
                self.config.project_name,
                "-Command",
                "cmd /c exit 0",
                "-WarmupSeconds",
                "15",
                "-TimeoutSeconds",
                str(max(self.config.resolve_timeout_seconds, self.config.project_timeout_seconds)),
            )

        launch_error: Exception | None = None
        try:
            self._log("Launching embedded executor from Resolve UI.")
            self._bootstrap_launcher()
        except Exception as exc:
            launch_error = exc

        if launch_error is not None:
            self._log("Bootstrap UI launch failed, retrying with clean Resolve restart.")
            self._run_script("dev_kill_davinci.ps1")
            self._run_script("dev_reset_runtime.ps1", "-IncludeLock")
            self._run_script("dev_start_resolve_with_python.ps1", "-ResolvePath", self.config.resolve_path)
            self._wait_for_condition(
                lambda: self._is_resolve_running(),
                self.config.resolve_timeout_seconds,
                f"Resolve did not start within {self.config.resolve_timeout_seconds} seconds.",
            )
            self._run_script(
                "dev_agent_project_start.ps1",
                "-TargetMode",
                "existing",
                "-ProjectName",
                self.config.project_name,
                "-Command",
                "cmd /c exit 0",
                "-WarmupSeconds",
                "15",
                "-TimeoutSeconds",
                str(max(self.config.resolve_timeout_seconds, self.config.project_timeout_seconds)),
            )
            try:
                self._bootstrap_launcher()
            except Exception as retry_exc:
                raise LiveResolveRunnerError(
                    "Failed to launch resolve_executor_bootstrap via Resolve UI automation. "
                    f"Initial error: {launch_error}. Retry error: {retry_exc}"
                ) from retry_exc

        self._log("Waiting for embedded executor to become healthy.")
        self._wait_for_condition(
            lambda: self._load_snapshot().is_healthy(self.config.fresh_within_seconds),
            self.config.executor_timeout_seconds,
            "Executor did not become healthy within "
            f"{self.config.executor_timeout_seconds} seconds after UI bootstrap launch.",
        )

    def _ensure_project_open(self, project_name: str, timeout_seconds: int) -> None:
        timeout_ms = timeout_seconds * 1000
        current = self._backend_invoker("project_current", {"timeout_ms": timeout_ms})
        if (
            current["exit_code"] == 0
            and current["result"].get("data", {}).get("project", {}).get("open")
            and current["result"].get("data", {}).get("project", {}).get("name") == project_name
        ):
            self._log(f"Target project '{project_name}' is already open.")
            return

        self._log(f"Opening Resolve project '{project_name}' through backend service.")
        opened = self._backend_invoker(
            "project_open",
            {"project_name": project_name, "timeout_ms": timeout_ms},
        )
        if opened["exit_code"] != 0:
            message = opened["result"].get("error", {}).get("message") or "project_open failed."
            raise LiveResolveRunnerError(message)

        confirmed = self._backend_invoker("project_current", {"timeout_ms": timeout_ms})
        if (
            confirmed["exit_code"] != 0
            or not confirmed["result"].get("data", {}).get("project", {}).get("open")
            or confirmed["result"].get("data", {}).get("project", {}).get("name") != project_name
        ):
            raise LiveResolveRunnerError(
                f"Project '{project_name}' did not become current after project_open."
            )

    def _load_snapshot(self) -> ExecutorSnapshot:
        return self._status_loader(self.status_path, self.lock_path)

    def _ensure_backend_container(self) -> None:
        if not self._container_checker(self.config.container_name):
            raise LiveResolveRunnerError(
                f"Docker container '{self.config.container_name}' is not running. "
                "Start the backend with .\\scripts\\dev_up.ps1 first."
            )

    def _is_resolve_running(self) -> bool:
        return any("Resolve.exe" in line for line in self._process_lister())

    def _run_script(self, script_name: str, *args: str) -> None:
        self._script_runner(str(self.scripts_dir / script_name), list(args))

    def _wait_for_condition(self, condition, timeout_seconds: int, failure_message: str) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.5)
        raise LiveResolveRunnerError(failure_message)

    def _log(self, message: str) -> None:
        self._logger(f"[agent-live] {message}")

    @staticmethod
    def _default_container_checker(name: str) -> bool:
        completed = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "true"

    @staticmethod
    def _default_process_lister() -> list[str]:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.splitlines()

    @staticmethod
    def _default_status_loader(status_path: Path, lock_path: Path) -> ExecutorSnapshot:
        raw_status: dict[str, Any] | None = None
        status_present = status_path.exists()
        lock_present = lock_path.exists()
        if status_present:
            try:
                raw_status = json.loads(status_path.read_text(encoding="utf-8"))
            except Exception:
                raw_status = None

        age_seconds: float | None = None
        last_poll_at = None if raw_status is None else raw_status.get("last_poll_at")
        if isinstance(last_poll_at, str) and last_poll_at.strip():
            normalized = last_poll_at.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
            except Exception:
                age_seconds = None

        return ExecutorSnapshot(
            available=raw_status is not None,
            running=bool(raw_status and raw_status.get("running")),
            resolve_connected=bool(raw_status and raw_status.get("resolve", {}).get("connected")),
            age_seconds=age_seconds,
            raw_status=raw_status,
            status_present=status_present,
            lock_present=lock_present,
        )

    @staticmethod
    def _default_script_runner(script_path: str, args: list[str]) -> None:
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
            *args,
        ]
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise LiveResolveRunnerError(
                f"Script '{Path(script_path).name}' failed with exit code {completed.returncode}."
            )

    def _default_bootstrap_launcher(self) -> None:
        self._run_script("dev_launch_executor_ui.ps1")

    def _default_backend_invoker(self, method: str, arguments: dict[str, Any]) -> dict[str, Any]:
        kwargs_json = json.dumps(arguments, separators=(",", ":"))
        python_code = """import json, sys
from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import create_bridge
from davinci_free_mcp.config import AppSettings
settings = AppSettings()
backend = ResolveBackendService(create_bridge(settings), settings)
method = getattr(backend, sys.argv[1])
kwargs = json.loads(sys.argv[2])
result = method(**kwargs)
print(result.model_dump_json())
sys.exit(0 if result.success else 2)
"""
        completed = subprocess.run(
            ["docker", "exec", "-i", self.config.container_name, "python", "-", method, kwargs_json],
            input=python_code,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = completed.stdout.strip()
        if not stdout:
            raise LiveResolveRunnerError(f"Backend tool '{method}' returned no output.")
        try:
            payload = json.loads(stdout)
        except Exception as exc:
            raise LiveResolveRunnerError(
                f"Backend tool '{method}' returned malformed JSON: {stdout}"
            ) from exc
        return {"exit_code": completed.returncode, "result": payload}

    @staticmethod
    def _default_command_runner(command: str) -> int:
        completed = subprocess.run(command, shell=True, check=False)
        return int(completed.returncode)

    @staticmethod
    def _default_logger(message: str) -> None:
        print(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an autonomous live Resolve automation flow via the embedded executor."
    )
    parser.add_argument("--project-name", required=True, help="Resolve project name to open.")
    parser.add_argument("--command", required=True, help="Host command to run after project open.")
    parser.add_argument("--resolve-timeout-seconds", type=int, default=45)
    parser.add_argument("--executor-timeout-seconds", type=int, default=120)
    parser.add_argument("--project-timeout-seconds", type=int, default=30)
    parser.add_argument("--fresh-within-seconds", type=int, default=90)
    parser.add_argument("--resolve-path", default=r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe")
    parser.add_argument("--container-name", default="davinci-free-mcp")
    parser.add_argument("--reinstall-bootstrap", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    runner = LiveResolveRunner(
        LiveRunnerConfig(
            project_name=args.project_name,
            command=args.command,
            resolve_timeout_seconds=args.resolve_timeout_seconds,
            executor_timeout_seconds=args.executor_timeout_seconds,
            project_timeout_seconds=args.project_timeout_seconds,
            fresh_within_seconds=args.fresh_within_seconds,
            resolve_path=args.resolve_path,
            container_name=args.container_name,
            reinstall_bootstrap=args.reinstall_bootstrap,
            repo_root=Path.cwd(),
        )
    )
    try:
        exit_code = runner.run()
    except LiveResolveRunnerError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
