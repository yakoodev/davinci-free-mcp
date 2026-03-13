param(
    [string]$ProjectName,
    [string]$ResolvePath = "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
    [int]$TimeoutSeconds = 30,
    [switch]$NoGui
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
    "-m", "davinci_free_mcp.external_agent.diagnostics",
    "--resolve-path", $ResolvePath,
    "--timeout-seconds", $TimeoutSeconds
)

if ($ProjectName) {
    $args += @("--project-name", $ProjectName)
}

if ($NoGui) {
    $args += "--nogui"
}

& $python @args
