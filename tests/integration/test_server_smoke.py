import asyncio
from pathlib import Path

import pytest


def test_create_server_smoke() -> None:
    pytest.importorskip("mcp")

    from davinci_free_mcp.config import AppSettings
    from davinci_free_mcp.server.main import create_server

    server = create_server(settings=AppSettings())

    assert server is not None

    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}
    assert {
        "resolve_health",
        "project_current",
        "project_list",
        "project_manager_folder_list",
        "project_manager_folder_open",
        "project_manager_folder_up",
        "project_manager_folder_path",
        "project_open",
        "timeline_list",
        "timeline_current",
        "timeline_create_empty",
        "timeline_set_current",
        "media_pool_list",
        "media_pool_folder_open",
        "media_pool_folder_create",
        "media_pool_folder_up",
        "media_pool_folder_root",
        "media_pool_folder_path",
        "media_pool_folder_list_recursive",
        "media_pool_folder_open_path",
        "media_import",
        "media_clip_inspect",
        "media_clip_inspect_path",
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
        "timeline_append_clips",
        "timeline_clips_place",
        "timeline_create_from_clips",
        "timeline_build_from_paths",
        "timeline_items_list",
        "timeline_track_items_list",
        "timeline_track_inspect",
        "timeline_item_inspect",
        "timeline_item_delete",
        "timeline_item_properties_get",
        "timeline_item_properties_set",
        "timeline_item_animation_preset_apply",
        "timeline_item_animation_clear",
        "timeline_item_move",
        "timeline_item_split",
        "timeline_item_set_source_range",
        "timeline_image_place_animated",
        "timeline_gap_close",
        "timeline_remove_gaps",
        "timeline_insert_gap",
        "timeline_inspect",
        "marker_add",
        "marker_list",
        "marker_inspect",
        "marker_list_range",
        "marker_delete",
    } <= tool_names


def test_create_server_loads_enabled_custom_modules() -> None:
    pytest.importorskip("mcp")

    from davinci_free_mcp.config import AppSettings
    from davinci_free_mcp.server.main import create_server

    server = create_server(
        settings=AppSettings(enabled_modules="template_custom,cs2_clips"),
    )

    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "template_custom_module_info" in tool_names
    assert "cs2_list_candidate_events" in tool_names
    assert "cs2_build_edit_plan" in tool_names


def test_create_server_loads_external_plugin_modules(tmp_path: Path) -> None:
    pytest.importorskip("mcp")

    from davinci_free_mcp.config import AppSettings
    from davinci_free_mcp.server.main import create_server

    repo_dir = tmp_path / "external_sample"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "plugin_module.py").write_text(
        "\n".join(
            [
                'from davinci_free_mcp.contracts import ModuleDescriptor',
                'module_id = "external_sample"',
                "",
                "def describe_module():",
                "    return ModuleDescriptor(",
                '        module_id="external_sample",',
                '        display_name="External Sample",',
                "        enabled_by_default=False,",
                '        kind="domain",',
                '        tools=["external_sample_info"],',
                "    )",
                "",
                "def register_tools(server, backend_service, settings):",
                "    @server.tool()",
                "    def external_sample_info():",
                '        return {"ok": True}',
                "",
            ]
        ),
        encoding="utf-8",
    )

    server = create_server(
        settings=AppSettings(modules_repos_dir=tmp_path),
    )

    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "external_sample_info" in tool_names
