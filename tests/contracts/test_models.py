from davinci_free_mcp.contracts import BridgeCommand, BridgeResult


def test_bridge_command_round_trip() -> None:
    command = BridgeCommand(
        command="resolve_health",
        target={"project": "Demo"},
        payload={"sample": True},
        timeout_ms=1234,
        context={"caller": "test"},
    )

    restored = BridgeCommand.model_validate(command.model_dump(mode="json"))

    assert restored.command == "resolve_health"
    assert restored.target["project"] == "Demo"
    assert restored.payload["sample"] is True
    assert restored.timeout_ms == 1234


def test_bridge_result_failure_preserves_category() -> None:
    result = BridgeResult.failure(
        "req-1",
        "timeout",
        "Executor did not respond in time.",
        details={"timeout_ms": 50},
    )

    restored = BridgeResult.model_validate(result.model_dump(mode="json"))

    assert restored.ok is False
    assert restored.error is not None
    assert restored.error.category == "timeout"
    assert restored.error.details["timeout_ms"] == 50

