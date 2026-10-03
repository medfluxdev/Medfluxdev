# Stops ONLY the processes that this launcher started.
# Reads the PID files written by spawn_medflux_backend.ps1 /
# spawn_medflux_frontend.ps1. For safety, the process's command line is
# verified (backend -> app.main, frontend -> next dev) before it is terminated,
# so an unwanted/unrelated process with a reused PID is never killed.
# Ollama is NEVER stopped here; PostgreSQL is NEVER stopped here.
#
# Exit code: 0 always (informational).

param(
    [string]$RuntimeDir = "$env:LOCALAPPDATA\MedFlux\runtime"
)

$ErrorActionPreference = "Continue"

$pairs = @(
    @{ PidFile = "backend.pid";  Verify = "app.main" },
    @{ PidFile = "frontend.pid"; Verify = "next" }
)

foreach ($pair in $pairs) {
    $pidPath = Join-Path $RuntimeDir $pair.PidFile
    if (-not (Test-Path -LiteralPath $pidPath)) { continue }

    $stored = (Get-Content -LiteralPath $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($stored)) {
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        continue
    }

    [int]$procId = 0
    if (-not [int]::TryParse(([string]$stored).Trim(), [ref]$procId)) {
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        continue
    }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host ("{0}: process {1} is no longer running." -f $pair.PidFile, $procId)
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        continue
    }

    $cmdline = [string]$proc.CommandLine
    if (-not $cmdline.Contains($pair.Verify)) {
        Write-Host ("{0}: PID {1} does NOT belong to this launcher (cmd: {2}) - skipped." -f $pair.PidFile, $procId, $cmdline)
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        continue
    }

    Write-Host ("{0}: stopping PID {1} (process tree)." -f $pair.PidFile, $procId)
    & taskkill.exe /PID $procId /T /F | Out-Null
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "STOP complete."
Write-Host "PostgreSQL and an already-running Ollama server were intentionally left untouched."
exit 0