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
            "The current toolset exposes low-level project, media, and timeline tools."
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
    def project_open(project_name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a project by name in the current Resolve database context."""

        return backend_service.project_open(project_name, timeout_ms).model_dump(
            mode="json"
        )

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

        return backend_service.timeline_create_empty(name, timeout_ms).model_dump(
            mode="json"
        )

    @server.tool()
    def timeline_set_current(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Switch the current timeline in the open project."""

        return backend_service.timeline_set_current(name, timeout_ms).model_dump(
            mode="json"
        )

    @server.tool()
    def media_pool_list(timeout_ms: int = 5000) -> dict[str, object]:
        """List the current media pool folder contents."""

        return backend_service.media_pool_list(timeout_ms).model_dump(mode="json")

    @server.tool()
    def media_pool_folder_open(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a direct child media pool folder from the current folder context."""

        return backend_service.media_pool_folder_open(name, timeout_ms).model_dump(
            mode="json"
        )

    @server.tool()
    def media_pool_folder_create(name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Create a direct child media pool folder and switch into it."""

        return backend_service.media_pool_folder_create(name, timeout_ms).model_dump(
            mode="json"
        )

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
    def media_pool_folder_open_path(path: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Open a media pool folder by relative or absolute path."""

        return backend_service.media_pool_folder_open_path(path, timeout_ms).model_dump(
            mode="json"
        )

    @server.tool()
    def media_import(paths: list[str], timeout_ms: int = 5000) -> dict[str, object]:
        """Import files or folders into the current media pool folder."""

        return backend_service.media_import(paths, timeout_ms).model_dump(mode="json")

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
    def marker_list(
        timeline_name: str | None = None,
        timeout_ms: int = 5000,
    ) -> dict[str, object]:
        """List markers on the current or specified timeline."""

        return backend_service.marker_list(
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

    @server.tool()
    def media_clip_inspect(clip_name: str, timeout_ms: int = 5000) -> dict[str, object]:
        """Inspect a clip in the current media pool folder."""

        return backend_service.media_clip_inspect(clip_name, timeout_ms).model_dump(
            mode="json"
        )

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
