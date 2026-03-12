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
    bridge_poll_interval_ms: int = 100
    mcp_transport: str = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_path: str = "/mcp"
    mcp_json_response: bool = True
    mcp_stateless_http: bool = True

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
