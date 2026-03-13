# Live Bootstrap Automation

## Summary

This document records the exact host-side live validation flow that worked on this machine to:

- start DaVinci Resolve with embedded Python scripts available
- open a real Resolve project
- launch `resolve_executor_bootstrap` inside Resolve without manual clicking
- verify the embedded executor through backend diagnostics and the public MCP endpoint

This is intentionally separate from general runtime docs because agents kept confusing:

- backend-only checks
- external scripting checks
- embedded Resolve script startup
- public MCP validation

This file is the canonical "what actually worked" guide for live retests.

## Environment assumptions

- OS: Windows
- Resolve path:
  `C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe`
- `fuscript.exe` path:
  `C:\Program Files\Blackmagic Design\DaVinci Resolve\fuscript.exe`
- local helper Python:
  `C:\Users\Yakoo\AppData\Local\Python\bin\python3.11.exe`
- live bridge mode:
  `local_http`
- live test project that worked:
  `Untitled Project 5`
- Resolve UI language during the successful run:
  Russian

Important:

- `fuscript.exe` started directly from the host is **not** equivalent to launching a script from `Workspace -> Scripts` inside Resolve.
- In the successful run, direct `fuscript.exe -l python3 resolve_executor_bootstrap.py` started the bootstrap process but `app.GetResolve()` stayed unavailable.
- The embedded executor became healthy only after the script was launched from the Resolve UI menu.

## Exact successful flow

### 1. Reset host-side runtime and reinstall the bootstrap

```powershell
.\scripts\dev_kill_davinci.ps1
.\scripts\dev_reset_runtime.ps1 -IncludeLock
.\scripts\dev_install_executor.ps1
docker compose down
.\scripts\dev_up.ps1
```

Expected result:

- no stale `Resolve.exe` or `fuscript.exe`
- clean `runtime/status/`
- fresh backend container
- freshly rendered bootstrap copied to:
  `C:\Users\Yakoo\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\resolve_executor_bootstrap.py`

### 2. Start Resolve with Python 3.11 in `PATH`

Set the helper Python explicitly and launch Resolve through the provided helper:

```powershell
$env:DFMCP_PYTHON="$env:LOCALAPPDATA\Python\bin\python3.11.exe"
.\scripts\dev_start_resolve_with_python.ps1
```

Why this matters:

- on this machine, launching Resolve normally can leave `Workspace -> Scripts` unavailable
- the helper injects Python 3.11 into `PATH` for the Resolve process only

### 3. Open the live test project

The successful run used:

- `Untitled Project 5`

The project was opened through startup orchestration:

```powershell
$pyExe="$env:LOCALAPPDATA\Python\bin\python3.11.exe"
$pyDir=Split-Path $pyExe -Parent
$pyRoot=Split-Path $pyDir -Parent
$pyScripts=Join-Path $pyRoot "Scripts"
$env:DFMCP_PYTHON=$pyExe
$env:PATH="$pyDir;$pyRoot;$pyScripts;$env:PATH"
.\scripts\dev_agent_project_start.ps1 -TargetMode existing -ProjectName "Untitled Project 5" -Command "cmd /c exit 0" -WarmupSeconds 15 -TimeoutSeconds 120
```

Expected result:

- Resolve main window title becomes:
  `DaVinci Resolve - Untitled Project 5`
- the startup helper may report `project_verification_state = "likely"` based on Resolve logs even when external scripting is unavailable

This is acceptable for this flow. The embedded executor validation happens later.

## 4. Launch `resolve_executor_bootstrap` through the Resolve UI

### What did not work

This host-side command started a process, but it did **not** produce a healthy embedded executor:

```powershell
& "C:\Program Files\Blackmagic Design\DaVinci Resolve\fuscript.exe" -l python3 "$env:APPDATA\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\resolve_executor_bootstrap.py"
```

Observed result:

- `fuscript.exe` stayed alive
- `runtime/status/executor_status.json` appeared
- but `resolve.connected = false`
- logs showed `resolve not ready`

Conclusion:

- this path is not a substitute for `Workspace -> Scripts`

### What did work

The successful run used UI automation against the already-open Resolve window.

First install the helper package if needed:

```powershell
& "$env:LOCALAPPDATA\Python\bin\python3.11.exe" -m pip install pywinauto
```

Then run this exact script:

```powershell
@'
from pywinauto import Application
import time

app = Application(backend="uia").connect(title_re=".*DaVinci Resolve.*")
win = app.window(title_re=".*DaVinci Resolve.*")

workspace = win.child_window(title="Рабочая область", control_type="MenuItem").wrapper_object()
workspace.expand()
time.sleep(0.3)

scripts = win.child_window(title="Сценарии", control_type="MenuItem").wrapper_object()
scripts.expand()
time.sleep(0.5)

bootstrap = win.child_window(title="resolve_executor_bootstrap", control_type="MenuItem").wrapper_object()
bootstrap.invoke()
print("invoked")
'@ | & "$env:LOCALAPPDATA\Python\bin\python3.11.exe" -
```

This relied on Russian-localized menu labels:

- top-level menu: `Рабочая область`
- submenu: `Сценарии`
- script item: `resolve_executor_bootstrap`

During inspection, the script item appeared directly under `Сценарии`.
There was no extra visible `Utility` label in the localized popup tree for this machine.

### Verified menu structure on this machine

The automation inspection showed:

- `Рабочая область`
- `Сценарии`
- `resolve_executor_bootstrap`
- `dfmcp_probe`
- `Comp`
- `Edit`
- `Color`
- `Deliver`

So if the agent cannot find `Utility`, it should not assume failure. It should inspect the actual popup items first.

## 5. Confirm the embedded executor is really healthy

After the successful UI-driven launch, these checks passed:

```powershell
Get-Content runtime\status\executor_status.json
Get-Content runtime\logs\resolve_executor.log -Tail 20
.\scripts\dev_diagnostics.ps1
```

Expected minimum fields in `runtime/status/executor_status.json`:

```json
{
  "running": true,
  "resolve": {
    "connected": true,
    "product_name": "DaVinci Resolve"
  },
  "project": {
    "open": true,
    "name": "Untitled Project 5"
  },
  "bridge": {
    "adapter": "local_http"
  }
}
```

Expected log lines:

- `[DFMCP][<instance>] started | mode=console | bridge=local_http`
- `[DFMCP][<instance>] resolve connected | version=... | project=Untitled Project 5 | timeline=...`
- `[DFMCP][<instance>] http listening | bind_host=127.0.0.1 | connect_host=host.docker.internal | port=5001`

Important distinction:

- `running = true` is not enough
- `resolve.connected = true` is the real success condition

## 6. Validate through the public MCP endpoint

Backend diagnostics are not sufficient. The public MCP layer must also be checked.

The successful run used this Python client flow:

```powershell
@'
import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("http://127.0.0.1:8000/mcp") as streams:
        read_stream, write_stream, _ = streams
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            print("INIT", init.serverInfo.name, init.serverInfo.version)

            tools = await session.list_tools()
            print(sorted([tool.name for tool in tools.tools]))

            for name, args in [
                ("resolve_health", {}),
                ("project_current", {}),
                ("timeline_list", {}),
                ("timeline_items_list", {"timeline_name": "MCP Smoke Timeline"}),
            ]:
                result = await session.call_tool(name, args)
                print(name, result.content[0].text)

anyio.run(main)
'@ | & "$env:LOCALAPPDATA\Python\bin\python3.11.exe" -
```

This verified:

- MCP server initialization
- `list_tools`
- `resolve_health`
- `project_current`
- `timeline_list`
- `timeline_items_list`

## 7. Successful mutation check through MCP

A real write-path validation also succeeded through the MCP endpoint:

1. call `media_pool_list`
2. choose an existing non-timeline clip
3. call `timeline_create_empty`
4. call `timeline_append_clips`
5. confirm via `timeline_items_list`

The successful smoke timeline name used during validation was:

- `Codex Smoke 1038`

The clip appended during that run was:

- `77777d8e-b4ba-4775-817d-900fafde51f9.png`

This confirmed:

- embedded executor was healthy
- backend bridge worked
- public MCP routing worked
- mutation tools still worked after the refactor

## Common failure modes

### `fuscript.exe` starts but `resolve.connected = false`

Cause:

- the script was started outside the real embedded Resolve menu path

Action:

- do not trust direct `fuscript.exe` startup
- use UI automation to launch the script from the Resolve menu

### External scripting diagnostics say `resolve_connected = false`

Cause:

- host-side `DaVinciResolveScript.scriptapp("Resolve")` is not available

Action:

- do not block on external scripting
- continue with embedded bootstrap startup and MCP validation

### Agent cannot find `Utility`

Cause:

- localized Resolve menus do not necessarily expose the tree the same way the docs phrase it

Action:

- inspect popup `MenuItem` labels in the running UI
- on this machine, `resolve_executor_bootstrap` was directly visible under `Сценарии`

### `executor_status.json` exists but diagnostics fail

Cause:

- stale runtime from an older run

Action:

```powershell
.\scripts\dev_kill_davinci.ps1
.\scripts\dev_reset_runtime.ps1 -IncludeLock
docker compose down
.\scripts\dev_up.ps1
```

Then redo the full flow.

## Recommended rule for future agents

When validating live Resolve integration on this machine, use this priority order:

1. reinstall bootstrap if it changed
2. restart backend container
3. start Resolve with `dev_start_resolve_with_python.ps1`
4. open `Untitled Project 5`
5. launch `resolve_executor_bootstrap` via Resolve UI automation using `pywinauto`
6. verify `runtime/status/executor_status.json` with `resolve.connected = true`
7. run `.\scripts\dev_diagnostics.ps1`
8. run public MCP `list_tools` and `call_tool` checks against `http://127.0.0.1:8000/mcp`

Do not treat:

- external scripting diagnostics
- direct `fuscript.exe` execution
- backend-only health checks

as proof that the embedded Resolve path is healthy.
