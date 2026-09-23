$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root "scripts\start_local_postgres.ps1"

# 1) Syntax validation.
$tokens = $null
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    $target, [ref]$tokens, [ref]$errors
)
if ($errors.Count -ne 0) {
    throw "PowerShell syntax errors: $($errors | ForEach-Object Message | Out-String)"
}
Write-Host "[PASS] PowerShell syntax"

# 2) Regression guard: pg_ctl start must never be piped/redirection-wrapped.
$source = Get-Content -LiteralPath $target -Raw
if ($source -match '\$PgCtlPath\s+start[^\r\n]*\|') {
    throw "pg_ctl start is inside a PowerShell pipeline."
}
if ($source -match '\$PgCtlPath\s+start[^\r\n]*Out-Host') {
    throw "pg_ctl start is redirected through Out-Host."
}
Write-Host "[PASS] no pg_ctl start pipeline"

# 3) Already-running path: an open TCP port must return zero promptly.
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
try {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    & powershell -NoProfile -ExecutionPolicy Bypass -File $target -Port $port -SkipServiceDiscovery
    $code = $LASTEXITCODE
    $watch.Stop()
    if ($code -ne 0) { throw "ready-port path returned exit code $code" }
    if ($watch.Elapsed.TotalSeconds -gt 5) {
        throw "ready-port path took too long: $($watch.Elapsed.TotalSeconds)s"
    }
} finally {
    $listener.Stop()
}
Write-Host "[PASS] already-running path"

# 4) Deterministic fail path: no server + missing pg_ctl must fail, not hang.
$probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$probe.Start()
$unusedPort = ([Net.IPEndPoint]$probe.LocalEndpoint).Port
$probe.Stop()

$missing = Join-Path $env:TEMP "medflux-no-such-pgctl.exe"
$missingData = Join-Path $env:TEMP "Medflux Missing PostgreSQL Data"
$watch = [Diagnostics.Stopwatch]::StartNew()
& powershell -NoProfile -ExecutionPolicy Bypass -File $target -Port $unusedPort -PgCtlPath $missing -DataDirOverride $missingData -SkipServiceDiscovery
$code = $LASTEXITCODE
$watch.Stop()
if ($code -eq 0) { throw "missing-pgctl path unexpectedly succeeded" }
if ($watch.Elapsed.TotalSeconds -gt 5) {
    throw "missing-pgctl path hung: $($watch.Elapsed.TotalSeconds)s"
}
Write-Host "[PASS] missing-pgctl path fails promptly"

Write-Host "Windows startup regression checks passed."
exit 0
