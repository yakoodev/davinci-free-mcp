"""
Standalone DaVinci Resolve Free executor bootstrap.

Modes:
- file_queue: poll requests/results from the shared runtime directory
- local_http: expose a local REST API from inside Resolve
"""

import json
import os
import shutil
import time
import traceback
import uuid
from datetime import datetime

try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer

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
CONFIG_DIR = RUNTIME_DIR / "config"
STATUS_PATH = STATUS_DIR / "executor_status.json"
LOCK_PATH = STATUS_DIR / "executor.lock.json"
POLL_INTERVAL_MS = 150
HEARTBEAT_INTERVAL_SECONDS = 5.0
LOCK_STALE_AFTER_SECONDS = 10.0
INSTANCE_ID = uuid.uuid4().hex[:8]
INSTANCE_STARTED_AT = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
LOCK_TOKEN = uuid.uuid4().hex


def ensure_dirs():
    for path in (REQUESTS_DIR, RESULTS_DIR, DEADLETTER_DIR, LOGS_DIR, STATUS_DIR, CONFIG_DIR):
        if not path.exists():
            path.mkdir(parents=True)


def read_env_config():
    config = {}
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return config
    try:
        with env_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    except Exception:
        return {}
    return config


ENV_CONFIG = read_env_config()
BRIDGE_MODE = ENV_CONFIG.get("DFMCP_BRIDGE_ADAPTER", "file_queue")
LOCAL_HTTP_HOST = ENV_CONFIG.get("DFMCP_LOCAL_HTTP_HOST", "127.0.0.1")
LOCAL_HTTP_PORT = int(ENV_CONFIG.get("DFMCP_LOCAL_HTTP_PORT", "5001"))


def prefix():
    return "[DFMCP][%s]" % INSTANCE_ID


def log_line(text):
    ensure_dirs()
    log_path = LOGS_DIR / "resolve_executor.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("[%s] %s\n" % (timestamp, text))


def console_line(text):
    line = "%s %s" % (prefix(), text)
    print(line)
    log_line(line)


def raw_log_line(text):
    log_line(text)


def iso_now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


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
        raw_log_line("Non-fatal JSON write failure for %s: %s" % (path, exc))
        return False


def read_json(path):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def safe_call(obj, method_name, *args):
    if obj is None:
        return None
    method = getattr(obj, method_name, None)
    if method is None:
        return None
    try:
        return method(*args)
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
        "resolve": resolve,
        "resolve_connected": resolve_connected,
        "product_name": product_name,
        "version": version,
        "project_manager": project_manager,
        "current_project": current_project,
        "current_timeline": current_timeline,
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
        "instance_id": INSTANCE_ID,
        "instance_started_at": INSTANCE_STARTED_AT,
        "started_at": INSTANCE_STARTED_AT,
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
        "lock": {
            "held": True,
            "lock_path": str(LOCK_PATH),
            "lock_token": LOCK_TOKEN,
            "lock_instance_id": INSTANCE_ID,
        },
        "bridge": {
            "adapter": BRIDGE_MODE,
            "mode": BRIDGE_MODE,
        },
    }


def load_status():
    ensure_dirs()
    status = read_json(STATUS_PATH)
    if isinstance(status, dict):
        return status
    return fresh_status_template()


def write_status(status):
    ensure_dirs()
    return best_effort_write_json(STATUS_PATH, status)


def update_status(running=None, last_poll=False, last_request_id=None, request_handled=False, last_error=None):
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
    status["instance_id"] = INSTANCE_ID
    status["instance_started_at"] = INSTANCE_STARTED_AT
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
    status["lock"] = {
        "held": True,
        "lock_path": str(LOCK_PATH),
        "lock_token": LOCK_TOKEN,
        "lock_instance_id": INSTANCE_ID,
    }
    status["bridge"] = {
        "adapter": BRIDGE_MODE,
        "mode": BRIDGE_MODE,
    }
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


def lock_is_stale(lock_data):
    if not isinstance(lock_data, dict):
        return True
    status = read_json(STATUS_PATH) or {}
    if status.get("running"):
        last_poll = parse_iso(status.get("last_poll_at"))
        if last_poll is not None:
            age = (datetime.utcnow() - last_poll).total_seconds()
            if age <= LOCK_STALE_AFTER_SECONDS:
                return False
    return True


def acquire_lock():
    ensure_dirs()
    lock_payload = {
        "token": LOCK_TOKEN,
        "instance_id": INSTANCE_ID,
        "instance_started_at": INSTANCE_STARTED_AT,
        "bridge_mode": BRIDGE_MODE,
    }
    for _ in range(2):
        try:
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            existing = read_json(LOCK_PATH)
            if not lock_is_stale(existing):
                owner = "-"
                if isinstance(existing, dict):
                    owner = existing.get("instance_id") or "-"
                console_line("already running | owner=%s" % owner)
                return False
            try:
                LOCK_PATH.unlink()
            except Exception:
                owner = "-"
                if isinstance(existing, dict):
                    owner = existing.get("instance_id") or "-"
                console_line("already running | owner=%s" % owner)
                return False
        else:
            with os.fdopen(fd, "w") as handle:
                json.dump(lock_payload, handle, indent=2)
            return True
    console_line("already running | owner=unknown")
    return False


def release_lock():
    existing = read_json(LOCK_PATH)
    if isinstance(existing, dict) and existing.get("token") == LOCK_TOKEN:
        try:
            LOCK_PATH.unlink()
        except Exception:
            pass


def move_to_deadletter(request_path):
    ensure_dirs()
    target = DEADLETTER_DIR / request_path.name
    if target.exists():
        target.unlink()
    shutil.move(str(request_path), str(target))


def make_error(category, message, details=None):
    return {"category": category, "message": message, "details": details or {}}


def make_result(request_id, ok, data=None, error=None, warnings=None, meta=None):
    return {
        "request_id": request_id,
        "ok": ok,
        "data": data,
        "error": error,
        "warnings": warnings or [],
        "meta": meta or {"bridge": BRIDGE_MODE},
    }


def current_project():
    return current_context()["current_project"]


def list_project_names(project_manager):
    project_names = safe_call(project_manager, "GetProjectListInCurrentFolder")
    if isinstance(project_names, list):
        return [str(name) for name in project_names]
    current_folder = safe_call(project_manager, "GetCurrentFolder")
    project_names = safe_call(current_folder, "GetProjectList")
    if isinstance(project_names, list):
        return [str(name) for name in project_names]
    return []


def list_timelines(project):
    timeline_count = safe_call(project, "GetTimelineCount") or 0
    items = []
    for index in range(1, int(timeline_count) + 1):
        timeline = safe_call(project, "GetTimelineByIndex", index)
        if timeline is None:
            continue
        items.append({"index": index, "name": safe_call(timeline, "GetName") or ("Timeline %s" % index)})
    return items


def handle_resolve_health(request_id):
    resolve = get_resolve()
    if resolve is None:
        return make_result(
            request_id,
            False,
            error=make_error("resolve_not_ready", "Resolve handle is not available in embedded environment."),
        )
    project = current_project()
    warnings = []
    if project is None:
        warnings.append("no_project_open")
    data = {
        "bridge": {"available": True, "adapter": BRIDGE_MODE},
        "executor": {"running": True},
        "resolve": {
            "connected": True,
            "product_name": safe_call(resolve, "GetProductName"),
            "version": safe_call(resolve, "GetVersionString"),
        },
        "project": {"open": project is not None, "name": safe_call(project, "GetName")},
    }
    return make_result(request_id, True, data=data, warnings=warnings)


def handle_project_current(request_id):
    project = current_project()
    warnings = []
    if project is None:
        warnings.append("no_project_open")
    return make_result(
        request_id,
        True,
        data={"project": {"open": project is not None, "name": safe_call(project, "GetName")}},
        warnings=warnings,
    )


def handle_project_list(request_id):
    resolve = get_resolve()
    if resolve is None:
        return make_result(
            request_id,
            False,
            error=make_error("resolve_not_ready", "Resolve handle is not available in embedded environment."),
        )
    project_manager = safe_call(resolve, "GetProjectManager")
    project_names = list_project_names(project_manager)
    return make_result(request_id, True, data={"projects": [{"name": name} for name in project_names]})


def handle_timeline_list(request_id):
    project = current_project()
    if project is None:
        return make_result(
            request_id,
            False,
            error=make_error("no_project_open", "No current project is open in Resolve."),
        )
    return make_result(
        request_id,
        True,
        data={
            "project": {"open": True, "name": safe_call(project, "GetName")},
            "timelines": list_timelines(project),
        },
    )


COMMAND_HANDLERS = {
    "resolve_health": handle_resolve_health,
    "project_current": handle_project_current,
    "project_list": handle_project_list,
    "timeline_list": handle_timeline_list,
}


def execute_command(request_id, command):
    handler = COMMAND_HANDLERS.get(command)
    if handler is None:
        return make_result(
            request_id,
            False,
            error=make_error("unsupported_command", "Unsupported command '%s' for executor." % command),
        )
    return handler(request_id)


def record_result(request_id, command, result):
    if result["ok"]:
        console_line("handled | id=%s | command=%s" % (request_id, command))
        update_status(last_request_id=request_id, request_handled=True, last_error="")
    else:
        error = result.get("error") or {}
        message = error.get("message") or "request failed"
        console_line("error | %s" % message)
        update_status(last_request_id=request_id, request_handled=True, last_error=message)


def process_request_file(request_path):
    try:
        with request_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        move_to_deadletter(request_path)
        console_line("error | malformed request")
        raw_log_line("Malformed request moved to deadletter: %s" % exc)
        return

    request_id = payload.get("request_id", "unknown")
    command = payload.get("command")
    result = execute_command(request_id, command)

    result_path = RESULTS_DIR / ("%s.json" % request_id)
    if not best_effort_write_json(result_path, result):
        console_line("error | failed to write result for request %s" % request_id)
        return

    try:
        request_path.unlink()
    except Exception:
        pass

    record_result(request_id, command, result)


class RequestHandler(BaseHTTPRequestHandler):
    runtime = None

    def _write_json(self, status_code, payload):
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            payload = {
                "running": True,
                "instance_id": INSTANCE_ID,
                "bridge_mode": BRIDGE_MODE,
            }
            self._write_json(200, payload)
            return
        if self.path == "/status":
            self._write_json(200, load_status())
            return
        self._write_json(404, {"error": "not_found"})

    def do_POST(self):
        if not self.path.startswith("/commands/"):
            self._write_json(404, {"error": "not_found"})
            return
        command_name = self.path.split("/")[-1]
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(raw_body)
        except Exception:
            self._write_json(
                400,
                make_result(
                    "unknown",
                    False,
                    error=make_error("validation_error", "Request body is not valid JSON."),
                ),
            )
            return

        request_id = payload.get("request_id") or uuid.uuid4().hex
        command = payload.get("command") or command_name
        result = execute_command(request_id, command)
        record_result(request_id, command, result)
        self._write_json(200, result)

    def log_message(self, format_string, *args):
        return


def heartbeat():
    status = load_status()
    last_request_id = (status.get("last_request_id") or "-")[:8]
    processed_count = status.get("processed_count", 0)
    context_summary = format_context_summary()
    console_line("alive | processed=%s | last_request=%s | %s" % (processed_count, last_request_id, context_summary))


def run_file_queue():
    last_heartbeat_at = 0.0
    while True:
        ensure_dirs()
        update_status(last_poll=True)
        request_files = sorted(REQUESTS_DIR.glob("*.json"))
        if request_files:
            process_request_file(request_files[0])
        now = time.time()
        if now - last_heartbeat_at >= HEARTBEAT_INTERVAL_SECONDS:
            heartbeat()
            last_heartbeat_at = now
        time.sleep(POLL_INTERVAL_MS / 1000.0)


def run_local_http():
    last_heartbeat_at = 0.0
    server = HTTPServer((LOCAL_HTTP_HOST, LOCAL_HTTP_PORT), RequestHandler)
    server.timeout = max(POLL_INTERVAL_MS / 1000.0, 0.1)
    console_line("http listening | host=%s | port=%s" % (LOCAL_HTTP_HOST, LOCAL_HTTP_PORT))
    while True:
        update_status(last_poll=True)
        server.handle_request()
        now = time.time()
        if now - last_heartbeat_at >= HEARTBEAT_INTERVAL_SECONDS:
            heartbeat()
            last_heartbeat_at = now


def run():
    console_line("started | mode=console | bridge=%s" % BRIDGE_MODE)
    context = current_context()
    if context["resolve_connected"]:
        console_line("resolve connected | %s" % format_context_summary())
    else:
        console_line("resolve not ready")

    if BRIDGE_MODE == "local_http":
        run_local_http()
        return

    run_file_queue()


def main():
    ensure_dirs()
    if not acquire_lock():
        return
    write_status(fresh_status_template())
    update_status(last_error="")
    run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        try:
            update_status(running=False, last_error="")
        except Exception:
            raw_log_line("Non-fatal status update failure during shutdown")
        console_line("stopped")
    except Exception:
        try:
            update_status(running=False, last_error="fatal executor error")
        except Exception:
            raw_log_line("Non-fatal status update failure during fatal error handling")
        console_line("fatal error | see resolve_executor.log")
        raw_log_line("Fatal executor error:\n%s" % traceback.format_exc())
        raise
    finally:
        release_lock()
