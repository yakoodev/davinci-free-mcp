"""Manual diagnostics for the first vertical slice."""

from __future__ import annotations

import json

from davinci_free_mcp.backend.executor_status import read_executor_status
from davinci_free_mcp.backend.service import ResolveBackendService
from davinci_free_mcp.bridge import create_bridge
from davinci_free_mcp.config import AppSettings


def main() -> None:
    settings = AppSettings()
    backend = ResolveBackendService(create_bridge(settings), settings)
    output = {
        "resolve_health": backend.resolve_health().model_dump(mode="json"),
        "project_current": backend.project_current().model_dump(mode="json"),
        "project_list": backend.project_list().model_dump(mode="json"),
        "timeline_list": backend.timeline_list().model_dump(mode="json"),
        "executor_status": read_executor_status(settings),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
