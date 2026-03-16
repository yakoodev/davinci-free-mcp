# Development

## Summary

This project should be built as a small, modular Python codebase with MCP at the edge, backend logic in the middle, and Resolve Free execution isolated behind a bridge.

The repository currently starts with documentation and references. The codebase should grow around the architecture already described in the docs, not around a copied reference implementation.

## Intended Repository Structure

```text
src/davinci_free_mcp/
  server/        # MCP server entrypoints, tool registration, transport wiring
  backend/       # command routing, orchestration, result normalization
  bridge/        # bridge contract plus adapter implementations
  resolve_exec/  # internal Resolve executor and command handlers
  contracts/     # Pydantic models for tools, commands, results, errors
  config/        # settings and environment loading
tests/
docs/
references/
```

## Module Ownership

### `server/`

Owns:

- MCP tool declarations
- MCP transport bootstrap
- MCP-facing schemas and descriptions

Must not own:

- direct Resolve API calls
- transport-specific bridge internals

### `backend/`

Owns:

- command orchestration
- precondition checks
- normalization of executor and bridge responses

Must not own:

- embedded Resolve script bootstrap
- MCP transport wiring details

### `bridge/`

Owns:

- bridge interface
- request/result transport handling
- adapter-specific recovery and timeout behavior

Must not own:

- Resolve business logic
- MCP tool schemas

### `resolve_exec/`

Owns:

- in-Resolve bootstrap
- internal command dispatch
- object resolution against Resolve's API
- JSON-safe serialization

Must not own:

- MCP-specific concepts
- external client logic

## Dev Workflow

### Create environment

Recommended baseline:

```powershell
& 'C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe' -m venv .venv
```

or:

```powershell
uv venv
```

Environment notes for this Windows host:

- recommended interpreter: `C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe`
- minimum supported version for the main project: `Python 3.10+`
- `python` in the current `PATH` may still resolve to `Python36`, so plain `python ...` is not a reliable command shape here

### Install dependencies

Expected dependency profile:

- `mcp`
- `pydantic`
- `pydantic-settings`
- `pytest`

Suggested command shape:

```powershell
& 'C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe' -m pip install -e .[dev]
```

or:

```powershell
uv sync
```

or:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

### Run MCP server in dev mode

Expected target:

```powershell
& 'C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe' -m davinci_free_mcp.server.main
```

### Run backend-only tests

Expected target:

```powershell
& 'C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe' -m pytest tests/backend -q
```

### Run bridge adapter tests

Expected target:

```powershell
& 'C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe' -m pytest tests/bridge -q
```

### Run manual Resolve integration checks

Expected target:

- start Resolve Free
- start the internal executor from Resolve's internal scripting entrypoint
- run backend or MCP commands from the external environment
- verify request/result flow with at least one read-only command

## Development Scripts

The repository includes PowerShell helper scripts to keep the Windows host and Docker workflow repeatable.

- `scripts/dev_up.ps1`
  Start the Dockerized backend and show container status.
- `scripts/dev_down.ps1`
  Stop the Dockerized backend.
- `scripts/dev_kill_davinci.ps1`
  Force-stop `Resolve.exe` and all `fuscript.exe` processes on the host.
- `scripts/dev_container_logs.ps1`
  Show backend container logs.
- `scripts/dev_install_executor.ps1`
  Copy the standalone bootstrap into the Resolve user scripts directory and remove the known duplicate system-level copy.
- `scripts/dev_start_resolve_with_python.ps1`
  Start Resolve with Python 3.11 added to `PATH` for that Resolve process so embedded Python scripts remain available in `Workspace -> Scripts`.
- `scripts/dev_uninstall_executor.ps1`
  Remove the bootstrap from Resolve script directories.
- `scripts/dev_reset_runtime.ps1`
  Clear generated runtime state without touching source files. By default it preserves the executor lock file.
- `scripts/dev_diagnostics.ps1`
  Run backend diagnostics against the live bridge.
- `scripts/dev_status.ps1`
  Print `runtime/status/executor_status.json` and highlight `instance_id`.
- `scripts/dev_logs.ps1`
  Show filtered executor log lines with `instance_id`-aware prefixes.
- `scripts/dev_who_owns_lock.ps1`
  Print lock ownership from `runtime/status/executor.lock.json`.
- `scripts/dev_smoke.ps1`
  Run a guarded smoke flow. It refuses to reset runtime if an executor appears to already be active.
- `scripts/dev_agent_live_run.ps1`
  Agent-only host helper that reuses a healthy executor when possible and otherwise performs a Python-aware cold start, launches `resolve_executor_bootstrap` via Resolve UI automation, opens a target project, and runs a host command outside MCP.
- `scripts/dev_smoke_live.ps1`
  Thin wrapper around `dev_agent_live_run.ps1` for canonical non-interactive live smoke runs.
- `scripts/dev_launch_executor_ui.ps1`
  Host-side helper that invokes `resolve_executor_bootstrap` through the Resolve UI menus via `pywinauto`.
- `scripts/dev_external_scripting_diagnostics.ps1`
  Agent-only host diagnostic for external Resolve scripting availability and optional `LoadProject()` verification.
- `scripts/dev_agent_external_run.ps1`
  Agent-only fallback runner that uses external scripting access, opens a project by name, and then runs a host command.

For the exact live workflow that successfully launched the embedded script from
the Resolve UI and then validated MCP end-to-end, see:

- `docs/LIVE_BOOTSTRAP_AUTOMATION.md`

Recommended cycle:

1. `.\scripts\dev_up.ps1`
2. `.\scripts\dev_install_executor.ps1`
3. `.\scripts\dev_smoke_live.ps1 -ProjectName "Untitled Project 5" -Command "C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\integration -q"`
4. if the autonomous helper fails, fall back to the manual live sequence from `docs/LIVE_BOOTSTRAP_AUTOMATION.md`
6. `.\scripts\dev_diagnostics.ps1`

Recommended retest cycle after feature changes:

1. `.\scripts\dev_kill_davinci.ps1`
2. if `scripts/resolve_executor_bootstrap.py` changed, run `.\scripts\dev_install_executor.ps1`
3. recreate the backend container:
   `docker compose down`
   `.\scripts\dev_up.ps1`
4. run `.\scripts\dev_smoke_live.ps1 -ProjectName "Untitled Project 5" -Command "C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\integration -q"`
5. if needed, use the manual fallback from `docs/LIVE_BOOTSTRAP_AUTOMATION.md`

Important:

- any time `scripts/resolve_executor_bootstrap.py` changes, rerun `.\scripts\dev_install_executor.ps1`
- then relaunch the bootstrap from Resolve so the live executor picks up the new command whitelist
- on this machine, if `Workspace -> Scripts` is disabled, Resolve was likely started without a usable Python in `PATH`; restart it with `.\scripts\dev_start_resolve_with_python.ps1`
- `.\scripts\dev_smoke_live.ps1` is the canonical autonomous live smoke path on this machine; the manual UI-driven flow is the fallback when the helper reports a specific automation failure
- for local test runs on this machine, prefer `C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest ...` over plain `pytest` or `python -m pytest`
- never run `.\scripts\dev_reset_runtime.ps1 -IncludeLock` while Resolve is still open
- keep `CHANGELOG.md` updated for every meaningful change set, milestone, or behavior change
- the external scripting fallback is temporary and agent-only; do not treat it as the default product architecture for Resolve Free

Recommended Python 3.11 smoke set on this host:

1. `C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\contracts\test_models.py -q`
2. `C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\backend\test_service.py -q`
3. `C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\integration\test_server_smoke.py -q`
4. `C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\integration\test_resolve_health_flow.py -q`

## Patch Notes

`CHANGELOG.md` is mandatory project hygiene.

Update it when you:

- add or remove tools
- change bridge behavior
- change executor startup or diagnostics
- change helper scripts or development workflow
- change public documentation in a way that affects usage

## Testing Strategy

Split testing into three layers:

### Contracts and schemas

- command envelope validation
- result envelope validation
- tool input and output schema checks

### Backend and adapters

- command routing
- timeout handling
- malformed result handling
- bridge unavailable paths

### Manual Resolve integration

- executor bootstrap
- `resolve_health`
- current project lookup
- project list lookup
- project open
- timeline list lookup

## Working With References

References are local source material, not default dependencies.

Rules:

- read the smallest useful subset first
- borrow concepts, contracts, and patterns
- avoid copying entire servers or wrappers
- document any reference-inspired design in our own terms
- keep the codebase independent from local clone layout

## Studio-Only Smell Checklist

Reject or rethink a design if it assumes any of the following:

- external `scriptapp("Resolve")` from the main backend process is the default connection path
- Resolve must expose local or network external scripting for the project to function
- the backend can hold native Resolve objects directly
- full API coverage is required before shipping a narrow workflow
- cloud/database switching is part of MVP
- Fusion- or render-heavy features are required to validate the architecture

## Recommended First Coding Module

Start with:

1. `contracts/`
2. `bridge/`
3. minimal `resolve_exec/` handshake

Reason:
The bridge is the highest-risk unknown. If it cannot be made stable enough, the rest of the stack should not be built on assumptions.
