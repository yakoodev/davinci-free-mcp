import threading
import time
from pathlib import Path

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import FileQueueBridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.resolve_exec import ResolveExecutor


class FakeTimeline:
    def __init__(self, name: str) -> None:
        self._name = name

    def GetName(self) -> str:
        return self._name


class FakeProject:
    def __init__(self, name: str, timelines: list[FakeTimeline] | None = None) -> None:
        self._name = name
        self._timelines = timelines or []

    def GetName(self) -> str:
        return self._name

    def GetCurrentTimeline(self) -> FakeTimeline | None:
        return self._timelines[0] if self._timelines else None

    def GetTimelineCount(self) -> int:
        return len(self._timelines)

    def GetTimelineByIndex(self, index: int) -> FakeTimeline | None:
        zero_index = index - 1
        if 0 <= zero_index < len(self._timelines):
            return self._timelines[zero_index]
        return None


class FakeProjectManager:
    def __init__(self, project: FakeProject | None, project_names: list[str] | None = None) -> None:
        self._project = project
        self._project_names = project_names or []

    def GetCurrentProject(self) -> FakeProject | None:
        return self._project

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return self._project_names


class FakeResolve:
    def __init__(self, project: FakeProject | None, project_names: list[str] | None = None) -> None:
        self._project_manager = FakeProjectManager(project, project_names)

    def GetProductName(self) -> str:
        return "DaVinci Resolve"

    def GetVersionString(self) -> str:
        return "free-test"

    def GetProjectManager(self) -> FakeProjectManager:
        return self._project_manager


def build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        runtime_dir=tmp_path,
        default_timeout_ms=500,
        bridge_poll_interval_ms=10,
    )


def process_until_handled(executor: ResolveExecutor, attempts: int = 50) -> None:
    for _ in range(attempts):
        result = executor.process_next_request_once()
        if result is not None:
            return
        time.sleep(0.01)


def invoke_with_executor(
    tmp_path: Path,
    resolve_factory,
    method_name: str,
):
    settings = build_settings(tmp_path)
    bridge = FileQueueBridge(settings)
    backend = ResolveBackendService(bridge, settings)
    executor = ResolveExecutor(
        settings,
        resolve_provider=resolve_factory,
    )

    thread = threading.Thread(target=process_until_handled, args=(executor,))
    thread.start()
    result = getattr(backend, method_name)()
    thread.join()
    return result


def test_backend_resolve_health_end_to_end(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(FakeProject("Demo Project"), ["Demo Project"]),
        "resolve_health",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["resolve"]["connected"] is True
    assert result.data["project"]["open"] is True
    assert result.data["project"]["name"] == "Demo Project"


def test_project_current_reports_no_project_warning(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, []),
        "project_current",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["project"]["open"] is False
    assert "no_project_open" in result.warnings


def test_project_list_returns_current_folder_projects(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, ["Alpha", "Beta"]),
        "project_list",
    )

    assert result.success is True
    assert result.data == {
        "projects": [
            {"name": "Alpha"},
            {"name": "Beta"},
        ]
    }


def test_timeline_list_returns_project_timelines(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            FakeProject(
                "Demo Project",
                [FakeTimeline("Timeline 1"), FakeTimeline("Timeline 2")],
            ),
            ["Demo Project"],
        ),
        "timeline_list",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["project"]["name"] == "Demo Project"
    assert result.data["timelines"] == [
        {"index": 1, "name": "Timeline 1"},
        {"index": 2, "name": "Timeline 2"},
    ]


def test_timeline_list_requires_open_project(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, []),
        "timeline_list",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_project_open"
