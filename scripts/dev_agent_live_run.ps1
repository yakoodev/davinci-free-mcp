param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectName,

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [int]$ResolveTimeoutSeconds = 45,
    [int]$ExecutorTimeoutSeconds = 120,
    [int]$ProjectTimeoutSeconds = 30,
    [int]$FreshWithinSeconds = 90,
    [string]$ResolvePath = "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
    [string]$ContainerName = "davinci-free-mcp",
    [switch]$ReinstallBootstrap
)

$ErrorActionPreference = "Stop"

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

$python = Get-PreferredPython
$args = @(
    "-m", "davinci_free_mcp.external_agent.live_run",
    "--project-name", $ProjectName,
    "--command", $Command,
    "--resolve-timeout-seconds", $ResolveTimeoutSeconds,
    "--executor-timeout-seconds", $ExecutorTimeoutSeconds,
    "--project-timeout-seconds", $ProjectTimeoutSeconds,
    "--fresh-within-seconds", $FreshWithinSeconds,
    "--resolve-path", $ResolvePath,
    "--container-name", $ContainerName
)

if ($ReinstallBootstrap) {
    $args += "--reinstall-bootstrap"
}

& $python @args
if ($LASTEXITCODE -ne 0) {
    throw "Live Resolve runner failed with exit code $LASTEXITCODE."
}
