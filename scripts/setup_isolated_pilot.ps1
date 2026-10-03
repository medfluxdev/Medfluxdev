# Safe entry point for a NEW isolated local pilot checkout.
# Does not provision PostgreSQL or alter existing installations.
param([int]$PostgresPort = 55440)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$preflight = Join-Path $PSScriptRoot "verify_local_pilot_preflight.ps1"
$setup = Join-Path $PSScriptRoot "setup.ps1"

if (-not (Test-Path -LiteralPath $preflight)) { throw "Missing preflight script" }
if (-not (Test-Path -LiteralPath $setup)) { throw "Missing setup script" }
if (-not (Test-Path -LiteralPath (Join-Path $root ".env"))) {
    throw "Prepare a NEW local .env explicitly; refusing generic database defaults."
}

Write-Host "Checking isolated local pilot configuration..."
& $preflight -Root $root -ExpectedPostgresPort $PostgresPort
if (-not $?) { throw "Preflight failed. Setup not started." }

# The legacy setup is run only after preflight succeeds. Its migrations and
# dependency installation are NOT read-only; run this only with authorization.
Write-Warning "Preflight passed. The next stage installs dependencies and runs database migrations."
Write-Warning "Do not run this on Ahmed's current installation or an existing shared database."
& $setup
if (-not $?) { throw "Setup failed. Review output before proceeding." }
Write-Host "Setup finished; runtime acceptance testing and release approval still required."
