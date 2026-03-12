"""Abstract bridge interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


class Bridge(ABC):
    """Transport-agnostic bridge interface."""

    @abstractmethod
    def submit_command(self, command: BridgeCommand) -> str:
        """Submit a command and return its request id."""

    @abstractmethod
    def await_result(self, request_id: str, timeout_ms: int) -> BridgeResult:
        """Wait for a result or return a normalized timeout/error result."""

    @abstractmethod
    def health_check(self) -> dict[str, object]:
        """Return bridge health details."""

    def cancel(self, request_id: str) -> None:
        """Cancellation is intentionally deferred for MVP."""
        raise NotImplementedError("cancel is not supported in MVP")

