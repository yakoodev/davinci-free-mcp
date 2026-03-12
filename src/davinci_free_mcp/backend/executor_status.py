"""Read and interpret executor status heartbeat."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from davinci_free_mcp.config import AppSettings


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_executor_status(settings: AppSettings | None = None, *, stale_after_seconds: int = 3) -> dict[str, object]:
    app_settings = settings or AppSettings()
    status_path = app_settings.runtime_dir / "status" / "executor_status.json"
    if not status_path.exists():
        return {
            "available": False,
            "state": "missing",
            "status_path": str(status_path),
            "fresh": False,
        }

    raw_data = json.loads(status_path.read_text(encoding="utf-8"))
    last_poll_at = _parse_iso_timestamp(raw_data.get("last_poll_at"))
    now = datetime.now(timezone.utc)
    fresh = False
    age_seconds = None
    if last_poll_at is not None:
        age_seconds = (now - last_poll_at).total_seconds()
        fresh = age_seconds <= stale_after_seconds

    running = bool(raw_data.get("running"))
    if not running:
        state = "stopped"
    elif fresh:
        state = "running"
    else:
        state = "stale"

    return {
        "available": True,
        "state": state,
        "fresh": fresh,
        "age_seconds": age_seconds,
        "status_path": str(status_path),
        "status": raw_data,
    }

