from davinci_free_mcp.contracts import (
    BridgeCommand,
    BridgeResult,
    ResolveMarkerInspectData,
    ResolveMarkerRangeListData,
    ResolveMediaClipInspectPathData,
    ResolveMediaPoolFolderRecursiveData,
    ResolveMediaPoolFolderStateData,
    ResolveTimelineInspectData,
    ResolveTimelineTrackInspectData,
    ResolveTimelineTrackItemsData,
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


def test_timeline_track_items_data_round_trip() -> None:
    payload = ResolveTimelineTrackItemsData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "track": {
                "track_type": "video",
                "track_index": 2,
                "items": [{"item_index": 0, "name": "clip001.mov", "start_frame": 0, "end_frame": 100}],
            },
        }
    )

    restored = ResolveTimelineTrackItemsData.model_validate(payload.model_dump(mode="json"))

    assert restored.track.track_index == 2
    assert restored.track.items[0].name == "clip001.mov"


def test_marker_inspect_data_round_trip() -> None:
    payload = ResolveMarkerInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "marker": {"frame": 24, "name": "Review", "color": "Blue", "duration": 1},
        }
    )

    restored = ResolveMarkerInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.marker.frame == 24
    assert restored.marker.name == "Review"


def test_media_clip_inspect_path_data_round_trip() -> None:
    payload = ResolveMediaClipInspectPathData.model_validate(
        {
            "folder": {"name": "Closeups"},
            "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
            "clip": {"name": "clip001.mov", "properties": {"File Path": "C:/media/clip001.mov"}},
        }
    )

    restored = ResolveMediaClipInspectPathData.model_validate(payload.model_dump(mode="json"))

    assert restored.path[-1].name == "Closeups"
    assert restored.clip.properties["File Path"] == "C:/media/clip001.mov"


def test_media_pool_folder_recursive_data_round_trip() -> None:
    payload = ResolveMediaPoolFolderRecursiveData.model_validate(
        {
            "folder": {"name": "Master"},
            "path": [{"name": "Master"}],
            "max_depth": 2,
            "tree": {
                "name": "Master",
                "clips": [{"name": "root.mov"}],
                "subfolders": [{"name": "Selects", "clips": [], "subfolders": []}],
            },
        }
    )

    restored = ResolveMediaPoolFolderRecursiveData.model_validate(payload.model_dump(mode="json"))

    assert restored.tree.subfolders[0].name == "Selects"
    assert restored.max_depth == 2


def test_timeline_track_inspect_data_round_trip() -> None:
    payload = ResolveTimelineTrackInspectData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "track_type": "video",
            "track_index": 1,
            "item_count": 2,
            "start_frame": 0,
            "end_frame": 200,
        }
    )

    restored = ResolveTimelineTrackInspectData.model_validate(payload.model_dump(mode="json"))

    assert restored.item_count == 2
    assert restored.end_frame == 200


def test_marker_range_list_data_round_trip() -> None:
    payload = ResolveMarkerRangeListData.model_validate(
        {
            "project": {"open": True, "name": "Demo Project"},
            "timeline": {"index": 1, "name": "Assembly"},
            "frame_from": 10,
            "frame_to": 20,
            "markers": [{"frame": 12, "name": "A"}],
        }
    )

    restored = ResolveMarkerRangeListData.model_validate(payload.model_dump(mode="json"))

    assert restored.frame_from == 10
    assert restored.markers[0].frame == 12
