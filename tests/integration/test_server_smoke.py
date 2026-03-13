import asyncio

import pytest


def test_create_server_smoke() -> None:
    pytest.importorskip("mcp")

    from davinci_free_mcp.server.main import create_server

    server = create_server()

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
        "timeline_append_clips",
        "timeline_clips_place",
        "timeline_create_from_clips",
        "timeline_items_list",
        "timeline_track_items_list",
        "timeline_track_inspect",
        "timeline_item_inspect",
        "timeline_item_delete",
        "timeline_inspect",
        "marker_add",
        "marker_list",
        "marker_inspect",
        "marker_list_range",
        "marker_delete",
    } <= tool_names
