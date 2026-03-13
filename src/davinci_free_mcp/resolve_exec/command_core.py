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
            "timeline_items_list": self._handle_timeline_items_list,
            "timeline_track_items_list": self._handle_timeline_track_items_list,
            "timeline_track_inspect": self._handle_timeline_track_inspect,
            "timeline_item_inspect": self._handle_timeline_item_inspect,
            "timeline_item_delete": self._handle_timeline_item_delete,
            "timeline_item_move": self._handle_timeline_item_move,
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
            if not clip_name:
                return self._failure(
                    command["request_id"],
                    "validation_error",
                    "Clip placement requires clip_name.",
                )
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
                    "name": clip_name,
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
