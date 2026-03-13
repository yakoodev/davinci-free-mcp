"""Agent-only Resolve startup orchestration via prefs and process control."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from davinci_free_mcp.external_agent.runner import (
    DEFAULT_RESOLVE_PATH,
    DEFAULT_SCRIPT_MODULE_DIR,
    ExternalResolveAgentRunner,
    ExternalResolveRunnerConfig,
    ExternalResolveRunnerError,
)

StartupMode = Literal["existing", "blank"]
VerificationState = Literal["confirmed", "likely", "failed"]
ScriptLaunchState = Literal["success", "failed", "skipped"]


class _CallableResolveProvider:
    def __init__(self, func) -> None:
        self._func = func

    def resolve(self) -> Any | None:
        return self._func()


def _appdata_path(*parts: str) -> Path:
    appdata = Path.home() / "AppData" / "Roaming"
    return appdata.joinpath("Blackmagic Design", "DaVinci Resolve", *parts)


DEFAULT_CONFIG_USER_XML = _appdata_path("Preferences", "config.user.xml")
DEFAULT_RECENT_PROJECTS = _appdata_path("Preferences", "recentprojects.conf")
DEFAULT_SUPPORT_DIR = _appdata_path("Support")
DEFAULT_LOG_PATH = DEFAULT_SUPPORT_DIR / "logs" / "davinci_resolve.log"
DEFAULT_LIBRARY_ROOT = DEFAULT_SUPPORT_DIR / "Resolve Project Library" / "Resolve Projects"


class ResolveStartupError(RuntimeError):
    """Raised when startup orchestration cannot proceed."""


@dataclass(slots=True)
class ResolveStartupPaths:
    config_user_xml: Path = DEFAULT_CONFIG_USER_XML
    recent_projects: Path = DEFAULT_RECENT_PROJECTS
    support_dir: Path = DEFAULT_SUPPORT_DIR
    log_path: Path = DEFAULT_LOG_PATH
    library_root: Path = DEFAULT_LIBRARY_ROOT
    backup_root: Path = Path("runtime") / "startup_backups"


@dataclass(slots=True)
class ResolveStartupConfig:
    target_mode: StartupMode
    project_name: str | None = None
    blank_project_name: str = "DFMCP Blank"
    command: str = "cmd /c exit 0"
    resolve_path: Path = DEFAULT_RESOLVE_PATH
    warmup_seconds: int = 60
    timeout_seconds: int = 120
    poll_interval_seconds: float = 1.0
    restore_prefs_on_exit: bool = False

    @property
    def startup_target(self) -> str:
        if self.target_mode == "blank":
            return self.blank_project_name
        if self.project_name is None or not self.project_name.strip():
            raise ResolveStartupError("project_name is required for target_mode='existing'.")
        return self.project_name.strip()


@dataclass(slots=True)
class PreparedStartupTarget:
    startup_target: str
    startup_mode: StartupMode
    prefs_backup_dir: Path
    log_size_before_launch: int
    recent_project_names: list[str]


@dataclass(slots=True)
class ProjectStartupResult:
    startup_target: str
    startup_mode: StartupMode
    project_verification_state: VerificationState
    script_launch_state: ScriptLaunchState
    prefs_backup_path: str
    current_project_name: str | None = None
    verification_reason: str = ""
    scripting_connected: bool = False
    command_exit_code: int | None = None


class ResolveProjectStartupOrchestrator:
    """Open Resolve into a target project via prefs, then run a host command."""

    def __init__(
        self,
        config: ResolveStartupConfig,
        *,
        paths: ResolveStartupPaths | None = None,
        process_lister=None,
        process_launcher=None,
        process_killer=None,
        command_runner=None,
        resolve_provider=None,
    ) -> None:
        self.config = config
        self.paths = paths or ResolveStartupPaths()
        self._process_lister = process_lister or self._default_process_lister
        self._process_launcher = process_launcher or self._default_process_launcher
        self._process_killer = process_killer or self._default_process_killer
        self._command_runner = command_runner or self._default_command_runner
        if resolve_provider is not None and not hasattr(resolve_provider, "resolve"):
            resolve_provider = _CallableResolveProvider(resolve_provider)
        self._external_runner = ExternalResolveAgentRunner(
            ExternalResolveRunnerConfig(
                project_name=self.config.startup_target,
                command=self.config.command,
                resolve_path=self.config.resolve_path,
                timeout_seconds=self.config.timeout_seconds,
                poll_interval_seconds=self.config.poll_interval_seconds,
                launch_wait_seconds=max(10, min(self.config.timeout_seconds, 60)),
            ),
            resolve_provider=resolve_provider,
            process_lister=self._process_lister,
            process_launcher=self._process_launcher,
            command_runner=self._command_runner,
            module_dir=DEFAULT_SCRIPT_MODULE_DIR,
        )

    def run(self) -> ProjectStartupResult:
        prepared = self.prepare_startup_target()
        try:
            self.launch_resolve(prepared)
            verification_state, current_project_name, reason, scripting_connected = (
                self.verify_current_project(prepared)
            )
            if verification_state == "failed":
                self.restore_preferences(prepared.prefs_backup_dir)
                return ProjectStartupResult(
                    startup_target=prepared.startup_target,
                    startup_mode=prepared.startup_mode,
                    project_verification_state=verification_state,
                    script_launch_state="skipped",
                    prefs_backup_path=str(prepared.prefs_backup_dir),
                    current_project_name=current_project_name,
                    verification_reason=reason,
                    scripting_connected=scripting_connected,
                )

            command_exit_code = self._command_runner(self.config.command)
            script_launch_state: ScriptLaunchState = (
                "success" if command_exit_code == 0 else "failed"
            )
            result = ProjectStartupResult(
                startup_target=prepared.startup_target,
                startup_mode=prepared.startup_mode,
                project_verification_state=verification_state,
                script_launch_state=script_launch_state,
                prefs_backup_path=str(prepared.prefs_backup_dir),
                current_project_name=current_project_name,
                verification_reason=reason,
                scripting_connected=scripting_connected,
                command_exit_code=command_exit_code,
            )
            if script_launch_state == "failed":
                self.restore_preferences(prepared.prefs_backup_dir)
                return result
            if self.config.restore_prefs_on_exit:
                self.restore_preferences(prepared.prefs_backup_dir)
            return result
        except Exception:
            self.restore_preferences(prepared.prefs_backup_dir)
            raise

    def prepare_startup_target(self) -> PreparedStartupTarget:
        startup_target = self.config.startup_target
        if not self.paths.config_user_xml.exists():
            raise ResolveStartupError(
                f"Resolve config file not found at '{self.paths.config_user_xml}'."
            )

        recent_project_names = self.read_recent_project_names()
        if startup_target not in recent_project_names and not self.project_exists_in_library(startup_target):
            raise ResolveStartupError(
                f"Project '{startup_target}' was not found in recentprojects.conf or the local Resolve project library."
            )

        backup_dir = self.create_backup()
        self.update_startup_preferences(startup_target)
        log_size = self.paths.log_path.stat().st_size if self.paths.log_path.exists() else 0
        return PreparedStartupTarget(
            startup_target=startup_target,
            startup_mode=self.config.target_mode,
            prefs_backup_dir=backup_dir,
            log_size_before_launch=log_size,
            recent_project_names=recent_project_names,
        )

    def create_backup(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.paths.backup_root / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.paths.config_user_xml, backup_dir / self.paths.config_user_xml.name)
        if self.paths.recent_projects.exists():
            shutil.copy2(self.paths.recent_projects, backup_dir / self.paths.recent_projects.name)
        return backup_dir

    def restore_preferences(self, backup_dir: Path) -> None:
        config_backup = backup_dir / self.paths.config_user_xml.name
        recent_backup = backup_dir / self.paths.recent_projects.name
        if config_backup.exists():
            shutil.copy2(config_backup, self.paths.config_user_xml)
        if recent_backup.exists():
            shutil.copy2(recent_backup, self.paths.recent_projects)

    def update_startup_preferences(self, startup_target: str) -> None:
        tree = ET.parse(self.paths.config_user_xml)
        root = tree.getroot()

        def set_text(tag_name: str, text: str) -> None:
            element = root.find(tag_name)
            if element is None:
                element = ET.SubElement(root, tag_name)
            element.text = text

        set_text("AutoReloadPrevProj", "true")
        set_text("LastWorkingProject", startup_target)
        last_folder = root.find("LastWorkingProjectFolder")
        if last_folder is not None and last_folder.text is None:
            last_folder.text = ""

        tree.write(self.paths.config_user_xml, encoding="utf-8", xml_declaration=False)

    def read_recent_project_names(self) -> list[str]:
        if not self.paths.recent_projects.exists():
            return []

        names: list[str] = []
        for raw_line in self.paths.recent_projects.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) >= 6:
                candidate = parts[4].strip()
                if candidate:
                    names.append(candidate)
                    continue
            if "\\" in line:
                names.append(line.rsplit("\\", 1)[-1].split(":", 1)[0].strip())
        return names

    def project_exists_in_library(self, project_name: str) -> bool:
        if not self.paths.library_root.exists():
            return False
        for candidate in self.paths.library_root.rglob(project_name):
            if candidate.is_dir() and (candidate / "Project.db").exists():
                return True
        return False

    def launch_resolve(self, prepared: PreparedStartupTarget) -> None:
        self._process_killer(["Resolve.exe", "fuscript.exe"])
        if not self.config.resolve_path.exists():
            raise ResolveStartupError(
                f"Resolve executable not found at '{self.config.resolve_path}'."
            )
        self._process_launcher([str(self.config.resolve_path)])
        deadline = time.monotonic() + self.config.timeout_seconds
        while time.monotonic() < deadline:
            if self._is_resolve_running():
                break
            time.sleep(self.config.poll_interval_seconds)
        else:
            raise ResolveStartupError(
                f"Resolve did not start within {self.config.timeout_seconds} seconds."
            )

        time.sleep(max(0, self.config.warmup_seconds))

    def verify_current_project(
        self,
        prepared: PreparedStartupTarget,
    ) -> tuple[VerificationState, str | None, str, bool]:
        try:
            resolve = self._external_runner.wait_for_external_scripting()
        except ExternalResolveRunnerError:
            resolve = None

        if resolve is not None:
            current_name = self._external_runner._safe_call(  # noqa: SLF001
                self._external_runner._safe_call(resolve, "GetProjectManager"),  # noqa: SLF001
                "GetCurrentProject",
            )
            current_project_name = self._external_runner._safe_call(current_name, "GetName")  # noqa: SLF001
            if current_project_name == prepared.startup_target:
                return (
                    "confirmed",
                    current_project_name,
                    "Confirmed via external scripting current project lookup.",
                    True,
                )

        log_text = self.read_new_log_text(prepared.log_size_before_launch)
        loading_marker = f"Loading project ({prepared.startup_target}) from project library"
        pointer_marker = f"Current project pointer changed to ({prepared.startup_target})"
        if loading_marker in log_text or pointer_marker in log_text:
            return (
                "likely",
                prepared.startup_target,
                "Confirmed by Resolve logs after startup.",
                False,
            )

        current_pref_target = self.read_last_working_project()
        if self._is_resolve_running() and current_pref_target == prepared.startup_target:
            return (
                "likely",
                current_pref_target,
                "Resolve is running and startup prefs still point to the requested target, but no external scripting confirmation is available.",
                False,
            )

        return (
            "failed",
            current_pref_target,
            "Resolve did not confirm the requested startup project through scripting or logs.",
            False,
        )

    def read_new_log_text(self, log_size_before_launch: int) -> str:
        if not self.paths.log_path.exists():
            return ""
        with self.paths.log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(max(0, log_size_before_launch))
            return handle.read()

    def read_last_working_project(self) -> str | None:
        tree = ET.parse(self.paths.config_user_xml)
        root = tree.getroot()
        element = root.find("LastWorkingProject")
        if element is None or element.text is None:
            return None
        return element.text.strip() or None

    @staticmethod
    def _default_process_lister() -> list[str]:
        output = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
        return output.stdout.splitlines()

    @staticmethod
    def _default_process_launcher(args: list[str]) -> None:
        subprocess.Popen(args)

    @staticmethod
    def _default_process_killer(process_names: list[str]) -> None:
        for process_name in process_names:
            subprocess.run(
                ["taskkill", "/F", "/IM", process_name],
                capture_output=True,
                text=True,
                check=False,
            )

    @staticmethod
    def _default_command_runner(command: str) -> int:
        completed = subprocess.run(command, shell=True, check=False)
        return int(completed.returncode)

    def _is_resolve_running(self) -> bool:
        return any("Resolve.exe" in line for line in self._process_lister())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start Resolve into a target project via prefs, then run a host command."
    )
    parser.add_argument("--target-mode", choices=["existing", "blank"], required=True)
    parser.add_argument("--project-name", help="Target project name for existing mode.")
    parser.add_argument(
        "--blank-project-name",
        default="DFMCP Blank",
        help="Pre-created blank project name for blank mode.",
    )
    parser.add_argument("--command", required=True, help="Host command to run after project gate.")
    parser.add_argument(
        "--resolve-path",
        default=str(DEFAULT_RESOLVE_PATH),
        help="Path to Resolve.exe.",
    )
    parser.add_argument(
        "--warmup-seconds",
        type=int,
        default=60,
        help="Minimum wait after Resolve process start before verification.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Maximum wait for Resolve process startup or scripting readiness.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=1.0,
        help="Polling interval for Resolve process checks.",
    )
    parser.add_argument(
        "--restore-prefs-on-exit",
        default="false",
        choices=["true", "false"],
        help="Restore backed up prefs after a successful run.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = ResolveStartupConfig(
        target_mode=args.target_mode,
        project_name=args.project_name,
        blank_project_name=args.blank_project_name,
        command=args.command,
        resolve_path=Path(args.resolve_path),
        warmup_seconds=args.warmup_seconds,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        restore_prefs_on_exit=args.restore_prefs_on_exit == "true",
    )
    orchestrator = ResolveProjectStartupOrchestrator(config)
    try:
        result = orchestrator.run()
    except ResolveStartupError as exc:
        print(str(exc))
        raise SystemExit(2) from exc

    print(json.dumps(asdict(result), indent=2))
    if result.script_launch_state == "failed":
        raise SystemExit(result.command_exit_code or 1)
    if result.project_verification_state == "failed":
        raise SystemExit(2)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
