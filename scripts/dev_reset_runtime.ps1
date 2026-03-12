param(
    [switch]$IncludeLock
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$targets = @(
    "runtime\status\executor_status.json",
    "runtime\logs\resolve_executor.log"
)

if ($IncludeLock) {
    $targets += "runtime\status\executor.lock.json"
}

foreach ($target in $targets) {
    Remove-Item (Join-Path $repoRoot $target) -Force -ErrorAction SilentlyContinue
}

$patterns = @(
    "runtime\spool\requests\*.json",
    "runtime\spool\results\*.json",
    "runtime\spool\deadletter\*.json"
)

foreach ($pattern in $patterns) {
    Get-ChildItem (Join-Path $repoRoot $pattern) -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

if (-not $IncludeLock) {
    Write-Host "Runtime cleared. Lock file was preserved."
    exit 0
}

Write-Host "Runtime cleared."
