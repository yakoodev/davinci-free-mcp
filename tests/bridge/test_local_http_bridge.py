import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from davinci_free_mcp.bridge.local_http import LocalHttpBridge
from davinci_free_mcp.config import AppSettings
from davinci_free_mcp.contracts import BridgeCommand


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"running": True, "instance_id": "http1234"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        payload = json.loads(body)
        result = {
            "request_id": payload["request_id"],
            "ok": True,
            "data": {"project": {"open": True, "name": "Demo"}},
            "error": None,
            "warnings": [],
            "meta": {"bridge": "local_http"},
        }
        raw = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        return


def test_local_http_bridge_round_trip(tmp_path: Path) -> None:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings = AppSettings(runtime_dir=tmp_path, local_http_host=host, local_http_port=port)
        bridge = LocalHttpBridge(settings)
        health = bridge.health_check()
        assert health["available"] is True

        command = BridgeCommand(command="project_current")
        bridge.submit_command(command)
        result = bridge.await_result(command.request_id, 1000)
        assert result.ok is True
        assert result.data == {"project": {"open": True, "name": "Demo"}}
    finally:
        server.shutdown()
        server.server_close()
