# Build source-only pilot handoff archive from a clean, reviewed release checkout.
# Does NOT install, run, merge, deploy, provision databases, or invoke GPU.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
  if ((git status --porcelain) -ne $null) { throw "Working tree must be clean." }
  $branch = (git branch --show-current).Trim()
  if ($branch -ne "release/ahmed-pilot-package-20260929") { throw "Wrong branch: $branch" }
  $tracked = @(git ls-files)
  $forbidden = @($tracked | Where-Object { $_ -match '(^|/)(\.env($|\.)|pgdata/|node_modules/|\.venv/|data/contracts/|data/backups/)' -and $_ -notmatch '(^|/)\.env\.example$' })
  if ($forbidden.Count -gt 0) { throw "Potentially sensitive tracked paths found; STOP: $($forbidden -join ', ')" }
  $sha = (git rev-parse HEAD).Trim()
  $out = Join-Path (Split-Path $root -Parent) "MedFlux_Ahmed_Pilot_SOURCE_$($sha.Substring(0,12)).zip"
  if (Test-Path $out) { throw "Archive already exists; refusing overwrite: $out" }
  git archive --format=zip --output="$out" HEAD
  if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
  Write-Host "Created source-only handoff archive: $out"
  Write-Host "Pinned revision: $sha"
  Write-Warning "NOT a validated installer. Do not distribute until local installation + analysis walkthrough passes and Jamal approves."
} finally { Pop-Location }
