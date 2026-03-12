$ErrorActionPreference = "Stop"

$targets = @("fuscript", "Resolve")
$stopped = @()

foreach ($name in $targets) {
    $procs = Get-Process $name -ErrorAction SilentlyContinue
    if ($null -ne $procs) {
        $procs | Stop-Process -Force
        $stopped += $procs | ForEach-Object { "{0}:{1}" -f $_.ProcessName, $_.Id }
    }
}

if ($stopped.Count -eq 0) {
    Write-Host "No DaVinci-related processes were running."
    exit 0
}

Write-Host "Stopped processes:"
$stopped | ForEach-Object { Write-Host "  $_" }
