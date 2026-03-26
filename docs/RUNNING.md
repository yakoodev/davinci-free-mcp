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

For embedded Python scripts, the safer option on this machine is:

```powershell
.\scripts\dev_start_resolve_with_python.ps1
```

This starts Resolve with Python 3.11 injected into `PATH` for that process.
Without that step, `Workspace -> Scripts` may stay disabled even though the bootstrap file is installed.

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

For the exact host-side automation flow that successfully launched
`resolve_executor_bootstrap` inside the Resolve UI and then validated the public
MCP endpoint, see:

- `docs/LIVE_BOOTSTRAP_AUTOMATION.md`

## Recommended live retest flow after feature changes

When you have changed backend code, bridge code, or `scripts/resolve_executor_bootstrap.py`, use this exact cycle:

1. Fully close DaVinci Resolve and stale helper processes:

```powershell
.\scripts\dev_kill_davinci.ps1
```

2. If `scripts/resolve_executor_bootstrap.py` changed, reinstall it:

```powershell
.\scripts\dev_install_executor.ps1
```

3. Recreate the backend container so the live backend matches your latest code:

```powershell
docker compose down
.\scripts\dev_up.ps1
```

4. Start Resolve through the Python-aware helper:

```powershell
.\scripts\dev_start_resolve_with_python.ps1
```

5. Open the live test project in Resolve.
Recommended current project on this machine:

- `Untitled Project 5`

6. Start the embedded bootstrap from:

```text
Workspace -> Scripts -> Utility -> resolve_executor_bootstrap
```

7. Verify that the executor really came up:

```powershell
.\scripts\dev_diagnostics.ps1
```

Expected minimum result:

- `resolve_health.success = true`
- `resolve_health.data.executor.running = true`
- `project_current.data.project.name = <your live test project>`

8. Run live MCP checks or smoke tests.

This flow is currently the most reliable host-side retest path because it avoids the stale-process problem, forces the backend to match the latest code, and starts Resolve with a Python-capable environment so `Workspace -> Scripts` is available.

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

The current tool surface is split into four groups:

- Resolve/project tools: `resolve_health`, `project_current`, `project_list`, `project_manager_folder_list`, `project_manager_folder_open`, `project_manager_folder_up`, `project_manager_folder_path`, `project_open`
- Media pool tools: `media_pool_list`, `media_pool_folder_open`, `media_pool_folder_create`, `media_pool_folder_up`, `media_pool_folder_root`, `media_pool_folder_path`, `media_pool_folder_list_recursive`, `media_pool_folder_open_path`, `media_import`, `media_clip_inspect`, `media_clip_inspect_path`
- Timeline and marker tools: `timeline_list`, `timeline_current`, `timeline_create_empty`, `timeline_set_current`, `timeline_append_clips`, `timeline_clips_place`, `timeline_create_from_clips`, `timeline_build_from_paths`, `timeline_items_list`, `timeline_inspect`, `timeline_track_items_list`, `timeline_track_inspect`, `timeline_item_inspect`, `timeline_item_delete`, `timeline_item_properties_get`, `timeline_item_properties_set`, `timeline_item_animation_preset_apply`, `timeline_item_animation_clear`, `timeline_image_place_animated`, `timeline_item_move`, `timeline_item_split`, `timeline_item_set_source_range`, `timeline_gap_close`, `timeline_remove_gaps`, `timeline_insert_gap`, `marker_add`, `marker_list`, `marker_inspect`, `marker_list_range`, `marker_delete`
- Local media-analysis tools: `audio_probe`, `audio_transcribe_segments`, `audio_detect_events`, `video_probe`, `video_detect_shots`, `video_sample_frames`, `video_extract_roi_frames`, `video_build_contact_sheet`, `video_detect_overlay_events`, `video_extract_segment_screenshots`, `video_segment_from_speech`, `video_segment_visual`, `video_segment_audio_visual`, `edit_plan_from_candidates`

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
   - `project_open`
   - `timeline_list`
   - `audio_probe`

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
DFMCP_LOCAL_HTTP_BIND_HOST=127.0.0.1
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
DFMCP_LOCAL_HTTP_BIND_HOST=127.0.0.1
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
- `project_open.success = true` when called with an existing project name
- `timeline_list.success = true`

## Agent live automation

For agent-only live validation, use the host helper instead of opening the project by hand:

```powershell
.\scripts\dev_agent_live_run.ps1 -ProjectName "Untitled Project 5" -Command "C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\integration -q"
```

What it does:

- reuses a healthy executor when available
- otherwise performs a Python-aware Resolve cold start, launches `resolve_executor_bootstrap` through Resolve UI automation, and waits for `resolve.connected = true`
- opens the requested project through the backend `project_open` command
- runs the supplied command on the host outside MCP

Important:

- the backend container must already be running
- bootstrap installation can be refreshed with `-ReinstallBootstrap`
- `.\scripts\dev_smoke_live.ps1` is the canonical autonomous smoke path on this machine
- if the helper reports a UI automation failure, follow `docs/LIVE_BOOTSTRAP_AUTOMATION.md` as the manual fallback
- if embedded scripts are disabled in Resolve, restart Resolve with `.\scripts\dev_start_resolve_with_python.ps1`

For a smoke-style wrapper around the same flow:

```powershell
.\scripts\dev_smoke_live.ps1 -ProjectName "Untitled Project 5" -Command "C:\Users\Yakoo\AppData\Local\Python\pythoncore-3.11-64\python.exe -m pytest tests\integration -q"
```

Recommended public MCP smoke for the new low-level toolset:

1. `media_pool_list`
2. `media_clip_inspect` for an existing clip in the current folder
3. `media_pool_folder_create` with a unique test bin name
4. `media_pool_folder_up`
5. `timeline_create_from_clips` with a unique timeline name
6. `marker_add`
7. `marker_list`
8. `marker_delete`
9. `timeline_items_list`

Recommended smoke for the local media-analysis layer:

1. `audio_probe` on a known local media file
2. `video_probe` on a known local media file
3. `video_detect_shots`
4. `video_sample_frames`
5. `video_build_contact_sheet`
6. `edit_plan_from_candidates` with a tiny synthetic candidate list

## Agent external scripting fallback

If embedded executor startup is blocked but Resolve external scripting is available on the host, use the agent-only external runner:

```powershell
.\scripts\dev_external_scripting_diagnostics.ps1 -ProjectName "Demo Project"
.\scripts\dev_agent_external_run.ps1 -ProjectName "Demo Project" -Command "pytest tests\integration -q"
```

What it does:

- starts Resolve when needed
- waits for `DaVinciResolveScript.scriptapp("Resolve")` to become available
- opens the requested project through `LoadProject(projectName)`
- confirms `GetCurrentProject()` before running the host command

Important:

- this is an `agent-only` fallback path
- it does not use MCP or the embedded executor
- if diagnostics still report `resolve_connected = false`, the next fallback is UI automation
- `-NoGui` is available for experiments, but should not be the default unless proven stable on this machine

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
