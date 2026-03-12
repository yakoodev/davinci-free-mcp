# Running

## Important

`docker compose` runs only the **external MCP/backend layer**.
DaVinci Resolve Free itself must run on the **host machine**, not inside Docker.

The shared point between them is the same `runtime/` directory:

- container path: `/app/runtime`
- host path: `<repo>\runtime`

## 1. Start the MCP container

From the repository root:

```powershell
.\scripts\dev_up.ps1
```

Check logs:

```powershell
.\scripts\dev_container_logs.ps1 -Follow
```

Expected MCP endpoint:

- `http://localhost:8000/mcp`

Stop it:

```powershell
docker compose down
```

To fully stop DaVinci-side runtime processes on the host, including orphaned `fuscript.exe` instances:

```powershell
.\scripts\dev_kill_davinci.ps1
```

## 2. Start DaVinci Resolve Free

On Windows host, start Resolve normally or from PowerShell:

```powershell
& "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
```

Resolve must be started on the host, not in Docker.

## 3. Install and start the internal executor inside Resolve

Use the standalone Python 3.6-compatible bootstrap script:

- `scripts/resolve_executor_bootstrap.py`

Important:

- this script is intentionally standalone
- it does not import the main project package
- it is designed to run inside Resolve's older embedded Python runtime

Install it with:

```powershell
.\scripts\dev_install_executor.ps1
```

The exact target path on this Windows setup is:

```text
C:\Users\Yakoo\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\resolve_executor_bootstrap.py
```

Run the install script again whenever `scripts/resolve_executor_bootstrap.py` changes.

Avoid keeping duplicate copies in multiple script folders. The install script removes the known system-level duplicate by default.

Before first run:

1. Open the script and confirm `REPO_ROOT` points to your repo.
2. Run `.\scripts\dev_install_executor.ps1`.
3. Restart Resolve if it was already open.

Then start it from:

```text
Workspace -> Scripts -> Utility -> resolve_executor_bootstrap
```

When it starts successfully, status is now shown through the DaVinci Console with lines like:

- `[DFMCP] started | mode=console`
- `[DFMCP] resolve connected | version=... | project=... | timeline=...`
- `[DFMCP] alive | processed=... | last_request=... | ...`
- `[DFMCP] handled | id=... | command=resolve_health`
- `[DFMCP] error | ...`

If the script is already running and you launch it again, Resolve Console should print:

- `[DFMCP][newid] duplicate executor blocked | owner=<existing-id> | owner_started_at=<timestamp>`

The script also writes to:

```text
runtime/logs/resolve_executor.log
```

The canonical machine-readable status is also written to:

```text
runtime/status/executor_status.json
```

That status file now includes `instance_id` and lock metadata so duplicate writers are easier to spot.

## 4. Run the first diagnostic check

If you want a direct backend-only health check from the host repo:

```powershell
.\scripts\dev_diagnostics.ps1
```

This returns JSON with:

- `resolve_health`
- `project_current`
- `project_list`
- `timeline_list`
- `executor_status`

In DaVinci Console, you should also see:

- `[DFMCP] handled ...` after a request is processed
- periodic `[DFMCP] alive ...` heartbeat lines
- `[DFMCP] resolve connected ...` if `app.GetResolve()` succeeded

For machine-readable status, check:

```powershell
.\scripts\dev_status.ps1
```

For lock ownership, check:

```powershell
.\scripts\dev_who_owns_lock.ps1
```

Key fields in `executor_status.json`:

- `running`
- `mode`
- `last_poll_at`
- `last_request_at`
- `last_request_id`
- `processed_count`
- `last_error`
- `resolve.connected`
- `project.name`
- `timeline.name`

For a short smoke workflow during development:

```powershell
.\scripts\dev_smoke.ps1
```

## 5. Use MCP over HTTP

If your MCP client supports Streamable HTTP, point it to:

```text
http://localhost:8000/mcp
```

The current tools are:

- `resolve_health`
- `project_current`
- `project_list`
- `timeline_list`

## 6. Connect to Codex Desktop

If your Codex Desktop build supports custom MCP servers, point it to the Streamable HTTP endpoint:

```text
http://localhost:8000/mcp
```

Practical checklist:

1. Start the backend with `.\scripts\dev_up.ps1`
2. Make sure diagnostics are healthy with `.\scripts\dev_diagnostics.ps1`
3. In Codex Desktop, add a custom MCP server that targets `http://localhost:8000/mcp`
4. After adding it, ask Codex to list available tools or call:
   - `resolve_health`
   - `project_current`
   - `project_list`
   - `timeline_list`

If your build uses the shared Codex config file instead of an in-app form, configure the MCP server there to use the same URL.

The OpenAI developer site confirms that Codex supports MCP and that MCP is part of the Codex/OpenAI tooling surface:

- [OpenAI for developers](https://developers.openai.com/)
- [Models overview](https://developers.openai.com/api/docs/models)

## Optional internal REST prototype

The executor can also run in `local_http` mode, inspired by the `dev-beluck/davinci-rest` reference.

To try it:

1. Create `.env` from `.env.example`
2. Set:

```text
DFMCP_BRIDGE_ADAPTER=local_http
DFMCP_LOCAL_HTTP_PORT=5001
DFMCP_LOCAL_HTTP_HOST=host.docker.internal
```

3. Restart the Docker service with `.\scripts\dev_up.ps1`
4. Reinstall and relaunch the bootstrap inside Resolve

In this mode:

- Resolve hosts a local HTTP server on `127.0.0.1`
- the backend uses `LocalHttpBridge`
- the command set stays the same as in `file_queue` mode
- when the backend runs in Docker on Windows/macOS, it must reach the host via `host.docker.internal`

Recommended REST test flow:

1. Copy `.env.example` to `.env`
2. Set:

```text
DFMCP_BRIDGE_ADAPTER=local_http
DFMCP_LOCAL_HTTP_PORT=5001
DFMCP_LOCAL_HTTP_HOST=host.docker.internal
```

3. Run:

```powershell
.\scripts\dev_up.ps1
.\scripts\dev_install_executor.ps1
```

4. Restart Resolve
5. Launch `resolve_executor_bootstrap`
6. Check:

```powershell
.\scripts\dev_status.ps1
.\scripts\dev_diagnostics.ps1
```

Expected result:

- `executor_status.status.bridge.adapter = local_http`
- `resolve_health.success = true`
- `project_current.success = true`
- `project_list.success = true`
- `timeline_list.success = true`

## Failure isolation

If `docker compose up` works but `resolve_health` times out:

- container is running, but executor likely is not reading `runtime/spool/requests`
- also check whether `runtime/status/executor_status.json` has a fresh `last_poll_at`
- and check whether DaVinci Console shows `[DFMCP] alive ...`

If executor starts but `resolve.connected` is `false` or error is `resolve_not_ready`:

- the script is running, but not inside a valid Resolve embedded environment

If JSON is malformed:

- executor serialization or result writing is broken

If `project.open` is `false`:

- chain is working, but no project is open in Resolve
