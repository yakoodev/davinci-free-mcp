from pathlib import Path

import pytest

from davinci_free_mcp.external_agent.live_run import (
    ExecutorSnapshot,
    LiveResolveRunner,
    LiveResolveRunnerError,
    LiveRunnerConfig,
)


def build_runner(
    tmp_path: Path,
    *,
    snapshot_sequence: list[ExecutorSnapshot],
    resolve_process_states: list[bool] | None = None,
    container_running: bool = True,
    bootstrap_error: Exception | None = None,
    backend_responses: list[dict] | None = None,
) -> tuple[LiveResolveRunner, dict[str, list]]:
    state = {
        "snapshot_index": 0,
        "scripts": [],
        "bootstrap_calls": [],
        "commands": [],
        "logs": [],
    }
    process_states = resolve_process_states[:] if resolve_process_states is not None else [True]
    backend_values = backend_responses[:] if backend_responses is not None else [
        {
            "exit_code": 0,
            "result": {"data": {"project": {"open": True, "name": "Demo Project"}}},
        }
    ]

    def container_checker(name: str) -> bool:
        return container_running

    def process_lister() -> list[str]:
        current = process_states[0] if process_states else True
        if len(process_states) > 1:
            process_states.pop(0)
        return ["Resolve.exe"] if current else []

    def status_loader(status_path: Path, lock_path: Path) -> ExecutorSnapshot:
        index = min(state["snapshot_index"], len(snapshot_sequence) - 1)
        snapshot = snapshot_sequence[index]
        state["snapshot_index"] += 1
        return snapshot

    def script_runner(script_path: str, args: list[str]) -> None:
        state["scripts"].append((Path(script_path).name, list(args)))

    def bootstrap_launcher() -> None:
        state["bootstrap_calls"].append("launch")
        if bootstrap_error is not None:
            raise bootstrap_error

    def backend_invoker(method: str, arguments: dict) -> dict:
        state["commands"].append((method, arguments))
        if backend_values:
            return backend_values.pop(0)
        raise AssertionError(f"Unexpected backend call: {method}")

    def command_runner(command: str) -> int:
        state["commands"].append(("host_command", {"command": command}))
        return 0

    def logger(message: str) -> None:
        state["logs"].append(message)

    runner = LiveResolveRunner(
        LiveRunnerConfig(
            project_name="Demo Project",
            command="cmd /c exit 0",
            resolve_timeout_seconds=1,
            executor_timeout_seconds=1,
            project_timeout_seconds=1,
            fresh_within_seconds=90,
            repo_root=tmp_path,
        ),
        container_checker=container_checker,
        process_lister=process_lister,
        status_loader=status_loader,
        script_runner=script_runner,
        bootstrap_launcher=bootstrap_launcher,
        backend_invoker=backend_invoker,
        command_runner=command_runner,
        logger=logger,
    )
    return runner, state


def healthy_snapshot() -> ExecutorSnapshot:
    return ExecutorSnapshot(
        available=True,
        running=True,
        resolve_connected=True,
        age_seconds=1.0,
        raw_status={"running": True, "resolve": {"connected": True}},
        status_present=True,
        lock_present=True,
    )


def stale_snapshot(*, status_present: bool = True, lock_present: bool = True) -> ExecutorSnapshot:
    return ExecutorSnapshot(
        available=status_present,
        running=False,
        resolve_connected=False,
        age_seconds=999.0 if status_present else None,
        raw_status={"running": False, "resolve": {"connected": False}} if status_present else None,
        status_present=status_present,
        lock_present=lock_present,
    )


def test_live_runner_reuses_healthy_executor_without_reset(tmp_path: Path) -> None:
    runner, state = build_runner(
        tmp_path,
        snapshot_sequence=[healthy_snapshot()],
        backend_responses=[
            {
                "exit_code": 0,
                "result": {"data": {"project": {"open": True, "name": "Demo Project"}}},
            }
        ],
    )

    exit_code = runner.run()

    assert exit_code == 0
    assert state["scripts"] == []
    assert state["bootstrap_calls"] == []


def test_live_runner_resets_runtime_when_stale_and_resolve_not_running(tmp_path: Path) -> None:
    runner, state = build_runner(
        tmp_path,
        snapshot_sequence=[stale_snapshot(), stale_snapshot(), healthy_snapshot(), healthy_snapshot()],
        resolve_process_states=[False, False, True, True],
        backend_responses=[
            {
                "exit_code": 0,
                "result": {"data": {"project": {"open": True, "name": "Demo Project"}}},
            }
        ],
    )

    runner.run()

    assert ("dev_kill_davinci.ps1", []) in state["scripts"]
    assert ("dev_reset_runtime.ps1", ["-IncludeLock"]) in state["scripts"]
    assert any(name == "dev_start_resolve_with_python.ps1" for name, _ in state["scripts"])
    assert state["bootstrap_calls"] == ["launch"]


def test_live_runner_uses_python_aware_resolve_launcher_on_cold_start(tmp_path: Path) -> None:
    runner, state = build_runner(
        tmp_path,
        snapshot_sequence=[stale_snapshot(status_present=False, lock_present=False), healthy_snapshot(), healthy_snapshot()],
        resolve_process_states=[False, False, True, True],
        backend_responses=[
            {
                "exit_code": 0,
                "result": {"data": {"project": {"open": True, "name": "Demo Project"}}},
            }
        ],
    )

    runner.run()

    start_calls = [entry for entry in state["scripts"] if entry[0] == "dev_start_resolve_with_python.ps1"]
    assert len(start_calls) == 1


def test_live_runner_reports_bootstrap_launch_failure_after_retry(tmp_path: Path) -> None:
    runner, _state = build_runner(
        tmp_path,
        snapshot_sequence=[stale_snapshot(status_present=False, lock_present=False)],
        resolve_process_states=[True, True, True, True],
        bootstrap_error=RuntimeError("missing menu item"),
    )

    with pytest.raises(LiveResolveRunnerError) as exc:
        runner.run()

    assert "Failed to launch resolve_executor_bootstrap" in str(exc.value)


def test_live_runner_opens_project_and_runs_command_after_diagnostics_path(tmp_path: Path) -> None:
    runner, state = build_runner(
        tmp_path,
        snapshot_sequence=[healthy_snapshot()],
        backend_responses=[
            {
                "exit_code": 0,
                "result": {"data": {"project": {"open": False, "name": None}}},
            },
            {
                "exit_code": 0,
                "result": {"data": {"opened": True}},
            },
            {
                "exit_code": 0,
                "result": {"data": {"project": {"open": True, "name": "Demo Project"}}},
            },
        ],
    )

    runner.run()

    assert ("project_current", {"timeout_ms": 1000}) in state["commands"]
    assert ("project_open", {"project_name": "Demo Project", "timeout_ms": 1000}) in state["commands"]
    assert ("host_command", {"command": "cmd /c exit 0"}) in state["commands"]
