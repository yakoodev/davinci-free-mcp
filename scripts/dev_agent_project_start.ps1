param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("existing", "blank")]
    [string]$TargetMode,

    [string]$ProjectName,
    [string]$BlankProjectName = "DFMCP Blank",

    [Parameter(Mandatory = $true)]
    [string]$Command,

    [string]$ResolvePath = "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
    [int]$WarmupSeconds = 60,
    [int]$TimeoutSeconds = 120,
    [double]$PollIntervalSeconds = 1.0,
    [bool]$RestorePrefsOnExit = $false
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
    "-m", "davinci_free_mcp.external_agent.startup",
    "--target-mode", $TargetMode,
    "--blank-project-name", $BlankProjectName,
    "--command", $Command,
    "--resolve-path", $ResolvePath,
    "--warmup-seconds", $WarmupSeconds,
    "--timeout-seconds", $TimeoutSeconds,
    "--poll-interval-seconds", $PollIntervalSeconds,
    "--restore-prefs-on-exit", ($RestorePrefsOnExit.ToString().ToLowerInvariant())
)

if ($ProjectName) {
    $args += @("--project-name", $ProjectName)
}

& $python @args
if ($LASTEXITCODE -ne 0) {
    throw "Resolve project startup flow failed with exit code $LASTEXITCODE."
}
