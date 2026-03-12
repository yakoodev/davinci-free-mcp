import threading
import time
from pathlib import Path

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import FileQueueBridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.resolve_exec import ResolveExecutor


class FakeProject:
    def __init__(self, name: str) -> None:
        self._name = name

    def GetName(self) -> str:
        return self._name


class FakeProjectManager:
    def __init__(self, project: FakeProject | None) -> None:
        self._project = project

    def GetCurrentProject(self) -> FakeProject | None:
        return self._project


class FakeResolve:
    def __init__(self, project: FakeProject | None) -> None:
        self._project_manager = FakeProjectManager(project)

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


def test_backend_resolve_health_end_to_end(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    bridge = FileQueueBridge(settings)
    backend = ResolveBackendService(bridge, settings)
    executor = ResolveExecutor(
        settings,
        resolve_provider=lambda: FakeResolve(FakeProject("Demo Project")),
    )

    thread = threading.Thread(target=process_until_handled, args=(executor,))
    thread.start()
    result = backend.resolve_health()
    thread.join()

    assert result.success is True
    assert result.data is not None
    assert result.data["resolve"]["connected"] is True
    assert result.data["project"]["open"] is True
    assert result.data["project"]["name"] == "Demo Project"


def test_backend_resolve_health_reports_no_project_warning(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    bridge = FileQueueBridge(settings)
    backend = ResolveBackendService(bridge, settings)
    executor = ResolveExecutor(
        settings,
        resolve_provider=lambda: FakeResolve(None),
    )

    thread = threading.Thread(target=process_until_handled, args=(executor,))
    thread.start()
    result = backend.resolve_health()
    thread.join()

    assert result.success is True
    assert result.data is not None
    assert result.data["project"]["open"] is False
    assert "no_project_open" in result.warnings
