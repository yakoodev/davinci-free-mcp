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
docker compose up --build -d
```

Check logs:

```powershell
docker compose logs -f mcp
```

Expected MCP endpoint:

- `http://localhost:8000/mcp`

Stop it:

```powershell
docker compose down
```

## 2. Start DaVinci Resolve Free

On Windows host, start Resolve normally or from PowerShell:

```powershell
& "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
```

Resolve must be started on the host, not in Docker.

## 3. Start the internal executor inside Resolve

Use the standalone Python 3.6-compatible bootstrap script:

- `scripts/resolve_executor_bootstrap.py`

Important:

- this script is intentionally standalone
- it does not import the main project package
- it is designed to run inside Resolve's older embedded Python runtime

Recommended install path on Windows:

```text
C:\Users\Yakoo\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\
```

Avoid keeping duplicate copies in multiple script folders. If Resolve shows the script twice in the menu, delete one of the copies and leave only the user-level one.

Before first run:

1. Open the script and confirm `REPO_ROOT` points to your repo.
2. Copy the script into the user-level `Utility` folder.
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

The script also writes to:

```text
runtime/logs/resolve_executor.log
```

The canonical machine-readable status is also written to:

```text
runtime/status/executor_status.json
```

## 4. Run the first diagnostic check

If you want a direct backend-only health check from the host repo:

```powershell
python -m davinci_free_mcp.backend.diagnostics
```

This should return JSON with:

- `bridge.available`
- `executor.running`
- `resolve.connected`
- `resolve.product_name`
- `resolve.version`
- `project.open`
- optional `project.name`

In DaVinci Console, you should also see:

- `[DFMCP] handled ...` after a request is processed
- periodic `[DFMCP] alive ...` heartbeat lines
- `[DFMCP] resolve connected ...` if `app.GetResolve()` succeeded

In headless mode, check:

```powershell
Get-Content ".\runtime\status\executor_status.json"
```

Key fields:

- `running`
- `last_poll_at`
- `last_request_at`
- `last_request_id`
- `processed_count`
- `last_error`
- `resolve.connected`
- `project.name`
- `timeline.name`

## 5. Use MCP over HTTP

If your MCP client supports Streamable HTTP, point it to:

```text
http://localhost:8000/mcp
```

The first tool currently exposed is:

- `resolve_health`

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
