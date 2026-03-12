$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$statusPath = Join-Path $repoRoot "runtime\status\executor_status.json"

if (-not (Test-Path $statusPath)) {
    Write-Host "executor status not found"
    exit 0
}

$json = Get-Content $statusPath -Raw | ConvertFrom-Json
Write-Host ("instance_id: " + $json.instance_id)
Write-Host ("bridge: " + $json.bridge.adapter)
Write-Host ("running: " + $json.running)
Write-Host ("resolve.connected: " + $json.resolve.connected)
Write-Host ("project: " + $json.project.name)
Write-Host ("timeline: " + $json.timeline.name)
Write-Host ("last_request_id: " + $json.last_request_id)
Write-Host ""
Get-Content $statusPath
