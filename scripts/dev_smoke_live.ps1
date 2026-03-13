param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [switch]$ReinstallBootstrap
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "dev_agent_live_run.ps1") `
    -ProjectName $ProjectName `
    -Command $Command `
    -ReinstallBootstrap:$ReinstallBootstrap
