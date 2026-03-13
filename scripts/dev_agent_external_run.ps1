param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [string]$ResolvePath = "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
    [int]$TimeoutSeconds = 120,
    [int]$LaunchWaitSeconds = 60,
    [double]$PollIntervalSeconds = 1.0,
    [switch]$NoGui
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ("[agent-external] " + $Message)
}

function Get-PreferredPython {
    if ($env:DFMCP_PYTHON) {
        return $env:DFMCP_PYTHON
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Python\bin\python3.11.exe"),
        (Join-Path $env:LOCALAPPDATA "Python\pythoncore-3.11-64\python.exe"),
        "python3.11",
        "python"
    )

    foreach ($candidate in $candidates) {
        try {
            $null = & $candidate -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
        catch {
        }
    }

    throw "Python 3.10+ was not found. Set DFMCP_PYTHON or install Python 3.11."
}

Write-Step "Running external Resolve automation flow."
 $python = Get-PreferredPython

$args = @(
    "-m", "davinci_free_mcp.external_agent.runner",
    "--project-name", $ProjectName,
    "--command", $Command,
    "--resolve-path", $ResolvePath,
    "--timeout-seconds", $TimeoutSeconds,
    "--launch-wait-seconds", $LaunchWaitSeconds,
    "--poll-interval-seconds", $PollIntervalSeconds
)

if ($NoGui) {
    $args += "--nogui"
}

& $python @args
if ($LASTEXITCODE -ne 0) {
    throw "External agent run failed with exit code $LASTEXITCODE."
}

Write-Step "External Resolve automation completed successfully."
