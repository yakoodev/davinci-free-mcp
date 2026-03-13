"""Diagnostics for agent-only external Resolve scripting."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from davinci_free_mcp.external_agent.runner import (
    DEFAULT_FUSIONSCRIPT_DLL,
    DEFAULT_SCRIPT_MODULE_DIR,
    ExternalResolveAgentRunner,
    ExternalResolveRunnerConfig,
    ExternalResolveRunnerError,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check external Resolve scripting readiness for agent-only automation."
    )
    parser.add_argument("--project-name", help="Optional project name to validate via LoadProject().")
    parser.add_argument(
        "--resolve-path",
        default=r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
        help="Path to Resolve.exe.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="Maximum wait for scripting readiness if Resolve is already running.",
    )
    parser.add_argument(
        "--nogui",
        action="store_true",
        help="Launch Resolve with -nogui when startup is required.",
    )
    args = parser.parse_args()

    config = ExternalResolveRunnerConfig(
        project_name=args.project_name or "",
        command="cmd /c exit 0",
        resolve_path=Path(args.resolve_path),
        timeout_seconds=args.timeout_seconds,
        nogui=args.nogui,
    )
    runner = ExternalResolveAgentRunner(config)
    state = runner.collect_state()
    payload: dict[str, object] = {
        "resolve_running": state.resolve_running,
        "module_path_exists": state.module_path_exists,
        "dll_path_exists": state.dll_path_exists,
        "resolve_connected": state.resolve_connected,
        "project_manager_available": state.project_manager_available,
        "current_project_name": state.current_project_name,
        "module_path": str(DEFAULT_SCRIPT_MODULE_DIR),
        "dll_path": str(DEFAULT_FUSIONSCRIPT_DLL),
    }

    if args.project_name:
        try:
            runner.ensure_resolve_started()
            resolve = runner.wait_for_external_scripting()
            opened_project = runner.open_project(resolve)
        except ExternalResolveRunnerError as exc:
            payload["project_open"] = {
                "success": False,
                "project_name": args.project_name,
                "error": str(exc),
            }
            print(json.dumps(payload, indent=2))
            raise SystemExit(2) from exc
        else:
            payload["project_open"] = {
                "success": True,
                "project_name": opened_project,
            }

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
