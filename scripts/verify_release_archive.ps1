param([Parameter(Mandatory=$true)][string]$ManifestPath)
$ErrorActionPreference = "Stop"
$manifestFile = (Resolve-Path -LiteralPath $ManifestPath).Path
$manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 1 -or $manifest.package_type -ne "source-only") { throw "Unsupported manifest." }
if ($manifest.artifact -notmatch '^[A-Za-z0-9_.-]+\.zip$') { throw "Unsafe artifact name." }
if ($manifest.sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw "Invalid SHA256." }
if ($manifest.commit -notmatch '^[a-f0-9]{40}$') { throw "Invalid commit." }
$dir = Split-Path -Parent $manifestFile
$archive = Join-Path $dir $manifest.artifact
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { throw "Archive missing: $archive" }
$actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
if ($actual -ine $manifest.sha256) { throw "SHA256 mismatch: archive may have been modified." }
Write-Host "PASS: archive SHA256 matches manifest for commit $($manifest.commit)"
if (-not $manifest.acceptance_tested -or -not $manifest.distribution_approved) {
  Write-Warning "Integrity verified ONLY. Installation, runtime behavior and distribution remain unapproved."
}
