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


def test_marker_list_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "markers": [{"frame": "bad"}],
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_list()

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_media_clip_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "folder": {"name": "Master"},
                    "clip": {"name": "clip001.mov", "properties": ["bad"]},
                },
            )
        ),
        AppSettings(),
    )

    result = service.media_clip_inspect("clip001.mov")

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_create_from_clips_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "created": True,
                    "timeline": {"index": 1, "name": "Assembly"},
                    "count": "bad",
                    "clip_names": ["clip001.mov"],
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_create_from_clips("Assembly", ["clip001.mov"])

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "video_track_count": "bad",
                    "audio_track_count": 1,
                    "video_item_count": 2,
                    "audio_item_count": 0,
                    "marker_count": 3,
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_inspect()

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_track_items_list_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track": {"track_type": "video", "track_index": "bad", "items": []},
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_track_items_list("video", 1)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_project_manager_folder_path_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "folder": {"name": "Clients"},
                    "path": [{"name": "Root"}, {"name": 123}],
                    "subfolders": [],
                    "projects": [],
                },
            )
        ),
        AppSettings(),
    )

    result = service.project_manager_folder_path()

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_marker_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "marker": {"frame": "bad"},
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_inspect(10)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_track_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "track_type": "video",
                    "track_index": 1,
                    "item_count": "bad",
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_track_inspect("video", 1)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_marker_list_range_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "frame_from": 10,
                    "frame_to": 20,
                    "markers": [{"frame": "bad"}],
                },
            )
        ),
        AppSettings(),
    )

    result = service.marker_list_range(10, 20)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_inspect_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "item": {
                        "item_index": 0,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": 1,
                        "start_frame": "bad",
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_inspect("video", 1, 0)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_move_normalizes_invalid_executor_payload() -> None:
    service = ResolveBackendService(
        FakeBridge(
            BridgeResult.success(
                "req-1",
                data={
                    "moved": True,
                    "project": {"open": True, "name": "Demo Project"},
                    "timeline": {"index": 1, "name": "Assembly"},
                    "source_item": {
                        "item_index": 0,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": 1,
                        "start_frame": 100,
                        "end_frame": 124,
                    },
                    "item": {
                        "item_index": 1,
                        "name": "clip001.mov",
                        "track_type": "video",
                        "track_index": "bad",
                        "start_frame": 200,
                        "end_frame": 224,
                    },
                },
            )
        ),
        AppSettings(),
    )

    result = service.timeline_item_move("video", 1, 0, 200)

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"
