<#
.SYNOPSIS
  Browser-Tests (Playwright) gegen eine lokale Wegwerf-Datenbank.

.DESCRIPTION
  1. Liest frontend/e2e/.env (falls vorhanden) bzw. frontend/e2e/.env.example.
  2. Migriert die Wegwerf-Datenbank (E2E_DATABASE_URL, nie Port 5432) und legt Testdaten an.
  3. Startet Backend (Port aus E2E_API_URL) und Frontend (Port aus E2E_BASE_URL).
  4. Fuehrt Playwright aus und beendet beide Server.

.PARAMETER UpdateSnapshots
  Bildvergleich-Referenzen neu schreiben (nach bewussten Design-Aenderungen).

.PARAMETER Baseline
  Barrierefreiheits-Verstoesse nur protokollieren, nicht fehlschlagen lassen.
#>
param([switch]$UpdateSnapshots, [switch]$Baseline)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"

$envFile = Join-Path $frontend "e2e/.env"
if (-not (Test-Path $envFile)) { $envFile = Join-Path $frontend "e2e/.env.example" }
foreach ($line in Get-Content $envFile) {
  if ($line -match '^([A-Z0-9_]+)=(.*)$') { Set-Item -Path "env:$($Matches[1])" -Value $Matches[2] }
}
if ($env:E2E_DATABASE_URL -match ':5432/') { throw "E2E_DATABASE_URL darf nicht Port 5432 verwenden." }

$apiPort = ([uri]$env:E2E_API_URL).Port
$webPort = ([uri]$env:E2E_BASE_URL).Port
$python = Join-Path $backend ".venv/Scripts/python.exe"

$env:DATABASE_URL = $env:E2E_DATABASE_URL
$env:APP_ENV = "development"
$env:AUTH_ENABLED = "true"
$env:AUTH_COOKIE_SECURE = "false"
$env:MEDFLUX_INSECURE_DEV = "false"
$env:APP_SECRET_KEY = "e2e-only-secret-key-not-for-production-0001"
$env:CORS_ORIGINS = $env:E2E_BASE_URL
$env:APP_PUBLIC_URL = $env:E2E_BASE_URL
$env:REMINDER_SCHEDULER_ENABLED = "false"
$env:DATA_DIR = Join-Path $env:TEMP "medflux-e2e-data"
$env:CONTRACTS_DIR = Join-Path $env:DATA_DIR "contracts"
$env:BACKUPS_DIR = Join-Path $env:DATA_DIR "backups"

Push-Location $backend
& $python -m alembic upgrade head
& $python scripts/seed_e2e.py
$api = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $apiPort -PassThru -WindowStyle Hidden
Pop-Location

Push-Location $frontend
$env:NEXT_PUBLIC_API_URL = $env:E2E_API_URL
$env:NEXT_PUBLIC_ORG_SLUG = $env:E2E_ORG_SLUG
$web = Start-Process -FilePath "npx.cmd" -ArgumentList "next", "dev", "-p", $webPort -PassThru -WindowStyle Hidden
try {
  $deadline = (Get-Date).AddMinutes(3)
  while ((Get-Date) -lt $deadline) {
    try { Invoke-WebRequest -UseBasicParsing "$($env:E2E_BASE_URL)/login" -TimeoutSec 5 | Out-Null; break } catch { Start-Sleep -Seconds 2 }
  }
  if ($Baseline) { $env:E2E_AXE_BASELINE = "1" }
  $args = @("playwright", "test")
  # "all": auch Referenzen mit kleinen Abweichungen neu schreiben (z. B. nach Farbaenderungen).
  if ($UpdateSnapshots) { $args += "--update-snapshots=all" }
  & npx.cmd @args
  $code = $LASTEXITCODE
} finally {
  # Ganzen Prozessbaum beenden (npx startet next als Kindprozess, der sonst Port und Datei-Sperren behaelt).
  & taskkill.exe /PID $web.Id /T /F 2>&1 | Out-Null
  Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
  Pop-Location
}
exit $code
