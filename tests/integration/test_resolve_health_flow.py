import threading
import time
from pathlib import Path

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import FileQueueBridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.resolve_exec import ResolveExecutor


class FakeMediaPoolItem:
    def __init__(self, name: str, properties: dict[str, str] | None = None) -> None:
        self._name = name
        self._properties = properties or {"Clip Name": name, "File Path": f"C:/media/{name}"}

    def GetName(self) -> str:
        return self._name

    def GetClipProperty(self) -> dict[str, str]:
        return self._properties


class FakeTimelineItem:
    def __init__(self, name: str, start_frame: int, end_frame: int) -> None:
        self._name = name
        self._start_frame = start_frame
        self._end_frame = end_frame
        self._media_pool_item = FakeMediaPoolItem(name)

    def GetName(self) -> str:
        return self._name

    def GetStart(self) -> int:
        return self._start_frame

    def GetEnd(self) -> int:
        return self._end_frame

    def GetMediaPoolItem(self) -> FakeMediaPoolItem:
        return self._media_pool_item


class FakeTimeline:
    def __init__(
        self,
        name: str,
        video_tracks: list[list[FakeTimelineItem]] | None = None,
        audio_tracks: list[list[FakeTimelineItem]] | None = None,
    ) -> None:
        self._name = name
        self._tracks = {
            "video": video_tracks or [],
            "audio": audio_tracks or [],
        }

    def GetName(self) -> str:
        return self._name

    def GetTrackCount(self, track_type: str) -> int:
        return len(self._tracks.get(track_type, []))

    def GetItemListInTrack(self, track_type: str, track_index: int) -> list[FakeTimelineItem]:
        zero_index = track_index - 1
        tracks = self._tracks.get(track_type, [])
        if 0 <= zero_index < len(tracks):
            return tracks[zero_index]
        return []

    def append_items(self, clips: list[FakeMediaPoolItem]) -> bool:
        if not self._tracks["video"]:
            self._tracks["video"].append([])

        start_frame = 0
        if self._tracks["video"][0]:
            start_frame = self._tracks["video"][0][-1].GetEnd()

        for clip in clips:
            end_frame = start_frame + 100
            self._tracks["video"][0].append(
                FakeTimelineItem(clip.GetName(), start_frame, end_frame)
            )
            start_frame = end_frame
        return True


class FakeMediaPoolFolder:
    def __init__(
        self,
        name: str,
        subfolders: list["FakeMediaPoolFolder"] | None = None,
        clips: list[FakeMediaPoolItem] | None = None,
    ) -> None:
        self._name = name
        self._subfolders = subfolders or []
        self._clips = clips or []

    def GetName(self) -> str:
        return self._name

    def GetSubFolderList(self) -> list["FakeMediaPoolFolder"]:
        return self._subfolders

    def GetClipList(self) -> list[FakeMediaPoolItem]:
        return self._clips

    def add_clip(self, clip: FakeMediaPoolItem) -> None:
        self._clips.append(clip)


class FakeMediaPool:
    def __init__(self, project: "FakeProject", current_folder: FakeMediaPoolFolder) -> None:
        self._project = project
        self._current_folder = current_folder

    def GetCurrentFolder(self) -> FakeMediaPoolFolder:
        return self._current_folder

    def CreateEmptyTimeline(self, name: str) -> FakeTimeline:
        timeline = FakeTimeline(name, video_tracks=[[]], audio_tracks=[])
        self._project.add_timeline(timeline, set_current=True)
        return timeline

    def ImportMedia(self, paths: list[str]) -> list[FakeMediaPoolItem]:
        imported: list[FakeMediaPoolItem] = []
        for path in paths:
            clip_name = Path(path).name
            clip = FakeMediaPoolItem(clip_name)
            self._current_folder.add_clip(clip)
            imported.append(clip)
        return imported

    def AppendToTimeline(self, clips: list[FakeMediaPoolItem]) -> bool:
        timeline = self._project.GetCurrentTimeline()
        if timeline is None:
            return False
        return timeline.append_items(clips)


class FakeProject:
    def __init__(
        self,
        name: str,
        timelines: list[FakeTimeline] | None = None,
        current_timeline: FakeTimeline | None = None,
        media_pool_folder: FakeMediaPoolFolder | None = None,
    ) -> None:
        self._name = name
        self._timelines = timelines or []
        self._current_timeline = current_timeline
        self._media_pool_folder = media_pool_folder or FakeMediaPoolFolder("Master")
        self._media_pool = FakeMediaPool(self, self._media_pool_folder)

    def GetName(self) -> str:
        return self._name

    def GetCurrentTimeline(self) -> FakeTimeline | None:
        return self._current_timeline

    def SetCurrentTimeline(self, timeline: FakeTimeline) -> bool:
        self._current_timeline = timeline
        return True

    def GetTimelineCount(self) -> int:
        return len(self._timelines)

    def GetTimelineByIndex(self, index: int) -> FakeTimeline | None:
        zero_index = index - 1
        if 0 <= zero_index < len(self._timelines):
            return self._timelines[zero_index]
        return None

    def GetMediaPool(self) -> FakeMediaPool:
        return self._media_pool

    def add_timeline(self, timeline: FakeTimeline, *, set_current: bool = False) -> None:
        self._timelines.append(timeline)
        if set_current:
            self._current_timeline = timeline


class FakeProjectManager:
    def __init__(self, project: FakeProject | None, project_names: list[str] | None = None) -> None:
        self._project = project
        self._project_names = project_names or []

    def GetCurrentProject(self) -> FakeProject | None:
        return self._project

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return self._project_names


class FakeResolve:
    def __init__(self, project: FakeProject | None, project_names: list[str] | None = None) -> None:
        self._project_manager = FakeProjectManager(project, project_names)

    def GetProductName(self) -> str:
        return "DaVinci Resolve"

    def GetVersionString(self) -> str:
        return "free-test"

    def GetProjectManager(self) -> FakeProjectManager:
        return self._project_manager


def build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        runtime_dir=tmp_path,
        default_timeout_ms=500,
        bridge_poll_interval_ms=10,
    )


def process_until_handled(executor: ResolveExecutor, attempts: int = 50) -> None:
    for _ in range(attempts):
        result = executor.process_next_request_once()
        if result is not None:
            return
        time.sleep(0.01)


def invoke_with_executor(
    tmp_path: Path,
    resolve_factory,
    method_name: str,
    *args,
    **kwargs,
):
    settings = build_settings(tmp_path)
    bridge = FileQueueBridge(settings)
    backend = ResolveBackendService(bridge, settings)
    executor = ResolveExecutor(
        settings,
        resolve_provider=resolve_factory,
    )

    thread = threading.Thread(target=process_until_handled, args=(executor,))
    thread.start()
    result = getattr(backend, method_name)(*args, **kwargs)
    thread.join()
    return result


def build_project(
    *,
    current_timeline: FakeTimeline | None = None,
    timelines: list[FakeTimeline] | None = None,
    folder_name: str = "Master",
    subfolder_names: list[str] | None = None,
    clip_names: list[str] | None = None,
    clip_items: list[FakeMediaPoolItem] | None = None,
) -> FakeProject:
    media_folder = FakeMediaPoolFolder(
        folder_name,
        subfolders=[FakeMediaPoolFolder(name) for name in (subfolder_names or [])],
        clips=clip_items or [FakeMediaPoolItem(name) for name in (clip_names or [])],
    )
    return FakeProject(
        "Demo Project",
        timelines=timelines,
        current_timeline=current_timeline,
        media_pool_folder=media_folder,
    )


def test_backend_resolve_health_end_to_end(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(build_project(), ["Demo Project"]),
        "resolve_health",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["resolve"]["connected"] is True
    assert result.data["project"]["open"] is True
    assert result.data["project"]["name"] == "Demo Project"


def test_project_current_reports_no_project_warning(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, []),
        "project_current",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["project"]["open"] is False
    assert "no_project_open" in result.warnings


def test_project_list_returns_current_folder_projects(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, ["Alpha", "Beta"]),
        "project_list",
    )

    assert result.success is True
    assert result.data == {
        "projects": [
            {"name": "Alpha"},
            {"name": "Beta"},
        ]
    }


def test_timeline_list_returns_project_timelines(tmp_path: Path) -> None:
    timelines = [FakeTimeline("Timeline 1"), FakeTimeline("Timeline 2")]
    project = build_project(timelines=timelines, current_timeline=timelines[0])
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_list",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["project"]["name"] == "Demo Project"
    assert result.data["timelines"] == [
        {"index": 1, "name": "Timeline 1"},
        {"index": 2, "name": "Timeline 2"},
    ]


def test_timeline_list_requires_open_project(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, []),
        "timeline_list",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_project_open"


def test_timeline_current_returns_active_timeline(tmp_path: Path) -> None:
    current_timeline = FakeTimeline("Cut 1")
    project = build_project(timelines=[current_timeline], current_timeline=current_timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_current",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"] == {"index": 1, "name": "Cut 1"}


def test_timeline_current_requires_active_timeline(tmp_path: Path) -> None:
    project = build_project(timelines=[FakeTimeline("Cut 1")], current_timeline=None)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_current",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_current_timeline"


def test_timeline_create_empty_succeeds(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_create_empty",
        "Assembly",
    )

    assert result.success is True
    assert result.data == {
        "created": True,
        "timeline": {"index": 1, "name": "Assembly"},
    }


def test_timeline_create_empty_requires_project(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, []),
        "timeline_create_empty",
        "Assembly",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_project_open"


def test_media_pool_list_returns_folder_contents(tmp_path: Path) -> None:
    project = build_project(
        subfolder_names=["Day 1", "Day 2"],
        clip_names=["clip001.mov", "clip002.wav"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_list",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Master"},
        "subfolders": [{"name": "Day 1"}, {"name": "Day 2"}],
        "clips": [{"name": "clip001.mov"}, {"name": "clip002.wav"}],
    }


def test_media_pool_list_filters_out_timeline_entries(tmp_path: Path) -> None:
    project = build_project(
        clip_items=[
            FakeMediaPoolItem("clip001.mov"),
            FakeMediaPoolItem(
                "Timeline 1",
                {"Clip Name": "Timeline 1", "Type": "Timeline"},
            ),
        ]
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_list",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["clips"] == [{"name": "clip001.mov"}]


def test_media_import_imports_into_current_folder(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_import",
        ["C:/media/clip001.mov", "C:/media/clip002.wav"],
    )

    assert result.success is True
    assert result.data == {
        "imported_count": 2,
        "items": [{"name": "clip001.mov"}, {"name": "clip002.wav"}],
    }


def test_timeline_append_clips_appends_into_named_timeline(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[]])
    project = build_project(
        timelines=[timeline],
        current_timeline=None,
        clip_names=["clip001.mov", "clip002.mov"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_append_clips",
        ["clip001.mov", "clip002.mov"],
        timeline_name="Assembly",
    )

    assert result.success is True
    assert result.data == {
        "timeline": {"index": 1, "name": "Assembly"},
        "appended": True,
        "count": 2,
        "clip_names": ["clip001.mov", "clip002.mov"],
    }


def test_timeline_append_clips_uses_current_timeline(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[]])
    project = build_project(
        timelines=[timeline],
        current_timeline=timeline,
        clip_names=["clip001.mov"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_append_clips",
        ["clip001.mov"],
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"]["name"] == "Assembly"


def test_timeline_append_clips_auto_creates_timeline(tmp_path: Path) -> None:
    existing = FakeTimeline("Imported Timeline")
    project = build_project(
        timelines=[existing],
        current_timeline=None,
        clip_names=["clip001.mov"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_append_clips",
        ["clip001.mov"],
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"]["name"] == "Imported Timeline 2"


def test_timeline_append_clips_fails_for_missing_clip(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[]])
    project = build_project(timelines=[timeline], current_timeline=timeline, clip_names=[])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_append_clips",
        ["missing.mov"],
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_timeline_append_clips_fails_for_ambiguous_clip_name(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[]])
    project = build_project(
        timelines=[timeline],
        current_timeline=timeline,
        clip_names=["dup.mov", "dup.mov"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_append_clips",
        ["dup.mov"],
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_timeline_items_list_returns_all_tracks(tmp_path: Path) -> None:
    timeline = FakeTimeline(
        "Assembly",
        video_tracks=[
            [FakeTimelineItem("clip001.mov", 0, 100), FakeTimelineItem("clip002.mov", 100, 200)]
        ],
        audio_tracks=[[FakeTimelineItem("audio001.wav", 0, 200)]],
    )
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_items_list",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"] == {"index": 1, "name": "Assembly"}
    assert result.data["tracks"] == [
        {
            "track_type": "video",
            "track_index": 1,
            "items": [
                {"name": "clip001.mov", "start_frame": 0, "end_frame": 100, "item_index": 0},
                {"name": "clip002.mov", "start_frame": 100, "end_frame": 200, "item_index": 1},
            ],
        },
        {
            "track_type": "audio",
            "track_index": 1,
            "items": [
                {"name": "audio001.wav", "start_frame": 0, "end_frame": 200, "item_index": 0}
            ],
        },
    ]


def test_timeline_items_list_resolves_explicit_timeline_name(tmp_path: Path) -> None:
    active_timeline = FakeTimeline("Assembly")
    named_timeline = FakeTimeline("Review", video_tracks=[[FakeTimelineItem("clip001.mov", 0, 100)]])
    project = build_project(
        timelines=[active_timeline, named_timeline],
        current_timeline=active_timeline,
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_items_list",
        timeline_name="Review",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"]["name"] == "Review"


def test_timeline_items_list_requires_current_timeline_when_not_specified(tmp_path: Path) -> None:
    project = build_project(timelines=[FakeTimeline("Assembly")], current_timeline=None)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_items_list",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_current_timeline"
