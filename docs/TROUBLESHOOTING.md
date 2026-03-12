# Troubleshooting

## `resolve_not_ready`

Symptoms:

- diagnostics return `resolve_not_ready`
- DaVinci Console shows `resolve=not_ready`

Checks:

- make sure the script was started from inside DaVinci Resolve, not from a regular Python shell
- verify that Resolve still has an open scripting session
- restart Resolve and launch `resolve_executor_bootstrap` again

## Duplicate executor

Symptoms:

- mixed console output from multiple runs
- `executor_status.json` flips between contradictory states
- repeated status writes from more than one instance

Checks:

- fully close Resolve and relaunch it
- make sure the bootstrap is started only once
- if needed, run `.\scripts\dev_reset_runtime.ps1 -IncludeLock` only after Resolve is fully closed
- if a second start happens while one is healthy, Resolve Console should print `[DFMCP] already running`
- compare `instance_id` in:
  - `.\scripts\dev_status.ps1`
  - `.\scripts\dev_who_owns_lock.ps1`
  - `.\scripts\dev_logs.ps1`

What we confirmed in practice:

- DaVinci Resolve itself does not automatically start our bootstrap on app launch
- `fuscript.exe` appears after launching `resolve_executor_bootstrap` from the Resolve scripts menu
- old behavior came from lingering `fuscript.exe` instances, not from Resolve silently loading an old script version by itself
- after a clean shutdown and a single manual script start, the executor runs with the current installed script version

## `unsupported_command`

Symptoms:

- diagnostics return `unsupported_command`

Meaning:

- the running executor instance does not know that command
- this is not evidence of a DaVinci Resolve Free limitation by itself

Checks:

- confirm you reinstalled `resolve_executor_bootstrap.py`
- relaunch the bootstrap inside Resolve
- compare `instance_id` in status, lock, and log output

## Stale status

Symptoms:

- `executor_status.state` is `stale`
- `last_poll_at` stops advancing

Checks:

- verify Resolve Console still prints `[DFMCP] alive ...`
- inspect `.\scripts\dev_logs.ps1`
- if the executor is no longer active, restart it from the Resolve menu

## Missing Python in Resolve

Symptoms:

- Python scripts do not appear in the Resolve menu
- Resolve Console reports that Python is not installed

Checks:

- install a Python version compatible with the Resolve embedded scripting environment
- restart Resolve after installation
- reinstall the bootstrap with `.\scripts\dev_install_executor.ps1`

## Permission issues on shared runtime

Symptoms:

- log entries mention non-fatal JSON write failures
- status updates lag while diagnostics are reading the same file

Checks:

- transient failures are tolerated; the executor should keep running
- if failures become persistent, stop repeated diagnostics loops and rerun `.\scripts\dev_smoke.ps1`
- if needed, reset runtime files with `.\scripts\dev_reset_runtime.ps1`
