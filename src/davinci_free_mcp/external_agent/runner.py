"""Agent-only Resolve runner that uses external scripting access."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


DEFAULT_RESOLVE_PATH = Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe")
DEFAULT_SCRIPT_API_DIR = Path(
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting"
)
DEFAULT_SCRIPT_MODULE_DIR = DEFAULT_SCRIPT_API_DIR / "Modules"
DEFAULT_FUSIONSCRIPT_DLL = Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll")


class ExternalResolveRunnerError(RuntimeError):
    """Raised when the external Resolve runner cannot proceed."""


@dataclass(slots=True)
class ExternalResolveRunnerConfig:
    project_name: str
    command: str
    resolve_path: Path = DEFAULT_RESOLVE_PATH
    timeout_seconds: int = 120
    poll_interval_seconds: float = 1.0
    launch_wait_seconds: int = 60
    nogui: bool = False


@dataclass(slots=True)
class ExternalResolveState:
    resolve_running: bool
    module_path_exists: bool
    dll_path_exists: bool
    resolve_connected: bool
    project_manager_available: bool
    current_project_name: str | None = None


class ResolveProvider(Protocol):
    """Protocol for host-side Resolve access."""

    def resolve(self) -> Any | None:
        """Return Resolve handle or None."""


class DaVinciResolveScriptProvider:
    """Resolve provider backed by DaVinciResolveScript.scriptapp('Resolve')."""

    def __init__(
        self,
        module_dir: Path = DEFAULT_SCRIPT_MODULE_DIR,
        dll_path: Path = DEFAULT_FUSIONSCRIPT_DLL,
    ) -> None:
        self.module_dir = module_dir
        self.dll_path = dll_path

    def resolve(self) -> Any | None:
        if not self.module_dir.exists():
            return None

        module_dir_str = str(self.module_dir)
        if module_dir_str not in sys.path:
            sys.path.insert(0, module_dir_str)

        os.environ.setdefault("RESOLVE_SCRIPT_API", str(DEFAULT_SCRIPT_API_DIR))
        os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(self.dll_path))
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        if module_dir_str not in existing_pythonpath.split(os.pathsep):
            os.environ["PYTHONPATH"] = (
                module_dir_str
                if not existing_pythonpath
                else existing_pythonpath + os.pathsep + module_dir_str
            )

        try:
            import DaVinciResolveScript as dvr_script  # type: ignore
        except Exception:
            return None

        try:
            return dvr_script.scriptapp("Resolve")
        except Exception:
            return None


class ExternalResolveAgentRunner:
    """External scripting runner for agent-only automation."""

    def __init__(
        self,
        config: ExternalResolveRunnerConfig,
        *,
        resolve_provider: ResolveProvider | None = None,
        process_lister=None,
        process_launcher=None,
        command_runner=None,
        module_dir: Path = DEFAULT_SCRIPT_MODULE_DIR,
        dll_path: Path = DEFAULT_FUSIONSCRIPT_DLL,
    ) -> None:
        self.config = config
        self.module_dir = module_dir
        self.dll_path = dll_path
        self.resolve_provider = resolve_provider or DaVinciResolveScriptProvider(
            module_dir=module_dir,
            dll_path=dll_path,
        )
        self._process_lister = process_lister or self._default_process_lister
        self._process_launcher = process_launcher or self._default_process_launcher
        self._command_runner = command_runner or self._default_command_runner

    def collect_state(self) -> ExternalResolveState:
        resolve_running = self._is_resolve_running()
        resolve = self.resolve_provider.resolve()
        project_manager = self._safe_call(resolve, "GetProjectManager")
        current_project = self._safe_call(project_manager, "GetCurrentProject")
        return ExternalResolveState(
            resolve_running=resolve_running,
            module_path_exists=self.module_dir.exists(),
            dll_path_exists=self.dll_path.exists(),
            resolve_connected=resolve is not None,
            project_manager_available=project_manager is not None,
            current_project_name=self._safe_call(current_project, "GetName"),
        )

    def ensure_resolve_started(self) -> None:
        if self._is_resolve_running():
            return

        if not self.config.resolve_path.exists():
            raise ExternalResolveRunnerError(
                f"Resolve executable not found at '{self.config.resolve_path}'."
            )

        launch_args = [str(self.config.resolve_path)]
        if self.config.nogui:
            launch_args.append("-nogui")
        self._process_launcher(launch_args)

        deadline = time.monotonic() + self.config.launch_wait_seconds
        while time.monotonic() < deadline:
            if self._is_resolve_running():
                return
            time.sleep(self.config.poll_interval_seconds)

        raise ExternalResolveRunnerError(
            f"Resolve did not start within {self.config.launch_wait_seconds} seconds."
        )

    def wait_for_external_scripting(self) -> Any:
        deadline = time.monotonic() + self.config.timeout_seconds
        last_state = self.collect_state()
        while time.monotonic() < deadline:
            resolve = self.resolve_provider.resolve()
            if resolve is not None:
                project_manager = self._safe_call(resolve, "GetProjectManager")
                if project_manager is not None:
                    return resolve
            time.sleep(self.config.poll_interval_seconds)
            last_state = self.collect_state()

        hint = (
            "Check Resolve Preferences -> System -> General and verify external scripting access is enabled."
        )
        raise ExternalResolveRunnerError(
            "External Resolve scripting is not available. "
            f"State: running={last_state.resolve_running}, "
            f"module_path_exists={last_state.module_path_exists}, "
            f"dll_path_exists={last_state.dll_path_exists}, "
            f"resolve_connected={last_state.resolve_connected}, "
            f"project_manager_available={last_state.project_manager_available}. "
            + hint
        )

    def open_project(self, resolve: Any) -> str:
        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            raise ExternalResolveRunnerError("Resolve project manager is not available.")

        opened_project = self._safe_call(project_manager, "LoadProject", self.config.project_name)
        if opened_project is None:
            raise ExternalResolveRunnerError(
                f"Project '{self.config.project_name}' was not found or could not be opened."
            )

        current_project = self._safe_call(project_manager, "GetCurrentProject")
        current_name = self._safe_call(current_project, "GetName")
        if current_name != self.config.project_name:
            raise ExternalResolveRunnerError(
                f"Resolve did not switch to project '{self.config.project_name}'. "
                f"Current project is '{current_name}'."
            )
        return current_name

    def run_agent_command(self) -> int:
        return self._command_runner(self.config.command)

    def run(self) -> int:
        self.ensure_resolve_started()
        resolve = self.wait_for_external_scripting()
        self.open_project(resolve)
        return self.run_agent_command()

    @staticmethod
    def _safe_call(obj: Any, method_name: str, *args: Any) -> Any | None:
        if obj is None:
            return None
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception:
            return None

    @staticmethod
    def _default_process_lister() -> list[str]:
        try:
            output = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return []
        return output.stdout.splitlines()

    def _is_resolve_running(self) -> bool:
        return any("Resolve.exe" in line for line in self._process_lister())

    @staticmethod
    def _default_process_launcher(args: list[str]) -> None:
        subprocess.Popen(args)

    @staticmethod
    def _default_command_runner(command: str) -> int:
        completed = subprocess.run(command, shell=True, check=False)
        return int(completed.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an agent-only Resolve automation flow via external scripting."
    )
    parser.add_argument("--project-name", required=True, help="Resolve project name to open.")
    parser.add_argument("--command", required=True, help="Host command to run after opening project.")
    parser.add_argument(
        "--resolve-path",
        default=str(DEFAULT_RESOLVE_PATH),
        help="Path to Resolve.exe.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Maximum wait for external scripting readiness.",
    )
    parser.add_argument(
        "--launch-wait-seconds",
        type=int,
        default=60,
        help="Maximum wait for Resolve process startup.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=1.0,
        help="Polling interval for Resolve readiness checks.",
    )
    parser.add_argument(
        "--nogui",
        action="store_true",
        help="Launch Resolve with -nogui.",
    )
    parser.add_argument(
        "--script-mode",
        default="command",
        choices=["command"],
        help="Agent-only execution mode. Reserved for future expansion.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = ExternalResolveRunnerConfig(
        project_name=args.project_name,
        command=args.command,
        resolve_path=Path(args.resolve_path),
        timeout_seconds=args.timeout_seconds,
        launch_wait_seconds=args.launch_wait_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        nogui=args.nogui,
    )
    runner = ExternalResolveAgentRunner(config)
    try:
        exit_code = runner.run()
    except ExternalResolveRunnerError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    raise SystemExit(exit_code)
