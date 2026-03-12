"""Local HTTP bridge adapter."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


class LocalHttpBridge(Bridge):
    """Synchronous local HTTP adapter for an executor-hosted REST server."""

    adapter_name = "local_http"

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.base_url = f"http://{self.settings.local_http_host}:{self.settings.local_http_port}"
        self._pending_results: dict[str, BridgeResult] = {}

    def submit_command(self, command: BridgeCommand) -> str:
        endpoint = f"{self.base_url}/commands/{command.command}"
        request = Request(
            endpoint,
            data=json.dumps(command.model_dump(mode="json")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout_seconds = max(command.timeout_ms / 1000.0, 0.1)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_data = response.read().decode("utf-8")
        except HTTPError as exc:
            self._pending_results[command.request_id] = BridgeResult.failure(
                command.request_id,
                "execution_failure",
                f"Executor HTTP bridge returned HTTP {exc.code}.",
                details={"status_code": exc.code},
                meta={"bridge": self.adapter_name},
            )
            return command.request_id
        except URLError as exc:
            self._pending_results[command.request_id] = BridgeResult.failure(
                command.request_id,
                "bridge_unavailable",
                "Executor HTTP bridge is unavailable.",
                details={"exception": str(exc)},
                meta={"bridge": self.adapter_name},
            )
            return command.request_id

        try:
            payload = json.loads(raw_data)
            result = BridgeResult.model_validate(payload)
        except Exception as exc:
            result = BridgeResult.failure(
                command.request_id,
                "execution_failure",
                "Malformed result payload returned by HTTP executor.",
                details={"exception": str(exc)},
                meta={"bridge": self.adapter_name},
            )

        self._pending_results[command.request_id] = result
        return command.request_id

    def await_result(self, request_id: str, timeout_ms: int) -> BridgeResult:
        result = self._pending_results.pop(request_id, None)
        if result is not None:
            return result
        return BridgeResult.failure(
            request_id,
            "timeout",
            "Timed out waiting for HTTP executor result.",
            details={"request_id": request_id, "timeout_ms": timeout_ms},
            meta={"bridge": self.adapter_name},
        )

    def health_check(self) -> dict[str, object]:
        endpoint = f"{self.base_url}/health"
        request = Request(endpoint, method="GET")
        try:
            with urlopen(request, timeout=max(self.settings.local_http_timeout_ms / 1000.0, 0.1)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "available": False,
                "adapter": self.adapter_name,
                "base_url": self.base_url,
                "error": str(exc),
            }

        return {
            "available": True,
            "adapter": self.adapter_name,
            "base_url": self.base_url,
            "executor": payload,
        }
