# AGENTS.md

## Resolve Runtime Operations

- During development and testing, the agent may stop DaVinci-side runtime processes without asking first by running `.\scripts\dev_kill_davinci.ps1`.
- During development and testing, the agent may start DaVinci Resolve on the host machine without asking first when a live MCP or bridge test requires it.
- After updating `scripts/resolve_executor_bootstrap.py`, the agent should reinstall it with `.\scripts\dev_install_executor.ps1` before live validation.
- When a live test depends on the embedded executor, the preferred sequence is:
  1. stop stale DaVinci-side processes if needed
  2. start Resolve
  3. run `resolve_executor_bootstrap`
  4. run `.\scripts\dev_diagnostics.ps1`
  5. run MCP smoke checks

## Validation Preference

- Prefer validating new Resolve features against the live MCP endpoint when Resolve is available, not only through fake integration tests.
