$ErrorActionPreference = "Stop"

$userTarget = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\resolve_executor_bootstrap.py"
$systemTarget = "C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility\resolve_executor_bootstrap.py"

Remove-Item $userTarget -Force -ErrorAction SilentlyContinue
Remove-Item $systemTarget -Force -ErrorAction SilentlyContinue

Write-Host "Executor bootstrap removed from Resolve script directories."
