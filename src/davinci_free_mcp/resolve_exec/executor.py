"""Internal executor for Resolve Free."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand, BridgeResult, ResolveHealthData


def resolve_from_embedded_environment(explicit_app: Any | None = None) -> Any | None:
    """Return a Resolve handle when running inside Resolve's embedded environment."""

    app_obj = explicit_app
    if app_obj is None:
        app_obj = globals().get("app")

    if app_obj is None or not hasattr(app_obj, "GetResolve"):
        return None

    try:
        return app_obj.GetResolve()
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


class ResolveExecutor:
    """Polling executor meant to run inside Resolve Free."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        *,
        resolve_provider: Callable[[], Any | None] | None = None,
        adapter_name: str = "file_queue",
    ) -> None:
        self.settings = settings or AppSettings()
        self.requests_dir = self.settings.requests_dir
        self.results_dir = self.settings.results_dir
        self.deadletter_dir = self.settings.deadletter_dir
        self.adapter_name = adapter_name
        self.resolve_provider = resolve_provider or resolve_from_embedded_environment
        self._ensure_runtime_dirs()

    def _ensure_runtime_dirs(self) -> None:
        for path in (self.requests_dir, self.results_dir, self.deadletter_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _list_requests(self) -> list[Path]:
        return sorted(self.requests_dir.glob("*.json"))

    def _deadletter(self, request_path: Path) -> None:
        target = self.deadletter_dir / request_path.name
        os.replace(request_path, target)

    def process_next_request_once(self) -> BridgeResult | None:
        request_files = self._list_requests()
        if not request_files:
            return None

        request_path = request_files[0]
        try:
            raw_data = json.loads(request_path.read_text(encoding="utf-8"))
            command = BridgeCommand.model_validate(raw_data)
        except Exception:
            self._deadletter(request_path)
            return None

        result = self.handle_command(command)
        _atomic_write_json(
            self.results_dir / f"{command.request_id}.json",
            result.model_dump(mode="json"),
        )
        request_path.unlink(missing_ok=True)
        return result

    def handle_command(self, command: BridgeCommand) -> BridgeResult:
        if command.command != "resolve_health":
            return BridgeResult.failure(
                command.request_id,
                "unsupported_in_free_mode",
                f"Unsupported command '{command.command}' for MVP executor.",
                meta={"bridge": self.adapter_name},
            )

        resolve = self.resolve_provider()
        if resolve is None:
            return BridgeResult.failure(
                command.request_id,
                "resolve_not_ready",
                "Resolve handle is not available in the embedded environment.",
                meta={"bridge": self.adapter_name},
            )

        product_name = self._safe_call(resolve, "GetProductName")
        version = self._safe_call(resolve, "GetVersionString")
        project_name = None
        warnings: list[str] = []

        project_manager = self._safe_call(resolve, "GetProjectManager")
        current_project = None
        if project_manager is not None:
            current_project = self._safe_call(project_manager, "GetCurrentProject")

        if current_project is not None:
            project_name = self._safe_call(current_project, "GetName")
        else:
            warnings.append("no_project_open")

        payload = ResolveHealthData.model_validate(
            {
                "bridge": {
                    "available": True,
                    "adapter": self.adapter_name,
                },
                "executor": {
                    "running": True,
                },
                "resolve": {
                    "connected": True,
                    "product_name": product_name,
                    "version": version,
                },
                "project": {
                    "open": current_project is not None,
                    "name": project_name,
                },
            }
        )

        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            warnings=warnings,
            meta={"bridge": self.adapter_name},
        )

    def run_forever(self) -> None:
        while True:
            self.process_next_request_once()
            time.sleep(self.settings.bridge_poll_interval_ms / 1000.0)

    @staticmethod
    def _safe_call(obj: Any, method_name: str) -> Any | None:
        if obj is None:
            return None
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method()
        except Exception:
            return None

