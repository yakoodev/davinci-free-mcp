"""Internal executor for Resolve Free."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import (
    BridgeCommand,
    BridgeResult,
    ResolveHealthData,
    ResolveMediaClipSummary,
    ResolveMediaImportData,
    ResolveMediaPoolFolderSummary,
    ResolveMediaPoolListData,
    ResolveMediaPoolSubfolderSummary,
    ResolveProjectCurrentData,
    ResolveProjectListData,
    ResolveProjectStatus,
    ResolveProjectSummary,
    ResolveTimelineAppendClipsData,
    ResolveTimelineCreateEmptyData,
    ResolveTimelineCurrentData,
    ResolveTimelineItemSummary,
    ResolveTimelineItemsListData,
    ResolveTimelineListData,
    ResolveTimelineSummary,
    ResolveTimelineTrackSummary,
)


def resolve_from_embedded_environment(explicit_app: Any | None = None) -> Any | None:
    """Return a Resolve handle when running inside Resolve's embedded environment."""

    app_obj = explicit_app
    if app_obj is None:
        app_obj = globals().get("app")

    if app_obj is None or not hasattr(app_obj, "GetResolve"):
        return None

    try:
        return app_obj.GetResolve()
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


class ResolveExecutor:
    """Polling executor meant to run inside Resolve Free."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        *,
        resolve_provider: Callable[[], Any | None] | None = None,
        adapter_name: str = "file_queue",
    ) -> None:
        self.settings = settings or AppSettings()
        self.requests_dir = self.settings.requests_dir
        self.results_dir = self.settings.results_dir
        self.deadletter_dir = self.settings.deadletter_dir
        self.adapter_name = adapter_name
        self.resolve_provider = resolve_provider or resolve_from_embedded_environment
        self._ensure_runtime_dirs()
        self._command_handlers = {
            "resolve_health": self._handle_resolve_health,
            "project_current": self._handle_project_current,
            "project_list": self._handle_project_list,
            "timeline_list": self._handle_timeline_list,
            "timeline_current": self._handle_timeline_current,
            "timeline_create_empty": self._handle_timeline_create_empty,
            "media_pool_list": self._handle_media_pool_list,
            "media_import": self._handle_media_import,
            "timeline_append_clips": self._handle_timeline_append_clips,
            "timeline_items_list": self._handle_timeline_items_list,
        }

    def _ensure_runtime_dirs(self) -> None:
        for path in (self.requests_dir, self.results_dir, self.deadletter_dir):
            path.mkdir(parents=True, exist_ok=True)

    def _list_requests(self) -> list[Path]:
        return sorted(self.requests_dir.glob("*.json"))

    def _deadletter(self, request_path: Path) -> None:
        target = self.deadletter_dir / request_path.name
        os.replace(request_path, target)

    def process_next_request_once(self) -> BridgeResult | None:
        request_files = self._list_requests()
        if not request_files:
            return None

        request_path = request_files[0]
        try:
            raw_data = json.loads(request_path.read_text(encoding="utf-8"))
            command = BridgeCommand.model_validate(raw_data)
        except Exception:
            self._deadletter(request_path)
            return None

        result = self.handle_command(command)
        _atomic_write_json(
            self.results_dir / f"{command.request_id}.json",
            result.model_dump(mode="json"),
        )
        request_path.unlink(missing_ok=True)
        return result

    def handle_command(self, command: BridgeCommand) -> BridgeResult:
        handler = self._command_handlers.get(command.command)
        if handler is None:
            return BridgeResult.failure(
                command.request_id,
                "unsupported_command",
                f"Unsupported command '{command.command}' for executor.",
                meta={"bridge": self.adapter_name},
            )

        resolve = self.resolve_provider()
        if resolve is None:
            return BridgeResult.failure(
                command.request_id,
                "resolve_not_ready",
                "Resolve handle is not available in the embedded environment.",
                meta={"bridge": self.adapter_name},
            )

        return handler(command, resolve)

    def _handle_resolve_health(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        project_name = self._safe_call(current_project, "GetName")
        warnings: list[str] = []
        if current_project is None:
            warnings.append("no_project_open")

        payload = ResolveHealthData.model_validate(
            {
                "bridge": {"available": True, "adapter": self.adapter_name},
                "executor": {"running": True},
                "resolve": {
                    "connected": True,
                    "product_name": self._safe_call(resolve, "GetProductName"),
                    "version": self._safe_call(resolve, "GetVersionString"),
                },
                "project": {
                    "open": current_project is not None,
                    "name": project_name,
                },
            }
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            warnings=warnings,
            meta={"bridge": self.adapter_name},
        )

    def _handle_project_current(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        payload = ResolveProjectCurrentData(
            project=ResolveProjectStatus(
                open=current_project is not None,
                name=self._safe_call(current_project, "GetName"),
            )
        )
        warnings = ["no_project_open"] if current_project is None else []
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            warnings=warnings,
            meta={"bridge": self.adapter_name},
        )

    def _handle_project_list(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        project_manager = self._safe_call(resolve, "GetProjectManager")
        project_names = self._list_project_names(project_manager)
        payload = ResolveProjectListData(
            projects=[ResolveProjectSummary(name=name) for name in project_names]
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_timeline_list(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        timeline_count = self._safe_call(current_project, "GetTimelineCount") or 0
        timelines: list[ResolveTimelineSummary] = []
        for index in range(1, int(timeline_count) + 1):
            timeline = self._safe_call(current_project, "GetTimelineByIndex", index)
            if timeline is None:
                continue
            name = self._safe_call(timeline, "GetName") or f"Timeline {index}"
            timelines.append(ResolveTimelineSummary(index=index, name=name))

        payload = ResolveTimelineListData(
            project=ResolveProjectStatus(
                open=True,
                name=self._safe_call(current_project, "GetName"),
            ),
            timelines=timelines,
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_timeline_current(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        timeline = self._safe_call(current_project, "GetCurrentTimeline")
        if timeline is None:
            return BridgeResult.failure(
                command.request_id,
                "no_current_timeline",
                "No current timeline is active in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        payload = ResolveTimelineCurrentData(
            project=ResolveProjectStatus(open=True, name=self._safe_call(current_project, "GetName")),
            timeline=self._timeline_summary(current_project, timeline),
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_timeline_create_empty(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        timeline_name = str(command.payload.get("name") or "").strip()
        if not timeline_name:
            return BridgeResult.failure(
                command.request_id,
                "validation_error",
                "Timeline name is required.",
                meta={"bridge": self.adapter_name},
            )

        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return BridgeResult.failure(
                command.request_id,
                "object_not_found",
                "Current media pool is not available.",
                meta={"bridge": self.adapter_name},
            )

        created_timeline = self._safe_call(media_pool, "CreateEmptyTimeline", timeline_name)
        if created_timeline is None:
            created_timeline = self._resolve_timeline_by_name(current_project, timeline_name)

        if created_timeline is None:
            return BridgeResult.failure(
                command.request_id,
                "execution_failure",
                f"Resolve did not create timeline '{timeline_name}'.",
                meta={"bridge": self.adapter_name},
            )

        payload = ResolveTimelineCreateEmptyData(
            created=True,
            timeline=self._timeline_summary(current_project, created_timeline),
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_media_pool_list(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        current_folder = self._current_media_pool_folder(current_project)
        if current_folder is None:
            return BridgeResult.failure(
                command.request_id,
                "object_not_found",
                "Current media pool folder is not available.",
                meta={"bridge": self.adapter_name},
            )

        payload = ResolveMediaPoolListData(
            folder=ResolveMediaPoolFolderSummary(
                name=self._safe_call(current_folder, "GetName") or "Current Folder"
            ),
            subfolders=[
                ResolveMediaPoolSubfolderSummary(
                    name=self._safe_call(folder, "GetName") or "Folder"
                )
                for folder in self._list_media_subfolders(current_folder)
            ],
            clips=[
                ResolveMediaClipSummary(name=self._clip_name(clip) or "Unnamed Clip")
                for clip in self._list_media_clips(current_folder)
            ],
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_media_import(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        paths = command.payload.get("paths")
        if not isinstance(paths, list) or not paths:
            return BridgeResult.failure(
                command.request_id,
                "validation_error",
                "Import requires at least one path.",
                meta={"bridge": self.adapter_name},
            )

        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return BridgeResult.failure(
                command.request_id,
                "object_not_found",
                "Current media pool is not available.",
                meta={"bridge": self.adapter_name},
            )

        imported_items_raw = self._safe_call(media_pool, "ImportMedia", paths)
        imported_items = imported_items_raw if isinstance(imported_items_raw, list) else []
        payload = ResolveMediaImportData(
            imported_count=len(imported_items),
            items=[
                ResolveMediaClipSummary(name=self._clip_name(item) or str(path))
                for item, path in zip(imported_items, paths)
            ],
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_timeline_append_clips(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        clip_names = command.payload.get("clip_names")
        if not isinstance(clip_names, list) or not clip_names:
            return BridgeResult.failure(
                command.request_id,
                "validation_error",
                "At least one clip name is required.",
                meta={"bridge": self.adapter_name},
            )

        current_folder = self._current_media_pool_folder(current_project)
        if current_folder is None:
            return BridgeResult.failure(
                command.request_id,
                "object_not_found",
                "Current media pool folder is not available.",
                meta={"bridge": self.adapter_name},
            )

        resolved_clips: list[Any] = []
        for clip_name in clip_names:
            clip_result = self._resolve_clip_by_name(current_folder, str(clip_name))
            if isinstance(clip_result, BridgeResult):
                clip_result.request_id = command.request_id
                return clip_result
            resolved_clips.append(clip_result)

        timeline_name = command.target.get("timeline")
        timeline = None
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
            if timeline is None:
                return BridgeResult.failure(
                    command.request_id,
                    "object_not_found",
                    f"Timeline '{timeline_name}' was not found.",
                    meta={"bridge": self.adapter_name},
                )
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")
            if timeline is None:
                timeline = self._create_auto_timeline(current_project)
                if timeline is None:
                    return BridgeResult.failure(
                        command.request_id,
                        "execution_failure",
                        "Resolve could not create an automatic timeline for append.",
                        meta={"bridge": self.adapter_name},
                    )

        media_pool = self._media_pool(current_project)
        appended = False
        if media_pool is not None:
            self._safe_call(current_project, "SetCurrentTimeline", timeline)
            appended = bool(self._safe_call(media_pool, "AppendToTimeline", resolved_clips))

        if not appended:
            return BridgeResult.failure(
                command.request_id,
                "execution_failure",
                "Resolve failed to append the requested clips.",
                meta={"bridge": self.adapter_name},
            )

        payload = ResolveTimelineAppendClipsData(
            timeline=self._timeline_summary(current_project, timeline),
            appended=True,
            count=len(resolved_clips),
            clip_names=[str(name) for name in clip_names],
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def _handle_timeline_items_list(self, command: BridgeCommand, resolve: Any) -> BridgeResult:
        current_project = self._current_project(resolve)
        if current_project is None:
            return BridgeResult.failure(
                command.request_id,
                "no_project_open",
                "No current project is open in Resolve.",
                meta={"bridge": self.adapter_name},
            )

        timeline_name = command.target.get("timeline")
        timeline = (
            self._resolve_timeline_by_name(current_project, str(timeline_name))
            if timeline_name
            else self._safe_call(current_project, "GetCurrentTimeline")
        )
        if timeline is None:
            category = "object_not_found" if timeline_name else "no_current_timeline"
            message = (
                f"Timeline '{timeline_name}' was not found."
                if timeline_name
                else "No current timeline is active in Resolve."
            )
            return BridgeResult.failure(
                command.request_id,
                category,
                message,
                meta={"bridge": self.adapter_name},
            )

        tracks: list[ResolveTimelineTrackSummary] = []
        for track_type in ("video", "audio"):
            track_count = self._safe_call(timeline, "GetTrackCount", track_type) or 0
            for track_index in range(1, int(track_count) + 1):
                items = self._safe_call(timeline, "GetItemListInTrack", track_type, track_index)
                if not isinstance(items, list):
                    items = []
                tracks.append(
                    ResolveTimelineTrackSummary(
                        track_type=track_type,
                        track_index=track_index,
                        items=[
                            ResolveTimelineItemSummary(
                                item_index=item_index,
                                name=self._timeline_item_name(item) or f"{track_type} item {item_index}",
                                start_frame=self._timeline_item_frame(item, "GetStart"),
                                end_frame=self._timeline_item_frame(item, "GetEnd"),
                            )
                            for item_index, item in enumerate(items)
                        ],
                    )
                )

        payload = ResolveTimelineItemsListData(
            project=ResolveProjectStatus(open=True, name=self._safe_call(current_project, "GetName")),
            timeline=self._timeline_summary(current_project, timeline),
            tracks=tracks,
        )
        return BridgeResult.success(
            command.request_id,
            payload.model_dump(mode="json"),
            meta={"bridge": self.adapter_name},
        )

    def run_forever(self) -> None:
        while True:
            self.process_next_request_once()
            time.sleep(self.settings.bridge_poll_interval_ms / 1000.0)

    @staticmethod
    def _safe_call(obj: Any, method_name: str, *args: Any) -> Any | None:
        if obj is None:
            return None
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception:
            return None

    def _current_project(self, resolve: Any) -> Any | None:
        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return None
        return self._safe_call(project_manager, "GetCurrentProject")

    def _list_project_names(self, project_manager: Any) -> list[str]:
        if project_manager is None:
            return []

        project_names = self._safe_call(project_manager, "GetProjectListInCurrentFolder")
        if isinstance(project_names, list):
            return [str(name) for name in project_names]

        current_folder = self._safe_call(project_manager, "GetCurrentFolder")
        if current_folder is None:
            return []

        names = self._safe_call(current_folder, "GetProjectList")
        if isinstance(names, list):
            return [str(name) for name in names]
        return []

    def _timeline_summary(self, project: Any, timeline: Any) -> ResolveTimelineSummary:
        return ResolveTimelineSummary(
            index=self._timeline_index(project, timeline),
            name=self._safe_call(timeline, "GetName") or "Timeline",
        )

    def _timeline_index(self, project: Any, timeline: Any) -> int:
        timeline_count = self._safe_call(project, "GetTimelineCount") or 0
        timeline_name = self._safe_call(timeline, "GetName")
        for index in range(1, int(timeline_count) + 1):
            candidate = self._safe_call(project, "GetTimelineByIndex", index)
            if candidate is timeline:
                return index
            if timeline_name and self._safe_call(candidate, "GetName") == timeline_name:
                return index
        return 1

    def _resolve_timeline_by_name(self, project: Any, timeline_name: str) -> Any | None:
        timeline_count = self._safe_call(project, "GetTimelineCount") or 0
        for index in range(1, int(timeline_count) + 1):
            timeline = self._safe_call(project, "GetTimelineByIndex", index)
            if self._safe_call(timeline, "GetName") == timeline_name:
                return timeline
        return None

    def _media_pool(self, project: Any) -> Any | None:
        return self._safe_call(project, "GetMediaPool")

    def _current_media_pool_folder(self, project: Any) -> Any | None:
        media_pool = self._media_pool(project)
        if media_pool is None:
            return None
        return self._safe_call(media_pool, "GetCurrentFolder")

    def _list_media_subfolders(self, folder: Any) -> list[Any]:
        subfolders = self._safe_call(folder, "GetSubFolderList")
        if isinstance(subfolders, list):
            return subfolders
        subfolders = self._safe_call(folder, "GetSubFolders")
        if isinstance(subfolders, list):
            return subfolders
        if isinstance(subfolders, dict):
            return list(subfolders.values())
        return []

    def _list_media_clips(self, folder: Any) -> list[Any]:
        clips = self._safe_call(folder, "GetClipList")
        if isinstance(clips, list):
            return [clip for clip in clips if self._is_media_pool_clip(clip)]
        clips = self._safe_call(folder, "GetClips")
        if isinstance(clips, list):
            return [clip for clip in clips if self._is_media_pool_clip(clip)]
        if isinstance(clips, dict):
            return [clip for clip in clips.values() if self._is_media_pool_clip(clip)]
        return []

    def _clip_name(self, clip: Any) -> str | None:
        name = self._safe_call(clip, "GetName")
        if name:
            return str(name)
        properties = self._safe_call(clip, "GetClipProperty")
        if isinstance(properties, dict):
            clip_name = properties.get("Clip Name") or properties.get("File Name")
            if clip_name:
                return str(clip_name)
        return None

    def _clip_properties(self, clip: Any) -> dict[str, Any]:
        properties = self._safe_call(clip, "GetClipProperty")
        return properties if isinstance(properties, dict) else {}

    def _is_media_pool_clip(self, clip: Any) -> bool:
        properties = self._clip_properties(clip)
        if not properties:
            return True

        type_markers = (
            properties.get("Type"),
            properties.get("Clip Type"),
            properties.get("TypeName"),
        )
        normalized_markers = {
            str(value).strip().lower() for value in type_markers if value is not None
        }
        if "timeline" in normalized_markers:
            return False

        media_markers = (
            "File Path",
            "Video Codec",
            "Audio Codec",
            "Frames",
            "Duration",
        )
        return any(properties.get(key) not in (None, "") for key in media_markers)

    def _resolve_clip_by_name(self, folder: Any, clip_name: str) -> Any | BridgeResult:
        matches = [clip for clip in self._list_media_clips(folder) if self._clip_name(clip) == clip_name]
        if not matches:
            return BridgeResult.failure(
                "pending-request-id",
                "object_not_found",
                f"Clip '{clip_name}' was not found in the current media pool folder.",
                meta={"bridge": self.adapter_name},
            )
        if len(matches) > 1:
            return BridgeResult.failure(
                "pending-request-id",
                "validation_error",
                f"Clip name '{clip_name}' is ambiguous in the current media pool folder.",
                details={"clip_name": clip_name, "match_count": len(matches)},
                meta={"bridge": self.adapter_name},
            )
        return matches[0]

    def _create_auto_timeline(self, project: Any) -> Any | None:
        media_pool = self._media_pool(project)
        if media_pool is None:
            return None

        suffix = 1
        while True:
            timeline_name = "Imported Timeline" if suffix == 1 else f"Imported Timeline {suffix}"
            if self._resolve_timeline_by_name(project, timeline_name) is None:
                timeline = self._safe_call(media_pool, "CreateEmptyTimeline", timeline_name)
                if timeline is None:
                    timeline = self._resolve_timeline_by_name(project, timeline_name)
                return timeline
            suffix += 1

    def _timeline_item_name(self, item: Any) -> str | None:
        name = self._safe_call(item, "GetName")
        if name:
            return str(name)
        media_pool_item = self._safe_call(item, "GetMediaPoolItem")
        return self._clip_name(media_pool_item)

    def _timeline_item_frame(self, item: Any, method_name: str) -> int | None:
        value = self._safe_call(item, method_name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
