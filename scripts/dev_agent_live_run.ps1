param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [int]$ResolveTimeoutSeconds = 45,
    [int]$ExecutorTimeoutSeconds = 120,
    [int]$ProjectTimeoutSeconds = 30,
    [int]$StaleAfterSeconds = 15,
    [string]$ResolvePath = "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
    [string]$ContainerName = "davinci-free-mcp",
    [switch]$ReinstallBootstrap
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$statusPath = Join-Path $repoRoot "runtime\status\executor_status.json"
$lockPath = Join-Path $repoRoot "runtime\status\executor.lock.json"

function Write-Step {
    param([string]$Message)
    Write-Host ("[agent-live] " + $Message)
}

function Test-ContainerRunning {
    param([string]$Name)

    $running = docker inspect -f "{{.State.Running}}" $Name 2>$null
    return ($LASTEXITCODE -eq 0 -and $running.Trim() -eq "true")
}

function Get-ExecutorStatus {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    try {
        return Get-Content $Path -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-StatusAgeSeconds {
    param($Status)

    if ($null -eq $Status -or [string]::IsNullOrWhiteSpace($Status.last_poll_at)) {
        return [double]::PositiveInfinity
    }

    try {
        $lastPoll = [datetime]::Parse($Status.last_poll_at).ToUniversalTime()
    }
    catch {
        return [double]::PositiveInfinity
    }

    return ([datetime]::UtcNow - $lastPoll).TotalSeconds
}

function Test-HealthyExecutor {
    param(
        $Status,
        [int]$FreshWithinSeconds
    )

    if ($null -eq $Status) {
        return $false
    }

    if (-not $Status.running) {
        return $false
    }

    if ($null -eq $Status.resolve -or -not $Status.resolve.connected) {
        return $false
    }

    return (Get-StatusAgeSeconds -Status $Status) -le $FreshWithinSeconds
}

function Wait-Until {
    param(
        [scriptblock]$Condition,
        [int]$TimeoutSeconds,
        [string]$FailureMessage
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) {
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw $FailureMessage
}

function Invoke-BackendTool {
    param(
        [string]$Method,
        [hashtable]$Arguments
    )

    $kwargsJson = $Arguments | ConvertTo-Json -Compress
    $python = @'
import json
import sys

from davinci_free_mcp.backend import ResolveBackendService
from davinci_free_mcp.bridge import create_bridge
from davinci_free_mcp.config import AppSettings

settings = AppSettings()
backend = ResolveBackendService(create_bridge(settings), settings)
method = getattr(backend, sys.argv[1])
kwargs = json.loads(sys.argv[2])
result = method(**kwargs)
print(result.model_dump_json())
sys.exit(0 if result.success else 2)
'@

    $rawOutput = $python | docker exec -i $ContainerName python - $Method $kwargsJson
    $exitCode = $LASTEXITCODE
    if ([string]::IsNullOrWhiteSpace($rawOutput)) {
        throw "Backend tool '$Method' returned no output."
    }

    $parsed = $rawOutput | ConvertFrom-Json
    return @{
        ExitCode = $exitCode
        Result = $parsed
    }
}

function Ensure-ProjectOpen {
    param(
        [string]$Name,
        [int]$TimeoutSeconds
    )

    $timeoutMs = $TimeoutSeconds * 1000
    $current = Invoke-BackendTool -Method "project_current" -Arguments @{ timeout_ms = $timeoutMs }
    if ($current.ExitCode -eq 0 -and $current.Result.data.project.open -and $current.Result.data.project.name -eq $Name) {
        Write-Step "Target project '$Name' is already open."
        return
    }

    Write-Step "Opening Resolve project '$Name' through backend service."
    $opened = Invoke-BackendTool -Method "project_open" -Arguments @{
        project_name = $Name
        timeout_ms = $timeoutMs
    }

    if ($opened.ExitCode -ne 0) {
        $message = $opened.Result.error.message
        if ([string]::IsNullOrWhiteSpace($message)) {
            $message = "project_open failed."
        }
        throw $message
    }

    $confirmed = Invoke-BackendTool -Method "project_current" -Arguments @{ timeout_ms = $timeoutMs }
    if ($confirmed.ExitCode -ne 0 -or -not $confirmed.Result.data.project.open -or $confirmed.Result.data.project.name -ne $Name) {
        throw "Project '$Name' did not become current after project_open."
    }
}

if (-not (Test-ContainerRunning -Name $ContainerName)) {
    throw "Docker container '$ContainerName' is not running. Start the backend with .\scripts\dev_up.ps1 first."
}

if ($ReinstallBootstrap) {
    Write-Step "Reinstalling Resolve bootstrap."
    & (Join-Path $PSScriptRoot "dev_install_executor.ps1")
}

$status = Get-ExecutorStatus -Path $statusPath
$healthyExecutor = Test-HealthyExecutor -Status $status -FreshWithinSeconds $StaleAfterSeconds
$resolveRunning = $null -ne (Get-Process Resolve -ErrorAction SilentlyContinue)
$staleRuntime = (Test-Path $lockPath) -or (Test-Path $statusPath)

if (-not $healthyExecutor) {
    if (-not $resolveRunning -or $staleRuntime) {
        Write-Step "Recovering host runtime before live run."
        & (Join-Path $PSScriptRoot "dev_kill_davinci.ps1")
        & (Join-Path $PSScriptRoot "dev_reset_runtime.ps1") -IncludeLock
        $resolveRunning = $false
    }

    if (-not $resolveRunning) {
        if (-not (Test-Path $ResolvePath)) {
            throw "Resolve executable not found at '$ResolvePath'."
        }

        Write-Step "Starting Resolve."
        Start-Process -FilePath $ResolvePath | Out-Null
    }

    Write-Step "Waiting for Resolve process."
    Wait-Until -TimeoutSeconds $ResolveTimeoutSeconds -FailureMessage "Resolve did not start within $ResolveTimeoutSeconds seconds." -Condition {
        $null -ne (Get-Process Resolve -ErrorAction SilentlyContinue)
    }

    Write-Step "Waiting for embedded executor to become healthy."
    Wait-Until -TimeoutSeconds $ExecutorTimeoutSeconds -FailureMessage "Executor did not become healthy within $ExecutorTimeoutSeconds seconds. Start resolve_executor_bootstrap inside Resolve if it is not already running." -Condition {
        $freshStatus = Get-ExecutorStatus -Path $statusPath
        Test-HealthyExecutor -Status $freshStatus -FreshWithinSeconds $StaleAfterSeconds
    }
}
else {
    Write-Step "Healthy executor detected, reusing current Resolve session."
}

Ensure-ProjectOpen -Name $ProjectName -TimeoutSeconds $ProjectTimeoutSeconds

Write-Step "Running agent command."
& $env:ComSpec /d /s /c $Command
if ($LASTEXITCODE -ne 0) {
    throw "Agent command failed with exit code $LASTEXITCODE."
}

Write-Step "Live run completed successfully."
