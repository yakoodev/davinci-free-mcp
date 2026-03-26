"""Shared Resolve command execution core.

This module must stay stdlib-only and Python-3.6-compatible because the
installer embeds its source into the Resolve bootstrap script.
"""

import copy
import os
import tempfile


DFMCP_ANIMATION_COMP_NAME = "DFMCP Anim"
DFMCP_ANIMATION_COMP_PREFIX = "DFMCP "
SUPPORTED_TIMELINE_ITEM_PROPERTIES = {
    "Opacity": "float",
    "ZoomX": "float",
    "ZoomY": "float",
    "Pan": "float",
    "Tilt": "float",
    "RotationAngle": "float",
    "CompositeMode": "int",
    "CropLeft": "float",
    "CropRight": "float",
    "CropTop": "float",
    "CropBottom": "float",
}
SUPPORTED_ANIMATION_PRESETS = (
    "fade_in",
    "fade_out",
    "fade_in_out",
    "zoom_in_soft",
    "zoom_out_soft",
    "slide_up_fade",
    "slide_down_fade",
    "slide_left_fade",
    "slide_right_fade",
)
SUPPORTED_ANIMATION_DIRECTIONS = ("up", "down", "left", "right", "in", "out")
SUPPORTED_ANIMATION_EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out")
FALLBACK_FADE_TEMPLATE = """{
Tools = ordered() {
    MediaIn1 = MediaIn { Inputs = {}, ViewInfo = OperatorInfo { Pos = { 0, 0 } } },
    Background1 = Background { Inputs = { GlobalOut = Input { Value = __DURATION__ } }, ViewInfo = OperatorInfo { Pos = { 110, 0 } } },
    Merge1 = Merge {
        Inputs = {
            Background = Input { SourceOp = "Background1", Source = "Output" },
            Foreground = Input { SourceOp = "MediaIn1", Source = "Output" },
            Blend = Input { SourceOp = "BlendSpline", Source = "Value" }
        },
        ViewInfo = OperatorInfo { Pos = { 220, 0 } }
    },
    MediaOut1 = MediaOut { Inputs = { Input = Input { SourceOp = "Merge1", Source = "Output" } }, ViewInfo = OperatorInfo { Pos = { 330, 0 } } },
    BlendSpline = BezierSpline {
        SplineColor = { Red = 255, Green = 196, Blue = 0 },
        NameSet = true,
        KeyFrames = {
            [0] = { __START_VALUE__ },
            [__MID_DURATION__] = { __END_VALUE__ }
        }
    }
}
}"""
FALLBACK_TRANSFORM_TEMPLATE = """{
Tools = ordered() {
    MediaIn1 = MediaIn { Inputs = {}, ViewInfo = OperatorInfo { Pos = { 0, 0 } } },
    Background1 = Background { Inputs = { GlobalOut = Input { Value = __DURATION__ } }, ViewInfo = OperatorInfo { Pos = { 110, 0 } } },
    Transform1 = Transform {
        Inputs = {
            Input = Input { SourceOp = "MediaIn1", Source = "Output" },
            Size = Input { SourceOp = "SizeSpline", Source = "Value" },
            Center = Input { Value = { __CENTER_X__, __CENTER_Y__ } }
        },
        ViewInfo = OperatorInfo { Pos = { 220, 0 } }
    },
    Merge1 = Merge {
        Inputs = {
            Background = Input { SourceOp = "Background1", Source = "Output" },
            Foreground = Input { SourceOp = "Transform1", Source = "Output" },
            Blend = Input { SourceOp = "BlendSpline", Source = "Value" }
        },
        ViewInfo = OperatorInfo { Pos = { 330, 0 } }
    },
    MediaOut1 = MediaOut { Inputs = { Input = Input { SourceOp = "Merge1", Source = "Output" } }, ViewInfo = OperatorInfo { Pos = { 440, 0 } } },
    BlendSpline = BezierSpline {
        SplineColor = { Red = 255, Green = 196, Blue = 0 },
        NameSet = true,
        KeyFrames = {
            [0] = { __START_OPACITY__ },
            [__MID_DURATION__] = { __END_OPACITY__ }
        }
    },
    SizeSpline = BezierSpline {
        SplineColor = { Red = 0, Green = 170, Blue = 255 },
        NameSet = true,
        KeyFrames = {
            [0] = { __START_SCALE__ },
            [__MID_DURATION__] = { __END_SCALE__ }
        }
    }
}
}"""


def execute_resolve_command(command, resolve_provider, adapter_name="file_queue"):
    """Execute a bridge command against a Resolve provider and return a wire result."""

    core = ResolveCommandCore(resolve_provider, adapter_name=adapter_name)
    return core.execute(command)


class ResolveCommandCore(object):
    """Transport-agnostic command registry and Resolve helpers."""

    def __init__(self, resolve_provider, adapter_name="file_queue"):
        self.resolve_provider = resolve_provider
        self.adapter_name = adapter_name
        self._handlers = {
            "resolve_health": self._handle_resolve_health,
            "project_current": self._handle_project_current,
            "project_list": self._handle_project_list,
            "project_manager_folder_list": self._handle_project_manager_folder_list,
            "project_manager_folder_open": self._handle_project_manager_folder_open,
            "project_manager_folder_up": self._handle_project_manager_folder_up,
            "project_manager_folder_path": self._handle_project_manager_folder_path,
            "project_open": self._handle_project_open,
            "timeline_list": self._handle_timeline_list,
            "timeline_current": self._handle_timeline_current,
            "timeline_create_empty": self._handle_timeline_create_empty,
            "timeline_set_current": self._handle_timeline_set_current,
            "media_pool_list": self._handle_media_pool_list,
            "media_pool_folder_open": self._handle_media_pool_folder_open,
            "media_pool_folder_create": self._handle_media_pool_folder_create,
            "media_pool_folder_up": self._handle_media_pool_folder_up,
            "media_pool_folder_root": self._handle_media_pool_folder_root,
            "media_pool_folder_path": self._handle_media_pool_folder_path,
            "media_pool_folder_list_recursive": self._handle_media_pool_folder_list_recursive,
            "media_pool_folder_open_path": self._handle_media_pool_folder_open_path,
            "media_clip_inspect": self._handle_media_clip_inspect,
            "media_clip_inspect_path": self._handle_media_clip_inspect_path,
            "media_import": self._handle_media_import,
            "timeline_append_clips": self._handle_timeline_append_clips,
            "timeline_clips_place": self._handle_timeline_clips_place,
            "timeline_create_from_clips": self._handle_timeline_create_from_clips,
            "timeline_build_from_paths": self._handle_timeline_build_from_paths,
            "timeline_items_list": self._handle_timeline_items_list,
            "timeline_track_items_list": self._handle_timeline_track_items_list,
            "timeline_track_inspect": self._handle_timeline_track_inspect,
            "timeline_item_inspect": self._handle_timeline_item_inspect,
            "timeline_item_delete": self._handle_timeline_item_delete,
            "timeline_item_properties_get": self._handle_timeline_item_properties_get,
            "timeline_item_properties_set": self._handle_timeline_item_properties_set,
            "timeline_item_animation_preset_apply": self._handle_timeline_item_animation_preset_apply,
            "timeline_item_animation_clear": self._handle_timeline_item_animation_clear,
            "timeline_item_move": self._handle_timeline_item_move,
            "timeline_item_split": self._handle_timeline_item_split,
            "timeline_item_set_source_range": self._handle_timeline_item_set_source_range,
            "timeline_gap_close": self._handle_timeline_gap_close,
            "timeline_remove_gaps": self._handle_timeline_remove_gaps,
            "timeline_insert_gap": self._handle_timeline_insert_gap,
            "timeline_inspect": self._handle_timeline_inspect,
            "marker_add": self._handle_marker_add,
            "marker_list": self._handle_marker_list,
            "marker_inspect": self._handle_marker_inspect,
            "marker_list_range": self._handle_marker_list_range,
            "marker_delete": self._handle_marker_delete,
        }

    def execute(self, command):
        normalized = self._normalize_command(command)
        request_id = normalized["request_id"]
        command_name = normalized["command"]
        handler = self._handlers.get(command_name)
        if handler is None:
            return self._failure(
                request_id,
                "unsupported_command",
                "Unsupported command '%s' for executor." % command_name,
            )

        resolve = self.resolve_provider()
        if resolve is None:
            return self._failure(
                request_id,
                "resolve_not_ready",
                "Resolve handle is not available in the embedded environment.",
            )

        return handler(normalized, resolve)

    def _normalize_command(self, command):
        payload = self._extract_mapping(command, "payload")
        target = self._extract_mapping(command, "target")
        context = self._extract_mapping(command, "context")

        request_id = self._extract_value(command, "request_id") or "unknown"
        command_name = self._extract_value(command, "command") or ""
        timeout_ms = self._extract_value(command, "timeout_ms")
        if timeout_ms is None:
            timeout_ms = 5000

        return {
            "request_id": str(request_id),
            "command": str(command_name),
            "payload": payload,
            "target": target,
            "context": context,
            "timeout_ms": timeout_ms,
        }

    @staticmethod
    def _extract_value(container, key):
        if isinstance(container, dict):
            return container.get(key)
        return getattr(container, key, None)

    def _extract_mapping(self, container, key):
        value = self._extract_value(container, key)
        if isinstance(value, dict):
            return copy.deepcopy(value)
        return {}

    def _success(self, request_id, data=None, warnings=None, meta=None):
        return {
            "request_id": request_id,
            "ok": True,
            "data": data or {},
            "error": None,
            "warnings": warnings or [],
            "meta": meta or {"bridge": self.adapter_name},
        }

    def _failure(
        self,
        request_id,
        category,
        message,
        details=None,
        warnings=None,
        meta=None,
    ):
        return {
            "request_id": request_id,
            "ok": False,
            "data": None,
            "error": {
                "category": category,
                "message": message,
                "details": details or {},
            },
            "warnings": warnings or [],
            "meta": meta or {"bridge": self.adapter_name},
        }

    def _handle_resolve_health(self, command, resolve):
        current_project = self._current_project(resolve)
        warnings = []
        if current_project is None:
            warnings.append("no_project_open")

        return self._success(
            command["request_id"],
            data={
                "bridge": {"available": True, "adapter": self.adapter_name},
                "executor": {"running": True},
                "resolve": {
                    "connected": True,
                    "product_name": self._safe_call(resolve, "GetProductName"),
                    "version": self._safe_call(resolve, "GetVersionString"),
                },
                "project": {
                    "open": current_project is not None,
                    "name": self._safe_call(current_project, "GetName"),
                },
            },
            warnings=warnings,
        )

    def _handle_project_current(self, command, resolve):
        current_project = self._current_project(resolve)
        warnings = []
        if current_project is None:
            warnings.append("no_project_open")

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": current_project is not None,
                    "name": self._safe_call(current_project, "GetName"),
                }
            },
            warnings=warnings,
        )

    def _handle_project_list(self, command, resolve):
        project_manager = self._safe_call(resolve, "GetProjectManager")
        project_names = self._list_project_names(project_manager)
        return self._success(
            command["request_id"],
            data={"projects": [{"name": name} for name in project_names]},
        )

    def _handle_project_manager_folder_list(self, command, resolve):
        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve project manager is not available.",
            )

        return self._success(
            command["request_id"],
            data=self._project_manager_folder_listing(project_manager),
        )

    def _handle_project_manager_folder_open(self, command, resolve):
        folder_name = str(command["payload"].get("name") or "").strip()
        if not folder_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Project manager folder name is required.",
            )

        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve project manager is not available.",
            )

        folder_names = self._list_project_manager_folder_names(project_manager)
        if folder_name not in folder_names:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Project manager folder '%s' was not found in the current folder."
                % folder_name,
                details={"folder_name": folder_name},
            )

        opened = bool(self._safe_call(project_manager, "OpenFolder", folder_name))
        current_name = self._project_manager_current_folder_name(project_manager)
        if not opened or current_name != folder_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to project manager folder '%s'." % folder_name,
                details={"folder_name": folder_name, "current_folder_name": current_name},
            )

        return self._success(
            command["request_id"],
            data=self._project_manager_folder_state(project_manager),
        )

    def _handle_project_manager_folder_up(self, command, resolve):
        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve project manager is not available.",
            )

        current_path = self._project_manager_folder_path(project_manager)
        if len(current_path) <= 1:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Current project manager folder is already the root folder.",
            )

        parent_path = current_path[:-1]
        moved = bool(self._safe_call(project_manager, "GotoParentFolder"))
        if not moved:
            moved = self._project_manager_open_path_from_root(project_manager, parent_path)
        current_name = self._project_manager_current_folder_name(project_manager)
        expected_name = parent_path[-1]
        if not moved or current_name != expected_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to the parent project manager folder.",
                details={"current_folder_name": current_name, "expected_folder_name": expected_name},
            )

        return self._success(
            command["request_id"],
            data=self._project_manager_folder_state(project_manager),
        )

    def _handle_project_manager_folder_path(self, command, resolve):
        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve project manager is not available.",
            )

        return self._success(
            command["request_id"],
            data=self._project_manager_folder_state(project_manager),
        )

    def _handle_project_open(self, command, resolve):
        project_name = str(command["payload"].get("project_name") or "").strip()
        if not project_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Project name is required.",
            )

        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve project manager is not available.",
            )

        opened_project = self._safe_call(project_manager, "LoadProject", project_name)
        if opened_project is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Project '%s' was not found or could not be opened." % project_name,
                details={"project_name": project_name},
            )

        current_project = self._current_project(resolve)
        current_project_name = self._safe_call(current_project, "GetName")
        if current_project is None or current_project_name != project_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to project '%s'." % project_name,
                details={
                    "project_name": project_name,
                    "current_project_name": current_project_name,
                },
            )

        return self._success(
            command["request_id"],
            data={
                "opened": True,
                "project": {"open": True, "name": current_project_name},
            },
        )

    def _handle_timeline_list(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timelines = []
        timeline_count = self._safe_call(current_project, "GetTimelineCount") or 0
        for index in range(1, int(timeline_count) + 1):
            timeline = self._safe_call(current_project, "GetTimelineByIndex", index)
            if timeline is None:
                continue
            timelines.append(
                {
                    "index": index,
                    "name": self._safe_call(timeline, "GetName") or "Timeline %s" % index,
                }
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timelines": timelines,
            },
        )

    def _handle_timeline_current(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline = self._safe_call(current_project, "GetCurrentTimeline")
        if timeline is None:
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
            },
        )

    def _handle_timeline_create_empty(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = str(command["payload"].get("name") or "").strip()
        if not timeline_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Timeline name is required.",
            )

        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool is not available.",
            )

        created_timeline = self._safe_call(media_pool, "CreateEmptyTimeline", timeline_name)
        if created_timeline is None:
            created_timeline = self._resolve_timeline_by_name(current_project, timeline_name)

        if created_timeline is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not create timeline '%s'." % timeline_name,
            )

        return self._success(
            command["request_id"],
            data={
                "created": True,
                "timeline": self._timeline_summary(current_project, created_timeline),
            },
        )

    def _handle_timeline_set_current(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = str(command["payload"].get("name") or "").strip()
        if not timeline_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Timeline name is required.",
            )

        timeline = self._resolve_timeline_by_name(current_project, timeline_name)
        if timeline is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Timeline '%s' was not found." % timeline_name,
            )

        switched = bool(self._safe_call(current_project, "SetCurrentTimeline", timeline))
        active_timeline = self._safe_call(current_project, "GetCurrentTimeline")
        active_name = self._safe_call(active_timeline, "GetName")
        if not switched or active_timeline is None or active_name != timeline_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to timeline '%s'." % timeline_name,
                details={"timeline_name": timeline_name, "current_timeline_name": active_name},
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, active_timeline),
            },
        )

    def _handle_media_pool_list(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        current_folder = self._current_media_pool_folder(current_project)
        if current_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_listing(current_folder),
        )

    def _handle_media_pool_folder_open(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        folder_name = str(command["payload"].get("name") or "").strip()
        if not folder_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Media pool folder name is required.",
            )

        current_folder = self._current_media_pool_folder(current_project)
        if current_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        target_folder, error = self._resolve_media_subfolder_by_name(current_folder, folder_name)
        if error is not None:
            return self._failure(
                command["request_id"],
                error["category"],
                error["message"],
                details=error.get("details"),
            )

        media_pool = self._media_pool(current_project)
        switched = False
        if media_pool is not None:
            switched = bool(self._safe_call(media_pool, "SetCurrentFolder", target_folder))
        active_folder = self._current_media_pool_folder(current_project)
        active_name = self._safe_call(active_folder, "GetName")
        if not switched or active_folder is None or active_name != folder_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to media pool folder '%s'." % folder_name,
                details={"folder_name": folder_name, "current_folder_name": active_name},
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_listing(active_folder),
        )

    def _handle_media_pool_folder_create(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        folder_name = str(command["payload"].get("name") or "").strip()
        if not folder_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Media pool folder name is required.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        if media_pool is None or current_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        created_folder = self._safe_call(media_pool, "AddSubFolder", current_folder, folder_name)
        if created_folder is None:
            created_folder, error = self._resolve_media_subfolder_by_name(current_folder, folder_name)
            if error is not None:
                return self._failure(
                    command["request_id"],
                    "execution_failure",
                    "Resolve did not create media pool folder '%s'." % folder_name,
                )

        switched = bool(self._safe_call(media_pool, "SetCurrentFolder", created_folder))
        active_folder = self._current_media_pool_folder(current_project)
        active_name = self._safe_call(active_folder, "GetName")
        if not switched or active_folder is None or active_name != folder_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to media pool folder '%s'." % folder_name,
                details={"folder_name": folder_name, "current_folder_name": active_name},
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_listing(active_folder),
        )

    def _handle_media_pool_folder_up(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if media_pool is None or current_folder is None or root_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        parent_folder = self._find_parent_media_folder(root_folder, current_folder)
        if parent_folder is None:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Current media pool folder is already the root folder.",
            )

        switched = bool(self._safe_call(media_pool, "SetCurrentFolder", parent_folder))
        active_folder = self._current_media_pool_folder(current_project)
        active_name = self._safe_call(active_folder, "GetName")
        parent_name = self._safe_call(parent_folder, "GetName")
        if not switched or active_folder is None or active_name != parent_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to the parent media pool folder.",
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_listing(active_folder),
        )

    def _handle_media_pool_folder_root(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        media_pool = self._media_pool(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if media_pool is None or root_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        switched = bool(self._safe_call(media_pool, "SetCurrentFolder", root_folder))
        active_folder = self._current_media_pool_folder(current_project)
        active_name = self._safe_call(active_folder, "GetName")
        root_name = self._safe_call(root_folder, "GetName")
        if not switched or active_folder is None or active_name != root_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to the root media pool folder.",
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_state(root_folder, root_folder),
        )

    def _handle_media_pool_folder_path(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if current_folder is None or root_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_state(current_folder, root_folder),
        )

    def _handle_media_pool_folder_list_recursive(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if current_folder is None or root_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        max_depth = command["payload"].get("max_depth")
        if max_depth is not None:
            try:
                max_depth = int(max_depth)
            except (TypeError, ValueError):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Max depth must be an integer.",
                )
            if max_depth < 0:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Max depth must be zero or greater.",
                )

        return self._success(
            command["request_id"],
            data={
                "folder": {"name": self._safe_call(current_folder, "GetName") or "Current Folder"},
                "path": self._media_pool_folder_path(root_folder, current_folder),
                "max_depth": max_depth,
                "tree": self._media_pool_folder_tree(current_folder, max_depth=max_depth),
            },
        )

    def _handle_media_pool_folder_open_path(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        path_value = str(command["payload"].get("path") or "").strip()
        if not path_value:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Media pool folder path is required.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if media_pool is None or current_folder is None or root_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        target_folder, error = self._resolve_media_folder_by_path(
            root_folder,
            current_folder,
            path_value,
        )
        if error is not None:
            return self._failure(
                command["request_id"],
                error["category"],
                error["message"],
                details=error.get("details"),
            )

        switched = bool(self._safe_call(media_pool, "SetCurrentFolder", target_folder))
        active_folder = self._current_media_pool_folder(current_project)
        active_name = self._safe_call(active_folder, "GetName")
        target_name = self._safe_call(target_folder, "GetName")
        if not switched or active_folder is None or active_name != target_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to media pool folder path '%s'." % path_value,
                details={"path": path_value, "current_folder_name": active_name},
            )

        return self._success(
            command["request_id"],
            data=self._media_pool_folder_state(active_folder, root_folder),
        )

    def _handle_media_clip_inspect(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        clip_name = str(command["payload"].get("clip_name") or "").strip()
        if not clip_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Clip name is required.",
            )

        current_folder = self._current_media_pool_folder(current_project)
        if current_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        clip, error = self._resolve_clip_by_name(current_folder, clip_name)
        if error is not None:
            return self._failure(
                command["request_id"],
                error["category"],
                error["message"],
                details=error.get("details"),
            )

        return self._success(
            command["request_id"],
            data={
                "folder": {"name": self._safe_call(current_folder, "GetName") or "Current Folder"},
                "clip": {
                    "name": self._clip_name(clip) or clip_name,
                    "properties": self._clip_string_properties(clip),
                },
            },
        )

    def _handle_media_clip_inspect_path(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        path_value = str(command["payload"].get("path") or "").strip()
        if not path_value:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Clip path is required.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if media_pool is None or current_folder is None or root_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        normalized_path = str(path_value).replace("\\", "/")
        path_segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
        if not path_segments:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Clip path is required.",
            )

        clip_name = path_segments[-1]
        folder_segments = path_segments[:-1]
        if folder_segments:
            folder_path = ("/" if normalized_path.startswith("/") else "") + "/".join(folder_segments)
            target_folder, error = self._resolve_media_folder_by_path(
                root_folder,
                current_folder,
                folder_path,
            )
            if error is not None:
                return self._failure(
                    command["request_id"],
                    error["category"],
                    error["message"],
                    details=error.get("details"),
                )
        else:
            target_folder = root_folder if normalized_path.startswith("/") else current_folder

        clip, error = self._resolve_clip_by_name(target_folder, clip_name)
        if error is not None:
            details = dict(error.get("details") or {})
            details["path"] = path_value
            return self._failure(
                command["request_id"],
                error["category"],
                error["message"],
                details=details,
            )

        return self._success(
            command["request_id"],
            data={
                "folder": {"name": self._safe_call(target_folder, "GetName") or "Current Folder"},
                "path": self._media_pool_folder_path(root_folder, target_folder),
                "clip": {
                    "name": self._clip_name(clip) or clip_name,
                    "properties": self._clip_string_properties(clip),
                },
            },
        )

    def _handle_media_import(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        paths = command["payload"].get("paths")
        if not isinstance(paths, list) or not paths:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Import requires at least one path.",
            )

        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool is not available.",
            )

        imported_items_raw = self._safe_call(media_pool, "ImportMedia", paths)
        if not isinstance(imported_items_raw, list):
            imported_items_raw = []

        items = []
        for item, path in zip(imported_items_raw, paths):
            items.append({"name": self._clip_name(item) or str(path)})

        return self._success(
            command["request_id"],
            data={
                "imported_count": len(imported_items_raw),
                "items": items,
            },
        )

    def _handle_timeline_append_clips(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        clip_names = command["payload"].get("clip_names")
        if not isinstance(clip_names, list) or not clip_names:
            return self._failure(
                command["request_id"],
                "validation_error",
                "At least one clip name is required.",
            )

        current_folder = self._current_media_pool_folder(current_project)
        if current_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        resolved_clips = []
        for clip_name in clip_names:
            clip, error = self._resolve_clip_by_name(current_folder, str(clip_name))
            if error is not None:
                return self._failure(
                    command["request_id"],
                    error["category"],
                    error["message"],
                    details=error.get("details"),
                )
            resolved_clips.append(clip)

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
            if timeline is None:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")
            if timeline is None:
                timeline = self._create_auto_timeline(current_project)
                if timeline is None:
                    return self._failure(
                        command["request_id"],
                        "execution_failure",
                        "Resolve could not create an automatic timeline for append.",
                    )

        media_pool = self._media_pool(current_project)
        appended = False
        if media_pool is not None:
            self._safe_call(current_project, "SetCurrentTimeline", timeline)
            appended = bool(self._safe_call(media_pool, "AppendToTimeline", resolved_clips))

        if not appended:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to append the requested clips.",
            )

        return self._success(
            command["request_id"],
            data={
                "timeline": self._timeline_summary(current_project, timeline),
                "appended": True,
                "count": len(resolved_clips),
                "clip_names": [str(name) for name in clip_names],
            },
        )

    def _handle_timeline_clips_place(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        placements = command["payload"].get("placements")
        if not isinstance(placements, list) or not placements:
            return self._failure(
                command["request_id"],
                "validation_error",
                "At least one clip placement is required.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")
        if timeline is None:
            return self._failure(
                command["request_id"],
                "no_current_timeline" if not timeline_name else "object_not_found",
                "No current timeline is active in Resolve."
                if not timeline_name
                else "Timeline '%s' was not found." % timeline_name,
            )

        current_folder = self._current_media_pool_folder(current_project)
        media_pool = self._media_pool(current_project)
        root_folder = self._safe_call(media_pool, "GetRootFolder") if media_pool is not None else None
        if current_folder is None or media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        clip_infos = []
        normalized = []
        required_track_indexes = {"video": 0, "audio": 0}
        for placement in placements:
            if not isinstance(placement, dict):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Each clip placement must be an object.",
                )
            clip_name = str(placement.get("clip_name") or "").strip()
            media_pool_path_value = placement.get("media_pool_path")
            media_pool_path = str(media_pool_path_value or "").strip()
            if not clip_name and not media_pool_path:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Clip placement requires clip_name or media_pool_path.",
                )
            if media_pool_path:
                clip, error = self._resolve_clip_by_media_pool_path(
                    root_folder,
                    current_folder,
                    media_pool_path,
                )
            else:
                clip, error = self._resolve_clip_by_name(current_folder, clip_name)
            if error is not None:
                return self._failure(
                    command["request_id"],
                    error["category"],
                    error["message"],
                    details=error.get("details"),
                )
            try:
                record_frame = int(placement.get("record_frame"))
                track_index = int(placement.get("track_index", 1))
            except (TypeError, ValueError):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Clip placement requires integer record_frame and track_index.",
                )
            if track_index < 1:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Track index must be at least 1.",
                )

            media_type = placement.get("media_type", 1)
            try:
                media_type = int(media_type)
            except (TypeError, ValueError):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Media type must be an integer when provided.",
                )
            if media_type not in (1, 2):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Media type must be 1 (video) or 2 (audio).",
                )

            clip_info = {
                "mediaPoolItem": clip,
                "recordFrame": record_frame,
                "trackIndex": track_index,
            }
            start_frame = placement.get("start_frame")
            end_frame = placement.get("end_frame")
            if start_frame is not None:
                try:
                    clip_info["startFrame"] = int(start_frame)
                except (TypeError, ValueError):
                    return self._failure(
                        command["request_id"],
                        "validation_error",
                        "Start frame must be an integer when provided.",
                    )
            if end_frame is not None:
                try:
                    clip_info["endFrame"] = int(end_frame)
                except (TypeError, ValueError):
                    return self._failure(
                        command["request_id"],
                        "validation_error",
                        "End frame must be an integer when provided.",
                    )
            if (
                "startFrame" in clip_info
                and "endFrame" in clip_info
                and clip_info["startFrame"] >= clip_info["endFrame"]
            ):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "End frame must be greater than start frame.",
                )
            clip_info["mediaType"] = media_type
            clip_infos.append(clip_info)
            track_type = "audio" if media_type == 2 else "video"
            required_track_indexes[track_type] = max(required_track_indexes[track_type], track_index)
            normalized.append(
                {
                    "name": clip_name or self._clip_name(clip) or "Timeline Item",
                    "track_type": track_type,
                    "track_index": track_index,
                }
            )

        self._safe_call(current_project, "SetCurrentTimeline", timeline)
        ensured, ensure_error = self._ensure_timeline_tracks(timeline, required_track_indexes)
        if not ensured:
            return self._failure(
                command["request_id"],
                "execution_failure",
                ensure_error or "Resolve failed to prepare the required timeline tracks.",
            )
        appended_items = self._safe_call(media_pool, "AppendToTimeline", clip_infos)
        if not isinstance(appended_items, list) or len(appended_items) != len(clip_infos):
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to place the requested clips.",
            )

        placed = []
        for item, summary in zip(appended_items, normalized):
            selector = self._timeline_item_selector(item)
            placed.append(
                {
                    "item_index": selector.get("item_index"),
                    "name": self._timeline_item_name(item) or summary["name"],
                    "track_type": selector.get("track_type") or summary["track_type"],
                    "track_index": selector.get("track_index") or summary["track_index"],
                    "start_frame": self._timeline_item_frame(item, "GetStart"),
                    "end_frame": self._timeline_item_frame(item, "GetEnd"),
                }
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "placed_count": len(placed),
                "items": placed,
            },
        )

    def _handle_timeline_create_from_clips(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = str(command["payload"].get("name") or "").strip()
        if not timeline_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Timeline name is required.",
            )

        clip_names = command["payload"].get("clip_names")
        if not isinstance(clip_names, list) or not clip_names:
            return self._failure(
                command["request_id"],
                "validation_error",
                "At least one clip name is required.",
            )

        current_folder = self._current_media_pool_folder(current_project)
        media_pool = self._media_pool(current_project)
        if current_folder is None or media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        resolved_clips = []
        for clip_name in clip_names:
            clip, error = self._resolve_clip_by_name(current_folder, str(clip_name))
            if error is not None:
                return self._failure(
                    command["request_id"],
                    error["category"],
                    error["message"],
                    details=error.get("details"),
                )
            resolved_clips.append(clip)

        created_timeline = self._safe_call(
            media_pool, "CreateTimelineFromClips", timeline_name, resolved_clips
        )
        if created_timeline is None:
            created_timeline = self._resolve_timeline_by_name(current_project, timeline_name)

        if created_timeline is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not create timeline '%s'." % timeline_name,
            )

        switched = bool(self._safe_call(current_project, "SetCurrentTimeline", created_timeline))
        active_timeline = self._safe_call(current_project, "GetCurrentTimeline")
        active_name = self._safe_call(active_timeline, "GetName")
        if not switched or active_timeline is None or active_name != timeline_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to timeline '%s'." % timeline_name,
                details={"timeline_name": timeline_name, "current_timeline_name": active_name},
            )

        return self._success(
            command["request_id"],
            data={
                "created": True,
                "timeline": self._timeline_summary(current_project, active_timeline),
                "count": len(resolved_clips),
                "clip_names": [str(name) for name in clip_names],
            },
        )

    def _handle_timeline_build_from_paths(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = str(command["payload"].get("name") or "").strip()
        if not timeline_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Timeline name is required.",
            )

        paths = command["payload"].get("paths")
        if not isinstance(paths, list) or not paths:
            return self._failure(
                command["request_id"],
                "validation_error",
                "At least one media path is required.",
            )

        media_pool = self._media_pool(current_project)
        current_folder = self._current_media_pool_folder(current_project)
        if media_pool is None or current_folder is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool folder is not available.",
            )

        normalized_paths = [str(path) for path in paths]
        imported_items = self._safe_call(media_pool, "ImportMedia", normalized_paths)
        if not isinstance(imported_items, list) or not imported_items:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to import the requested media paths.",
            )
        if len(imported_items) != len(normalized_paths):
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve imported only part of the requested media paths.",
                details={
                    "requested_count": len(normalized_paths),
                    "imported_count": len(imported_items),
                },
            )

        created_timeline = self._safe_call(
            media_pool,
            "CreateTimelineFromClips",
            timeline_name,
            imported_items,
        )
        if created_timeline is None:
            created_timeline = self._resolve_timeline_by_name(current_project, timeline_name)

        if created_timeline is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not create timeline '%s' from imported media." % timeline_name,
            )

        switched = bool(self._safe_call(current_project, "SetCurrentTimeline", created_timeline))
        active_timeline = self._safe_call(current_project, "GetCurrentTimeline")
        active_name = self._safe_call(active_timeline, "GetName")
        if not switched or active_timeline is None or active_name != timeline_name:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve did not switch to timeline '%s'." % timeline_name,
                details={"timeline_name": timeline_name, "current_timeline_name": active_name},
            )

        return self._success(
            command["request_id"],
            data={
                "created": True,
                "timeline": self._timeline_summary(current_project, active_timeline),
                "imported_count": len(imported_items),
                "count": len(imported_items),
                "paths": normalized_paths,
                "clip_names": [
                    self._clip_name(item) or normalized_paths[index]
                    for index, item in enumerate(imported_items)
                ],
            },
        )

    def _handle_timeline_items_list(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        tracks = []
        for track_type in ("video", "audio"):
            track_count = self._safe_call(timeline, "GetTrackCount", track_type) or 0
            for track_index in range(1, int(track_count) + 1):
                items = self._safe_call(timeline, "GetItemListInTrack", track_type, track_index)
                if not isinstance(items, list):
                    items = []
                tracks.append(
                    {
                        "track_type": track_type,
                        "track_index": track_index,
                        "items": [
                            {
                                "item_index": item_index,
                                "name": self._timeline_item_name(item)
                                or "%s item %s" % (track_type, item_index),
                                "start_frame": self._timeline_item_frame(item, "GetStart"),
                                "end_frame": self._timeline_item_frame(item, "GetEnd"),
                            }
                            for item_index, item in enumerate(items)
                        ],
                    }
                )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "tracks": tracks,
            },
        )

    def _handle_timeline_track_items_list(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        track_type = str(command["payload"].get("track_type") or "").strip().lower()
        if track_type not in ("video", "audio"):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Track type must be 'video' or 'audio'.",
            )

        try:
            track_index = int(command["payload"].get("track_index"))
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Track index must be an integer.",
            )

        if track_index < 1:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Track index must be at least 1.",
            )

        track_count = self._safe_call(timeline, "GetTrackCount", track_type) or 0
        if track_index > int(track_count):
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Track %s %s was not found." % (track_type, track_index),
                details={"track_type": track_type, "track_index": track_index},
            )

        items = self._safe_call(timeline, "GetItemListInTrack", track_type, track_index)
        if not isinstance(items, list):
            items = []

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "track": {
                    "track_type": track_type,
                    "track_index": track_index,
                    "items": [
                        {
                            "item_index": item_index,
                            "name": self._timeline_item_name(item)
                            or "%s item %s" % (track_type, item_index),
                            "start_frame": self._timeline_item_frame(item, "GetStart"),
                            "end_frame": self._timeline_item_frame(item, "GetEnd"),
                        }
                        for item_index, item in enumerate(items)
                    ],
                },
            },
        )

    def _handle_timeline_track_inspect(self, command, resolve):
        track_data, failure = self._resolve_track_payload(command, resolve)
        if failure is not None:
            return failure

        current_project = track_data["project"]
        timeline = track_data["timeline"]
        track_type = track_data["track_type"]
        track_index = track_data["track_index"]
        items = track_data["items"]

        start_frame = None
        end_frame = None
        for item in items:
            item_start = self._timeline_item_frame(item, "GetStart")
            item_end = self._timeline_item_frame(item, "GetEnd")
            if item_start is not None:
                start_frame = item_start if start_frame is None else min(start_frame, item_start)
            if item_end is not None:
                end_frame = item_end if end_frame is None else max(end_frame, item_end)

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "track_type": track_type,
                "track_index": track_index,
                "item_count": len(items),
                "start_frame": start_frame,
                "end_frame": end_frame,
            },
        )

    def _handle_timeline_item_inspect(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        current_project = item_data["project"]
        timeline = item_data["timeline"]
        item = item_data["item"]

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "item": {
                    "item_index": item_data["item_index"],
                    "name": self._timeline_item_name(item) or "Timeline Item",
                    "track_type": item_data["track_type"],
                    "track_index": item_data["track_index"],
                    "start_frame": self._timeline_item_frame(item, "GetStart"),
                    "end_frame": self._timeline_item_frame(item, "GetEnd"),
                },
                "duration": self._timeline_item_frame(item, "GetDuration"),
                "source_start_frame": self._timeline_item_frame(item, "GetSourceStartFrame"),
                "source_end_frame": self._timeline_item_frame(item, "GetSourceEndFrame"),
                "left_offset": self._timeline_item_frame(item, "GetLeftOffset"),
                "right_offset": self._timeline_item_frame(item, "GetRightOffset"),
            },
        )

    def _handle_timeline_item_delete(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        current_project = item_data["project"]
        timeline = item_data["timeline"]
        item = item_data["item"]
        ripple = bool(command["payload"].get("ripple", False))
        item_summary = {
            "item_index": item_data["item_index"],
            "name": self._timeline_item_name(item) or "Timeline Item",
            "track_type": item_data["track_type"],
            "track_index": item_data["track_index"],
            "start_frame": self._timeline_item_frame(item, "GetStart"),
            "end_frame": self._timeline_item_frame(item, "GetEnd"),
        }

        deleted = bool(self._safe_call(timeline, "DeleteClips", [item], ripple))
        if not deleted:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to delete the requested timeline item.",
            )

        return self._success(
            command["request_id"],
            data={
                "deleted": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "item": item_summary,
                "ripple": ripple,
            },
        )

    def _handle_timeline_item_properties_get(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        item = item_data["item"]
        if item_data["track_type"] != "video":
            return self._failure(
                command["request_id"],
                "unsupported_in_free_mode",
                "Timeline item properties are only supported for video items in v1.",
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(item_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(item_data["project"], item_data["timeline"]),
                "item": self._timeline_item_summary(
                    item,
                    item_index=item_data["item_index"],
                    track_type=item_data["track_type"],
                    track_index=item_data["track_index"],
                ),
                "properties": self._read_supported_item_properties(item),
            },
        )

    def _handle_timeline_item_properties_set(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        item = item_data["item"]
        if item_data["track_type"] != "video":
            return self._failure(
                command["request_id"],
                "unsupported_in_free_mode",
                "Timeline item properties are only supported for video items in v1.",
            )

        properties = command["payload"].get("properties")
        if not isinstance(properties, dict) or not properties:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Properties payload must be a non-empty object.",
            )

        normalized_properties = {}
        for key, raw_value in properties.items():
            property_key = str(key)
            if property_key not in SUPPORTED_TIMELINE_ITEM_PROPERTIES:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Unsupported timeline item property '%s'." % property_key,
                    details={"property": property_key},
                )
            normalized_value, value_error = self._normalize_timeline_item_property_value(
                property_key,
                raw_value,
            )
            if value_error is not None:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    value_error,
                    details={"property": property_key, "value": raw_value},
                )
            applied = self._safe_call(item, "SetProperty", property_key, normalized_value)
            if not applied:
                return self._failure(
                    command["request_id"],
                    "execution_failure",
                    "Resolve failed to set timeline item property '%s'." % property_key,
                    details={"property": property_key, "value": normalized_value},
                )
            normalized_properties[property_key] = normalized_value

        return self._success(
            command["request_id"],
            data={
                "updated": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(item_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(item_data["project"], item_data["timeline"]),
                "item": self._timeline_item_summary(
                    item,
                    item_index=item_data["item_index"],
                    track_type=item_data["track_type"],
                    track_index=item_data["track_index"],
                ),
                "properties": self._read_supported_item_properties(item),
            },
        )

    def _handle_timeline_item_animation_preset_apply(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        item = item_data["item"]
        if item_data["track_type"] != "video":
            return self._failure(
                command["request_id"],
                "unsupported_in_free_mode",
                "Animation presets are only supported for video items in v1.",
            )

        preset = str(command["payload"].get("preset") or "").strip()
        if preset not in SUPPORTED_ANIMATION_PRESETS:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Unsupported animation preset '%s'." % preset,
                details={"preset": preset},
            )

        duration_frames = command["payload"].get("duration_frames")
        if duration_frames is None:
            duration_frames = 12
        try:
            duration_frames = int(duration_frames)
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Animation duration_frames must be an integer when provided.",
            )
        if duration_frames < 1:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Animation duration_frames must be at least 1.",
            )

        intensity = command["payload"].get("intensity")
        if intensity is None:
            intensity = 1.0
        try:
            intensity = float(intensity)
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Animation intensity must be numeric when provided.",
            )
        if intensity <= 0:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Animation intensity must be greater than 0.",
            )

        direction = command["payload"].get("direction")
        if direction is None:
            direction = self._default_animation_direction_for_preset(preset)
        direction = str(direction)
        if direction not in SUPPORTED_ANIMATION_DIRECTIONS:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Unsupported animation direction '%s'." % direction,
                details={"direction": direction},
            )

        easing = command["payload"].get("easing")
        if easing is None:
            easing = "ease_in_out"
        easing = str(easing)
        if easing not in SUPPORTED_ANIMATION_EASINGS:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Unsupported animation easing '%s'." % easing,
                details={"easing": easing},
            )

        self._delete_dfmcp_animation_comps(item)
        template_path = self._write_animation_template(
            preset,
            duration_frames,
            intensity,
            direction,
            easing,
        )
        if template_path is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Failed to prepare the Fusion animation template.",
            )

        before_names = self._timeline_item_fusion_comp_names(item)
        imported_comp = self._safe_call(item, "ImportFusionComp", template_path)
        if imported_comp is None:
            imported_comp = self._safe_call(item, "AddFusionComp")
        after_names = self._timeline_item_fusion_comp_names(item)
        resolved_name = self._resolve_new_fusion_comp_name(before_names, after_names)
        if resolved_name is None and after_names:
            resolved_name = after_names[-1]
        if resolved_name is None and imported_comp is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to create a Fusion composition for the requested animation preset.",
                details={"preset": preset},
            )

        if resolved_name and resolved_name != DFMCP_ANIMATION_COMP_NAME:
            renamed = self._safe_call(
                item,
                "RenameFusionCompByName",
                resolved_name,
                DFMCP_ANIMATION_COMP_NAME,
            )
            if renamed:
                resolved_name = DFMCP_ANIMATION_COMP_NAME
        elif resolved_name is None:
            resolved_name = DFMCP_ANIMATION_COMP_NAME

        return self._success(
            command["request_id"],
            data={
                "applied": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(item_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(item_data["project"], item_data["timeline"]),
                "item": self._timeline_item_summary(
                    item,
                    item_index=item_data["item_index"],
                    track_type=item_data["track_type"],
                    track_index=item_data["track_index"],
                ),
                "applied_preset": preset,
                "fusion_comp_name": resolved_name,
                "properties": self._read_supported_item_properties(item),
            },
        )

    def _handle_timeline_item_animation_clear(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        item = item_data["item"]
        if item_data["track_type"] != "video":
            return self._failure(
                command["request_id"],
                "unsupported_in_free_mode",
                "Animation presets are only supported for video items in v1.",
            )

        removed_names = self._delete_dfmcp_animation_comps(item)
        return self._success(
            command["request_id"],
            data={
                "cleared": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(item_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(item_data["project"], item_data["timeline"]),
                "item": self._timeline_item_summary(
                    item,
                    item_index=item_data["item_index"],
                    track_type=item_data["track_type"],
                    track_index=item_data["track_index"],
                ),
                "fusion_comp_name": removed_names[-1] if removed_names else None,
            },
        )

    def _handle_timeline_item_move(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        current_project = item_data["project"]
        timeline = item_data["timeline"]
        item = item_data["item"]

        try:
            record_frame = int(command["payload"].get("record_frame"))
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Record frame must be an integer.",
            )

        target_track_type = command["payload"].get("target_track_type")
        if target_track_type is None:
            target_track_type = item_data["track_type"]
        else:
            target_track_type = str(target_track_type).strip().lower()
            if target_track_type not in ("video", "audio"):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Target track type must be 'video' or 'audio'.",
                )

        target_track_index = command["payload"].get("target_track_index")
        if target_track_index is None:
            target_track_index = item_data["track_index"]
        else:
            try:
                target_track_index = int(target_track_index)
            except (TypeError, ValueError):
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Target track index must be an integer when provided.",
                )
            if target_track_index < 1:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Target track index must be at least 1.",
                )

        media_pool_item = self._safe_call(item, "GetMediaPoolItem")
        if media_pool_item is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Timeline item cannot be moved because its media pool item is unavailable.",
            )

        source_start_frame = self._timeline_item_frame(item, "GetSourceStartFrame")
        source_end_frame = self._timeline_item_frame(item, "GetSourceEndFrame")
        if source_start_frame is None or source_end_frame is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Timeline item cannot be moved because its source frame range is unavailable.",
            )
        if source_start_frame >= source_end_frame:
            item_duration = self._timeline_item_frame(item, "GetDuration")
            if (
                source_start_frame == 0
                and source_end_frame == 0
                and item_duration is not None
                and item_duration > 0
            ):
                source_end_frame = item_duration
            else:
                return self._failure(
                    command["request_id"],
                    "execution_failure",
                    "Timeline item cannot be moved because its source frame range is invalid.",
                    details={
                        "source_start_frame": source_start_frame,
                        "source_end_frame": source_end_frame,
                    },
                )

        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool is not available.",
            )

        required_track_indexes = {"video": 0, "audio": 0}
        required_track_indexes[target_track_type] = int(target_track_index)
        ensured, ensure_error = self._ensure_timeline_tracks(timeline, required_track_indexes)
        if not ensured:
            return self._failure(
                command["request_id"],
                "execution_failure",
                ensure_error or "Resolve failed to prepare the target timeline tracks.",
            )

        self._safe_call(current_project, "SetCurrentTimeline", timeline)
        clip_info = {
            "mediaPoolItem": media_pool_item,
            "startFrame": source_start_frame,
            "endFrame": source_end_frame,
            "recordFrame": record_frame,
            "trackIndex": int(target_track_index),
            "mediaType": 2 if target_track_type == "audio" else 1,
        }
        appended_items = self._safe_call(media_pool, "AppendToTimeline", [clip_info])
        if not isinstance(appended_items, list) or len(appended_items) != 1:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to place the moved timeline item.",
            )

        moved_item = appended_items[0]
        moved_selector = self._timeline_item_selector(moved_item)
        source_item_summary = self._timeline_item_summary(
            item,
            item_index=item_data["item_index"],
            track_type=item_data["track_type"],
            track_index=item_data["track_index"],
        )
        moved_item_summary = self._timeline_item_summary(
            moved_item,
            item_index=moved_selector.get("item_index"),
            track_type=moved_selector.get("track_type") or target_track_type,
            track_index=moved_selector.get("track_index") or int(target_track_index),
            fallback_name=source_item_summary["name"],
        )

        deleted = bool(self._safe_call(timeline, "DeleteClips", [item], False))
        if not deleted:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve placed the moved timeline item but failed to delete the source item.",
                details={
                    "move_completed": False,
                    "source_item": source_item_summary,
                    "item": moved_item_summary,
                },
            )

        return self._success(
            command["request_id"],
            data={
                "moved": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "source_item": source_item_summary,
                "item": moved_item_summary,
            },
        )

    def _handle_timeline_item_split(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        try:
            split_frame = int(command["payload"].get("record_frame"))
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Record frame must be an integer.",
            )

        item = item_data["item"]
        item_start = self._timeline_item_frame(item, "GetStart")
        item_end = self._timeline_item_frame(item, "GetEnd")
        if item_start is None or item_end is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Timeline item timing is unavailable.",
            )
        if split_frame <= item_start or split_frame >= item_end:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Split frame must be strictly inside the timeline item range.",
                details={"record_frame": split_frame, "start_frame": item_start, "end_frame": item_end},
            )

        media_pool_item = self._safe_call(item, "GetMediaPoolItem")
        if media_pool_item is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Timeline item cannot be split because its media pool item is unavailable.",
            )

        source_start_frame, source_end_frame, range_error = self._timeline_item_source_range(item)
        if range_error is not None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                range_error["message"],
                details=range_error.get("details"),
            )

        split_offset = split_frame - item_start
        left_end = source_start_frame + split_offset
        right_start = left_end
        current_project = item_data["project"]
        timeline = item_data["timeline"]
        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool is not available.",
            )

        self._safe_call(current_project, "SetCurrentTimeline", timeline)
        appended_items = self._safe_call(
            media_pool,
            "AppendToTimeline",
            [
                {
                    "mediaPoolItem": media_pool_item,
                    "startFrame": source_start_frame,
                    "endFrame": left_end,
                    "recordFrame": item_start,
                    "trackIndex": item_data["track_index"],
                    "mediaType": 2 if item_data["track_type"] == "audio" else 1,
                },
                {
                    "mediaPoolItem": media_pool_item,
                    "startFrame": right_start,
                    "endFrame": source_end_frame,
                    "recordFrame": split_frame,
                    "trackIndex": item_data["track_index"],
                    "mediaType": 2 if item_data["track_type"] == "audio" else 1,
                },
            ],
        )
        if not isinstance(appended_items, list) or len(appended_items) != 2:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to split the requested timeline item.",
            )

        source_item_summary = self._timeline_item_summary(
            item,
            item_index=item_data["item_index"],
            track_type=item_data["track_type"],
            track_index=item_data["track_index"],
        )
        deleted = bool(self._safe_call(timeline, "DeleteClips", [item], False))
        if not deleted:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve split the timeline item but failed to delete the source item.",
                details={"source_item": source_item_summary},
            )

        marker, warnings = self._maybe_add_technical_marker(
            timeline,
            split_frame,
            "Split",
            command["payload"].get("add_marker", True),
        )
        left_item_summary = self._resolved_timeline_item_summary(
            timeline,
            appended_items[0],
            item_data["track_type"],
            item_data["track_index"],
            fallback_name=source_item_summary["name"],
        )
        right_item_summary = self._resolved_timeline_item_summary(
            timeline,
            appended_items[1],
            item_data["track_type"],
            item_data["track_index"],
            fallback_name=source_item_summary["name"],
        )
        return self._success(
            command["request_id"],
            data={
                "split_frame": split_frame,
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "left_item": left_item_summary,
                "right_item": right_item_summary,
                "marker": marker,
            },
            warnings=warnings,
        )

    def _handle_timeline_item_set_source_range(self, command, resolve):
        item_data, failure = self._resolve_timeline_item(command, resolve)
        if failure is not None:
            return failure

        try:
            source_start_frame = int(command["payload"].get("source_start_frame"))
            source_end_frame = int(command["payload"].get("source_end_frame"))
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Source start and end frames must be integers.",
            )
        if source_end_frame <= source_start_frame:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Source end frame must be greater than source start frame.",
            )

        current_project = item_data["project"]
        timeline = item_data["timeline"]
        item = item_data["item"]
        media_pool_item = self._safe_call(item, "GetMediaPoolItem")
        if media_pool_item is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Timeline item cannot be updated because its media pool item is unavailable.",
            )

        item_start = self._timeline_item_frame(item, "GetStart")
        if item_start is None:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Timeline item timing is unavailable.",
            )

        media_pool = self._media_pool(current_project)
        if media_pool is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Current media pool is not available.",
            )

        source_item_summary = self._timeline_item_summary(
            item,
            item_index=item_data["item_index"],
            track_type=item_data["track_type"],
            track_index=item_data["track_index"],
        )
        self._safe_call(current_project, "SetCurrentTimeline", timeline)
        appended_items = self._safe_call(
            media_pool,
            "AppendToTimeline",
            [
                {
                    "mediaPoolItem": media_pool_item,
                    "startFrame": source_start_frame,
                    "endFrame": source_end_frame,
                    "recordFrame": item_start,
                    "trackIndex": item_data["track_index"],
                    "mediaType": 2 if item_data["track_type"] == "audio" else 1,
                }
            ],
        )
        if not isinstance(appended_items, list) or len(appended_items) != 1:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to update the timeline item source range.",
            )

        deleted = bool(self._safe_call(timeline, "DeleteClips", [item], False))
        if not deleted:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve placed the updated timeline item but failed to delete the source item.",
                details={"source_item": source_item_summary},
            )

        marker, warnings = self._maybe_add_technical_marker(
            timeline,
            item_start,
            "Trim",
            command["payload"].get("add_marker", True),
        )
        return self._success(
            command["request_id"],
            data={
                "updated": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "source_item": source_item_summary,
                "item": self._resolved_timeline_item_summary(
                    timeline,
                    appended_items[0],
                    item_data["track_type"],
                    item_data["track_index"],
                    fallback_name=source_item_summary["name"],
                ),
                "marker": marker,
            },
            warnings=warnings,
        )

    def _handle_timeline_gap_close(self, command, resolve):
        track_data, failure = self._resolve_track_payload(command, resolve)
        if failure is not None:
            return failure

        try:
            frame_from = int(command["payload"].get("frame_from"))
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Gap start frame must be an integer.",
            )

        frame_to = command["payload"].get("frame_to")
        try:
            frame_to_value = int(frame_to) if frame_to is not None else None
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Gap end frame must be an integer when provided.",
            )
        if frame_to_value is not None and frame_to_value <= frame_from:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Gap end frame must be greater than gap start frame.",
            )

        gap_data, gap_error = self._resolve_gap_range(
            track_data["items"],
            frame_from,
            frame_to_value,
        )
        if gap_error is not None:
            return self._failure(
                command["request_id"],
                gap_error["category"],
                gap_error["message"],
                details=gap_error.get("details"),
            )

        shifted_items = [
            {"item": entry["item"], "record_frame": entry["item"].GetStart() - gap_data["duration"]}
            for entry in gap_data["following_items"]
        ]
        shifted_count, shift_error = self._recreate_shifted_items(
            track_data["project"],
            track_data["timeline"],
            shifted_items,
        )
        if shift_error is not None:
            return self._failure(
                command["request_id"],
                shift_error["category"],
                shift_error["message"],
                details=shift_error.get("details"),
            )

        marker, warnings = self._maybe_add_technical_marker(
            track_data["timeline"],
            gap_data["frame_from"],
            "Gap Close",
            command["payload"].get("add_marker", True),
        )
        return self._success(
            command["request_id"],
            data={
                "closed": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(track_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(track_data["project"], track_data["timeline"]),
                "track_type": track_data["track_type"],
                "track_index": track_data["track_index"],
                "frame_from": gap_data["frame_from"],
                "frame_to": gap_data["frame_to"],
                "shifted_item_count": shifted_count,
                "marker": marker,
            },
            warnings=warnings,
        )

    def _handle_timeline_remove_gaps(self, command, resolve):
        track_data, failure = self._resolve_track_payload(command, resolve)
        if failure is not None:
            return failure

        items = track_data["items"]
        if len(items) < 2:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "No internal gaps were found on the requested track.",
            )

        sorted_entries = self._timeline_track_entries(items)
        removed_gap_count = 0
        shifted_items = []
        current_end = sorted_entries[0]["end_frame"]
        first_gap_start = None
        for entry in sorted_entries[1:]:
            if entry["start_frame"] > current_end:
                removed_gap_count += 1
                if first_gap_start is None:
                    first_gap_start = current_end
            target_start = current_end
            if entry["start_frame"] != target_start:
                shifted_items.append({"item": entry["item"], "record_frame": target_start})
            current_end = target_start + (entry["end_frame"] - entry["start_frame"])

        if removed_gap_count == 0:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "No internal gaps were found on the requested track.",
            )

        shifted_count, shift_error = self._recreate_shifted_items(
            track_data["project"],
            track_data["timeline"],
            shifted_items,
        )
        if shift_error is not None:
            return self._failure(
                command["request_id"],
                shift_error["category"],
                shift_error["message"],
                details=shift_error.get("details"),
            )

        marker, warnings = self._maybe_add_technical_marker(
            track_data["timeline"],
            first_gap_start,
            "Remove Gaps",
            command["payload"].get("add_marker", True),
        )
        return self._success(
            command["request_id"],
            data={
                "removed_gap_count": removed_gap_count,
                "shifted_item_count": shifted_count,
                "project": {
                    "open": True,
                    "name": self._safe_call(track_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(track_data["project"], track_data["timeline"]),
                "track_type": track_data["track_type"],
                "track_index": track_data["track_index"],
                "marker": marker,
            },
            warnings=warnings,
        )

    def _handle_timeline_insert_gap(self, command, resolve):
        track_data, failure = self._resolve_track_payload(command, resolve)
        if failure is not None:
            return failure

        try:
            at_frame = int(command["payload"].get("at_frame"))
            duration = int(command["payload"].get("duration"))
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Gap insertion frame and duration must be integers.",
            )
        if duration <= 0:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Gap duration must be greater than zero.",
            )

        overlap_entry = self._find_track_item_covering_frame(track_data["items"], at_frame)
        if overlap_entry is not None:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Gap cannot be inserted inside an existing timeline item.",
                details={"at_frame": at_frame},
            )

        shifted_items = []
        for entry in self._timeline_track_entries(track_data["items"]):
            if entry["start_frame"] >= at_frame:
                shifted_items.append({"item": entry["item"], "record_frame": entry["start_frame"] + duration})

        shifted_count, shift_error = self._recreate_shifted_items(
            track_data["project"],
            track_data["timeline"],
            shifted_items,
        )
        if shift_error is not None:
            return self._failure(
                command["request_id"],
                shift_error["category"],
                shift_error["message"],
                details=shift_error.get("details"),
            )

        marker, warnings = self._maybe_add_technical_marker(
            track_data["timeline"],
            at_frame,
            "Insert Gap",
            command["payload"].get("add_marker", True),
        )
        return self._success(
            command["request_id"],
            data={
                "inserted": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(track_data["project"], "GetName"),
                },
                "timeline": self._timeline_summary(track_data["project"], track_data["timeline"]),
                "track_type": track_data["track_type"],
                "track_index": track_data["track_index"],
                "at_frame": at_frame,
                "duration": duration,
                "shifted_item_count": shifted_count,
                "marker": marker,
            },
            warnings=warnings,
        )

    def _handle_timeline_inspect(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        video_track_count, video_item_count = self._timeline_track_counts(timeline, "video")
        audio_track_count, audio_item_count = self._timeline_track_counts(timeline, "audio")

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "video_track_count": video_track_count,
                "audio_track_count": audio_track_count,
                "video_item_count": video_item_count,
                "audio_item_count": audio_item_count,
                "marker_count": len(self._timeline_markers(timeline)),
            },
        )

    def _handle_marker_add(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        marker_name = str(command["payload"].get("name") or "").strip()
        if not marker_name:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker name is required.",
            )

        frame = command["payload"].get("frame")
        try:
            frame_value = int(frame)
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker frame must be an integer.",
            )

        duration = command["payload"].get("duration", 1)
        try:
            duration_value = int(duration)
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker duration must be an integer.",
            )
        if duration_value < 1:
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker duration must be at least 1 frame.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        color_value = str(command["payload"].get("color") or "Blue")
        note_value = command["payload"].get("note")
        if note_value is None:
            note_value = ""
        else:
            note_value = str(note_value)

        added = bool(
            self._safe_call(
                timeline,
                "AddMarker",
                frame_value,
                color_value,
                marker_name,
                note_value,
                duration_value,
                "",
            )
        )
        if not added:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to add a marker to timeline '%s'."
                % (self._safe_call(timeline, "GetName") or "Timeline"),
            )

        return self._success(
            command["request_id"],
            data={
                "added": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "marker": {
                    "frame": frame_value,
                    "color": color_value,
                    "name": marker_name,
                    "note": note_value or None,
                    "duration": duration_value,
                    "custom_data": "",
                },
            },
        )

    def _handle_marker_list(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "markers": self._timeline_markers(timeline),
            },
        )

    def _handle_marker_inspect(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        frame = command["payload"].get("frame")
        try:
            frame_value = int(frame)
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker frame must be an integer.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        marker = self._timeline_markers_by_frame(timeline).get(frame_value)
        if marker is None:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Marker at frame %s was not found." % frame_value,
                details={"frame": frame_value},
            )

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "marker": marker,
            },
        )

    def _handle_marker_list_range(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        frame_from = command["payload"].get("frame_from")
        frame_to = command["payload"].get("frame_to")
        try:
            frame_from_value = int(frame_from) if frame_from is not None else None
            frame_to_value = int(frame_to) if frame_to is not None else None
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker range values must be integers.",
            )
        if (
            frame_from_value is not None
            and frame_to_value is not None
            and frame_from_value > frame_to_value
        ):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker range start must be less than or equal to range end.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        markers = self._timeline_markers(timeline)
        filtered = []
        for marker in markers:
            frame_value = marker.get("frame")
            if frame_from_value is not None and frame_value < frame_from_value:
                continue
            if frame_to_value is not None and frame_value > frame_to_value:
                continue
            filtered.append(marker)

        return self._success(
            command["request_id"],
            data={
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "frame_from": frame_from_value,
                "frame_to": frame_to_value,
                "markers": filtered,
            },
        )

    def _handle_marker_delete(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        frame = command["payload"].get("frame")
        try:
            frame_value = int(frame)
        except (TypeError, ValueError):
            return self._failure(
                command["request_id"],
                "validation_error",
                "Marker frame must be an integer.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        markers_by_frame = self._timeline_markers_by_frame(timeline)
        if frame_value not in markers_by_frame:
            return self._failure(
                command["request_id"],
                "object_not_found",
                "Marker at frame '%s' was not found." % frame_value,
                details={"frame": frame_value},
            )

        deleted = bool(self._safe_call(timeline, "DeleteMarkerAtFrame", frame_value))
        if not deleted:
            return self._failure(
                command["request_id"],
                "execution_failure",
                "Resolve failed to delete the requested marker.",
                details={"frame": frame_value},
            )

        return self._success(
            command["request_id"],
            data={
                "deleted": True,
                "project": {
                    "open": True,
                    "name": self._safe_call(current_project, "GetName"),
                },
                "timeline": self._timeline_summary(current_project, timeline),
                "marker": {"frame": frame_value},
            },
        )

    @staticmethod
    def _safe_call(obj, method_name, *args):
        if obj is None:
            return None
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception:
            return None

    def _read_supported_item_properties(self, item):
        properties = {}
        for property_key in SUPPORTED_TIMELINE_ITEM_PROPERTIES:
            raw_value = self._safe_call(item, "GetProperty", property_key)
            normalized = self._normalize_property_output_value(raw_value)
            if normalized is not None:
                properties[property_key] = normalized
        return properties

    def _normalize_timeline_item_property_value(self, property_key, raw_value):
        expected_type = SUPPORTED_TIMELINE_ITEM_PROPERTIES.get(property_key)
        if expected_type == "int":
            if isinstance(raw_value, bool):
                return None, "Property '%s' does not accept boolean values." % property_key
            try:
                return int(raw_value), None
            except (TypeError, ValueError):
                return None, "Property '%s' must be an integer." % property_key
        try:
            return float(raw_value), None
        except (TypeError, ValueError):
            return None, "Property '%s' must be numeric." % property_key

    def _normalize_property_output_value(self, raw_value):
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, int):
            return int(raw_value)
        if isinstance(raw_value, float):
            return float(raw_value)
        try:
            if "." in str(raw_value):
                return float(raw_value)
            return int(raw_value)
        except (TypeError, ValueError):
            return str(raw_value)

    def _default_animation_direction_for_preset(self, preset):
        if preset == "zoom_in_soft":
            return "in"
        if preset == "zoom_out_soft":
            return "out"
        if preset.startswith("slide_"):
            if "_up_" in preset:
                return "up"
            if "_down_" in preset:
                return "down"
            if "_left_" in preset:
                return "left"
            if "_right_" in preset:
                return "right"
        return "in"

    def _timeline_item_fusion_comp_names(self, item):
        names = self._safe_call(item, "GetFusionCompNameList")
        if not isinstance(names, list):
            names = self._safe_call(item, "GetFusionCompNames")
        if not isinstance(names, list):
            names = []
        return [str(name) for name in names]

    def _resolve_new_fusion_comp_name(self, before_names, after_names):
        for name in after_names:
            if name not in before_names:
                return name
        return None

    def _delete_dfmcp_animation_comps(self, item):
        removed_names = []
        for comp_name in self._timeline_item_fusion_comp_names(item):
            if not str(comp_name).startswith(DFMCP_ANIMATION_COMP_PREFIX):
                continue
            deleted = self._safe_call(item, "DeleteFusionCompByName", str(comp_name))
            if deleted:
                removed_names.append(str(comp_name))
        return removed_names

    def _write_animation_template(self, preset, duration_frames, intensity, direction, easing):
        template_name = "fade.setting"
        if preset not in ("fade_in", "fade_out", "fade_in_out"):
            template_name = "transform.setting"

        template = self._load_animation_template(template_name)
        if not template:
            return None

        values = self._animation_template_values(
            preset,
            duration_frames,
            intensity,
            direction,
            easing,
        )
        for key, value in values.items():
            template = template.replace(key, value)

        file_name = "dfmcp_%s_%s.setting" % (preset, os.getpid())
        temp_path = os.path.join(tempfile.gettempdir(), file_name)
        handle = None
        try:
            handle = open(temp_path, "w")
            handle.write(template)
            handle.close()
        except Exception:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            return None
        return temp_path

    def _load_animation_template(self, template_name):
        template_path = self._repo_template_path(template_name)
        if template_path and os.path.exists(template_path):
            handle = None
            try:
                handle = open(template_path, "r")
                data = handle.read()
                handle.close()
                return data
            except Exception:
                if handle is not None:
                    try:
                        handle.close()
                    except Exception:
                        pass
        if template_name == "fade.setting":
            return FALLBACK_FADE_TEMPLATE
        return FALLBACK_TRANSFORM_TEMPLATE

    def _repo_template_path(self, template_name):
        repo_root = globals().get("REPO_ROOT")
        if not repo_root:
            repo_root = os.environ.get("DFMCP_REPO_ROOT")
        if not repo_root:
            repo_root = os.getcwd()
        if not repo_root:
            return None
        return os.path.join(
            repo_root,
            "src",
            "davinci_free_mcp",
            "resolve_exec",
            "templates",
            template_name,
        )

    def _animation_template_values(self, preset, duration_frames, intensity, direction, easing):
        mid_duration = max(1, int(duration_frames))
        blend_start = "0"
        blend_end = "1"
        size_start = "1"
        size_end = "1"
        center_x = "0.5"
        center_y = "0.5"

        if preset == "fade_out":
            blend_start = "1"
            blend_end = "0"
        elif preset == "fade_in_out":
            mid_duration = max(1, int(duration_frames) // 2)
        elif preset == "zoom_in_soft":
            size_start = self._stringify_float(1.0 + (0.12 * intensity))
            size_end = "1"
        elif preset == "zoom_out_soft":
            size_start = "1"
            size_end = self._stringify_float(1.0 + (0.12 * intensity))

        if preset.startswith("slide_"):
            offset = 0.08 * intensity
            if direction == "up":
                center_y = self._stringify_float(0.5 + offset)
            elif direction == "down":
                center_y = self._stringify_float(0.5 - offset)
            elif direction == "left":
                center_x = self._stringify_float(0.5 + offset)
            elif direction == "right":
                center_x = self._stringify_float(0.5 - offset)

        return {
            "__DURATION__": str(max(1, int(duration_frames))),
            "__MID_DURATION__": str(max(1, int(mid_duration))),
            "__START_VALUE__": blend_start,
            "__END_VALUE__": blend_end,
            "__START_OPACITY__": blend_start,
            "__END_OPACITY__": blend_end,
            "__START_SCALE__": size_start,
            "__END_SCALE__": size_end,
            "__CENTER_X__": center_x,
            "__CENTER_Y__": center_y,
            "__EASING__": str(easing),
        }

    def _stringify_float(self, value):
        text = "%.6f" % float(value)
        text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _current_project(self, resolve):
        project_manager = self._safe_call(resolve, "GetProjectManager")
        if project_manager is None:
            return None
        return self._safe_call(project_manager, "GetCurrentProject")

    def _list_project_names(self, project_manager):
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

    def _project_manager_current_folder_name(self, project_manager):
        current_folder = self._safe_call(project_manager, "GetCurrentFolder")
        if isinstance(current_folder, str):
            current_folder = current_folder.strip()
            return current_folder or None
        name = self._safe_call(current_folder, "GetName")
        if name is not None:
            name = str(name).strip()
            return name or None
        return None

    def _project_manager_folder_display_name(self, folder_name):
        if folder_name:
            return folder_name
        return "Root"

    def _list_project_manager_folder_names(self, project_manager):
        if project_manager is None:
            return []

        folder_names = self._safe_call(project_manager, "GetFolderListInCurrentFolder")
        if isinstance(folder_names, list):
            return [str(name) for name in folder_names]

        folder_names = self._safe_call(project_manager, "GetFoldersInCurrentFolder")
        if isinstance(folder_names, list):
            return [str(name) for name in folder_names]
        if isinstance(folder_names, dict):
            return [str(name) for name in folder_names.values()]
        return []

    def _project_manager_folder_listing(self, project_manager):
        current_name = self._project_manager_current_folder_name(project_manager)
        return {
            "folder": {"name": self._project_manager_folder_display_name(current_name)},
            "subfolders": [
                {"name": folder_name}
                for folder_name in self._list_project_manager_folder_names(project_manager)
            ],
            "projects": [
                {"name": project_name}
                for project_name in self._list_project_names(project_manager)
            ],
        }

    def _project_manager_folder_state(self, project_manager):
        listing = self._project_manager_folder_listing(project_manager)
        listing["path"] = [
            {"name": self._project_manager_folder_display_name(folder_name)}
            for folder_name in self._project_manager_folder_path(project_manager)
        ]
        return listing

    def _project_manager_folder_signature(self, project_manager):
        folder_names = self._list_project_manager_folder_names(project_manager)
        project_names = self._list_project_names(project_manager)
        return (
            self._project_manager_current_folder_name(project_manager),
            tuple(folder_names),
            tuple(project_names),
        )

    def _project_manager_folder_path(self, project_manager):
        current_name = self._project_manager_current_folder_name(project_manager)
        if current_name is None:
            if self._project_manager_goto_root(project_manager):
                return [self._project_manager_current_folder_name(project_manager)]
            return [None]

        original_signature = self._project_manager_folder_signature(project_manager)
        if not self._project_manager_goto_root(project_manager):
            return [current_name]

        found_path = self._project_manager_find_folder_path(project_manager, original_signature, [])
        if found_path is None:
            found_path = [self._project_manager_current_folder_name(project_manager) or current_name]

        self._project_manager_open_path_from_root(project_manager, found_path)
        return found_path

    def _project_manager_find_folder_path(self, project_manager, target_signature, parent_names):
        current_name = self._project_manager_current_folder_name(project_manager)
        if current_name is None:
            return None

        current_path = list(parent_names) + [current_name]
        if self._project_manager_folder_signature(project_manager) == target_signature:
            return current_path

        for folder_name in self._list_project_manager_folder_names(project_manager):
            if not self._safe_call(project_manager, "OpenFolder", folder_name):
                continue

            found_path = self._project_manager_find_folder_path(
                project_manager,
                target_signature,
                current_path,
            )
            if found_path is not None:
                return found_path

            if not self._project_manager_backtrack_to_path(project_manager, current_path):
                return None

        return None

    def _project_manager_backtrack_to_path(self, project_manager, path_names):
        moved = self._safe_call(project_manager, "GotoParentFolder")
        if moved:
            return True
        return self._project_manager_open_path_from_root(project_manager, path_names)

    def _project_manager_goto_root(self, project_manager):
        result = self._safe_call(project_manager, "GotoRootFolder")
        return bool(result)

    def _project_manager_open_path_from_root(self, project_manager, path_names):
        if not path_names:
            return self._project_manager_goto_root(project_manager)

        if not self._project_manager_goto_root(project_manager):
            return False

        current_name = self._project_manager_current_folder_name(project_manager)
        segments = list(path_names)
        if current_name is not None and segments and segments[0] == current_name:
            segments = segments[1:]

        for segment in segments:
            if not self._safe_call(project_manager, "OpenFolder", segment):
                return False
        return True

    def _timeline_summary(self, project, timeline):
        return {
            "index": self._timeline_index(project, timeline),
            "name": self._safe_call(timeline, "GetName") or "Timeline",
        }

    def _timeline_index(self, project, timeline):
        timeline_count = self._safe_call(project, "GetTimelineCount") or 0
        timeline_name = self._safe_call(timeline, "GetName")
        for index in range(1, int(timeline_count) + 1):
            candidate = self._safe_call(project, "GetTimelineByIndex", index)
            if candidate is timeline:
                return index
            if timeline_name and self._safe_call(candidate, "GetName") == timeline_name:
                return index
        return 1

    def _resolve_timeline_by_name(self, project, timeline_name):
        timeline_count = self._safe_call(project, "GetTimelineCount") or 0
        for index in range(1, int(timeline_count) + 1):
            timeline = self._safe_call(project, "GetTimelineByIndex", index)
            if self._safe_call(timeline, "GetName") == timeline_name:
                return timeline
        return None

    def _media_pool(self, project):
        return self._safe_call(project, "GetMediaPool")

    def _current_media_pool_folder(self, project):
        media_pool = self._media_pool(project)
        if media_pool is None:
            return None
        return self._safe_call(media_pool, "GetCurrentFolder")

    def _list_media_subfolders(self, folder):
        subfolders = self._safe_call(folder, "GetSubFolderList")
        if isinstance(subfolders, list):
            return subfolders
        subfolders = self._safe_call(folder, "GetSubFolders")
        if isinstance(subfolders, list):
            return subfolders
        if isinstance(subfolders, dict):
            return list(subfolders.values())
        return []

    def _find_parent_media_folder(self, root_folder, target_folder):
        if root_folder is None or target_folder is None or root_folder is target_folder:
            return None
        parent = self._find_parent_media_folder_by_identity(root_folder, target_folder)
        if parent is not None:
            return parent
        target_name = self._safe_call(target_folder, "GetName")
        if not target_name:
            return None
        matches = self._find_media_folder_parents_by_name(root_folder, str(target_name))
        if len(matches) == 1:
            return matches[0]
        return None

    def _find_parent_media_folder_by_identity(self, root_folder, target_folder):
        if root_folder is None or target_folder is None or root_folder is target_folder:
            return None
        for child in self._list_media_subfolders(root_folder):
            if child is target_folder:
                return root_folder
            parent = self._find_parent_media_folder_by_identity(child, target_folder)
            if parent is not None:
                return parent
        return None

    def _find_media_folder_parents_by_name(self, root_folder, target_name):
        matches = []
        for child in self._list_media_subfolders(root_folder):
            if self._safe_call(child, "GetName") == target_name:
                matches.append(root_folder)
            matches.extend(self._find_media_folder_parents_by_name(child, target_name))
        return matches

    def _media_pool_folder_listing(self, folder):
        return {
            "folder": {
                "name": self._safe_call(folder, "GetName") or "Current Folder"
            },
            "subfolders": [
                {"name": self._safe_call(child, "GetName") or "Folder"}
                for child in self._list_media_subfolders(folder)
            ],
            "clips": [
                {"name": self._clip_name(clip) or "Unnamed Clip"}
                for clip in self._list_media_clips(folder)
            ],
        }

    def _media_pool_folder_state(self, folder, root_folder):
        listing = self._media_pool_folder_listing(folder)
        listing["path"] = self._media_pool_folder_path(root_folder, folder)
        return listing

    def _media_pool_folder_tree(self, folder, max_depth=None, depth=0):
        node = {
            "name": self._safe_call(folder, "GetName") or "Folder",
            "clips": [
                {"name": self._clip_name(clip) or "Unnamed Clip"}
                for clip in self._list_media_clips(folder)
            ],
            "subfolders": [],
        }
        if max_depth is not None and depth >= max_depth:
            return node
        node["subfolders"] = [
            self._media_pool_folder_tree(child, max_depth=max_depth, depth=depth + 1)
            for child in self._list_media_subfolders(folder)
        ]
        return node

    def _media_pool_folder_path(self, root_folder, target_folder):
        if root_folder is None or target_folder is None:
            return []
        path_segments = self._find_media_folder_path(root_folder, target_folder)
        return [
            {"name": self._safe_call(folder, "GetName") or "Folder"}
            for folder in path_segments
        ]

    def _find_media_folder_path(self, root_folder, target_folder):
        if root_folder is None or target_folder is None:
            return []
        if root_folder is target_folder:
            return [root_folder]
        for child in self._list_media_subfolders(root_folder):
            child_path = self._find_media_folder_path(child, target_folder)
            if child_path:
                return [root_folder] + child_path
        target_name = self._safe_call(target_folder, "GetName")
        if not target_name:
            return []
        name_path = self._find_media_folder_path_by_name(root_folder, str(target_name))
        if len(name_path) == 1:
            return name_path[0]
        return []

    def _find_media_folder_path_by_name(self, root_folder, target_name):
        matches = []
        if self._safe_call(root_folder, "GetName") == target_name:
            matches.append([root_folder])
        for child in self._list_media_subfolders(root_folder):
            for child_path in self._find_media_folder_path_by_name(child, target_name):
                matches.append([root_folder] + child_path)
        return matches

    def _resolve_media_folder_by_path(self, root_folder, current_folder, path_value):
        normalized_path = str(path_value).replace("\\", "/")
        is_absolute = normalized_path.startswith("/")
        raw_segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
        if not raw_segments and not is_absolute:
            return None, {
                "category": "validation_error",
                "message": "Media pool folder path is required.",
                "details": {"path": path_value},
            }

        target_folder = root_folder if is_absolute else current_folder
        if raw_segments:
            root_name = self._safe_call(root_folder, "GetName")
            if is_absolute and root_name and raw_segments[0] == str(root_name):
                raw_segments = raw_segments[1:]

        for segment in raw_segments:
            if segment == ".":
                continue
            if segment == "..":
                parent = self._find_parent_media_folder(root_folder, target_folder)
                if parent is None:
                    return None, {
                        "category": "validation_error",
                        "message": "Path '%s' moves above the root media pool folder." % path_value,
                        "details": {"path": path_value},
                    }
                target_folder = parent
                continue
            target_folder, error = self._resolve_media_subfolder_by_name(target_folder, segment)
            if error is not None:
                error = dict(error)
                error["details"] = dict(error.get("details") or {}, path=path_value, segment=segment)
                return None, error
        return target_folder, None

    def _resolve_media_subfolder_by_name(self, folder, folder_name):
        matches = [
            child
            for child in self._list_media_subfolders(folder)
            if self._safe_call(child, "GetName") == folder_name
        ]
        if not matches:
            return None, {
                "category": "object_not_found",
                "message": "Media pool folder '%s' was not found in the current folder." % folder_name,
                "details": {"folder_name": folder_name},
            }
        if len(matches) > 1:
            return None, {
                "category": "validation_error",
                "message": "Media pool folder name '%s' is ambiguous in the current folder."
                % folder_name,
                "details": {"folder_name": folder_name, "match_count": len(matches)},
            }
        return matches[0], None

    def _list_media_clips(self, folder):
        clips = self._safe_call(folder, "GetClipList")
        if isinstance(clips, list):
            return [clip for clip in clips if self._is_media_pool_clip(clip)]
        clips = self._safe_call(folder, "GetClips")
        if isinstance(clips, list):
            return [clip for clip in clips if self._is_media_pool_clip(clip)]
        if isinstance(clips, dict):
            return [clip for clip in clips.values() if self._is_media_pool_clip(clip)]
        return []

    def _clip_name(self, clip):
        name = self._safe_call(clip, "GetName")
        if name:
            return str(name)
        properties = self._safe_call(clip, "GetClipProperty")
        if isinstance(properties, dict):
            clip_name = properties.get("Clip Name") or properties.get("File Name")
            if clip_name:
                return str(clip_name)
        return None

    def _clip_properties(self, clip):
        properties = self._safe_call(clip, "GetClipProperty")
        if isinstance(properties, dict):
            return properties
        return {}

    def _clip_string_properties(self, clip):
        properties = self._clip_properties(clip)
        normalized = {}
        for key, value in properties.items():
            if key is None or value is None:
                continue
            normalized[str(key)] = str(value)
        return normalized

    def _is_media_pool_clip(self, clip):
        properties = self._clip_properties(clip)
        if not properties:
            return True

        type_markers = (
            properties.get("Type"),
            properties.get("Clip Type"),
            properties.get("TypeName"),
        )
        normalized_markers = set(
            [str(value).strip().lower() for value in type_markers if value is not None]
        )
        if "timeline" in normalized_markers:
            return False

        media_markers = ("File Path", "Video Codec", "Audio Codec", "Frames", "Duration")
        return any(properties.get(key) not in (None, "") for key in media_markers)

    def _resolve_clip_by_name(self, folder, clip_name):
        matches = [
            clip for clip in self._list_media_clips(folder) if self._clip_name(clip) == clip_name
        ]
        if not matches:
            return None, {
                "category": "object_not_found",
                "message": "Clip '%s' was not found in the current media pool folder." % clip_name,
                "details": {},
            }
        if len(matches) > 1:
            return None, {
                "category": "validation_error",
                "message": "Clip name '%s' is ambiguous in the current media pool folder." % clip_name,
                "details": {"clip_name": clip_name, "match_count": len(matches)},
            }
        return matches[0], None

    def _resolve_clip_by_media_pool_path(self, root_folder, current_folder, path_value):
        normalized_path = str(path_value or "").replace("\\", "/").strip()
        if not normalized_path:
            return None, {
                "category": "validation_error",
                "message": "Media pool clip path is required.",
                "details": {"path": path_value},
            }

        path_segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
        if not path_segments:
            return None, {
                "category": "validation_error",
                "message": "Media pool clip path is required.",
                "details": {"path": path_value},
            }

        clip_name = path_segments[-1]
        folder_path = "/".join(path_segments[:-1])
        is_absolute = normalized_path.startswith("/")
        if folder_path:
            folder_value = ("/" if is_absolute else "") + folder_path
            target_folder, error = self._resolve_media_folder_by_path(
                root_folder,
                current_folder,
                folder_value,
            )
            if error is not None:
                return None, error
        else:
            target_folder = root_folder if is_absolute else current_folder
        return self._resolve_clip_by_name(target_folder, clip_name)

    def _create_auto_timeline(self, project):
        media_pool = self._media_pool(project)
        if media_pool is None:
            return None

        suffix = 1
        while True:
            timeline_name = "Imported Timeline" if suffix == 1 else "Imported Timeline %s" % suffix
            if self._resolve_timeline_by_name(project, timeline_name) is None:
                timeline = self._safe_call(media_pool, "CreateEmptyTimeline", timeline_name)
                if timeline is None:
                    timeline = self._resolve_timeline_by_name(project, timeline_name)
                return timeline
            suffix += 1

    def _timeline_item_name(self, item):
        name = self._safe_call(item, "GetName")
        if name:
            return str(name)
        media_pool_item = self._safe_call(item, "GetMediaPoolItem")
        return self._clip_name(media_pool_item)

    def _timeline_item_summary(
        self,
        item,
        item_index=None,
        track_type=None,
        track_index=None,
        fallback_name="Timeline Item",
    ):
        return {
            "item_index": item_index,
            "name": self._timeline_item_name(item) or fallback_name,
            "track_type": track_type,
            "track_index": track_index,
            "start_frame": self._timeline_item_frame(item, "GetStart"),
            "end_frame": self._timeline_item_frame(item, "GetEnd"),
        }

    def _timeline_item_frame(self, item, method_name):
        value = self._safe_call(item, method_name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _timeline_item_selector(self, item):
        track_data = self._safe_call(item, "GetTrackTypeAndIndex")
        if isinstance(track_data, (list, tuple)) and len(track_data) >= 2:
            try:
                return {
                    "track_type": str(track_data[0]),
                    "track_index": int(track_data[1]),
                    "item_index": None,
                }
            except (TypeError, ValueError):
                pass
        return {"track_type": None, "track_index": None, "item_index": None}

    def _resolved_timeline_item_summary(
        self,
        timeline,
        item,
        track_type,
        track_index,
        fallback_name="Timeline Item",
    ):
        item_index = self._find_timeline_item_index(timeline, track_type, track_index, item)
        return self._timeline_item_summary(
            item,
            item_index=item_index,
            track_type=track_type,
            track_index=track_index,
            fallback_name=fallback_name,
        )

    def _find_timeline_item_index(self, timeline, track_type, track_index, item):
        items = self._safe_call(timeline, "GetItemListInTrack", track_type, track_index)
        if not isinstance(items, list):
            return None
        for item_index, candidate in enumerate(items):
            if candidate is item:
                return item_index
        return None

    def _timeline_item_source_range(self, item):
        source_start_frame = self._timeline_item_frame(item, "GetSourceStartFrame")
        source_end_frame = self._timeline_item_frame(item, "GetSourceEndFrame")
        if source_start_frame is None or source_end_frame is None:
            return None, None, {
                "message": "Timeline item source frame range is unavailable.",
                "details": {},
            }
        if source_start_frame >= source_end_frame:
            item_duration = self._timeline_item_frame(item, "GetDuration")
            if (
                source_start_frame == 0
                and source_end_frame == 0
                and item_duration is not None
                and item_duration > 0
            ):
                source_end_frame = item_duration
            else:
                return None, None, {
                    "message": "Timeline item source frame range is invalid.",
                    "details": {
                        "source_start_frame": source_start_frame,
                        "source_end_frame": source_end_frame,
                    },
                }
        return source_start_frame, source_end_frame, None

    def _timeline_track_entries(self, items):
        entries = []
        for item in items:
            start_frame = self._timeline_item_frame(item, "GetStart")
            end_frame = self._timeline_item_frame(item, "GetEnd")
            if start_frame is None or end_frame is None:
                continue
            entries.append({"item": item, "start_frame": start_frame, "end_frame": end_frame})
        entries.sort(key=lambda value: (value["start_frame"], value["end_frame"]))
        return entries

    def _find_track_item_covering_frame(self, items, frame):
        for entry in self._timeline_track_entries(items):
            if entry["start_frame"] < frame and frame < entry["end_frame"]:
                return entry
        return None

    def _resolve_gap_range(self, items, frame_from, frame_to):
        sorted_entries = self._timeline_track_entries(items)
        if not sorted_entries:
            return None, {
                "category": "object_not_found",
                "message": "No gaps were found on the requested track.",
                "details": {"frame_from": frame_from},
            }

        previous_end = None
        for index, entry in enumerate(sorted_entries):
            start_frame = entry["start_frame"]
            if previous_end is not None and start_frame > previous_end:
                gap_start = previous_end
                gap_end = start_frame
                if frame_from >= gap_start and frame_from < gap_end:
                    resolved_frame_to = gap_end if frame_to is None else frame_to
                    if resolved_frame_to > gap_end:
                        return None, {
                            "category": "validation_error",
                            "message": "Requested gap range extends into a timeline item.",
                            "details": {
                                "frame_from": frame_from,
                                "frame_to": resolved_frame_to,
                                "gap_end": gap_end,
                            },
                        }
                    return {
                        "frame_from": frame_from,
                        "frame_to": resolved_frame_to,
                        "duration": resolved_frame_to - frame_from,
                        "following_items": sorted_entries[index:],
                    }, None
                if frame_to is not None and frame_from == gap_start and frame_to <= gap_end:
                    return {
                        "frame_from": frame_from,
                        "frame_to": frame_to,
                        "duration": frame_to - frame_from,
                        "following_items": sorted_entries[index:],
                    }, None
            previous_end = entry["end_frame"]
        return None, {
            "category": "object_not_found",
            "message": "No gap matching the requested range was found on the requested track.",
            "details": {"frame_from": frame_from, "frame_to": frame_to},
        }

    def _recreate_shifted_items(self, project, timeline, shifted_items):
        if not shifted_items:
            return 0, None

        media_pool = self._media_pool(project)
        if media_pool is None:
            return 0, {
                "category": "object_not_found",
                "message": "Current media pool is not available.",
                "details": {},
            }

        ordered = list(shifted_items)
        moving_left = False
        for shift in ordered:
            current_start = self._timeline_item_frame(shift["item"], "GetStart")
            target_start = int(shift["record_frame"])
            if current_start is not None and target_start < current_start:
                moving_left = True
                break
        ordered.sort(
            key=lambda value: self._timeline_item_frame(value["item"], "GetStart") or 0,
            reverse=not moving_left,
        )
        shifted_count = 0
        self._safe_call(project, "SetCurrentTimeline", timeline)
        for shift in ordered:
            item = shift["item"]
            media_pool_item = self._safe_call(item, "GetMediaPoolItem")
            if media_pool_item is None:
                return 0, {
                    "category": "execution_failure",
                    "message": "Timeline item cannot be recreated because its media pool item is unavailable.",
                    "details": {},
                }
            source_start_frame, source_end_frame, range_error = self._timeline_item_source_range(item)
            if range_error is not None:
                return 0, {
                    "category": "execution_failure",
                    "message": range_error["message"],
                    "details": range_error.get("details"),
                }
            selector = self._timeline_item_selector(item)
            track_type = selector.get("track_type")
            track_index = selector.get("track_index")
            if track_type not in ("video", "audio") or track_index is None:
                return 0, {
                    "category": "execution_failure",
                    "message": "Timeline item track metadata is unavailable.",
                    "details": {},
                }
            clip_info = {
                "mediaPoolItem": media_pool_item,
                "startFrame": source_start_frame,
                "endFrame": source_end_frame,
                "recordFrame": int(shift["record_frame"]),
                "trackIndex": int(track_index),
                "mediaType": 2 if track_type == "audio" else 1,
            }
            appended_items = self._safe_call(media_pool, "AppendToTimeline", [clip_info])
            if not isinstance(appended_items, list) or len(appended_items) != 1:
                return shifted_count, {
                    "category": "execution_failure",
                    "message": "Resolve failed to recreate the requested timeline items.",
                    "details": {"requested_count": len(shifted_items), "completed_count": shifted_count},
                }
            deleted = bool(self._safe_call(timeline, "DeleteClips", [item], False))
            if not deleted:
                return shifted_count, {
                    "category": "execution_failure",
                    "message": "Resolve recreated a timeline item but failed to delete the source item.",
                    "details": {"requested_count": len(shifted_items), "completed_count": shifted_count},
                }
            shifted_count += 1
        return shifted_count, None

    def _maybe_add_technical_marker(self, timeline, frame, name, add_marker):
        if not add_marker:
            return None, []
        added = bool(self._safe_call(timeline, "AddMarker", int(frame), "Blue", name, "", 1, ""))
        if not added:
            return None, ["technical_marker_add_failed"]
        return {
            "frame": int(frame),
            "color": "Blue",
            "name": name,
            "note": None,
            "duration": 1,
            "custom_data": "",
        }, []

    def _ensure_timeline_tracks(self, timeline, required_track_indexes):
        for track_type in ("video", "audio"):
            required_index = int(required_track_indexes.get(track_type, 0) or 0)
            if required_index < 1:
                continue

            current_count = int(self._safe_call(timeline, "GetTrackCount", track_type) or 0)
            while current_count < required_index:
                created = bool(
                    self._safe_call(
                        timeline,
                        "AddTrack",
                        track_type,
                        {"index": current_count + 1},
                    )
                )
                if not created:
                    return False, "Resolve failed to create %s track %s." % (
                        track_type,
                        current_count + 1,
                    )
                current_count = int(self._safe_call(timeline, "GetTrackCount", track_type) or 0)
        return True, None

    def _timeline_track_counts(self, timeline, track_type):
        track_count = self._safe_call(timeline, "GetTrackCount", track_type) or 0
        item_count = 0
        for track_index in range(1, int(track_count) + 1):
            items = self._safe_call(timeline, "GetItemListInTrack", track_type, track_index)
            if isinstance(items, list):
                item_count += len(items)
        return int(track_count), item_count

    def _resolve_track_payload(self, command, resolve):
        current_project = self._current_project(resolve)
        if current_project is None:
            return None, self._failure(
                command["request_id"],
                "no_project_open",
                "No current project is open in Resolve.",
            )

        timeline_name = command["target"].get("timeline")
        if timeline_name:
            timeline = self._resolve_timeline_by_name(current_project, str(timeline_name))
        else:
            timeline = self._safe_call(current_project, "GetCurrentTimeline")

        if timeline is None:
            if timeline_name:
                return None, self._failure(
                    command["request_id"],
                    "object_not_found",
                    "Timeline '%s' was not found." % timeline_name,
                )
            return None, self._failure(
                command["request_id"],
                "no_current_timeline",
                "No current timeline is active in Resolve.",
            )

        track_type = str(command["payload"].get("track_type") or "").strip().lower()
        if track_type not in ("video", "audio"):
            return None, self._failure(
                command["request_id"],
                "validation_error",
                "Track type must be 'video' or 'audio'.",
            )

        try:
            track_index = int(command["payload"].get("track_index"))
        except (TypeError, ValueError):
            return None, self._failure(
                command["request_id"],
                "validation_error",
                "Track index must be an integer.",
            )

        if track_index < 1:
            return None, self._failure(
                command["request_id"],
                "validation_error",
                "Track index must be at least 1.",
            )

        track_count = self._safe_call(timeline, "GetTrackCount", track_type) or 0
        if track_index > int(track_count):
            return None, self._failure(
                command["request_id"],
                "object_not_found",
                "Track %s %s was not found." % (track_type, track_index),
                details={"track_type": track_type, "track_index": track_index},
            )

        items = self._safe_call(timeline, "GetItemListInTrack", track_type, track_index)
        if not isinstance(items, list):
            items = []
        return {
            "project": current_project,
            "timeline": timeline,
            "track_type": track_type,
            "track_index": track_index,
            "items": items,
        }, None

    def _resolve_timeline_item(self, command, resolve):
        track_data, failure = self._resolve_track_payload(command, resolve)
        if failure is not None:
            return None, failure

        try:
            item_index = int(command["payload"].get("item_index"))
        except (TypeError, ValueError):
            return None, self._failure(
                command["request_id"],
                "validation_error",
                "Item index must be an integer.",
            )
        if item_index < 0:
            return None, self._failure(
                command["request_id"],
                "validation_error",
                "Item index must be zero or greater.",
            )
        if item_index >= len(track_data["items"]):
            return None, self._failure(
                command["request_id"],
                "object_not_found",
                "Timeline item %s was not found on track %s %s."
                % (item_index, track_data["track_type"], track_data["track_index"]),
                details={
                    "track_type": track_data["track_type"],
                    "track_index": track_data["track_index"],
                    "item_index": item_index,
                },
            )
        return {
            "project": track_data["project"],
            "timeline": track_data["timeline"],
            "track_type": track_data["track_type"],
            "track_index": track_data["track_index"],
            "item_index": item_index,
            "item": track_data["items"][item_index],
        }, None

    def _timeline_markers(self, timeline):
        markers_by_frame = self._timeline_markers_by_frame(timeline)
        frames = list(markers_by_frame.keys())
        frames.sort()
        return [markers_by_frame[frame] for frame in frames]

    def _timeline_markers_by_frame(self, timeline):
        raw_markers = self._safe_call(timeline, "GetMarkers")
        if not isinstance(raw_markers, dict):
            return {}

        markers = {}
        for frame_key, marker_payload in raw_markers.items():
            try:
                frame_value = int(frame_key)
            except (TypeError, ValueError):
                continue

            payload = marker_payload if isinstance(marker_payload, dict) else {}
            duration = payload.get("duration")
            try:
                duration_value = int(duration) if duration is not None else None
            except (TypeError, ValueError):
                duration_value = None

            markers[frame_value] = {
                "frame": frame_value,
                "color": self._optional_string(payload.get("color")),
                "name": self._optional_string(payload.get("name")),
                "note": self._optional_string(payload.get("note")),
                "duration": duration_value,
                "custom_data": self._optional_string(payload.get("custom_data")),
            }
        return markers

    @staticmethod
    def _optional_string(value):
        if value is None:
            return None
        return str(value)
