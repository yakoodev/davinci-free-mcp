$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$lockPath = Join-Path $repoRoot "runtime\status\executor.lock.json"

if (-not (Test-Path $lockPath)) {
    Write-Host "executor lock not found"
    exit 0
}

$json = Get-Content $lockPath -Raw | ConvertFrom-Json
Write-Host ("instance_id: " + $json.instance_id)
Write-Host ("instance_started_at: " + $json.instance_started_at)
Write-Host ("bridge_mode: " + $json.bridge_mode)
Write-Host ("token: " + $json.token)
Write-Host ""
Get-Content $lockPath
