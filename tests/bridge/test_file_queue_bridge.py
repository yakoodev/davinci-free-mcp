import json
from pathlib import Path

from davinci_free_mcp.bridge import FileQueueBridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


def build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(runtime_dir=tmp_path, bridge_poll_interval_ms=10)


def test_submit_command_creates_request_file(tmp_path: Path) -> None:
    bridge = FileQueueBridge(build_settings(tmp_path))
    command = BridgeCommand(command="resolve_health")

    bridge.submit_command(command)

    request_path = bridge.request_path(command.request_id)
    assert request_path.exists()

    payload = json.loads(request_path.read_text(encoding="utf-8"))
    assert payload["request_id"] == command.request_id
    assert payload["command"] == "resolve_health"


def test_await_result_returns_timeout(tmp_path: Path) -> None:
    bridge = FileQueueBridge(build_settings(tmp_path))

    result = bridge.await_result("missing-request", 20)

    assert result.ok is False
    assert result.error is not None
    assert result.error.category == "timeout"


def test_await_result_handles_malformed_json(tmp_path: Path) -> None:
    bridge = FileQueueBridge(build_settings(tmp_path))
    result_path = bridge.result_path("req-1")
    result_path.write_text("{bad json", encoding="utf-8")

    result = bridge.await_result("req-1", 50)

    assert result.ok is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_await_result_reads_valid_result(tmp_path: Path) -> None:
    bridge = FileQueueBridge(build_settings(tmp_path))
    result = BridgeResult.success("req-1", {"hello": "world"})
    bridge.result_path("req-1").write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )

    restored = bridge.await_result("req-1", 50)

    assert restored.ok is True
    assert restored.data == {"hello": "world"}

