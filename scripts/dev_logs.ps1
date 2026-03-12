param(
    [int]$Tail = 50
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $repoRoot "runtime\logs\resolve_executor.log"

if (-not (Test-Path $logPath)) {
    Write-Host "executor log not found"
    exit 0
}

Get-Content $logPath -Tail $Tail | Where-Object { $_ -match "\[DFMCP\]" -or $_ -match "Unsupported command" -or $_ -match "Resolve handle" }
