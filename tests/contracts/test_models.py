from davinci_free_mcp.contracts import (
    BridgeCommand,
    BridgeResult,
    ResolveMediaPoolFolderStateData,
    ResolveTimelineInspectData,
)


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


def test_media_pool_folder_state_data_round_trip() -> None:
    payload = ResolveMediaPoolFolderStateData.model_validate(
        {
            "folder": {"name": "Closeups"},
            "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
            "subfolders": [{"name": "Alt"}],
            "clips": [{"name": "clip001.mov"}],
        }
    )

    restored = ResolveMediaPoolFolderStateData.model_validate(payload.model_dump(mode="json"))

    assert restored.path[1].name == "Selects"
    assert restored.clips[0].name == "clip001.mov"


def test_timeline_inspect_data_round_trip() -> None:
    payload = ResolveTimelineInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 2, "name": "Review"},
            "video_track_count": 2,
            "audio_track_count": 1,
            "video_item_count": 5,
            "audio_item_count": 3,
            "marker_count": 4,
        }
    )

    restored = ResolveTimelineInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.timeline.name == "Review"
    assert restored.marker_count == 4
