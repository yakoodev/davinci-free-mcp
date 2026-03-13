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
- project and timeline tools: `resolve_health`, `project_current`, `project_list`, `project_manager_folder_list`, `project_manager_folder_open`, `project_manager_folder_up`, `project_manager_folder_path`, `project_open`, `timeline_list`, `timeline_current`, `timeline_create_empty`, `timeline_set_current`, `timeline_create_from_clips`
- media tools: `media_pool_list`, `media_pool_folder_open`, `media_pool_folder_create`, `media_pool_folder_up`, `media_clip_inspect`, `media_import`
- edit structure and review tools: `timeline_append_clips`, `timeline_items_list`, `marker_add`, `marker_list`, `marker_delete`
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
- `docs/LIVE_BOOTSTRAP_AUTOMATION.md`
  Exact working host-side automation flow for launching the embedded bootstrap in Resolve and validating MCP end-to-end.
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

3. Launch DaVinci Resolve Free with the Python-aware helper:

```powershell
.\scripts\dev_start_resolve_with_python.ps1
```

4. Open the live test project and run:

```text
Workspace -> Scripts -> Utility -> resolve_executor_bootstrap
```

5. Check the end-to-end diagnostic:

```powershell
.\scripts\dev_diagnostics.ps1
```

Detailed runtime instructions live in `docs/RUNNING.md`.

Recommended retest flow after changing live Resolve features:

1. `.\scripts\dev_kill_davinci.ps1`
2. if needed, `.\scripts\dev_install_executor.ps1`
3. recreate backend: `docker compose down` then `.\scripts\dev_up.ps1`
4. `.\scripts\dev_start_resolve_with_python.ps1`
5. open `Untitled Project 5` or your current test project
6. launch `resolve_executor_bootstrap`
7. run `.\scripts\dev_diagnostics.ps1`

For agent-only live validation against an existing Resolve project:

```powershell
.\scripts\dev_agent_live_run.ps1 -ProjectName "Demo Project" -Command "pytest tests\integration -q"
```

For agent-only fallback automation via external scripting access:

```powershell
.\scripts\dev_external_scripting_diagnostics.ps1 -ProjectName "Demo Project"
.\scripts\dev_agent_external_run.ps1 -ProjectName "Demo Project" -Command "pytest tests\integration -q"
```

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
