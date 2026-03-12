"""Minimal MCP server for the first vertical slice."""

from __future__ import annotations

import argparse
from typing import Any

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import create_bridge
from davinci_free_mcp.config import AppSettings

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
            "The current toolset exposes low-level read-only project and timeline tools."
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
    def timeline_list(timeout_ms: int = 5000) -> dict[str, object]:
        """Return timelines for the current project."""

        return backend_service.timeline_list(timeout_ms).model_dump(mode="json")

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
