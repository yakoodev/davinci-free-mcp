"""
Standalone DaVinci Resolve Free executor bootstrap.

Console-first version:
- writes structured status to runtime/status/executor_status.json
- writes logs to runtime/logs/resolve_executor.log
- prints human-readable lifecycle/activity/error messages to DaVinci Console
"""

import json
import os
import shutil
import time
import traceback
import uuid
from datetime import datetime

try:
    from pathlib import Path
except ImportError:
    print("[DFMCP] error | pathlib is required")
    raise


REPO_ROOT = Path(r"C:\Users\Yakoo\source\repos\DavinciFreeMcp")
RUNTIME_DIR = REPO_ROOT / "runtime"
REQUESTS_DIR = RUNTIME_DIR / "spool" / "requests"
RESULTS_DIR = RUNTIME_DIR / "spool" / "results"
DEADLETTER_DIR = RUNTIME_DIR / "spool" / "deadletter"
LOGS_DIR = RUNTIME_DIR / "logs"
STATUS_DIR = RUNTIME_DIR / "status"
STATUS_PATH = STATUS_DIR / "executor_status.json"
POLL_INTERVAL_MS = 150
HEARTBEAT_INTERVAL_SECONDS = 5.0


def ensure_dirs():
    for path in (REQUESTS_DIR, RESULTS_DIR, DEADLETTER_DIR, LOGS_DIR, STATUS_DIR):
        if not path.exists():
            path.mkdir(parents=True)


def log_line(text):
    ensure_dirs()
    log_path = LOGS_DIR / "resolve_executor.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("[%s] %s\n" % (timestamp, text))


def console_line(text):
    print(text)
    log_line(text)


def iso_now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def get_resolve():
    try:
        resolve = app.GetResolve()  # noqa: F821
        return resolve
    except Exception:
        return None


def atomic_write_json(path, payload):
    temp_path = Path(str(path) + ".%s.tmp" % uuid.uuid4().hex)
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    last_error = None
    for _ in range(5):
        try:
            os.replace(str(temp_path), str(path))
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.05)

    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        try:
            temp_path.unlink()
        except Exception:
            pass
        return
    except Exception:
        try:
            temp_path.unlink()
        except Exception:
            pass
        if last_error is not None:
            raise last_error
        raise


def best_effort_write_json(path, payload):
    try:
        atomic_write_json(path, payload)
        return True
    except Exception as exc:
        log_line("Non-fatal JSON write failure for %s: %s" % (path, exc))
        return False


def safe_call(obj, method_name):
    if obj is None:
        return None
    method = getattr(obj, method_name, None)
    if method is None:
        return None
    try:
        return method()
    except Exception:
        return None


def current_context():
    resolve = get_resolve()
    resolve_connected = resolve is not None
    product_name = safe_call(resolve, "GetProductName") if resolve_connected else None
    version = safe_call(resolve, "GetVersionString") if resolve_connected else None

    project_manager = safe_call(resolve, "GetProjectManager") if resolve_connected else None
    current_project = safe_call(project_manager, "GetCurrentProject") if project_manager is not None else None
    current_timeline = safe_call(current_project, "GetCurrentTimeline") if current_project is not None else None

    return {
        "resolve_connected": resolve_connected,
        "product_name": product_name,
        "version": version,
        "project_open": current_project is not None,
        "project_name": safe_call(current_project, "GetName") if current_project is not None else None,
        "timeline_available": current_timeline is not None,
        "timeline_name": safe_call(current_timeline, "GetName") if current_timeline is not None else None,
    }


def fresh_status_template():
    context = current_context()
    return {
        "running": True,
        "mode": "console",
        "started_at": iso_now(),
        "last_poll_at": None,
        "last_request_at": None,
        "last_request_id": "",
        "processed_count": 0,
        "last_error": "",
        "resolve": {
            "connected": context["resolve_connected"],
            "product_name": context["product_name"],
            "version": context["version"],
        },
        "project": {
            "open": context["project_open"],
            "name": context["project_name"],
        },
        "timeline": {
            "available": context["timeline_available"],
            "name": context["timeline_name"],
        },
        "bridge": {
            "adapter": "file_queue",
        },
    }


def load_status():
    ensure_dirs()
    if not STATUS_PATH.exists():
        return fresh_status_template()
    try:
        with STATUS_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return fresh_status_template()


def write_status(status):
    ensure_dirs()
    return best_effort_write_json(STATUS_PATH, status)


def update_status(
    *,
    running=None,
    last_poll=False,
    last_request_id=None,
    request_handled=False,
    last_error=None,
):
    status = load_status()
    context = current_context()

    if running is not None:
        status["running"] = running
    if last_poll:
        status["last_poll_at"] = iso_now()
    if last_request_id is not None:
        status["last_request_id"] = last_request_id
    if request_handled:
        status["last_request_at"] = iso_now()
        status["processed_count"] = int(status.get("processed_count", 0)) + 1
    if last_error is not None:
        status["last_error"] = last_error

    status["mode"] = "console"
    status["resolve"] = {
        "connected": context["resolve_connected"],
        "product_name": context["product_name"],
        "version": context["version"],
    }
    status["project"] = {
        "open": context["project_open"],
        "name": context["project_name"],
    }
    status["timeline"] = {
        "available": context["timeline_available"],
        "name": context["timeline_name"],
    }
    status["bridge"] = {"adapter": "file_queue"}
    write_status(status)
    return status


def format_context_summary():
    context = current_context()
    if not context["resolve_connected"]:
        return "resolve=not_ready"

    project_name = context["project_name"] or "-"
    if context["timeline_available"]:
        return "version=%s | project=%s | timeline=%s" % (
            context["version"] or "-",
            project_name,
            context["timeline_name"] or "-",
        )
    return "version=%s | project=%s | no current timeline" % (
        context["version"] or "-",
        project_name,
    )


def move_to_deadletter(request_path):
    ensure_dirs()
    target = DEADLETTER_DIR / request_path.name
    if target.exists():
        target.unlink()
    shutil.move(str(request_path), str(target))


def make_error(category, message, details=None):
    return {
        "category": category,
        "message": message,
        "details": details or {},
    }


def make_result(request_id, ok, data=None, error=None, warnings=None, meta=None):
    return {
        "request_id": request_id,
        "ok": ok,
        "data": data,
        "error": error,
        "warnings": warnings or [],
        "meta": meta or {"bridge": "file_queue"},
    }


def handle_resolve_health(request_id):
    resolve = get_resolve()
    if resolve is None:
        return make_result(
            request_id,
            False,
            error=make_error(
                "resolve_not_ready",
                "Resolve handle is not available in embedded environment.",
            ),
        )

    product_name = safe_call(resolve, "GetProductName")
    version = safe_call(resolve, "GetVersionString")

    project_manager = safe_call(resolve, "GetProjectManager")
    current_project = None
    if project_manager is not None:
        current_project = safe_call(project_manager, "GetCurrentProject")

    warnings = []
    project_name = None
    if current_project is not None:
        project_name = safe_call(current_project, "GetName")
    else:
        warnings.append("no_project_open")

    data = {
        "bridge": {
            "available": True,
            "adapter": "file_queue",
        },
        "executor": {
            "running": True,
        },
        "resolve": {
            "connected": True,
            "product_name": product_name,
            "version": version,
        },
        "project": {
            "open": current_project is not None,
            "name": project_name,
        },
    }
    return make_result(request_id, True, data=data, warnings=warnings)


def process_request_file(request_path):
    try:
        with request_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        move_to_deadletter(request_path)
        error_text = "malformed request"
        console_line("[DFMCP] error | %s" % error_text)
        log_line("Malformed request moved to deadletter: %s" % exc)
        return {
            "handled": False,
            "last_request_id": "-",
            "last_error": error_text,
        }

    request_id = payload.get("request_id", "unknown")
    command = payload.get("command")

    if command == "resolve_health":
        result = handle_resolve_health(request_id)
    else:
        result = make_result(
            request_id,
            False,
            error=make_error(
                "unsupported_in_free_mode",
                "Unsupported command '%s' for MVP executor." % command,
            ),
        )

    result_path = RESULTS_DIR / ("%s.json" % request_id)
    if not best_effort_write_json(result_path, result):
        console_line("[DFMCP] error | failed to write result for request %s" % request_id)
        return {
            "handled": False,
            "last_request_id": request_id,
            "last_error": "failed to write result",
        }

    try:
        request_path.unlink()
    except Exception:
        pass

    if result["ok"]:
        console_line("[DFMCP] handled | id=%s | command=%s" % (request_id, command))
        last_error = ""
    else:
        last_error = result.get("error", {}).get("message", "") or "request failed"
        console_line("[DFMCP] error | %s" % last_error)

    return {
        "handled": True,
        "last_request_id": request_id,
        "last_error": last_error,
    }


def run_forever():
    last_heartbeat_at = 0.0
    console_line("[DFMCP] started | mode=console")

    context = current_context()
    if context["resolve_connected"]:
        console_line("[DFMCP] resolve connected | %s" % format_context_summary())
    else:
        console_line("[DFMCP] resolve not ready")

    while True:
        ensure_dirs()
        status = update_status(last_poll=True)

        request_files = sorted(REQUESTS_DIR.glob("*.json"))
        if request_files:
            info = process_request_file(request_files[0])
            update_status(
                last_request_id=info.get("last_request_id", ""),
                request_handled=bool(info.get("handled")),
                last_error=info.get("last_error", ""),
            )

        now = time.time()
        if now - last_heartbeat_at >= HEARTBEAT_INTERVAL_SECONDS:
            status = load_status()
            last_request_id = (status.get("last_request_id") or "-")[:8]
            processed_count = status.get("processed_count", 0)
            context_summary = format_context_summary()
            console_line(
                "[DFMCP] alive | processed=%s | last_request=%s | %s"
                % (processed_count, last_request_id, context_summary)
            )
            last_heartbeat_at = now

        time.sleep(POLL_INTERVAL_MS / 1000.0)


def main():
    ensure_dirs()
    write_status(fresh_status_template())
    update_status(last_error="")
    run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            update_status(running=False, last_error="")
        except Exception:
            log_line("Non-fatal status update failure during shutdown")
        console_line("[DFMCP] stopped")
    except Exception:
        try:
            update_status(running=False, last_error="fatal executor error")
        except Exception:
            log_line("Non-fatal status update failure during fatal error handling")
        console_line("[DFMCP] fatal error | see resolve_executor.log")
        log_line("Fatal executor error:\n%s" % traceback.format_exc())
        raise
