param(
    [string]$ResolvePath = "C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ("[resolve-start] " + $Message)
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

if (-not (Test-Path $ResolvePath)) {
    throw "Resolve executable not found at '$ResolvePath'."
}

$python = Get-PreferredPython
$pythonCommand = Get-Command $python -ErrorAction Stop
$pythonPath = $pythonCommand.Source
$pythonDir = Split-Path -Parent $pythonPath
$pythonRoot = Split-Path -Parent $pythonDir
$pythonScriptsDir = Join-Path $pythonRoot "Scripts"

$resolveEnvPath = @($pythonDir, $pythonRoot)
if (Test-Path $pythonScriptsDir) {
    $resolveEnvPath += $pythonScriptsDir
}
$resolveEnvPath += $env:PATH

Write-Step ("Starting Resolve with Python from '{0}'." -f $pythonPath)
Write-Step "This keeps Resolve Python scripts enabled in the Workspace -> Scripts menu."

$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $ResolvePath
$startInfo.UseShellExecute = $false
$startInfo.WorkingDirectory = Split-Path -Parent $ResolvePath
$startInfo.Environment["PATH"] = ($resolveEnvPath -join ";")

[System.Diagnostics.Process]::Start($startInfo) | Out-Null

Write-Step "Resolve launch requested."
