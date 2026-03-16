"""UI automation helper for launching the embedded Resolve bootstrap script."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


class ResolveBootstrapUiError(RuntimeError):
    """Raised when Resolve UI automation cannot launch the bootstrap."""


@dataclass(slots=True)
class ResolveBootstrapUiConfig:
    window_title_re: str = ".*DaVinci Resolve.*"
    workspace_titles: tuple[str, ...] = ("Рабочая область", "Workspace")
    scripts_titles: tuple[str, ...] = ("Сценарии", "Scripts")
    bootstrap_titles: tuple[str, ...] = ("resolve_executor_bootstrap",)
    menu_delay_seconds: float = 0.5
    connect_timeout_seconds: float = 30.0
    connect_poll_seconds: float = 0.5
    enumerate_only: bool = False


@dataclass(slots=True)
class ResolveBootstrapUiResult:
    invoked: bool
    window_title: str | None
    workspace_title: str | None
    scripts_title: str | None
    bootstrap_title: str | None
    available_items: list[str]


class ResolveBootstrapUiLauncher:
    """Launch the embedded executor from Resolve's UI menus."""

    def __init__(
        self,
        config: ResolveBootstrapUiConfig | None = None,
        *,
        application_factory=None,
        sleeper=None,
    ) -> None:
        self.config = config or ResolveBootstrapUiConfig()
        self._application_factory = application_factory or self._default_application_factory
        self._sleep = sleeper or time.sleep

    def run(self) -> ResolveBootstrapUiResult:
        app = self._application_factory(backend="uia")
        app = self._connect_with_retry(app)
        window = app.window(title_re=self.config.window_title_re)
        window_title = self._safe_window_text(window)

        workspace = self._find_named_child(window, self.config.workspace_titles)
        workspace_title = self._safe_window_text(workspace)
        workspace.expand()
        self._sleep(self.config.menu_delay_seconds)

        scripts = self._find_named_child(window, self.config.scripts_titles)
        scripts_title = self._safe_window_text(scripts)
        scripts.expand()
        self._sleep(self.config.menu_delay_seconds)

        available_items = self._collect_menu_items(window)
        if self.config.enumerate_only:
            return ResolveBootstrapUiResult(
                invoked=False,
                window_title=window_title,
                workspace_title=workspace_title,
                scripts_title=scripts_title,
                bootstrap_title=None,
                available_items=available_items,
            )

        bootstrap = self._find_named_child(window, self.config.bootstrap_titles)
        bootstrap_title = self._safe_window_text(bootstrap)
        bootstrap.invoke()
        return ResolveBootstrapUiResult(
            invoked=True,
            window_title=window_title,
            workspace_title=workspace_title,
            scripts_title=scripts_title,
            bootstrap_title=bootstrap_title,
            available_items=available_items,
        )

    def _connect_with_retry(self, app: Any) -> Any:
        deadline = time.monotonic() + self.config.connect_timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                return app.connect(title_re=self.config.window_title_re)
            except Exception as exc:
                last_error = exc
                self._sleep(self.config.connect_poll_seconds)
        raise ResolveBootstrapUiError(
            f"Could not connect to a DaVinci Resolve window matching '{self.config.window_title_re}' "
            f"within {self.config.connect_timeout_seconds} seconds."
        ) from last_error

    def _find_named_child(self, window: Any, titles: tuple[str, ...]) -> Any:
        errors: list[str] = []
        for title in titles:
            try:
                return window.child_window(title=title, control_type="MenuItem").wrapper_object()
            except Exception as exc:
                errors.append(f"{title}: {exc}")
        available_items = self._collect_menu_items(window)
        raise ResolveBootstrapUiError(
            f"Could not find menu item {titles}. Available items: {available_items}. Errors: {errors}"
        )

    def _collect_menu_items(self, window: Any) -> list[str]:
        items: list[str] = []
        descendants = getattr(window, "descendants", None)
        if not callable(descendants):
            return items
        try:
            candidates = descendants(control_type="MenuItem")
        except Exception:
            return items
        for candidate in candidates:
            text = self._safe_window_text(candidate)
            if text:
                items.append(text)
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    @staticmethod
    def _safe_window_text(window: Any) -> str | None:
        for attr_name in ("window_text", "texts"):
            attr = getattr(window, attr_name, None)
            if not callable(attr):
                continue
            try:
                value = attr()
            except Exception:
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        return item.strip()
        element_info = getattr(window, "element_info", None)
        if element_info is not None:
            name = getattr(element_info, "name", None)
            if isinstance(name, str) and name.strip():
                return name.strip()
        return None

    @staticmethod
    def _default_application_factory(**kwargs: Any) -> Any:
        try:
            from pywinauto import Application
        except Exception as exc:  # pragma: no cover - depends on host runtime
            raise ResolveBootstrapUiError(
                "pywinauto is required for Resolve UI automation."
            ) from exc
        return Application(**kwargs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch resolve_executor_bootstrap from the DaVinci Resolve UI."
    )
    parser.add_argument(
        "--enumerate-only",
        action="store_true",
        help="Only inspect available menu items without invoking the bootstrap.",
    )
    parser.add_argument(
        "--menu-delay-seconds",
        type=float,
        default=0.5,
        help="Delay between menu expansion steps.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    launcher = ResolveBootstrapUiLauncher(
        ResolveBootstrapUiConfig(
            menu_delay_seconds=args.menu_delay_seconds,
            enumerate_only=args.enumerate_only,
        )
    )
    try:
        result = launcher.run()
    except ResolveBootstrapUiError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
