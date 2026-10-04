# Offline, read-only checks for a NEW local MedFlux pilot checkout.
# Does not connect to databases, run installers, read passwords aloud or touch Ahmed's computer.
param(
  [string]$Root = (Split-Path -Parent $PSScriptRoot),
  [int]$ExpectedPostgresPort = 55440
)
$ErrorActionPreference = "Stop"
$rootPath = [IO.Path]::GetFullPath($Root)
$issues = [System.Collections.Generic.List[string]]::new()
$envPath = Join-Path $rootPath ".env"
if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
  $issues.Add("Missing .env. Prepare it locally from .env.example; do not commit it.")
} else {
  $values = @{}
  foreach ($line in (Get-Content -LiteralPath $envPath)) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
      $values[$Matches[1].ToUpperInvariant()] = $Matches[2].Trim('"', "'")
    }
  }
  $envName = if ($values.ContainsKey("APP_ENV")) { $values["APP_ENV"].ToLowerInvariant() } else { "development" }
  if ($envName -ne "development") {
    $issues.Add("Local HTTP pilot requires APP_ENV=development; pilot/production require HTTPS secure cookies and different provisioning.")
  }
  if ($values["AUTH_ENABLED"] -ne "true") { $issues.Add("AUTH_ENABLED must be true.") }
  if ($values["MEDFLUX_INSECURE_DEV"] -eq "true") { $issues.Add("MEDFLUX_INSECURE_DEV must not be enabled.") }
  if (-not $values["APP_SECRET_KEY"] -or $values["APP_SECRET_KEY"] -eq "change-me" -or $values["APP_SECRET_KEY"].Length -lt 32) {
    $issues.Add("Set a unique APP_SECRET_KEY of at least 32 characters.")
  }
  if ($values["AUTH_COOKIE_SECURE"] -ne "false") {
    $issues.Add("Loopback HTTP requires AUTH_COOKIE_SECURE=false; never use this configuration on a public interface.")
  }
  if ($values["BACKEND_HOST"] -and $values["BACKEND_HOST"] -notin @("127.0.0.1","localhost")) {
    $issues.Add("BACKEND_HOST must be loopback for local HTTP.")
  }
  if ($values["CONTRACTS_ALLOW_DELETE"] -eq "true") {
    $issues.Add("Keep CONTRACTS_ALLOW_DELETE disabled until the deletion authorization policy is approved.")
  }
  $url = $values["DATABASE_URL"]
  if (-not $url) {
    $issues.Add("DATABASE_URL is missing.")
  } else {
    try {
      $uri = [Uri]($url -replace '^postgresql\+psycopg://', 'postgresql://')
      if ($uri.Host -notin @("127.0.0.1","localhost") -or $uri.Port -ne $ExpectedPostgresPort) {
        $issues.Add("DATABASE_URL must point to isolated loopback PostgreSQL on expected port $ExpectedPostgresPort.")
      }
    } catch { $issues.Add("DATABASE_URL cannot be parsed.") }
  }
}
foreach ($relative in @("backend/requirements.txt", "frontend/package.json", "scripts/provision_ahmed_local_pg.ps1")) {
  if (-not (Test-Path -LiteralPath (Join-Path $rootPath $relative))) { $issues.Add("Missing required file: $relative") }
}
if ($issues.Count -gt 0) {
  foreach ($issue in $issues) { Write-Host "FAIL: $issue" }
  throw "Offline pilot preflight failed ($($issues.Count) issue(s)); no installation attempted."
}
Write-Host "PASS: static local pilot configuration checks. No DB, runtime, authentication or AI inference was tested."
