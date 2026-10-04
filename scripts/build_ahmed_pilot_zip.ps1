# Create a source-only release archive and verifiable sidecar manifest.
# This is NOT an installer and must not be distributed before acceptance testing.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $root
try {
  $dirty = @(git status --porcelain)
  if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw "Working tree must be clean." }
  $branch = (git branch --show-current).Trim()
  if ($LASTEXITCODE -ne 0 -or $branch -ne "feature/integrated-release-build-20260929") {
    throw "Wrong branch: $branch"
  }
  $tracked = @(git ls-files)
  if ($LASTEXITCODE -ne 0) { throw "Cannot inspect tracked files" }
  $forbidden = @($tracked | Where-Object {
    $_ -match '(^|/)(\.env($|\.)|pgdata/|node_modules/|\.venv/|data/contracts/|data/backups/)' -and $_ -notmatch '(^|/)\.env\.example$'
  })
  if ($forbidden.Count -gt 0) { throw "Potentially sensitive tracked paths: $($forbidden -join ', ')" }
  $sha = (git rev-parse HEAD).Trim()
  if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-f]{40}$') { throw "Invalid HEAD" }
  $stem = "MedFlux_Integrated_SOURCE_$($sha.Substring(0,12))"
  $dir = Split-Path $root -Parent
  $out = Join-Path $dir "$stem.zip"
  $manifestPath = Join-Path $dir "$stem.manifest.json"
  if ((Test-Path $out) -or (Test-Path $manifestPath)) { throw "Output already exists; refusing overwrite." }
  try {
    git archive --format=zip --output="$out" HEAD
    if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
    $digest = (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifest = [ordered]@{
      schema_version = 1
      artifact = (Split-Path $out -Leaf)
      sha256 = $digest
      commit = $sha
      branch = $branch
      package_type = "source-only"
      installer_validated = $false
      acceptance_tested = $false
      distribution_approved = $false
    }
    $manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $manifestPath -Encoding UTF8 -NoNewline
  } catch {
    if (Test-Path $out) { Remove-Item -LiteralPath $out -Force }
    if (Test-Path $manifestPath) { Remove-Item -LiteralPath $manifestPath -Force }
    throw
  }
  Write-Host "Archive: $out"
  Write-Host "Manifest: $manifestPath"
  Write-Host "SHA256: $digest"
  Write-Warning "Source only; NOT an installer. No distribution without Jamal approval and acceptance testing."
} finally { Pop-Location }
