# AGENTS.md

## Resolve Runtime Operations

- During development and testing, the agent may stop DaVinci-side runtime processes without asking first by running `.\scripts\dev_kill_davinci.ps1`.
- During development and testing, the agent may start DaVinci Resolve on the host machine without asking first when a live MCP or bridge test requires it.
- When the live flow depends on Resolve Python scripts appearing in `Workspace -> Scripts`, prefer starting Resolve through `.\scripts\dev_start_resolve_with_python.ps1` so Python 3.11 is present in `PATH` for that Resolve process.
- After updating `scripts/resolve_executor_bootstrap.py`, the agent should reinstall it with `.\scripts\dev_install_executor.ps1` before live validation.
- When a live test depends on the embedded executor, the preferred sequence is:
  1. stop stale DaVinci-side processes if needed
  2. reinstall `resolve_executor_bootstrap.py` if it changed
  3. recreate the backend container when backend-facing code changed
  4. start Resolve with `.\scripts\dev_start_resolve_with_python.ps1`
  5. open the live test project
  6. run `resolve_executor_bootstrap` from `Workspace -> Scripts`
  7. run `.\scripts\dev_diagnostics.ps1`
  8. run MCP smoke checks

## Validation Preference

- Prefer validating new Resolve features against the live MCP endpoint when Resolve is available, not only through fake integration tests.
