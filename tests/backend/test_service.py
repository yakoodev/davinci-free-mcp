from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


class FakeBridge(Bridge):
    def __init__(self, result: BridgeResult) -> None:
        self._result = result

    def submit_command(self, command: BridgeCommand) -> str:
        return command.request_id

    def await_result(self, request_id: str, timeout_ms: int) -> BridgeResult:
        return self._result.model_copy(update={"request_id": request_id})

    def health_check(self) -> dict[str, object]:
        return {"available": True, "adapter": "fake"}


def test_marker_add_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "added": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "marker": {
                        "frame": "not-an-int",
                        "color": "Blue",
                        "name": "Review",
                        "duration": 1,
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_add(10, "Review")

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"
