$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

$statusPath = Join-Path $repoRoot "runtime\status\executor_status.json"
$lockPath = Join-Path $repoRoot "runtime\status\executor.lock.json"

if ((Test-Path $statusPath) -or (Test-Path $lockPath)) {
    Write-Host "Existing executor state detected."
    Write-Host "Close DaVinci Resolve or stop the running executor before dev_smoke."
    Write-Host "If you really need a hard reset, run:"
    Write-Host "  .\scripts\dev_reset_runtime.ps1 -IncludeLock"
    exit 1
}

& (Join-Path $PSScriptRoot "dev_reset_runtime.ps1")
Write-Host ""
Write-Host "Run resolve_executor_bootstrap inside DaVinci Resolve, then press Enter."
Read-Host | Out-Null

Write-Host ""
Write-Host "Diagnostics:"
& (Join-Path $PSScriptRoot "dev_diagnostics.ps1")

Write-Host ""
Write-Host "Executor status:"
& (Join-Path $PSScriptRoot "dev_status.ps1")

Write-Host ""
Write-Host "Executor log:"
& (Join-Path $PSScriptRoot "dev_logs.ps1")
