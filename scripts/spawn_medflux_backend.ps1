# Starts the MedFlux backend (uvicorn) as a hidden, tracked process.
# Writes the real PID to <RuntimeDir>\backend.pid so that STOP_MEDFLUX_LOCAL.bat
# can terminate exactly this process tree (and nothing else).
#
# Exit codes:
#   0  started
#   11 venv python missing
#  12 pyproject/requirements not found

param(
    [Parameter(Mandatory = $true)][string]$RootDir,
    [string]$RuntimeDir = "$env:LOCALAPPDATA\MedFlux\runtime",
    [string]$Port = "8000"
)

$ErrorActionPreference = "Stop"

$backendDir = Join-Path $RootDir "backend"
$py = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    Write-Host "[ERROR] Backend venv python missing: $py" -ForegroundColor Red
    exit 11
}

if (-not (Test-Path -LiteralPath $RuntimeDir)) {
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
}

$stdout = Join-Path $RuntimeDir "backend.log"
$stderr = Join-Path $RuntimeDir "backend.err.log"

$args = @("-m", "uvicorn", "app.main:app", "--reload", "--port", $Port)

$proc = Start-Process -FilePath $py `
    -ArgumentList $args `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Set-Content -LiteralPath (Join-Path $RuntimeDir "backend.pid") -Encoding ASCII
Write-Host "backend started (pid $($proc.Id))."
exit 0