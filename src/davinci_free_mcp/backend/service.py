"""Thin backend service layer."""

from __future__ import annotations

from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import (
    BridgeCommand,
    BridgeError,
    BridgeResult,
    ResolveHealthData,
    ToolResultEnvelope,
)


class ResolveBackendService:
    """Backend orchestrator for the first vertical slice."""

    def __init__(self, bridge: Bridge, settings: AppSettings | None = None) -> None:
        self.bridge = bridge
        self.settings = settings or AppSettings()

    def resolve_health(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        bridge_status = self.bridge.health_check()
        if not bridge_status.get("available", False):
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="bridge_unavailable",
                    message="Bridge health check failed before command submission.",
                    details={"bridge_status": bridge_status},
                ),
                meta={"bridge_status": bridge_status},
            )

        effective_timeout = timeout_ms or self.settings.default_timeout_ms
        command = BridgeCommand(
            command="resolve_health",
            timeout_ms=effective_timeout,
            context={"tool_name": "resolve_health", "caller": "backend"},
        )
        self.bridge.submit_command(command)
        result = self.bridge.await_result(command.request_id, effective_timeout)
        return self._normalize_result(result, bridge_status)

    def _normalize_result(
        self,
        result: BridgeResult,
        bridge_status: dict[str, object],
    ) -> ToolResultEnvelope:
        if not result.ok:
            return ToolResultEnvelope(
                success=False,
                error=result.error,
                warnings=result.warnings,
                meta={"bridge_status": bridge_status, **result.meta},
            )

        try:
            health = ResolveHealthData.model_validate(result.data or {})
        except Exception as exc:
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="execution_failure",
                    message="Executor returned an invalid health payload.",
                    details={"exception": str(exc)},
                ),
                warnings=result.warnings,
                meta={"bridge_status": bridge_status, **result.meta},
            )

        return ToolResultEnvelope(
            success=True,
            data=health.model_dump(mode="json"),
            warnings=result.warnings,
            meta={"bridge_status": bridge_status, **result.meta},
        )

