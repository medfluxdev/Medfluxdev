# Starts the MedFlux frontend (Next.js dev server) as a hidden, tracked process.
# Writes the real PID to <RuntimeDir>\frontend.pid so that STOP_MEDFLUX_LOCAL.bat
# can terminate exactly this process tree (and nothing else).
# node_modules must already exist (the launcher never downloads/installs).
#
# Exit codes:
#   0  started
#   12 node or npm not found
#   13 frontend/node_modules missing (run `npm install` once manually)

param(
    [Parameter(Mandatory = $true)][string]$RootDir,
    [string]$RuntimeDir = "$env:LOCALAPPDATA\MedFlux\runtime"
)

$ErrorActionPreference = "Stop"

$frontendDir = Join-Path $RootDir "frontend"

$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "[ERROR] node.exe was not found in PATH. Install/start Node.js first." -ForegroundColor Red
    exit 12
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[ERROR] frontend\node_modules is missing. Run 'npm install' once manually (the launcher never installs automatically)." -ForegroundColor Red
    exit 13
}

if (-not (Test-Path -LiteralPath $RuntimeDir)) {
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
}

$stdout = Join-Path $RuntimeDir "frontend.log"
$stderr = Join-Path $RuntimeDir "frontend.err.log"

$proc = Start-Process -FilePath $node.Source `
    -ArgumentList @("node_modules\next\dist\bin\next", "dev") `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Set-Content -LiteralPath (Join-Path $RuntimeDir "frontend.pid") -Encoding ASCII
Write-Host "frontend started (pid $($proc.Id))."
exit 0