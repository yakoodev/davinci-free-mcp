"""Backend orchestration and command normalization."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from davinci_free_mcp.backend.media_analysis import LocalMediaAnalyzer
from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import (
    AudioEventsData,
    AudioProbeData,
    AudioTranscriptionData,
    BridgeCommand,
    BridgeError,
    BridgeResult,
    ResolveHealthData,
    ResolveMarkerDeleteData,
    ResolveMarkerInspectData,
    ResolveMarkerListData,
    ResolveMarkerRangeListData,
    ResolveMediaClipInspectData,
    ResolveMediaClipInspectPathData,
    ResolveMediaImportData,
    ResolveMediaPoolFolderRecursiveData,
    ResolveMediaPoolFolderStateData,
    ResolveMediaPoolListData,
    ResolveMarkerAddData,
    ResolveProjectCurrentData,
    ResolveProjectManagerFolderListData,
    ResolveProjectManagerFolderStateData,
    ResolveProjectListData,
    ResolveProjectOpenData,
    ResolveTimelineAppendClipsData,
    ResolveTimelineBuildFromPathsData,
    ResolveTimelineClipsPlaceData,
    ResolveTimelineItemDeleteData,
    ResolveTimelineItemInspectData,
    ResolveTimelineItemMoveData,
    ResolveTimelineCreateEmptyData,
    ResolveTimelineCreateFromClipsData,
    ResolveTimelinePlacedItemData,
    ResolveTimelineCurrentData,
    ResolveTimelineInspectData,
    ResolveTimelineItemsListData,
    ResolveTimelineTrackInspectData,
    ResolveTimelineTrackItemsData,
    ResolveTimelineListData,
    ResolveTimelineSetCurrentData,
    ToolResultEnvelope,
    VideoProbeData,
    VideoSegmentationData,
    VideoSegmentScreenshotsData,
    VideoShotsData,
)

PayloadModelT = TypeVar("PayloadModelT", bound=BaseModel)


class ResolveBackendService:
    """Backend orchestrator for low-level Resolve Free commands."""

    def __init__(self, bridge: Bridge, settings: AppSettings | None = None) -> None:
        self.bridge = bridge
        self.settings = settings or AppSettings()
        self.media_analyzer = LocalMediaAnalyzer(self.settings)

    def resolve_health(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "resolve_health",
            ResolveHealthData,
            timeout_ms=timeout_ms,
        )

    def project_current(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_current",
            ResolveProjectCurrentData,
            timeout_ms=timeout_ms,
        )

    def project_list(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_list",
            ResolveProjectListData,
            timeout_ms=timeout_ms,
        )

    def project_manager_folder_list(
        self,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_manager_folder_list",
            ResolveProjectManagerFolderListData,
            timeout_ms=timeout_ms,
        )

    def project_manager_folder_open(
        self,
        name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_manager_folder_open",
            ResolveProjectManagerFolderStateData,
            payload={"name": name},
            timeout_ms=timeout_ms,
        )

    def project_manager_folder_up(
        self,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_manager_folder_up",
            ResolveProjectManagerFolderStateData,
            timeout_ms=timeout_ms,
        )

    def project_manager_folder_path(
        self,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_manager_folder_path",
            ResolveProjectManagerFolderStateData,
            timeout_ms=timeout_ms,
        )

    def project_open(
        self,
        project_name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "project_open",
            ResolveProjectOpenData,
            payload={"project_name": project_name},
            timeout_ms=timeout_ms,
        )

    def timeline_list(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_list",
            ResolveTimelineListData,
            timeout_ms=timeout_ms,
        )

    def timeline_current(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_current",
            ResolveTimelineCurrentData,
            timeout_ms=timeout_ms,
        )

    def timeline_create_empty(
        self,
        name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_create_empty",
            ResolveTimelineCreateEmptyData,
            payload={"name": name},
            timeout_ms=timeout_ms,
        )

    def timeline_set_current(
        self,
        name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_set_current",
            ResolveTimelineSetCurrentData,
            payload={"name": name},
            timeout_ms=timeout_ms,
        )

    def media_pool_list(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_list",
            ResolveMediaPoolListData,
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_open(
        self,
        name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_folder_open",
            ResolveMediaPoolListData,
            payload={"name": name},
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_create(
        self,
        name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_folder_create",
            ResolveMediaPoolListData,
            payload={"name": name},
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_up(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_folder_up",
            ResolveMediaPoolListData,
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_root(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_folder_root",
            ResolveMediaPoolFolderStateData,
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_path(self, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_folder_path",
            ResolveMediaPoolFolderStateData,
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_list_recursive(
        self,
        max_depth: int | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        payload = {}
        if max_depth is not None:
            payload["max_depth"] = max_depth
        return self._invoke_command(
            "media_pool_folder_list_recursive",
            ResolveMediaPoolFolderRecursiveData,
            payload=payload,
            timeout_ms=timeout_ms,
        )

    def media_pool_folder_open_path(
        self,
        path: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_pool_folder_open_path",
            ResolveMediaPoolFolderStateData,
            payload={"path": path},
            timeout_ms=timeout_ms,
        )

    def media_import(
        self,
        paths: list[str],
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_import",
            ResolveMediaImportData,
            payload={"paths": paths},
            timeout_ms=timeout_ms,
        )

    def timeline_append_clips(
        self,
        clip_names: list[str],
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_append_clips",
            ResolveTimelineAppendClipsData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={"clip_names": clip_names},
            timeout_ms=timeout_ms,
        )

    def timeline_clips_place(
        self,
        placements: list[dict[str, object]],
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_clips_place",
            ResolveTimelineClipsPlaceData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={"placements": placements},
            timeout_ms=timeout_ms,
        )

    def timeline_create_from_clips(
        self,
        name: str,
        clip_names: list[str],
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_create_from_clips",
            ResolveTimelineCreateFromClipsData,
            payload={"name": name, "clip_names": clip_names},
            timeout_ms=timeout_ms,
        )

    def timeline_build_from_paths(
        self,
        name: str,
        paths: list[str],
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_build_from_paths",
            ResolveTimelineBuildFromPathsData,
            payload={"name": name, "paths": paths},
            timeout_ms=timeout_ms,
        )

    def timeline_items_list(
        self,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_items_list",
            ResolveTimelineItemsListData,
            target={"timeline": timeline_name} if timeline_name else {},
            timeout_ms=timeout_ms,
        )

    def timeline_track_items_list(
        self,
        track_type: str,
        track_index: int,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_track_items_list",
            ResolveTimelineTrackItemsData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={"track_type": track_type, "track_index": track_index},
            timeout_ms=timeout_ms,
        )

    def timeline_track_inspect(
        self,
        track_type: str,
        track_index: int,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_track_inspect",
            ResolveTimelineTrackInspectData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={"track_type": track_type, "track_index": track_index},
            timeout_ms=timeout_ms,
        )

    def timeline_item_inspect(
        self,
        track_type: str,
        track_index: int,
        item_index: int,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_item_inspect",
            ResolveTimelineItemInspectData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={
                "track_type": track_type,
                "track_index": track_index,
                "item_index": item_index,
            },
            timeout_ms=timeout_ms,
        )

    def timeline_item_delete(
        self,
        track_type: str,
        track_index: int,
        item_index: int,
        ripple: bool = False,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_item_delete",
            ResolveTimelineItemDeleteData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={
                "track_type": track_type,
                "track_index": track_index,
                "item_index": item_index,
                "ripple": ripple,
            },
            timeout_ms=timeout_ms,
        )

    def timeline_item_move(
        self,
        track_type: str,
        track_index: int,
        item_index: int,
        record_frame: int,
        target_track_type: str | None = None,
        target_track_index: int | None = None,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        payload: dict[str, object] = {
            "track_type": track_type,
            "track_index": track_index,
            "item_index": item_index,
            "record_frame": record_frame,
        }
        if target_track_type is not None:
            payload["target_track_type"] = target_track_type
        if target_track_index is not None:
            payload["target_track_index"] = target_track_index
        return self._invoke_command(
            "timeline_item_move",
            ResolveTimelineItemMoveData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload=payload,
            timeout_ms=timeout_ms,
        )

    def timeline_inspect(
        self,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "timeline_inspect",
            ResolveTimelineInspectData,
            target={"timeline": timeline_name} if timeline_name else {},
            timeout_ms=timeout_ms,
        )

    def marker_add(
        self,
        frame: int,
        name: str,
        timeline_name: str | None = None,
        note: str | None = None,
        color: str | None = None,
        duration: int = 1,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "marker_add",
            ResolveMarkerAddData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={
                "frame": frame,
                "name": name,
                "note": note,
                "color": color,
                "duration": duration,
            },
            timeout_ms=timeout_ms,
        )

    def marker_list(
        self,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "marker_list",
            ResolveMarkerListData,
            target={"timeline": timeline_name} if timeline_name else {},
            timeout_ms=timeout_ms,
        )

    def marker_inspect(
        self,
        frame: int,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "marker_inspect",
            ResolveMarkerInspectData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={"frame": frame},
            timeout_ms=timeout_ms,
        )

    def marker_list_range(
        self,
        frame_from: int | None = None,
        frame_to: int | None = None,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        payload = {}
        if frame_from is not None:
            payload["frame_from"] = frame_from
        if frame_to is not None:
            payload["frame_to"] = frame_to
        return self._invoke_command(
            "marker_list_range",
            ResolveMarkerRangeListData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload=payload,
            timeout_ms=timeout_ms,
        )

    def marker_delete(
        self,
        frame: int,
        timeline_name: str | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "marker_delete",
            ResolveMarkerDeleteData,
            target={"timeline": timeline_name} if timeline_name else {},
            payload={"frame": frame},
            timeout_ms=timeout_ms,
        )

    def media_clip_inspect(
        self,
        clip_name: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_clip_inspect",
            ResolveMediaClipInspectData,
            payload={"clip_name": clip_name},
            timeout_ms=timeout_ms,
        )

    def media_clip_inspect_path(
        self,
        path: str,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_command(
            "media_clip_inspect_path",
            ResolveMediaClipInspectPathData,
            payload={"path": path},
            timeout_ms=timeout_ms,
        )

    def audio_probe(self, path: str, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_local_analysis("audio_probe", AudioProbeData, path=path)

    def audio_transcribe_segments(
        self,
        path: str,
        language: str | None = None,
        max_segment_sec: float = 15,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "audio_transcribe_segments",
            AudioTranscriptionData,
            path=path,
            language=language,
            max_segment_sec=max_segment_sec,
        )

    def audio_detect_events(
        self,
        path: str,
        min_silence_sec: float = 0.7,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "audio_detect_events",
            AudioEventsData,
            path=path,
            min_silence_sec=min_silence_sec,
        )

    def video_probe(self, path: str, timeout_ms: int | None = None) -> ToolResultEnvelope:
        return self._invoke_local_analysis("video_probe", VideoProbeData, path=path)

    def video_detect_shots(
        self,
        path: str,
        cut_threshold: float = 0.35,
        min_shot_sec: float = 1.0,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "video_detect_shots",
            VideoShotsData,
            path=path,
            cut_threshold=cut_threshold,
            min_shot_sec=min_shot_sec,
        )

    def video_extract_segment_screenshots(
        self,
        path: str,
        segments: list[dict[str, object]],
        screenshots_per_segment: int = 1,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "video_extract_segment_screenshots",
            VideoSegmentScreenshotsData,
            path=path,
            segments=segments,
            screenshots_per_segment=screenshots_per_segment,
        )

    def video_segment_from_speech(
        self,
        path: str,
        language: str | None = None,
        max_segment_sec: float = 15,
        screenshots_per_segment: int = 1,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "video_segment_from_speech",
            VideoSegmentationData,
            path=path,
            language=language,
            max_segment_sec=max_segment_sec,
            screenshots_per_segment=screenshots_per_segment,
        )

    def video_segment_visual(
        self,
        path: str,
        segment_mode: str = "shots",
        window_sec: float = 8,
        screenshots_per_segment: int = 1,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "video_segment_visual",
            VideoSegmentationData,
            path=path,
            segment_mode=segment_mode,
            window_sec=window_sec,
            screenshots_per_segment=screenshots_per_segment,
        )

    def video_segment_audio_visual(
        self,
        path: str,
        min_silence_sec: float = 0.7,
        screenshots_per_segment: int = 1,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        return self._invoke_local_analysis(
            "video_segment_audio_visual",
            VideoSegmentationData,
            path=path,
            min_silence_sec=min_silence_sec,
            screenshots_per_segment=screenshots_per_segment,
        )

    def _invoke_local_analysis(
        self,
        method_name: str,
        payload_model: type[PayloadModelT],
        **kwargs: object,
    ) -> ToolResultEnvelope:
        try:
            if "screenshots_per_segment" in kwargs and int(kwargs["screenshots_per_segment"]) <= 0:
                raise ValueError("screenshots_per_segment must be greater than 0.")
            analyzer_method = getattr(self.media_analyzer, method_name)
            result = analyzer_method(**kwargs)
            payload = payload_model.model_validate(result["data"])
        except FileNotFoundError as exc:
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="object_not_found",
                    message=str(exc),
                ),
            )
        except ValueError as exc:
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="validation_error",
                    message=str(exc),
                ),
            )
        except Exception as exc:
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="execution_failure",
                    message="Local media analysis failed.",
                    details={
                        "exception": str(exc),
                        "method_name": method_name,
                    },
                ),
            )
        return ToolResultEnvelope(
            success=True,
            data=(
                result["data"]
                if method_name in {"audio_transcribe_segments", "video_segment_from_speech"}
                else payload.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            ),
            warnings=result.get("warnings", []),
            meta={"local_analysis": True, "tool_name": method_name},
        )

    def _invoke_command(
        self,
        command_name: str,
        payload_model: type[PayloadModelT],
        *,
        target: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
        timeout_ms: int | None = None,
    ) -> ToolResultEnvelope:
        bridge_status = self.bridge.health_check()
        if not bridge_status.get("available", False):
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="bridge_unavailable",
                    message="Bridge health check failed before command submission.",
                    details={"bridge_status": bridge_status},
                ),
                meta={"bridge_status": bridge_status},
            )

        effective_timeout = timeout_ms or self.settings.default_timeout_ms
        command = BridgeCommand(
            command=command_name,
            target=target or {},
            payload=payload or {},
            timeout_ms=effective_timeout,
            context={"tool_name": command_name, "caller": "backend"},
        )
        self.bridge.submit_command(command)
        result = self.bridge.await_result(command.request_id, effective_timeout)
        return self._normalize_result(result, bridge_status, payload_model)

    def _normalize_result(
        self,
        result: BridgeResult,
        bridge_status: dict[str, object],
        payload_model: type[PayloadModelT],
    ) -> ToolResultEnvelope:
        if not result.ok:
            return ToolResultEnvelope(
                success=False,
                error=result.error,
                warnings=result.warnings,
                meta={"bridge_status": bridge_status, **result.meta},
            )

        try:
            payload = payload_model.model_validate(result.data or {})
        except Exception as exc:
            return ToolResultEnvelope(
                success=False,
                error=BridgeError(
                    category="execution_failure",
                    message="Executor returned an invalid payload.",
                    details={
                        "exception": str(exc),
                        "expected_model": payload_model.__name__,
                    },
                ),
                warnings=result.warnings,
                meta={"bridge_status": bridge_status, **result.meta},
            )

        return ToolResultEnvelope(
            success=True,
            data=payload.model_dump(mode="json"),
            warnings=result.warnings,
            meta={"bridge_status": bridge_status, **result.meta},
        )
