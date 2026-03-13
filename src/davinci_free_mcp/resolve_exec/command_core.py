"""Shared Resolve command execution core.

This module must stay stdlib-only and Python-3.6-compatible because the
installer embeds its source into the Resolve bootstrap script.
"""

import copy


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
            "project_open": self._handle_project_open,
            "timeline_list": self._handle_timeline_list,
            "timeline_current": self._handle_timeline_current,
            "timeline_create_empty": self._handle_timeline_create_empty,
            "timeline_set_current": self._handle_timeline_set_current,
            "media_pool_list": self._handle_media_pool_list,
            "media_pool_folder_open": self._handle_media_pool_folder_open,
            "media_import": self._handle_media_import,
            "timeline_append_clips": self._handle_timeline_append_clips,
            "timeline_items_list": self._handle_timeline_items_list,
            "marker_add": self._handle_marker_add,
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
                },
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

    def _timeline_item_frame(self, item, method_name):
        value = self._safe_call(item, method_name)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
