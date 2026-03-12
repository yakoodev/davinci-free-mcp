# DavinciFreeMcp

`DavinciFreeMcp` is a Python-first MCP server for **DaVinci Resolve Free**.
It is not a generic AI video editor and it is not a thin wrapper around Studio-only external scripting. The goal is to build a practical, extensible integration layer that exposes reliable Resolve operations to MCP clients through a narrow and maintainable backend.

## Problem

DaVinci Resolve Free needs a different architecture than DaVinci Resolve Studio.

The common external scripting flow used by many Resolve tools assumes that an external Python process can call `scriptapp("Resolve")` directly. That is a workable pattern for Studio, but it is not a safe foundation for a Free-focused product. For Resolve Free, the realistic approach is:

- run a constrained script or executor **inside** Resolve
- communicate with it from an external backend
- expose that backend through MCP
- optimize for a narrow, dependable workflow instead of full API parity on day one

## Current Status

The repository currently contains a working MVP vertical slice:

- Dockerized external MCP/backend service
- `file_queue` bridge over a shared runtime directory
- prototype `local_http` bridge for an executor-hosted REST server inside Resolve
- standalone internal executor for Resolve Free
- project and timeline tools: `resolve_health`, `project_current`, `project_list`, `timeline_list`, `timeline_current`, `timeline_create_empty`
- media tools: `media_pool_list`, `media_import`
- edit structure tools: `timeline_append_clips`, `timeline_items_list`
- console-first executor status inside DaVinci Resolve
- machine-readable executor heartbeat in `runtime/status/executor_status.json`
- instance-aware diagnostics with `instance_id` and lock ownership visibility

## Architectural Direction

The project is documented around five logical layers:

1. `mcp_server`
   Exposes MCP tools over `stdio` in MVP.
2. `application_backend`
   Validates tool inputs, routes commands, normalizes outputs, and owns the error model.
3. `bridge_contract`
   Defines transport-agnostic request/response envelopes, correlation IDs, timeouts, and health checks.
4. `bridge_adapters`
   Implements interchangeable transports. MVP documents `file_queue` as the default path and `local_http` as an optional alternative.
5. `resolve_executor`
   Runs inside Resolve Free, gets the Resolve handle from the embedded environment, executes constrained commands, and returns JSON-safe results.

## Intended Module Map

The first implementation phase is expected to grow into this shape:

```text
src/davinci_free_mcp/
  server/
  backend/
  bridge/
  resolve_exec/
  contracts/
  config/
tests/
docs/
references/
```

## MVP Scope

The MVP should cover:

- MCP as the primary external interface
- a minimal backend with stable request/result contracts
- an internal bridge for Resolve Free
- low-level tools for projects, media, timelines, and markers
- documentation that supports incremental implementation

The MVP should not try to cover:

- Studio-only external scripting flows
- broad render automation
- cloud/database administration
- Fusion-heavy automation
- high-level editing AI workflows
- provider-specific LLM orchestration

## Why the Bridge Matters

The highest-risk part of the system is not the MCP server. It is the handshake between an external Python backend and an internal Resolve Free executor. The docs therefore treat the bridge as a first-class subsystem with a stable contract and two interchangeable adapters:

- `file_queue`
  Default MVP recommendation. Safer, simpler to reason about, and easier to recover after partial failure.
- `local_http`
  Optional adapter with the same command schema. Useful if the embedded runtime can support a local request loop reliably.

## Documentation Index

- `docs/ARCHITECTURE.md`
  Target architecture, data flow, bridge model, and future extension path.
- `docs/REFERENCES.md`
  Local reference repositories and how to use them.
- `docs/ROADMAP.md`
  Ordered implementation stages and dependencies.
- `docs/TOOLS.md`
  MVP tool catalog and deferrals.
- `docs/DEVELOPMENT.md`
  Dev workflow, repo conventions, and anti-pattern guidance.
- `docs/README.ru.md`
  Short Russian overview and quick-start notes.
- `docs/TROUBLESHOOTING.md`
  Common runtime and development issues.
- `docs/RISKS_AND_ASSUMPTIONS.md`
  Confirmed facts, hypotheses, risks, and prototype priorities.
- `CHANGELOG.md`
  Project patch notes and milestone history.

## Quick Start

1. Start the external service:

```powershell
.\scripts\dev_up.ps1
```

2. Install the Resolve bootstrap script:

```powershell
.\scripts\dev_install_executor.ps1
```

3. Launch DaVinci Resolve Free and run:

```text
Workspace -> Scripts -> Utility -> resolve_executor_bootstrap
```

4. Check the end-to-end diagnostic:

```powershell
.\scripts\dev_diagnostics.ps1
```

Detailed runtime instructions live in `docs/RUNNING.md`.

To experiment with the internal REST prototype, copy `.env.example` to `.env` and set:

```text
DFMCP_BRIDGE_ADAPTER=local_http
DFMCP_LOCAL_HTTP_HOST=host.docker.internal
DFMCP_LOCAL_HTTP_BIND_HOST=127.0.0.1
```

## Repository Notes

- `references/` is treated as local research material and is intentionally excluded from git.
- `runtime/` is generated locally and is intentionally excluded from git.
- The internal executor is intentionally standalone and Python-3.6-compatible so it can run inside Resolve Free without depending on the main project environment.

## Current Focus

The current focus is to harden the bridge/executor workflow and stabilize the first low-level mutation tools for timeline and media-pool automation.
