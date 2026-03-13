"""Backend orchestration and command normalization."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from davinci_free_mcp.bridge.base import Bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import (
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
    ResolveProjectListData,
    ResolveProjectOpenData,
    ResolveTimelineAppendClipsData,
    ResolveTimelineClipsPlaceData,
    ResolveTimelineItemDeleteData,
    ResolveTimelineItemInspectData,
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
)

PayloadModelT = TypeVar("PayloadModelT", bound=BaseModel)


class ResolveBackendService:
    """Backend orchestrator for low-level Resolve Free commands."""

    def __init__(self, bridge: Bridge, settings: AppSettings | None = None) -> None:
        self.bridge = bridge
        self.settings = settings or AppSettings()

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
