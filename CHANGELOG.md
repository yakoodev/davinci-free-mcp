# Changelog

All notable changes to this project should be recorded in this file.

The format is intentionally simple:

- date
- version or milestone label
- short list of meaningful changes

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
