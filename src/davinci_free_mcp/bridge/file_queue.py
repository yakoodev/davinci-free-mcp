"""File queue bridge adapter."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


class FileQueueBridge(Bridge):
    """Simple polling-based file queue adapter for MVP."""

    adapter_name = "file_queue"

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.requests_dir = self.settings.requests_dir
        self.results_dir = self.settings.results_dir
        self.deadletter_dir = self.settings.deadletter_dir
        self.logs_dir = self.settings.logs_dir
        self._ensure_runtime_dirs()

    def _ensure_runtime_dirs(self) -> None:
        for path in (
            self.requests_dir,
            self.results_dir,
            self.deadletter_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def request_path(self, request_id: str) -> Path:
        return self.requests_dir / f"{request_id}.json"

    def result_path(self, request_id: str) -> Path:
        return self.results_dir / f"{request_id}.json"

    def submit_command(self, command: BridgeCommand) -> str:
        _atomic_write_json(
            self.request_path(command.request_id),
            command.model_dump(mode="json"),
        )
        return command.request_id

    def await_result(self, request_id: str, timeout_ms: int) -> BridgeResult:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        result_path = self.result_path(request_id)

        while time.monotonic() < deadline:
            if result_path.exists():
                try:
                    raw_data = json.loads(result_path.read_text(encoding="utf-8"))
                    result = BridgeResult.model_validate(raw_data)
                except (json.JSONDecodeError, ValueError) as exc:
                    result = BridgeResult.failure(
                        request_id,
                        "execution_failure",
                        "Malformed result payload returned by executor.",
                        details={"exception": str(exc), "path": str(result_path)},
                        meta={"bridge": self.adapter_name},
                    )
                result_path.unlink(missing_ok=True)
                return result

            time.sleep(self.settings.bridge_poll_interval_ms / 1000.0)

        return BridgeResult.failure(
            request_id,
            "timeout",
            "Timed out waiting for executor result.",
            details={"request_id": request_id, "timeout_ms": timeout_ms},
            meta={"bridge": self.adapter_name},
        )

    def health_check(self) -> dict[str, object]:
        self._ensure_runtime_dirs()
        return {
            "available": True,
            "adapter": self.adapter_name,
            "requests_dir": str(self.requests_dir),
            "results_dir": str(self.results_dir),
            "deadletter_dir": str(self.deadletter_dir),
        }

