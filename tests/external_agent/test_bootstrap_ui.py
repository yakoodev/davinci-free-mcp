from davinci_free_mcp.external_agent.bootstrap_ui import (
    ResolveBootstrapUiConfig,
    ResolveBootstrapUiError,
    ResolveBootstrapUiLauncher,
)


class FakeMenuItem:
    def __init__(self, title: str) -> None:
        self._title = title
        self.expanded = False
        self.invoked = False

    def wrapper_object(self):
        return self

    def expand(self) -> None:
        self.expanded = True

    def invoke(self) -> None:
        self.invoked = True

    def window_text(self) -> str:
        return self._title


class FakeWindow:
    def __init__(self, items: dict[str, FakeMenuItem]) -> None:
        self._items = items

    def child_window(self, title: str, control_type: str):
        if control_type != "MenuItem" or title not in self._items:
            raise RuntimeError(f"missing:{title}")
        return self._items[title]

    def descendants(self, control_type: str):
        if control_type != "MenuItem":
            return []
        return list(self._items.values())

    def window_text(self) -> str:
        return "DaVinci Resolve"


class FakeApplication:
    def __init__(self, window: FakeWindow) -> None:
        self._window = window

    def connect(self, title_re: str):
        return self

    def window(self, title_re: str):
        return self._window


def test_bootstrap_ui_launcher_invokes_bootstrap_menu_item() -> None:
    items = {
        "Рабочая область": FakeMenuItem("Рабочая область"),
        "Сценарии": FakeMenuItem("Сценарии"),
        "resolve_executor_bootstrap": FakeMenuItem("resolve_executor_bootstrap"),
    }
    launcher = ResolveBootstrapUiLauncher(
        ResolveBootstrapUiConfig(menu_delay_seconds=0.0),
        application_factory=lambda **kwargs: FakeApplication(FakeWindow(items)),
        sleeper=lambda seconds: None,
    )

    result = launcher.run()

    assert result.invoked is True
    assert items["Рабочая область"].expanded is True
    assert items["Сценарии"].expanded is True
    assert items["resolve_executor_bootstrap"].invoked is True


def test_bootstrap_ui_launcher_reports_available_items_when_bootstrap_missing() -> None:
    items = {
        "Рабочая область": FakeMenuItem("Рабочая область"),
        "Сценарии": FakeMenuItem("Сценарии"),
        "Comp": FakeMenuItem("Comp"),
    }
    launcher = ResolveBootstrapUiLauncher(
        ResolveBootstrapUiConfig(menu_delay_seconds=0.0),
        application_factory=lambda **kwargs: FakeApplication(FakeWindow(items)),
        sleeper=lambda seconds: None,
    )

    try:
        launcher.run()
    except ResolveBootstrapUiError as exc:
        message = str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ResolveBootstrapUiError")

    assert "Available items" in message
    assert "Comp" in message
