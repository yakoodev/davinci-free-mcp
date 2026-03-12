"""Core data contracts for the first vertical slice."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

BridgeErrorCategory = Literal[
    "bridge_unavailable",
    "resolve_not_ready",
    "no_project_open",
    "no_current_timeline",
    "object_not_found",
    "unsupported_command",
    "unsupported_in_free_mode",
    "validation_error",
    "execution_failure",
    "timeout",
]


class BridgeError(BaseModel):
    """Normalized bridge or executor error."""

    category: BridgeErrorCategory
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class BridgeCommand(BaseModel):
    """Transport-agnostic command envelope."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    command: str
    target: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=5000, gt=0)
    context: dict[str, Any] = Field(default_factory=dict)


class BridgeResult(BaseModel):
    """Transport-agnostic result envelope."""

    request_id: str
    ok: bool
    data: dict[str, Any] | None = None
    error: BridgeError | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(
        cls,
        request_id: str,
        data: dict[str, Any] | None = None,
        *,
        warnings: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "BridgeResult":
        return cls(
            request_id=request_id,
            ok=True,
            data=data or {},
            warnings=warnings or [],
            meta=meta or {},
        )

    @classmethod
    def failure(
        cls,
        request_id: str,
        category: BridgeErrorCategory,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "BridgeResult":
        return cls(
            request_id=request_id,
            ok=False,
            error=BridgeError(
                category=category,
                message=message,
                details=details or {},
            ),
            warnings=warnings or [],
            meta=meta or {},
        )


class ResolveBridgeStatus(BaseModel):
    available: bool
    adapter: str


class ResolveExecutorStatus(BaseModel):
    running: bool


class ResolveAppStatus(BaseModel):
    connected: bool
    product_name: str | None = None
    version: str | None = None


class ResolveProjectStatus(BaseModel):
    open: bool
    name: str | None = None


class ResolveProjectSummary(BaseModel):
    name: str


class ResolveTimelineSummary(BaseModel):
    index: int
    name: str


class ResolveHealthData(BaseModel):
    """Structured response for the first health tool."""

    bridge: ResolveBridgeStatus
    executor: ResolveExecutorStatus
    resolve: ResolveAppStatus
    project: ResolveProjectStatus


class ResolveProjectCurrentData(BaseModel):
    project: ResolveProjectStatus


class ResolveProjectListData(BaseModel):
    projects: list[ResolveProjectSummary] = Field(default_factory=list)


class ResolveTimelineListData(BaseModel):
    project: ResolveProjectStatus
    timelines: list[ResolveTimelineSummary] = Field(default_factory=list)


class ToolResultEnvelope(BaseModel):
    """Backend-friendly result for tools."""

    success: bool
    data: dict[str, Any] | None = None
    error: BridgeError | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
