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
        "timeline_list",
        "timeline_current",
        "timeline_create_empty",
        "media_pool_list",
        "media_import",
        "timeline_append_clips",
        "timeline_items_list",
    } <= tool_names
