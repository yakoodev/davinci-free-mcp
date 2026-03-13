from pathlib import Path

import pytest

from davinci_free_mcp.external_agent.runner import (
    DEFAULT_FUSIONSCRIPT_DLL,
    DEFAULT_SCRIPT_MODULE_DIR,
    ExternalResolveAgentRunner,
    ExternalResolveRunnerConfig,
    ExternalResolveRunnerError,
)


class FakeProject:
    def __init__(self, name: str) -> None:
        self._name = name

    def GetName(self) -> str:
        return self._name


class FakeProjectManager:
    def __init__(self, projects: dict[str, FakeProject], current: str | None = None) -> None:
        self._projects = projects
        self._current = current

    def GetCurrentProject(self) -> FakeProject | None:
        if self._current is None:
            return None
        return self._projects.get(self._current)

    def LoadProject(self, project_name: str) -> FakeProject | None:
        project = self._projects.get(project_name)
        if project is not None:
            self._current = project_name
        return project


class FakeResolve:
    def __init__(self, project_manager: FakeProjectManager | None) -> None:
        self._project_manager = project_manager

    def GetProjectManager(self) -> FakeProjectManager | None:
        return self._project_manager


class SequenceResolveProvider:
    def __init__(self, values: list[object | None]) -> None:
        self._values = values
        self._index = 0

    def resolve(self):
        if not self._values:
            return None
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value


def build_runner(
    *,
    resolve_provider,
    process_lines: list[str] | None = None,
    launched: list[list[str]] | None = None,
    command_results: list[int] | None = None,
    timeout_seconds: int = 1,
    poll_interval_seconds: float = 0.0,
    launch_wait_seconds: int = 0,
    nogui: bool = False,
) -> ExternalResolveAgentRunner:
    config = ExternalResolveRunnerConfig(
        project_name="Demo Project",
        command="cmd /c exit 0",
        resolve_path=Path(__file__),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        launch_wait_seconds=launch_wait_seconds,
        nogui=nogui,
    )
    process_lines = process_lines or ["Resolve.exe                  42 Console                    1     42,000 K"]
    launched = launched if launched is not None else []
    command_results = command_results if command_results is not None else [0]

    def process_lister():
        return process_lines

    def process_launcher(args: list[str]) -> None:
        launched.append(args)

    def command_runner(command: str) -> int:
        return command_results.pop(0)

    runner = ExternalResolveAgentRunner(
        config,
        resolve_provider=resolve_provider,
        process_lister=process_lister,
        process_launcher=process_launcher,
        command_runner=command_runner,
        module_dir=DEFAULT_SCRIPT_MODULE_DIR,
        dll_path=DEFAULT_FUSIONSCRIPT_DLL,
    )
    return runner


def test_collect_state_reports_connected_project_manager() -> None:
    project = FakeProject("Demo Project")
    manager = FakeProjectManager({"Demo Project": project}, current="Demo Project")
    runner = build_runner(resolve_provider=SequenceResolveProvider([FakeResolve(manager)]))

    state = runner.collect_state()

    assert state.resolve_running is True
    assert state.resolve_connected is True
    assert state.project_manager_available is True
    assert state.current_project_name == "Demo Project"


def test_wait_for_external_scripting_returns_resolve_when_project_manager_available() -> None:
    project = FakeProject("Demo Project")
    manager = FakeProjectManager({"Demo Project": project})
    resolve = FakeResolve(manager)
    runner = build_runner(
        resolve_provider=SequenceResolveProvider([None, resolve]),
        timeout_seconds=2,
    )

    assert runner.wait_for_external_scripting() is resolve


def test_wait_for_external_scripting_raises_with_hint_when_unavailable() -> None:
    runner = build_runner(
        resolve_provider=SequenceResolveProvider([None, None, None]),
        timeout_seconds=0,
    )

    with pytest.raises(ExternalResolveRunnerError) as exc:
        runner.wait_for_external_scripting()

    assert "external scripting access is enabled" in str(exc.value)


def test_open_project_loads_named_project_and_confirms_current_project() -> None:
    project = FakeProject("Demo Project")
    manager = FakeProjectManager({"Demo Project": project})
    runner = build_runner(resolve_provider=SequenceResolveProvider([FakeResolve(manager)]))

    opened_name = runner.open_project(FakeResolve(manager))

    assert opened_name == "Demo Project"
    assert manager.GetCurrentProject() is project


def test_open_project_raises_when_project_missing() -> None:
    manager = FakeProjectManager({})
    runner = build_runner(resolve_provider=SequenceResolveProvider([FakeResolve(manager)]))

    with pytest.raises(ExternalResolveRunnerError) as exc:
        runner.open_project(FakeResolve(manager))

    assert "was not found" in str(exc.value)


def test_run_executes_agent_command_after_project_open() -> None:
    project = FakeProject("Demo Project")
    manager = FakeProjectManager({"Demo Project": project})
    runner = build_runner(
        resolve_provider=SequenceResolveProvider([FakeResolve(manager), FakeResolve(manager)]),
    )

    exit_code = runner.run()

    assert exit_code == 0


def test_ensure_resolve_started_launches_with_nogui_flag() -> None:
    project = FakeProject("Demo Project")
    manager = FakeProjectManager({"Demo Project": project})
    launched: list[list[str]] = []
    process_states = [
        [],
        ["Resolve.exe                  42 Console                    1     42,000 K"],
    ]

    def process_lister():
        return process_states.pop(0) if process_states else ["Resolve.exe"]

    runner = ExternalResolveAgentRunner(
        ExternalResolveRunnerConfig(
            project_name="Demo Project",
            command="cmd /c exit 0",
            resolve_path=Path(__file__),
            launch_wait_seconds=1,
            poll_interval_seconds=0.0,
            nogui=True,
        ),
        resolve_provider=SequenceResolveProvider([FakeResolve(manager)]),
        process_lister=process_lister,
        process_launcher=lambda args: launched.append(args),
        command_runner=lambda command: 0,
        module_dir=DEFAULT_SCRIPT_MODULE_DIR,
        dll_path=DEFAULT_FUSIONSCRIPT_DLL,
    )

    runner.ensure_resolve_started()

    assert launched == [[str(Path(__file__)), "-nogui"]]
