"""Read and interpret executor status heartbeat."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from davinci_free_mcp.config import AppSettings


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def read_executor_status(
    settings: AppSettings | None = None,
    *,
    stale_after_seconds: int = 3,
) -> dict[str, object]:
    app_settings = settings or AppSettings()
    status_path = app_settings.status_path
    lock_path = app_settings.lock_path
    if not status_path.exists():
        return {
            "available": False,
            "state": "missing",
            "status_path": str(status_path),
            "fresh": False,
            "executor_runtime": {
                "lock_present": lock_path.exists(),
                "lock_owner_instance_id": None,
                "status_instance_id": None,
                "status_matches_lock": False,
                "possible_duplicate_executor": False,
                "possible_stale_writer": False,
            },
        }

    raw_data = json.loads(status_path.read_text(encoding="utf-8"))
    lock_data = {}
    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            lock_data = {}

    last_poll_at = _parse_iso_timestamp(raw_data.get("last_poll_at"))
    now = datetime.now(timezone.utc)
    fresh = False
    age_seconds = None
    if last_poll_at is not None:
        age_seconds = (now - last_poll_at).total_seconds()
        fresh = age_seconds <= stale_after_seconds

    running = bool(raw_data.get("running"))
    last_error = str(raw_data.get("last_error") or "")
    if last_error and not running:
        state = "error"
    elif not running:
        state = "stopped"
    elif fresh:
        state = "running"
    else:
        state = "stale"

    status_instance_id = raw_data.get("instance_id")
    lock_owner_instance_id = lock_data.get("instance_id")
    resolve_connected = bool(((raw_data.get("resolve") or {}).get("connected")))
    status_matches_lock = bool(status_instance_id and lock_owner_instance_id and status_instance_id == lock_owner_instance_id)
    possible_duplicate_executor = lock_path.exists() and bool(status_instance_id) and bool(lock_owner_instance_id) and status_instance_id != lock_owner_instance_id
    possible_stale_writer = running and fresh and not resolve_connected and bool(lock_owner_instance_id)

    return {
        "available": True,
        "state": state,
        "fresh": fresh,
        "age_seconds": age_seconds,
        "status_path": str(status_path),
        "status": raw_data,
        "executor_runtime": {
            "lock_present": lock_path.exists(),
            "lock_owner_instance_id": lock_owner_instance_id,
            "status_instance_id": status_instance_id,
            "status_matches_lock": status_matches_lock,
            "possible_duplicate_executor": possible_duplicate_executor,
            "possible_stale_writer": possible_stale_writer,
            "lock_path": str(lock_path),
        },
    }
