from __future__ import annotations

import threading
import time
from pathlib import Path

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import FileQueueBridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand
from davinci_free_mcp.resolve_exec import ResolveExecutor
from davinci_free_mcp.resolve_exec.command_core import execute_resolve_command


class FakeMediaPoolItem:
    def __init__(self, name: str, properties: dict[str, str] | None = None) -> None:
        self._name = name
        self._properties = properties or {"Clip Name": name, "File Path": f"C:/media/{name}"}

    def GetName(self) -> str:
        return self._name

    def GetClipProperty(self) -> dict[str, str]:
        return self._properties


class FakeTimelineItem:
    def __init__(
        self,
        name: str,
        start_frame: int,
        end_frame: int,
        *,
        source_start_frame: int = 0,
        source_end_frame: int | None = None,
        left_offset: int = 0,
        right_offset: int = 0,
        media_pool_item: FakeMediaPoolItem | None = None,
    ) -> None:
        self._name = name
        self._start_frame = start_frame
        self._end_frame = end_frame
        self._media_pool_item = media_pool_item or FakeMediaPoolItem(name)
        self._source_start_frame = source_start_frame
        self._source_end_frame = end_frame if source_end_frame is None else source_end_frame
        self._left_offset = left_offset
        self._right_offset = right_offset

    def GetName(self) -> str:
        return self._name

    def GetStart(self) -> int:
        return self._start_frame

    def GetEnd(self) -> int:
        return self._end_frame

    def GetDuration(self, subframe_precision: bool = False) -> int:
        return self._end_frame - self._start_frame

    def GetSourceStartFrame(self) -> int:
        return self._source_start_frame

    def GetSourceEndFrame(self) -> int:
        return self._source_end_frame

    def GetLeftOffset(self, subframe_precision: bool = False) -> int:
        return self._left_offset

    def GetRightOffset(self, subframe_precision: bool = False) -> int:
        return self._right_offset

    def GetTrackTypeAndIndex(self) -> list[object]:
        return [getattr(self, "_track_type", "video"), getattr(self, "_track_index", 1)]

    def GetMediaPoolItem(self) -> FakeMediaPoolItem:
        return self._media_pool_item

    def invalidate(self) -> None:
        self._name = ""
        self._start_frame = None
        self._end_frame = None


class FakeTimeline:
    def __init__(
        self,
        name: str,
        video_tracks: list[list[FakeTimelineItem]] | None = None,
        audio_tracks: list[list[FakeTimelineItem]] | None = None,
        *,
        allow_implicit_track_create: bool = True,
        fail_delete: bool = False,
    ) -> None:
        self._name = name
        self._tracks = {
            "video": video_tracks or [],
            "audio": audio_tracks or [],
        }
        self._markers: dict[int, dict[str, object]] = {}
        self._allow_implicit_track_create = allow_implicit_track_create
        self._fail_delete = fail_delete

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

    def append_clip_infos(self, clip_infos: list[dict[str, object]]) -> list[FakeTimelineItem]:
        appended: list[FakeTimelineItem] = []
        for clip_info in clip_infos:
            clip = clip_info["mediaPoolItem"]
            record_frame = int(clip_info.get("recordFrame", 0))
            track_index = int(clip_info.get("trackIndex", 1))
            media_type = int(clip_info.get("mediaType", 1))
            start_frame = int(clip_info.get("startFrame", 0))
            end_frame = int(clip_info.get("endFrame", start_frame + 100))
            track_type = "audio" if media_type == 2 else "video"

            if not self._allow_implicit_track_create and len(self._tracks[track_type]) < track_index:
                return []
            while len(self._tracks[track_type]) < track_index:
                self._tracks[track_type].append([])

            item = FakeTimelineItem(
                clip.GetName(),
                record_frame,
                record_frame + max(1, end_frame - start_frame),
                source_start_frame=start_frame,
                source_end_frame=end_frame,
            )
            item._track_type = track_type
            item._track_index = track_index
            self._tracks[track_type][track_index - 1].append(item)
            self._tracks[track_type][track_index - 1].sort(key=lambda value: value.GetStart())
            appended.append(item)
        return appended

    def AddTrack(self, track_type: str, new_track_options: object = None) -> bool:
        tracks = self._tracks.get(track_type)
        if tracks is None:
            return False

        track_index = len(tracks) + 1
        if isinstance(new_track_options, dict) and "index" in new_track_options:
            try:
                track_index = int(new_track_options["index"])
            except (TypeError, ValueError):
                return False
        if track_index < 1 or track_index > len(tracks) + 1:
            return False

        tracks.insert(track_index - 1, [])
        return True

    def DeleteClips(self, timeline_items: list[FakeTimelineItem], ripple: bool = False) -> bool:
        if self._fail_delete:
            return False
        deleted = False
        for track_type in ("video", "audio"):
            for index, track_items in enumerate(self._tracks[track_type]):
                removed = [item for item in track_items if item in timeline_items]
                kept = [item for item in track_items if item not in timeline_items]
                if len(kept) != len(track_items):
                    for item in removed:
                        item.invalidate()
                    self._tracks[track_type][index] = kept
                    deleted = True
        return deleted

    def AddMarker(
        self,
        frame: int,
        color: str,
        name: str,
        note: str,
        duration: int,
        custom_data: str,
    ) -> bool:
        self._markers[int(frame)] = {
            "color": color,
            "name": name,
            "note": note,
            "duration": int(duration),
            "custom_data": custom_data,
        }
        return True

    def marker_at(self, frame: int) -> dict[str, object] | None:
        return self._markers.get(frame)

    def GetMarkers(self) -> dict[int, dict[str, object]]:
        return dict(self._markers)

    def DeleteMarkerAtFrame(self, frame: int) -> bool:
        frame_value = int(frame)
        if frame_value not in self._markers:
            return False
        del self._markers[frame_value]
        return True


class FakeMediaPoolFolder:
    def __init__(
        self,
        name: str,
        subfolders: list["FakeMediaPoolFolder"] | None = None,
        clips: list[FakeMediaPoolItem] | None = None,
        parent: "FakeMediaPoolFolder" | None = None,
    ) -> None:
        self._name = name
        self._subfolders = subfolders or []
        self._clips = clips or []
        self._parent = parent
        for subfolder in self._subfolders:
            subfolder._parent = self

    def GetName(self) -> str:
        return self._name

    def GetSubFolderList(self) -> list["FakeMediaPoolFolder"]:
        return self._subfolders

    def GetClipList(self) -> list[FakeMediaPoolItem]:
        return self._clips

    def add_clip(self, clip: FakeMediaPoolItem) -> None:
        self._clips.append(clip)

    def add_subfolder(self, folder: "FakeMediaPoolFolder") -> "FakeMediaPoolFolder":
        folder._parent = self
        self._subfolders.append(folder)
        return folder


class FakeMediaPool:
    def __init__(self, project: "FakeProject", current_folder: FakeMediaPoolFolder) -> None:
        self._project = project
        self._current_folder = current_folder
        self._root_folder = current_folder
        while getattr(self._root_folder, "_parent", None) is not None:
            self._root_folder = self._root_folder._parent

    def GetRootFolder(self) -> FakeMediaPoolFolder:
        return self._root_folder

    def GetCurrentFolder(self) -> FakeMediaPoolFolder:
        return self._current_folder

    def SetCurrentFolder(self, folder: FakeMediaPoolFolder) -> bool:
        self._current_folder = folder
        return True

    def CreateEmptyTimeline(self, name: str) -> FakeTimeline:
        timeline = FakeTimeline(name, video_tracks=[[]], audio_tracks=[])
        self._project.add_timeline(timeline, set_current=True)
        return timeline

    def CreateTimelineFromClips(self, name: str, clips: list[FakeMediaPoolItem]) -> FakeTimeline:
        timeline = FakeTimeline(name, video_tracks=[[]], audio_tracks=[])
        timeline.append_items(clips)
        self._project.add_timeline(timeline, set_current=True)
        return timeline

    def AddSubFolder(self, folder: FakeMediaPoolFolder, name: str) -> FakeMediaPoolFolder:
        return folder.add_subfolder(FakeMediaPoolFolder(name))

    def ImportMedia(self, paths: list[str]) -> list[FakeMediaPoolItem]:
        imported: list[FakeMediaPoolItem] = []
        for path in paths:
            clip_name = Path(path).name
            clip = FakeMediaPoolItem(clip_name)
            self._current_folder.add_clip(clip)
            imported.append(clip)
        return imported

    def AppendToTimeline(self, clips: list[object]) -> object:
        timeline = self._project.GetCurrentTimeline()
        if timeline is None:
            return []
        if clips and isinstance(clips[0], dict):
            return timeline.append_clip_infos(clips)
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


class FakeProjectManagerFolder:
    def __init__(
        self,
        name: str,
        subfolders: list["FakeProjectManagerFolder"] | None = None,
        projects: list[str] | None = None,
        parent: "FakeProjectManagerFolder" | None = None,
    ) -> None:
        self._name = name
        self._subfolders = subfolders or []
        self._projects = projects or []
        self._parent = parent
        for subfolder in self._subfolders:
            subfolder._parent = self

    def child_named(self, name: str) -> "FakeProjectManagerFolder" | None:
        for subfolder in self._subfolders:
            if subfolder._name == name:
                return subfolder
        return None


class FakeProjectManager:
    def __init__(
        self,
        project: FakeProject | None,
        project_names: list[str] | None = None,
        known_projects: dict[str, FakeProject] | None = None,
        root_folder: FakeProjectManagerFolder | None = None,
        current_folder: FakeProjectManagerFolder | None = None,
    ) -> None:
        self._project = project
        self._project_names = project_names or []
        self._known_projects = known_projects or {}
        self._root_folder = root_folder
        self._current_folder = current_folder or root_folder

    def GetCurrentProject(self) -> FakeProject | None:
        return self._project

    def GetProjectListInCurrentFolder(self) -> list[str]:
        if self._current_folder is not None:
            return list(self._current_folder._projects)
        return self._project_names

    def GetFolderListInCurrentFolder(self) -> list[str]:
        if self._current_folder is None:
            return []
        return [folder._name for folder in self._current_folder._subfolders]

    def GetFoldersInCurrentFolder(self) -> dict[int, str]:
        folder_names = self.GetFolderListInCurrentFolder()
        return {index: name for index, name in enumerate(folder_names, start=1)}

    def GotoRootFolder(self) -> bool:
        if self._root_folder is None:
            return False
        self._current_folder = self._root_folder
        return True

    def GotoParentFolder(self) -> bool:
        if self._current_folder is None or self._current_folder._parent is None:
            return False
        self._current_folder = self._current_folder._parent
        return True

    def GetCurrentFolder(self) -> str | None:
        if self._current_folder is None:
            return None
        return self._current_folder._name

    def OpenFolder(self, folder_name: str) -> bool:
        if self._current_folder is None:
            return False
        target = self._current_folder.child_named(folder_name)
        if target is None:
            return False
        self._current_folder = target
        return True

    def LoadProject(self, project_name: str) -> FakeProject | None:
        project = self._known_projects.get(project_name)
        if project is not None:
            self._project = project
        return project


class FakeResolve:
    def __init__(
        self,
        project: FakeProject | None,
        project_names: list[str] | None = None,
        known_projects: dict[str, FakeProject] | None = None,
        project_root_folder: FakeProjectManagerFolder | None = None,
        project_current_folder: FakeProjectManagerFolder | None = None,
    ) -> None:
        self._project_manager = FakeProjectManager(
            project,
            project_names,
            known_projects,
            root_folder=project_root_folder,
            current_folder=project_current_folder,
        )

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
    name: str = "Demo Project",
    current_timeline: FakeTimeline | None = None,
    timelines: list[FakeTimeline] | None = None,
    folder_name: str = "Master",
    subfolder_names: list[str] | None = None,
    clip_names: list[str] | None = None,
    clip_items: list[FakeMediaPoolItem] | None = None,
    media_pool_folder: FakeMediaPoolFolder | None = None,
) -> FakeProject:
    media_folder = media_pool_folder or FakeMediaPoolFolder(
        folder_name,
        subfolders=[FakeMediaPoolFolder(name) for name in (subfolder_names or [])],
        clips=clip_items or [FakeMediaPoolItem(name) for name in (clip_names or [])],
    )
    return FakeProject(
        name,
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


def test_shared_command_core_matches_executor_result_shape(tmp_path: Path) -> None:
    project = build_project(
        timelines=[FakeTimeline("Assembly", video_tracks=[[FakeTimelineItem("clip001.mov", 0, 100)]])],
        current_timeline=FakeTimeline("Scratch"),
        clip_names=["clip001.mov"],
    )
    resolve = FakeResolve(project, ["Demo Project"])
    command = BridgeCommand(
        command="timeline_items_list",
        target={"timeline": "Assembly"},
        payload={},
        context={"tool_name": "timeline_items_list"},
    )
    executor = ResolveExecutor(build_settings(tmp_path), resolve_provider=lambda: resolve)

    executor_result = executor.handle_command(command)
    core_result = execute_resolve_command(
        command.model_dump(mode="json"),
        lambda: resolve,
        adapter_name="file_queue",
    )

    assert executor_result.model_dump(mode="json") == core_result


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


def test_project_manager_folder_list_returns_current_folder_context(tmp_path: Path) -> None:
    commercials = FakeProjectManagerFolder("Commercials", projects=["Spot A"])
    clients = FakeProjectManagerFolder(
        "Clients",
        subfolders=[commercials, FakeProjectManagerFolder("Internal")],
        projects=["Pitch Deck"],
    )
    root = FakeProjectManagerFolder("Root", subfolders=[clients], projects=["Global"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            project_root_folder=root,
            project_current_folder=clients,
        ),
        "project_manager_folder_list",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Clients"},
        "subfolders": [{"name": "Commercials"}, {"name": "Internal"}],
        "projects": [{"name": "Pitch Deck"}],
    }


def test_project_manager_folder_open_switches_to_child_folder(tmp_path: Path) -> None:
    commercials = FakeProjectManagerFolder("Commercials", projects=["Spot A"])
    clients = FakeProjectManagerFolder("Clients", subfolders=[commercials])
    root = FakeProjectManagerFolder("Root", subfolders=[clients])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            project_root_folder=root,
            project_current_folder=root,
        ),
        "project_manager_folder_open",
        "Clients",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Clients"},
        "path": [{"name": "Root"}, {"name": "Clients"}],
        "subfolders": [{"name": "Commercials"}],
        "projects": [],
    }


def test_project_manager_folder_up_switches_to_parent_folder(tmp_path: Path) -> None:
    commercials = FakeProjectManagerFolder("Commercials", projects=["Spot A"])
    clients = FakeProjectManagerFolder("Clients", subfolders=[commercials])
    root = FakeProjectManagerFolder("Root", subfolders=[clients])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            project_root_folder=root,
            project_current_folder=commercials,
        ),
        "project_manager_folder_up",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Clients"},
        "path": [{"name": "Root"}, {"name": "Clients"}],
        "subfolders": [{"name": "Commercials"}],
        "projects": [],
    }


def test_project_manager_folder_path_returns_breadcrumb(tmp_path: Path) -> None:
    commercials = FakeProjectManagerFolder("Commercials", projects=["Spot A"])
    clients = FakeProjectManagerFolder("Clients", subfolders=[commercials])
    root = FakeProjectManagerFolder("Root", subfolders=[clients], projects=["Global"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            project_root_folder=root,
            project_current_folder=commercials,
        ),
        "project_manager_folder_path",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Commercials"},
        "path": [{"name": "Root"}, {"name": "Clients"}, {"name": "Commercials"}],
        "subfolders": [],
        "projects": [{"name": "Spot A"}],
    }


def test_project_manager_folder_up_rejects_root_folder(tmp_path: Path) -> None:
    root = FakeProjectManagerFolder("Root", projects=["Global"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            project_root_folder=root,
            project_current_folder=root,
        ),
        "project_manager_folder_up",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_project_manager_folder_path_normalizes_blank_root_name(tmp_path: Path) -> None:
    root = FakeProjectManagerFolder("", projects=["Untitled Project 5"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            project_root_folder=root,
            project_current_folder=root,
        ),
        "project_manager_folder_path",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Root"},
        "path": [{"name": "Root"}],
        "subfolders": [],
        "projects": [{"name": "Untitled Project 5"}],
    }


def test_project_open_switches_to_named_project(tmp_path: Path) -> None:
    target_project = build_project(name="Beta")
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(
            None,
            ["Alpha", "Beta"],
            {"Beta": target_project},
        ),
        "project_open",
        "Beta",
    )

    assert result.success is True
    assert result.data == {
        "opened": True,
        "project": {"open": True, "name": "Beta"},
    }


def test_project_open_returns_not_found_for_unknown_project(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(None, ["Alpha"]),
        "project_open",
        "Missing",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_project_open_requires_resolve_handle(tmp_path: Path) -> None:
    result = invoke_with_executor(
        tmp_path,
        lambda: None,
        "project_open",
        "Alpha",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "resolve_not_ready"


def test_project_open_updates_project_current_state(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    bridge = FileQueueBridge(settings)
    beta_project = build_project(name="Beta")
    backend = ResolveBackendService(bridge, settings)
    fake_resolve = FakeResolve(
        None,
        ["Alpha", "Beta"],
        {"Beta": beta_project},
    )
    executor = ResolveExecutor(
        settings,
        resolve_provider=lambda: fake_resolve,
    )

    open_thread = threading.Thread(target=process_until_handled, args=(executor,))
    open_thread.start()
    open_result = backend.project_open("Beta")
    open_thread.join()

    current_thread = threading.Thread(target=process_until_handled, args=(executor,))
    current_thread.start()
    current_result = backend.project_current()
    current_thread.join()

    assert open_result.success is True
    assert current_result.success is True
    assert current_result.data == {
        "project": {"open": True, "name": "Beta"},
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


def test_timeline_set_current_switches_active_timeline(tmp_path: Path) -> None:
    timeline_a = FakeTimeline("Assembly")
    timeline_b = FakeTimeline("Review")
    project = build_project(
        timelines=[timeline_a, timeline_b],
        current_timeline=timeline_a,
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_set_current",
        "Review",
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 2, "name": "Review"},
    }
    assert project.GetCurrentTimeline() is timeline_b


def test_timeline_set_current_fails_for_missing_timeline(tmp_path: Path) -> None:
    project = build_project(
        timelines=[FakeTimeline("Assembly")],
        current_timeline=FakeTimeline("Assembly"),
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_set_current",
        "Missing",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


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


def test_media_pool_folder_open_switches_into_child_folder(tmp_path: Path) -> None:
    selects = FakeMediaPoolFolder(
        "Selects",
        subfolders=[FakeMediaPoolFolder("Closeups")],
        clips=[FakeMediaPoolItem("clip010.mov")],
    )
    project = FakeProject(
        "Demo Project",
        media_pool_folder=FakeMediaPoolFolder(
            "Master",
            subfolders=[selects, FakeMediaPoolFolder("Day 2")],
            clips=[FakeMediaPoolItem("clip001.mov")],
        ),
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_open",
        "Selects",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Selects"},
        "subfolders": [{"name": "Closeups"}],
        "clips": [{"name": "clip010.mov"}],
    }
    assert project.GetMediaPool().GetCurrentFolder() is selects


def test_media_pool_folder_open_fails_for_ambiguous_name(tmp_path: Path) -> None:
    project = FakeProject(
        "Demo Project",
        media_pool_folder=FakeMediaPoolFolder(
            "Master",
            subfolders=[FakeMediaPoolFolder("Selects"), FakeMediaPoolFolder("Selects")],
        ),
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_open",
        "Selects",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_media_pool_folder_open_fails_for_missing_child_folder(tmp_path: Path) -> None:
    project = build_project(subfolder_names=["Day 1"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_open",
        "Missing",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


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


def test_timeline_track_items_list_returns_one_track(tmp_path: Path) -> None:
    timeline = FakeTimeline(
        "Assembly",
        video_tracks=[
            [FakeTimelineItem("clip001.mov", 0, 100)],
            [FakeTimelineItem("clip002.mov", 100, 200), FakeTimelineItem("clip003.mov", 200, 300)],
        ],
        audio_tracks=[[FakeTimelineItem("audio001.wav", 0, 300)]],
    )
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_track_items_list",
        "video",
        2,
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "track": {
            "track_type": "video",
            "track_index": 2,
            "items": [
                {"name": "clip002.mov", "start_frame": 100, "end_frame": 200, "item_index": 0},
                {"name": "clip003.mov", "start_frame": 200, "end_frame": 300, "item_index": 1},
            ],
        },
    }


def test_timeline_track_items_list_rejects_invalid_track_type(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[FakeTimelineItem("clip001.mov", 0, 100)]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_track_items_list",
        "subtitle",
        1,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_timeline_track_items_list_returns_not_found_for_missing_track(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[FakeTimelineItem("clip001.mov", 0, 100)]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_track_items_list",
        "video",
        5,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_timeline_track_inspect_returns_bounds_and_count(tmp_path: Path) -> None:
    timeline = FakeTimeline(
        "Assembly",
        video_tracks=[
            [],
            [FakeTimelineItem("clip002.mov", 100, 200), FakeTimelineItem("clip003.mov", 220, 340)],
        ],
    )
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_track_inspect",
        "video",
        2,
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "track_type": "video",
        "track_index": 2,
        "item_count": 2,
        "start_frame": 100,
        "end_frame": 340,
    }


def test_timeline_track_inspect_returns_not_found_for_missing_track(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[FakeTimelineItem("clip001.mov", 0, 100)]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_track_inspect",
        "audio",
        1,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_timeline_clips_place_places_subclip_on_requested_track(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[]], allow_implicit_track_create=False)
    project = build_project(
        timelines=[timeline],
        current_timeline=timeline,
        clip_names=["clip001.mov", "clip002.mov"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_clips_place",
        [
            {
                "clip_name": "clip001.mov",
                "record_frame": 100,
                "track_index": 1,
                "start_frame": 0,
                "end_frame": 24,
            },
            {
                "clip_name": "clip002.mov",
                "record_frame": 200,
                "track_index": 2,
                "start_frame": 10,
                "end_frame": 40,
            },
        ],
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "placed_count": 2,
        "items": [
            {
                "item_index": None,
                "name": "clip001.mov",
                "track_type": "video",
                "track_index": 1,
                "start_frame": 100,
                "end_frame": 124,
            },
            {
                "item_index": None,
                "name": "clip002.mov",
                "track_type": "video",
                "track_index": 2,
                "start_frame": 200,
                "end_frame": 230,
            },
        ],
    }
    assert timeline.GetTrackCount("video") == 2


def test_timeline_item_inspect_returns_clip_timing_details(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly", video_tracks=[[FakeTimelineItem("clip001.mov", 100, 124)]])
    project = build_project(timelines=[timeline], current_timeline=timeline)
    timeline._tracks["video"][0][0]._track_type = "video"
    timeline._tracks["video"][0][0]._track_index = 1

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_inspect",
        "video",
        1,
        0,
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "item": {
            "item_index": 0,
            "name": "clip001.mov",
            "track_type": "video",
            "track_index": 1,
            "start_frame": 100,
            "end_frame": 124,
        },
        "duration": 24,
        "source_start_frame": 0,
        "source_end_frame": 124,
        "left_offset": 0,
        "right_offset": 0,
    }


def test_timeline_item_delete_removes_selected_item(tmp_path: Path) -> None:
    first = FakeTimelineItem("clip001.mov", 100, 124)
    second = FakeTimelineItem("clip002.mov", 200, 224)
    first._track_type = "video"
    first._track_index = 1
    second._track_type = "video"
    second._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[first, second]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_delete",
        "video",
        1,
        0,
    )

    assert result.success is True
    assert result.data == {
        "deleted": True,
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "item": {
            "item_index": 0,
            "name": "clip001.mov",
            "track_type": "video",
            "track_index": 1,
            "start_frame": 100,
            "end_frame": 124,
        },
        "ripple": False,
    }
    assert len(timeline.GetItemListInTrack("video", 1)) == 1
    assert timeline.GetItemListInTrack("video", 1)[0].GetName() == "clip002.mov"


def test_timeline_item_move_recreates_clip_on_same_track(tmp_path: Path) -> None:
    first = FakeTimelineItem("clip001.mov", 100, 124, source_start_frame=10, source_end_frame=34)
    second = FakeTimelineItem("clip002.mov", 200, 224)
    first._track_type = "video"
    first._track_index = 1
    second._track_type = "video"
    second._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[first, second]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        300,
    )

    assert result.success is True
    assert result.data == {
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
            "item_index": None,
            "name": "clip001.mov",
            "track_type": "video",
            "track_index": 1,
            "start_frame": 300,
            "end_frame": 324,
        },
    }
    moved_names = [item.GetName() for item in timeline.GetItemListInTrack("video", 1)]
    assert moved_names == ["clip002.mov", "clip001.mov"]


def test_timeline_item_move_auto_creates_target_track(tmp_path: Path) -> None:
    item = FakeTimelineItem("clip001.mov", 100, 124, source_start_frame=10, source_end_frame=34)
    item._track_type = "video"
    item._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[item]], allow_implicit_track_create=False)
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        400,
        target_track_index=2,
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["item"]["track_index"] == 2
    assert timeline.GetTrackCount("video") == 2
    assert timeline.GetItemListInTrack("video", 1) == []
    assert timeline.GetItemListInTrack("video", 2)[0].GetStart() == 400


def test_timeline_item_move_falls_back_to_item_duration_for_zero_source_range(tmp_path: Path) -> None:
    item = FakeTimelineItem("clip001.mov", 100, 124, source_start_frame=0, source_end_frame=0)
    item._track_type = "video"
    item._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[item]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        500,
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["item"]["start_frame"] == 500
    assert result.data["item"]["end_frame"] == 524


def test_timeline_item_move_uses_named_timeline_when_provided(tmp_path: Path) -> None:
    active = FakeTimeline("Assembly", video_tracks=[[]])
    review_item = FakeTimelineItem("clip001.mov", 100, 124, source_start_frame=0, source_end_frame=24)
    review_item._track_type = "video"
    review_item._track_index = 1
    review = FakeTimeline("Review", video_tracks=[[review_item]])
    project = build_project(timelines=[active, review], current_timeline=active)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        250,
        timeline_name="Review",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"] == {"index": 2, "name": "Review"}
    assert active.GetItemListInTrack("video", 1) == []
    assert review.GetItemListInTrack("video", 1)[0].GetStart() == 250


def test_timeline_item_move_rejects_invalid_target_track_type(tmp_path: Path) -> None:
    item = FakeTimelineItem("clip001.mov", 100, 124)
    item._track_type = "video"
    item._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[item]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        300,
        target_track_type="subtitle",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_timeline_item_move_fails_without_media_pool_item(tmp_path: Path) -> None:
    item = FakeTimelineItem("clip001.mov", 100, 124, media_pool_item=None)
    item._media_pool_item = None
    item._track_type = "video"
    item._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[item]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        300,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_move_fails_for_invalid_source_extents(tmp_path: Path) -> None:
    item = FakeTimelineItem("clip001.mov", 100, 124, source_start_frame=30, source_end_frame=30)
    item._track_type = "video"
    item._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[item]])
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        300,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"


def test_timeline_item_move_reports_non_atomic_failure_when_delete_fails(tmp_path: Path) -> None:
    item = FakeTimelineItem("clip001.mov", 100, 124, source_start_frame=0, source_end_frame=24)
    item._track_type = "video"
    item._track_index = 1
    timeline = FakeTimeline("Assembly", video_tracks=[[item]], fail_delete=True)
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_item_move",
        "video",
        1,
        0,
        300,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "execution_failure"
    assert result.error.details["move_completed"] is False
    assert len(timeline.GetItemListInTrack("video", 1)) == 2


def test_marker_add_adds_marker_to_current_timeline(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_add",
        120,
        "Cut point",
        note="Review this join",
        duration=12,
    )

    assert result.success is True
    assert result.data == {
        "added": True,
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "marker": {
            "frame": 120,
            "color": "Blue",
            "name": "Cut point",
            "note": "Review this join",
            "duration": 12,
            "custom_data": "",
        },
    }
    assert timeline.marker_at(120) == {
        "color": "Blue",
        "name": "Cut point",
        "note": "Review this join",
        "duration": 12,
        "custom_data": "",
    }


def test_marker_add_uses_named_timeline_when_provided(tmp_path: Path) -> None:
    active = FakeTimeline("Assembly")
    review = FakeTimeline("Review")
    project = build_project(
        timelines=[active, review],
        current_timeline=active,
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_add",
        48,
        "Needs VO",
        timeline_name="Review",
        color="Green",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"] == {"index": 2, "name": "Review"}
    assert review.marker_at(48) is not None
    assert active.marker_at(48) is None


def test_marker_add_requires_positive_duration(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_add",
        10,
        "Bad marker",
        duration=0,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_marker_add_requires_current_timeline_when_not_specified(tmp_path: Path) -> None:
    project = build_project(timelines=[FakeTimeline("Assembly")], current_timeline=None)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_add",
        10,
        "Review",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_current_timeline"


def test_marker_list_returns_sorted_markers_for_current_timeline(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    timeline.AddMarker(120, "Blue", "Second", "", 1, "")
    timeline.AddMarker(24, "Green", "First", "note", 12, "custom")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_list",
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "markers": [
            {
                "frame": 24,
                "color": "Green",
                "name": "First",
                "note": "note",
                "duration": 12,
                "custom_data": "custom",
            },
            {
                "frame": 120,
                "color": "Blue",
                "name": "Second",
                "note": "",
                "duration": 1,
                "custom_data": "",
            },
        ],
    }


def test_marker_list_uses_named_timeline_when_provided(tmp_path: Path) -> None:
    active = FakeTimeline("Assembly")
    review = FakeTimeline("Review")
    review.AddMarker(48, "Red", "Needs fix", "", 4, "")
    project = build_project(timelines=[active, review], current_timeline=active)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_list",
        timeline_name="Review",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"] == {"index": 2, "name": "Review"}
    assert result.data["markers"][0]["frame"] == 48


def test_marker_list_requires_current_timeline_when_not_specified(tmp_path: Path) -> None:
    project = build_project(timelines=[FakeTimeline("Assembly")], current_timeline=None)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_list",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_current_timeline"


def test_marker_inspect_returns_one_marker(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    timeline.AddMarker(24, "Green", "First", "note", 12, "custom")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_inspect",
        24,
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "marker": {
            "frame": 24,
            "color": "Green",
            "name": "First",
            "note": "note",
            "duration": 12,
            "custom_data": "custom",
        },
    }


def test_marker_inspect_returns_not_found_for_missing_frame(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_inspect",
        999,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_marker_list_range_filters_markers_by_frame_bounds(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    timeline.AddMarker(10, "Blue", "A", "", 1, "")
    timeline.AddMarker(20, "Blue", "B", "", 1, "")
    timeline.AddMarker(30, "Blue", "C", "", 1, "")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_list_range",
        15,
        25,
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "frame_from": 15,
        "frame_to": 25,
        "markers": [
            {
                "frame": 20,
                "color": "Blue",
                "name": "B",
                "note": "",
                "duration": 1,
                "custom_data": "",
            }
        ],
    }


def test_marker_list_range_rejects_inverted_bounds(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_list_range",
        30,
        10,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_marker_delete_removes_marker_from_current_timeline(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    timeline.AddMarker(24, "Blue", "Review", "", 1, "")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_delete",
        24,
    )

    assert result.success is True
    assert result.data == {
        "deleted": True,
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "marker": {"frame": 24},
    }
    assert timeline.marker_at(24) is None


def test_marker_delete_uses_named_timeline_when_provided(tmp_path: Path) -> None:
    active = FakeTimeline("Assembly")
    review = FakeTimeline("Review")
    review.AddMarker(10, "Blue", "Delete me", "", 1, "")
    project = build_project(timelines=[active, review], current_timeline=active)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_delete",
        10,
        timeline_name="Review",
    )

    assert result.success is True
    assert review.marker_at(10) is None
    assert result.data is not None
    assert result.data["timeline"] == {"index": 2, "name": "Review"}


def test_marker_delete_returns_not_found_for_missing_frame(tmp_path: Path) -> None:
    timeline = FakeTimeline("Assembly")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "marker_delete",
        999,
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_media_pool_folder_create_creates_and_switches_to_child_folder(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_create",
        "Selects",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Selects"},
        "subfolders": [],
        "clips": [],
    }
    assert project.GetMediaPool().GetCurrentFolder().GetName() == "Selects"


def test_media_pool_folder_create_requires_name(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_create",
        "",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_media_pool_folder_up_switches_to_parent_folder(tmp_path: Path) -> None:
    child = FakeMediaPoolFolder("Selects", clips=[FakeMediaPoolItem("clip001.mov")])
    root = FakeMediaPoolFolder("Master", subfolders=[child])
    project = build_project(media_pool_folder=child)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_up",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Master"},
        "subfolders": [{"name": "Selects"}],
        "clips": [],
    }
    assert project.GetMediaPool().GetCurrentFolder() is root


def test_media_pool_folder_up_returns_validation_error_on_root(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_up",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_media_pool_folder_root_switches_to_root_folder(tmp_path: Path) -> None:
    child = FakeMediaPoolFolder("Selects", clips=[FakeMediaPoolItem("clip001.mov")])
    root = FakeMediaPoolFolder("Master", subfolders=[child], clips=[FakeMediaPoolItem("root.mov")])
    project = build_project(media_pool_folder=child)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_root",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Master"},
        "path": [{"name": "Master"}],
        "subfolders": [{"name": "Selects"}],
        "clips": [{"name": "root.mov"}],
    }
    assert project.GetMediaPool().GetCurrentFolder() is root


def test_media_pool_folder_path_returns_breadcrumb_for_current_folder(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups", clips=[FakeMediaPoolItem("clip001.mov")])
    selects = FakeMediaPoolFolder("Selects", subfolders=[closeups])
    FakeMediaPoolFolder("Master", subfolders=[selects])
    project = build_project(media_pool_folder=closeups)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_path",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Closeups"},
        "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
        "subfolders": [],
        "clips": [{"name": "clip001.mov"}],
    }


def test_media_pool_folder_list_recursive_returns_tree(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups", clips=[FakeMediaPoolItem("clip001.mov")])
    selects = FakeMediaPoolFolder(
        "Selects",
        subfolders=[closeups],
        clips=[FakeMediaPoolItem("select.mov")],
    )
    root = FakeMediaPoolFolder("Master", subfolders=[selects], clips=[FakeMediaPoolItem("root.mov")])
    project = build_project(media_pool_folder=root)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_list_recursive",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Master"},
        "path": [{"name": "Master"}],
        "max_depth": None,
        "tree": {
            "name": "Master",
            "clips": [{"name": "root.mov"}],
            "subfolders": [
                {
                    "name": "Selects",
                    "clips": [{"name": "select.mov"}],
                    "subfolders": [
                        {
                            "name": "Closeups",
                            "clips": [{"name": "clip001.mov"}],
                            "subfolders": [],
                        }
                    ],
                }
            ],
        },
    }


def test_media_pool_folder_list_recursive_respects_max_depth(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups", clips=[FakeMediaPoolItem("clip001.mov")])
    selects = FakeMediaPoolFolder("Selects", subfolders=[closeups])
    root = FakeMediaPoolFolder("Master", subfolders=[selects])
    project = build_project(media_pool_folder=root)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_list_recursive",
        1,
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["max_depth"] == 1
    assert result.data["tree"]["subfolders"][0]["subfolders"] == []


def test_media_pool_folder_open_path_supports_relative_navigation(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups")
    selects = FakeMediaPoolFolder("Selects", subfolders=[closeups])
    root = FakeMediaPoolFolder("Master", subfolders=[selects, FakeMediaPoolFolder("Day 2")])
    project = build_project(media_pool_folder=root)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_open_path",
        "Selects/Closeups",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Closeups"},
        "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
        "subfolders": [],
        "clips": [],
    }
    assert project.GetMediaPool().GetCurrentFolder() is closeups


def test_media_pool_folder_open_path_supports_absolute_and_parent_segments(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups")
    selects = FakeMediaPoolFolder("Selects", subfolders=[closeups])
    FakeMediaPoolFolder("Master", subfolders=[selects, FakeMediaPoolFolder("Day 2")])
    project = build_project(media_pool_folder=closeups)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_open_path",
        "/Master/Selects/../Day 2",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Day 2"},
        "path": [{"name": "Master"}, {"name": "Day 2"}],
        "subfolders": [],
        "clips": [],
    }
    assert project.GetMediaPool().GetCurrentFolder().GetName() == "Day 2"


def test_media_pool_folder_open_path_rejects_navigation_above_root(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_pool_folder_open_path",
        "../../Outside",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_media_clip_inspect_returns_properties_from_current_folder(tmp_path: Path) -> None:
    clip = FakeMediaPoolItem(
        "clip001.mov",
        {"Clip Name": "clip001.mov", "File Path": "C:/media/clip001.mov", "FPS": "24"},
    )
    project = build_project(clip_items=[clip])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_clip_inspect",
        "clip001.mov",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Master"},
        "clip": {
            "name": "clip001.mov",
            "properties": {
                "Clip Name": "clip001.mov",
                "File Path": "C:/media/clip001.mov",
                "FPS": "24",
            },
        },
    }


def test_media_clip_inspect_returns_not_found_for_missing_clip(tmp_path: Path) -> None:
    project = build_project(clip_names=["clip001.mov"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_clip_inspect",
        "missing.mov",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_media_clip_inspect_returns_validation_error_for_ambiguous_clip(tmp_path: Path) -> None:
    project = build_project(clip_names=["dup.mov", "dup.mov"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_clip_inspect",
        "dup.mov",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_media_clip_inspect_path_resolves_relative_path(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups", clips=[FakeMediaPoolItem("clip001.mov")])
    selects = FakeMediaPoolFolder("Selects", subfolders=[closeups])
    root = FakeMediaPoolFolder("Master", subfolders=[selects])
    project = build_project(media_pool_folder=root)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_clip_inspect_path",
        "Selects/Closeups/clip001.mov",
    )

    assert result.success is True
    assert result.data == {
        "folder": {"name": "Closeups"},
        "path": [{"name": "Master"}, {"name": "Selects"}, {"name": "Closeups"}],
        "clip": {
            "name": "clip001.mov",
            "properties": {"Clip Name": "clip001.mov", "File Path": "C:/media/clip001.mov"},
        },
    }


def test_media_clip_inspect_path_supports_relative_parent_segments(tmp_path: Path) -> None:
    closeups = FakeMediaPoolFolder("Closeups", clips=[FakeMediaPoolItem("clip001.mov")])
    selects = FakeMediaPoolFolder("Selects", subfolders=[closeups])
    FakeMediaPoolFolder("Master", subfolders=[selects])
    project = build_project(media_pool_folder=closeups)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_clip_inspect_path",
        "../Closeups/clip001.mov",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["clip"]["name"] == "clip001.mov"
    assert result.data["folder"] == {"name": "Closeups"}


def test_media_clip_inspect_path_returns_not_found_for_missing_clip(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "media_clip_inspect_path",
        "missing.mov",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_timeline_create_from_clips_creates_new_current_timeline(tmp_path: Path) -> None:
    existing = FakeTimeline("Assembly")
    project = build_project(
        timelines=[existing],
        current_timeline=existing,
        clip_names=["clip001.mov", "clip002.mov"],
    )

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_create_from_clips",
        "Review Cut",
        ["clip001.mov", "clip002.mov"],
    )

    assert result.success is True
    assert result.data == {
        "created": True,
        "timeline": {"index": 2, "name": "Review Cut"},
        "count": 2,
        "clip_names": ["clip001.mov", "clip002.mov"],
    }
    assert project.GetCurrentTimeline() is project.GetTimelineByIndex(2)


def test_timeline_create_from_clips_requires_non_empty_list(tmp_path: Path) -> None:
    project = build_project()

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_create_from_clips",
        "Review Cut",
        [],
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_timeline_create_from_clips_fails_for_missing_clip(tmp_path: Path) -> None:
    project = build_project(clip_names=["clip001.mov"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_create_from_clips",
        "Review Cut",
        ["missing.mov"],
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "object_not_found"


def test_timeline_create_from_clips_fails_for_ambiguous_clip(tmp_path: Path) -> None:
    project = build_project(clip_names=["dup.mov", "dup.mov"])

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_create_from_clips",
        "Review Cut",
        ["dup.mov"],
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_timeline_inspect_returns_track_and_marker_counts(tmp_path: Path) -> None:
    timeline = FakeTimeline(
        "Assembly",
        video_tracks=[
            [FakeTimelineItem("clip001.mov", 0, 100), FakeTimelineItem("clip002.mov", 100, 200)],
            [FakeTimelineItem("clip003.mov", 0, 120)],
        ],
        audio_tracks=[[FakeTimelineItem("audio001.wav", 0, 200)]],
    )
    timeline.AddMarker(24, "Blue", "A", "", 1, "")
    timeline.AddMarker(48, "Green", "B", "", 2, "")
    project = build_project(timelines=[timeline], current_timeline=timeline)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_inspect",
    )

    assert result.success is True
    assert result.data == {
        "project": {"open": True, "name": "Demo Project"},
        "timeline": {"index": 1, "name": "Assembly"},
        "video_track_count": 2,
        "audio_track_count": 1,
        "video_item_count": 3,
        "audio_item_count": 1,
        "marker_count": 2,
    }


def test_timeline_inspect_resolves_explicit_timeline_name(tmp_path: Path) -> None:
    active = FakeTimeline("Assembly")
    review = FakeTimeline("Review", video_tracks=[[FakeTimelineItem("clip001.mov", 0, 100)]])
    project = build_project(timelines=[active, review], current_timeline=active)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_inspect",
        timeline_name="Review",
    )

    assert result.success is True
    assert result.data is not None
    assert result.data["timeline"] == {"index": 2, "name": "Review"}
    assert result.data["video_item_count"] == 1


def test_timeline_inspect_requires_current_timeline_when_not_specified(tmp_path: Path) -> None:
    project = build_project(timelines=[FakeTimeline("Assembly")], current_timeline=None)

    result = invoke_with_executor(
        tmp_path,
        lambda: FakeResolve(project, ["Demo Project"]),
        "timeline_inspect",
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.category == "no_current_timeline"
