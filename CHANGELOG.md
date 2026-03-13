# Changelog

All notable changes to this project should be recorded in this file.

The format is intentionally simple:

- date
- version or milestone label
- short list of meaningful changes

## 2026-03-13 - Marker, media folder, and timeline creation expansion

- added low-level marker tools:
  - `marker_list`
  - `marker_delete`
- added low-level media pool navigation and inspection tools:
  - `media_pool_folder_create`
  - `media_pool_folder_up`
  - `media_clip_inspect`
- added low-level timeline creation tool:
  - `timeline_create_from_clips`
- extended backend, executor, and MCP contracts for marker listing/deletion, folder creation/up-navigation, clip inspection, and timeline creation from resolved media pool clips
- expanded backend and integration coverage for the new toolset
- hardened `file_queue` result polling on Windows by retrying around transient result-file `PermissionError`

## 2026-03-12 - Core media and timeline tool expansion

- added low-level timeline tools:
  - `timeline_current`
  - `timeline_create_empty`
  - `timeline_append_clips`
  - `timeline_items_list`
- added low-level media tools:
  - `media_pool_list`
  - `media_import`
- extended backend and executor contracts for media pool listings, imports, timeline append results, and grouped track item inspection
- added integration coverage for timeline creation, media import, append flows, ambiguous clip detection, and grouped timeline track inspection

## 2026-03-12 - Agent live automation and project opening

- added low-level `project_open` across executor, backend, and MCP server
- added agent-only host helper `scripts/dev_agent_live_run.ps1` to wait for executor readiness, open a target project, and run a host command outside MCP
- added `scripts/dev_smoke_live.ps1` for non-interactive live smoke runs
- added agent-only external scripting fallback with `scripts/dev_external_scripting_diagnostics.ps1` and `scripts/dev_agent_external_run.ps1`
- updated docs to recommend the new live automation flow for agent-driven validation

## 2026-03-12 - Embedded script launch stabilization

- added `scripts/dev_start_resolve_with_python.ps1` to start Resolve with Python 3.11 present in `PATH`
- confirmed that embedded `Workspace -> Scripts` availability on this machine depends on launching Resolve with a usable Python in `PATH`
- documented the reliable retest cycle for live feature validation:
  - kill stale Resolve processes
  - reinstall bootstrap when needed
  - recreate the backend container
  - start Resolve with Python-aware environment
  - open the test project
  - launch `resolve_executor_bootstrap`
  - run diagnostics and MCP smoke checks

## 2026-03-12 - MVP foundation

- created the initial MCP-first project scaffold for DaVinci Resolve Free
- added documentation for architecture, roadmap, tools, references, development, risks, running, and troubleshooting
- added Dockerized external MCP/backend service
- implemented `file_queue` bridge
- implemented standalone Resolve bootstrap for internal execution in Resolve Free
- added console-first executor observability and machine-readable executor status
- added read-only tools:
  - `resolve_health`
  - `project_current`
  - `project_list`
  - `timeline_list`
- added `instance_id` and lock ownership diagnostics for executor duplication analysis
- added `local_http` bridge prototype inspired by the internal REST approach
- added PowerShell helper scripts for install, runtime reset, diagnostics, logs, lock inspection, and smoke checks

## 2026-03-12 - Executor observability and read-only expansion

- added read-only project and timeline tools to the backend and MCP surface
- added `instance_id` to executor logging and status output
- added lock ownership diagnostics for duplicate executor investigation
- added `dev_kill_davinci.ps1` for full shutdown of `Resolve.exe` and `fuscript.exe`
- made duplicate executor warnings explicit in DaVinci Console
- normalized unknown-command handling toward `unsupported_command`
- documented Codex Desktop connection flow and REST-mode verification
- added Russian-language overview documentation
- documented `host.docker.internal` as the correct local HTTP host for Dockerized backend testing
