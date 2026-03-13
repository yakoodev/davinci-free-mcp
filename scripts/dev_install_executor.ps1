param(
    [switch]$RemoveSystemCopy = $true
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$templatePath = Join-Path $repoRoot "scripts\resolve_executor_bootstrap.py"
$coreSourcePath = Join-Path $repoRoot "src\davinci_free_mcp\resolve_exec\command_core.py"
$userDir = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
$userTarget = Join-Path $userDir "resolve_executor_bootstrap.py"
$systemTarget = "C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility\resolve_executor_bootstrap.py"

New-Item -ItemType Directory -Force -Path $userDir | Out-Null

$template = Get-Content $templatePath -Raw
$coreSource = Get-Content $coreSourcePath -Raw
$renderedRepoRoot = $repoRoot.Replace('\', '/')
$rendered = $template.Replace("__DFMCP_INSTALL_REPO_ROOT__", $renderedRepoRoot)
$rendered = $rendered.Replace("# __DFMCP_EMBEDDED_COMMAND_CORE__", $coreSource)
Set-Content -Path $userTarget -Value $rendered -Encoding utf8

if ($RemoveSystemCopy -and (Test-Path $systemTarget)) {
    Remove-Item $systemTarget -Force
}

Write-Host "Executor installed:"
Write-Host "  $userTarget"
Write-Host "Rendered with embedded shared command core."
if ($RemoveSystemCopy) {
    Write-Host "System-level duplicate removed when present."
}
