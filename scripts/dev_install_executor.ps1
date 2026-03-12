param(
    [switch]$RemoveSystemCopy = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "scripts\resolve_executor_bootstrap.py"
$userDir = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
$userTarget = Join-Path $userDir "resolve_executor_bootstrap.py"
$systemTarget = "C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility\resolve_executor_bootstrap.py"

New-Item -ItemType Directory -Force -Path $userDir | Out-Null
Copy-Item $source $userTarget -Force

if ($RemoveSystemCopy -and (Test-Path $systemTarget)) {
    Remove-Item $systemTarget -Force
}

Write-Host "Executor installed:"
Write-Host "  $userTarget"
if ($RemoveSystemCopy) {
    Write-Host "System-level duplicate removed when present."
}
