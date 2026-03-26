"""Minimal MCP server for the first vertical slice."""

from __future__ import annotations

import argparse
from typing import Any

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import create_bridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.modules import discover_available_modules

MCP_IMPORT_ERROR: Exception | None = None
MCP_VARIANT: str | None = None

try:
    from mcp.server.fastmcp import FastMCP as MCPApp
except Exception as fastmcp_error:
    try:
        from mcp.server.mcpserver import MCPServer as MCPApp
    except Exception as mcpserver_error:
        MCPApp = None
        MCP_IMPORT_ERROR = mcpserver_error
    else:
        MCP_VARIANT = "mcpserver"
        MCP_IMPORT_ERROR = None
else:
    MCP_VARIANT = "fastmcp"
    MCP_IMPORT_ERROR = None


def register_core_tools(server: Any, backend_service: ResolveBackendService, settings: AppSettings) -> None:
    """Register the shared low-level Resolve and generic media-analysis tools."""

    @server.tool()
    def resolve_health(timeout_ms: int = 5000) -> dict[str, object]:
        """Return bridge, executor, Resolve, and project health information."""

        return backend_service.resolve_health(timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_current(timeout_ms: int = 5000) -> dict[str, object]:
        """Return the current Resolve project context."""

        return backend_service.project_current(timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_list(timeout_ms: int = 5000) -> dict[str, object]:
        """Return projects in the current project-manager folder context."""

        return backend_service.project_list(timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_manager_folder_list(timeout_ms: int = 5000) -> dict[str, object]:
        """Return the current project-manager folder and its direct child folders/projects."""

        return backend_service.project_manager_folder_list(timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_manager_folder_open(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a direct child folder in the current project-manager context."""

        return backend_service.project_manager_folder_open(name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_manager_folder_up(timeout_ms: int = 5000) -> dict[str, object]:
        """Move the project-manager context to the parent folder."""

        return backend_service.project_manager_folder_up(timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_manager_folder_path(timeout_ms: int = 5000) -> dict[str, object]:
        """Return the current project-manager folder with breadcrumb path."""

        return backend_service.project_manager_folder_path(timeout_ms).model_dump(mode="json")

    @server.tool()
    def project_open(project_name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a project by name in the current Resolve database context."""

        return backend_service.project_open(project_name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def timeline_list(timeout_ms: int = 5000) -> dict[str, object]:
        """Return timelines for the current project."""

        return backend_service.timeline_list(timeout_ms).model_dump(mode="json")

    @server.tool()
    def timeline_current(timeout_ms: int = 5000) -> dict[str, object]:
        """Return the current timeline for the open project."""

        return backend_service.timeline_current(timeout_ms).model_dump(mode="json")

    @server.tool()
    def timeline_create_empty(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Create an empty timeline in the current project."""

        return backend_service.timeline_create_empty(name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def timeline_set_current(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Switch the current timeline in the open project."""

        return backend_service.timeline_set_current(name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_list(timeout_ms: int = 5000) -> dict[str, object]:
        """List the current media pool folder contents."""

        return backend_service.media_pool_list(timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_open(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a direct child media pool folder from the current folder context."""

        return backend_service.media_pool_folder_open(name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_create(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Create a direct child media pool folder and switch into it."""

        return backend_service.media_pool_folder_create(name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_up(timeout_ms: int = 5000) -> dict[str, object]:
        """Move the current media pool folder context to its parent folder."""

        return backend_service.media_pool_folder_up(timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_root(timeout_ms: int = 5000) -> dict[str, object]:
        """Switch the current media pool folder context to the root folder."""

        return backend_service.media_pool_folder_root(timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_path(timeout_ms: int = 5000) -> dict[str, object]:
        """Return the current media pool folder, listing, and breadcrumb path."""

        return backend_service.media_pool_folder_path(timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_list_recursive(
        max_depth: int | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return the current media pool folder tree recursively."""

        return backend_service.media_pool_folder_list_recursive(
            max_depth=max_depth,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_open_path(path: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a media pool folder by relative or absolute path."""

        return backend_service.media_pool_folder_open_path(path, timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_import(paths: list[str], timeout_ms: int = 5000) -> dict[str, object]:
        """Import files or folders into the current media pool folder."""

        return backend_service.media_import(paths, timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_clip_inspect(clip_name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Inspect a clip in the current media pool folder."""

        return backend_service.media_clip_inspect(clip_name, timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_clip_inspect_path(path: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Inspect a clip by relative or absolute media-pool path."""

        return backend_service.media_clip_inspect_path(path, timeout_ms).model_dump(mode="json")

    @server.tool()
    def audio_probe(path: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Inspect local audio metadata and high-level audio flags."""

        return backend_service.audio_probe(path, timeout_ms).model_dump(mode="json")

    @server.tool()
    def audio_transcribe_segments(
        path: str,
        language: str | None = None,
        max_segment_sec: float = 15,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Transcribe local audio into speech segments when transcript data is available."""

        return backend_service.audio_transcribe_segments(
            path,
            language=language,
            max_segment_sec=max_segment_sec,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def audio_detect_events(
        path: str,
        min_silence_sec: float = 0.7,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Detect low-level events in local audio without transcript output."""

        return backend_service.audio_detect_events(
            path,
            min_silence_sec=min_silence_sec,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_probe(path: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Inspect local video metadata and track presence."""

        return backend_service.video_probe(path, timeout_ms).model_dump(mode="json")

    @server.tool()
    def video_detect_shots(
        path: str,
        cut_threshold: float = 0.35,
        min_shot_sec: float = 1.0,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Detect scene-like shot ranges for local video."""

        return backend_service.video_detect_shots(
            path,
            cut_threshold=cut_threshold,
            min_shot_sec=min_shot_sec,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_sample_frames(
        path: str,
        start: float = 0.0,
        end: float | None = None,
        fps: float = 1.0,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Extract full-frame samples from local video at a fixed rate."""

        return backend_service.video_sample_frames(
            path,
            start=start,
            end=end,
            fps=fps,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_extract_roi_frames(
        path: str,
        x: int,
        y: int,
        width: int,
        height: int,
        start: float = 0.0,
        end: float | None = None,
        fps: float = 1.0,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Extract ROI-focused frame samples from local video at a fixed rate."""

        return backend_service.video_extract_roi_frames(
            path,
            x=x,
            y=y,
            width=width,
            height=height,
            start=start,
            end=end,
            fps=fps,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_build_contact_sheet(
        path: str,
        frames_dir: str,
        columns: int = 4,
        rows: int = 4,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Build contact-sheet artifacts from previously extracted frame samples."""

        return backend_service.video_build_contact_sheet(
            path,
            frames_dir=frames_dir,
            columns=columns,
            rows=rows,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_detect_overlay_events(
        path: str,
        frames_dir: str,
        min_change_ratio: float = 0.05,
        min_event_gap_sec: float = 0.5,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Build generic frame-change candidates from sampled overlay or ROI frames."""

        return backend_service.video_detect_overlay_events(
            path,
            frames_dir=frames_dir,
            min_change_ratio=min_change_ratio,
            min_event_gap_sec=min_event_gap_sec,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_extract_segment_screenshots(
        path: str,
        segments: list[dict[str, object]],
        screenshots_per_segment: int = 1,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Extract screenshots for explicit local video time ranges."""

        return backend_service.video_extract_segment_screenshots(
            path,
            segments=segments,
            screenshots_per_segment=screenshots_per_segment,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_segment_from_speech(
        path: str,
        language: str | None = None,
        max_segment_sec: float = 15,
        screenshots_per_segment: int = 1,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Build speech-driven local video segments with screenshots."""

        return backend_service.video_segment_from_speech(
            path,
            language=language,
            max_segment_sec=max_segment_sec,
            screenshots_per_segment=screenshots_per_segment,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_segment_visual(
        path: str,
        segment_mode: str = "shots",
        window_sec: float = 8,
        screenshots_per_segment: int = 1,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Build visual-only local video segments with screenshots."""

        return backend_service.video_segment_visual(
            path,
            segment_mode=segment_mode,
            window_sec=window_sec,
            screenshots_per_segment=screenshots_per_segment,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def video_segment_audio_visual(
        path: str,
        min_silence_sec: float = 0.7,
        screenshots_per_segment: int = 1,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Build audio-event-aligned local video segments with screenshots."""

        return backend_service.video_segment_audio_visual(
            path,
            min_silence_sec=min_silence_sec,
            screenshots_per_segment=screenshots_per_segment,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def edit_plan_from_candidates(
        source_path: str,
        candidates: list[dict[str, object]],
        target_timeline_name: str | None = None,
        pre_roll_sec: float = 2.0,
        post_roll_sec: float = 1.5,
        min_segment_sec: float = 2.5,
        max_segment_sec: float = 6.0,
        merge_gap_sec: float = 1.0,
    ) -> dict[str, object]:
        """Build a machine-readable rough-cut proposal from candidate events."""

        return backend_service.edit_plan_from_candidates(
            source_path=source_path,
            candidates=candidates,
            target_timeline_name=target_timeline_name,
            pre_roll_sec=pre_roll_sec,
            post_roll_sec=post_roll_sec,
            min_segment_sec=min_segment_sec,
            max_segment_sec=max_segment_sec,
            merge_gap_sec=merge_gap_sec,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_append_clips(
        clip_names: list[str],
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Append clips from the current media pool folder into a timeline."""

        return backend_service.timeline_append_clips(
            clip_names,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_clips_place(
        placements: list[dict[str, object]],
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Place clips by `clip_name` or `media_pool_path` into the target or current timeline."""

        return backend_service.timeline_clips_place(
            placements,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_create_from_clips(
        name: str,
        clip_names: list[str],
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Create a new timeline from clips in the current media pool folder."""

        return backend_service.timeline_create_from_clips(
            name,
            clip_names,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_build_from_paths(
        name: str,
        paths: list[str],
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Import media paths and build a new timeline from the imported clips in one step."""

        return backend_service.timeline_build_from_paths(
            name,
            paths,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_items_list(
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return grouped timeline items for the target or current timeline."""

        return backend_service.timeline_items_list(
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_inspect(
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return summary counts for the target or current timeline."""

        return backend_service.timeline_inspect(
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_track_items_list(
        track_type: str,
        track_index: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return items for one track on the target or current timeline."""

        return backend_service.timeline_track_items_list(
            track_type,
            track_index,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_track_inspect(
        track_type: str,
        track_index: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return summary counts and bounds for one track on the target or current timeline."""

        return backend_service.timeline_track_inspect(
            track_type,
            track_index,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_inspect(
        track_type: str,
        track_index: int,
        item_index: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Inspect one timeline item by track and item index."""

        return backend_service.timeline_item_inspect(
            track_type,
            track_index,
            item_index,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_delete(
        track_type: str,
        track_index: int,
        item_index: int,
        ripple: bool = False,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Delete one timeline item by track and item index, with optional ripple delete."""

        return backend_service.timeline_item_delete(
            track_type,
            track_index,
            item_index,
            ripple=ripple,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_properties_get(
        track_type: str,
        track_index: int,
        item_index: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return supported clip properties for one timeline item."""

        return backend_service.timeline_item_properties_get(
            track_type,
            track_index,
            item_index,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_properties_set(
        track_type: str,
        track_index: int,
        item_index: int,
        properties: dict[str, object],
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Set supported static clip properties for one timeline item."""

        return backend_service.timeline_item_properties_set(
            track_type,
            track_index,
            item_index,
            properties,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_animation_preset_apply(
        track_type: str,
        track_index: int,
        item_index: int,
        preset: str,
        timeline_name: str | None = None,
        duration_frames: int | None = None,
        intensity: float | None = None,
        direction: str | None = None,
        easing: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Apply one Fusion-backed animation preset to a video timeline item."""

        return backend_service.timeline_item_animation_preset_apply(
            track_type,
            track_index,
            item_index,
            preset,
            timeline_name=timeline_name,
            duration_frames=duration_frames,
            intensity=intensity,
            direction=direction,
            easing=easing,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_animation_clear(
        track_type: str,
        track_index: int,
        item_index: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Remove DFMCP-managed animation Fusion comps from one timeline item."""

        return backend_service.timeline_item_animation_clear(
            track_type,
            track_index,
            item_index,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_move(
        track_type: str,
        track_index: int,
        item_index: int,
        record_frame: int,
        target_track_type: str | None = None,
        target_track_index: int | None = None,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Move one timeline item by recreating it at a new location and deleting the source item."""

        return backend_service.timeline_item_move(
            track_type,
            track_index,
            item_index,
            record_frame,
            target_track_type=target_track_type,
            target_track_index=target_track_index,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_split(
        track_type: str,
        track_index: int,
        item_index: int,
        record_frame: int,
        timeline_name: str | None = None,
        add_marker: bool = True,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Split one timeline item at a record frame on the target or current timeline."""

        return backend_service.timeline_item_split(
            track_type,
            track_index,
            item_index,
            record_frame,
            timeline_name=timeline_name,
            add_marker=add_marker,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_image_place_animated(
        path: str,
        record_frame: int,
        track_index: int,
        duration_frames: int,
        preset: str,
        timeline_name: str | None = None,
        opacity: float | None = None,
        scale: float | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Import one image, place it on the timeline, and apply an animation preset."""

        return backend_service.timeline_image_place_animated(
            path,
            record_frame,
            track_index,
            duration_frames,
            preset,
            timeline_name=timeline_name,
            opacity=opacity,
            scale=scale,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_item_set_source_range(
        track_type: str,
        track_index: int,
        item_index: int,
        source_start_frame: int,
        source_end_frame: int,
        timeline_name: str | None = None,
        add_marker: bool = True,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Replace one timeline item with the same placement but a different source range."""

        return backend_service.timeline_item_set_source_range(
            track_type,
            track_index,
            item_index,
            source_start_frame,
            source_end_frame,
            timeline_name=timeline_name,
            add_marker=add_marker,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_gap_close(
        track_type: str,
        track_index: int,
        frame_from: int,
        frame_to: int | None = None,
        timeline_name: str | None = None,
        add_marker: bool = True,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Close one gap on the requested track with ripple movement of later items."""

        return backend_service.timeline_gap_close(
            track_type,
            track_index,
            frame_from,
            frame_to=frame_to,
            timeline_name=timeline_name,
            add_marker=add_marker,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_remove_gaps(
        track_type: str,
        track_index: int,
        timeline_name: str | None = None,
        add_marker: bool = True,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Compact one track by removing all internal gaps."""

        return backend_service.timeline_remove_gaps(
            track_type,
            track_index,
            timeline_name=timeline_name,
            add_marker=add_marker,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def timeline_insert_gap(
        track_type: str,
        track_index: int,
        at_frame: int,
        duration: int,
        timeline_name: str | None = None,
        add_marker: bool = True,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Insert a gap on one track by shifting later items to the right."""

        return backend_service.timeline_insert_gap(
            track_type,
            track_index,
            at_frame,
            duration,
            timeline_name=timeline_name,
            add_marker=add_marker,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def marker_add(
        frame: int,
        name: str,
        timeline_name: str | None = None,
        note: str | None = None,
        color: str | None = None,
        duration: int = 1,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Add a timeline marker to the current or specified timeline."""

        return backend_service.marker_add(
            frame,
            name,
            timeline_name=timeline_name,
            note=note,
            color=color,
            duration=duration,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def marker_list(timeline_name: str | None = None, timeout_ms: int = 5000) -> dict[str, object]:
        """List markers on the current or specified timeline."""

        return backend_service.marker_list(
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def marker_inspect(
        frame: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Return one marker from the current or specified timeline by frame."""

        return backend_service.marker_inspect(
            frame,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def marker_list_range(
        frame_from: int | None = None,
        frame_to: int | None = None,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """List markers filtered to a frame range on the current or specified timeline."""

        return backend_service.marker_list_range(
            frame_from=frame_from,
            frame_to=frame_to,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")

    @server.tool()
    def marker_delete(
        frame: int,
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """Delete a marker from the current or specified timeline by frame."""

        return backend_service.marker_delete(
            frame,
            timeline_name=timeline_name,
            timeout_ms=timeout_ms,
        ).model_dump(mode="json")


def create_server(
    backend: ResolveBackendService | None = None,
    settings: AppSettings | None = None,
) -> Any:
    """Create the MCP server instance."""

    if MCPApp is None:
        raise RuntimeError(
            "The 'mcp' package is not available. Install project dependencies first."
        ) from MCP_IMPORT_ERROR

    app_settings = settings or AppSettings()
    backend_service = backend or ResolveBackendService(
        create_bridge(app_settings),
        app_settings,
    )

    server_kwargs = {
        "instructions": (
            "MCP-first bridge for DaVinci Resolve Free. "
            "The current toolset exposes low-level project, media, timeline, and generic media-analysis tools."
        ),
    }
    if MCP_VARIANT == "fastmcp":
        server_kwargs.update(
            {
                "json_response": app_settings.mcp_json_response,
                "stateless_http": app_settings.mcp_stateless_http,
                "streamable_http_path": app_settings.mcp_path,
            }
        )

    server = MCPApp("DavinciFreeMcp", **server_kwargs)
    discovery = discover_available_modules(app_settings)
    for warning in discovery.warnings:
        print(f"[modules] {warning}", file=sys.stderr)
    for module_info in discovery.modules:
        if not module_info.selected:
            continue
        module = module_info.module
        module.register_tools(server, backend_service, app_settings)
    return server


def main() -> None:
    """Run the MCP server."""

    parser = argparse.ArgumentParser(description="Run the DavinciFreeMcp server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=None,
        help="MCP transport to use.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host for HTTP transport.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP transport.",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="HTTP path for streamable HTTP transport.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    transport = args.transport or settings.mcp_transport
    host = args.host or settings.mcp_host
    port = args.port or settings.mcp_port
    path = args.path or settings.mcp_path

    server = create_server(settings=settings)
    if transport == "stdio":
        server.run(transport="stdio")
        return

    if MCP_VARIANT == "fastmcp":
        import uvicorn

        app = server.streamable_http_app()
        uvicorn.run(app, host=host, port=port)
        return

    server.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path=path,
        json_response=settings.mcp_json_response,
        stateless_http=settings.mcp_stateless_http,
    )


if __name__ == "__main__":
    main()
