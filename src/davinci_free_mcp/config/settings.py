"""Application settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Runtime settings for the first vertical slice."""

    model_config = SettingsConfigDict(
        env_prefix="DFMCP_",
        extra="ignore",
    )

    runtime_dir: Path = Path("runtime")
    default_timeout_ms: int = 5000
    bridge_adapter: str = "file_queue"
    bridge_poll_interval_ms: int = 100
    local_http_host: str = "127.0.0.1"
    local_http_port: int = 5001
    local_http_timeout_ms: int = 5000
    mcp_transport: str = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_path: str = "/mcp"
    mcp_json_response: bool = True
    mcp_stateless_http: bool = True
    transcribe_provider: str = "faster_whisper"
    transcribe_model: str = "base"
    transcribe_device: str = "cpu"
    transcribe_compute_type: str = "int8"
    transcribe_beam_size: int = 1

    @property
    def spool_dir(self) -> Path:
        return self.runtime_dir / "spool"

    @property
    def requests_dir(self) -> Path:
        return self.spool_dir / "requests"

    @property
    def results_dir(self) -> Path:
        return self.spool_dir / "results"

    @property
    def deadletter_dir(self) -> Path:
        return self.spool_dir / "deadletter"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs"

    @property
    def analysis_dir(self) -> Path:
        return self.runtime_dir / "analysis"

    @property
    def status_dir(self) -> Path:
        return self.runtime_dir / "status"

    @property
    def status_path(self) -> Path:
        return self.status_dir / "executor_status.json"

    @property
    def lock_path(self) -> Path:
        return self.status_dir / "executor.lock.json"
