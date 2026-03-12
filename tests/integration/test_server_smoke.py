import pytest


def test_create_server_smoke() -> None:
    pytest.importorskip("mcp")

    from davinci_free_mcp.server.main import create_server

    server = create_server()

    assert server is not None
