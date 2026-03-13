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
        "project_open",
        "timeline_list",
        "timeline_current",
        "timeline_create_empty",
        "timeline_set_current",
        "media_pool_list",
        "media_pool_folder_open",
        "media_import",
        "timeline_append_clips",
        "timeline_items_list",
        "marker_add",
    } <= tool_names
