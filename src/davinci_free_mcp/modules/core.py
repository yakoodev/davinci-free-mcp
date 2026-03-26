"""Core built-in low-level MCP tools."""

from __future__ import annotations

from typing import Any

from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import ModuleDescriptor


module_id = "core"


def is_enabled(settings: AppSettings) -> bool:
    return True


def describe_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        module_id=module_id,
        display_name="Core Resolve Tools",
        enabled_by_default=True,
        kind="core",
        tools=[
            "resolve_health",
            "project_current",
            "timeline_current",
            "media_pool_list",
            "timeline_item_properties_get",
            "timeline_item_properties_set",
            "timeline_item_animation_preset_apply",
            "timeline_item_animation_clear",
            "timeline_image_place_animated",
            "audio_probe",
            "audio_transcribe_segments",
            "audio_detect_events",
            "video_probe",
            "video_detect_shots",
            "video_sample_frames",
            "video_extract_roi_frames",
            "video_build_contact_sheet",
            "video_detect_overlay_events",
            "video_extract_segment_screenshots",
            "video_segment_from_speech",
            "video_segment_visual",
            "video_segment_audio_visual",
            "edit_plan_from_candidates",
        ],
    )


def register_tools(server: Any, backend_service: Any, settings: AppSettings) -> None:
    from davinci_free_mcp.server.main import register_core_tools

    register_core_tools(server, backend_service, settings)
