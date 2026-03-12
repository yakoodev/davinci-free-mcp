import json
from pathlib import Path

from davinci_free_mcp.backend.executor_status import read_executor_status
from davinci_free_mcp.config import AppSettings


def build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(runtime_dir=tmp_path)


def test_read_executor_status_reports_missing_file(tmp_path: Path) -> None:
    status = read_executor_status(build_settings(tmp_path))

    assert status["available"] is False
    assert status["state"] == "missing"


def test_read_executor_status_reports_error_state(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    status_path = settings.runtime_dir / "status" / "executor_status.json"
    lock_path = settings.runtime_dir / "status" / "executor.lock.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(
        json.dumps(
            {
                "running": False,
                "mode": "console",
                "instance_id": "abc12345",
                "last_poll_at": "2026-03-12T09:42:27Z",
                "last_error": "fatal executor error",
            }
        ),
        encoding="utf-8",
    )
    lock_path.write_text(
        json.dumps(
            {
                "instance_id": "abc12345",
                "instance_started_at": "2026-03-12T09:40:00Z",
                "bridge_mode": "file_queue",
                "token": "lock-token",
            }
        ),
        encoding="utf-8",
    )

    status = read_executor_status(settings)

    assert status["available"] is True
    assert status["state"] == "error"
    assert status["executor_runtime"]["status_matches_lock"] is True
