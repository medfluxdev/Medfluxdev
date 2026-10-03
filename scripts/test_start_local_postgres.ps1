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

# 3) Fail-closed: a bare TCP listener (no PostgreSQL protocol) must NOT be
#    reported as "PostgreSQL ready". A listening socket does not identify the
#    database; only a PostgreSQL wire-protocol answer may.
function Invoke-Launcher {
    param([int]$Port)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & powershell -NoProfile -ExecutionPolicy Bypass -File $target -Port $Port -SkipServiceDiscovery
    $code = $LASTEXITCODE
    $sw.Stop()
    return @{ Code = $code; Seconds = $sw.Elapsed.TotalSeconds }
}

$bare = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$bare.Start()
$barePort = ([Net.IPEndPoint]$bare.LocalEndpoint).Port
try {
    $r = Invoke-Launcher -Port $barePort
    if ($r.Code -eq 0) { throw "bare TCP listener was wrongly reported as PostgreSQL-ready" }
    if ($r.Seconds -gt 5) { throw "bare-listener path took too long: $($r.Seconds)s" }
} finally {
    $bare.Stop()
}
Write-Host "[PASS] bare TCP listener is not PostgreSQL-ready"

# 4) Positive case: a fake PostgreSQL startup-protocol responder IS detected.
$responder = Start-Job -ArgumentList $barePort -ScriptBlock {
    param($Port)
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    $listener.Start()
    try {
        # Bounded: the launcher opens a probe connection (Test-MedfluxPort) and
        # one identity connection (Test-PostgresIdentity). Self-terminate so the
        # test never has to interrupt a blocked AcceptTcpClient.
        for ($i = 0; $i -lt 2; $i++) {
            if (-not $listener.Pending()) {
                Start-Sleep -Milliseconds 200
                $i--
                continue
            }
            $client = $listener.AcceptTcpClient()
            $stream = $client.GetStream()
            $buf = [byte[]]::new(9)
            $read = 0
            while ($read -lt 9) {
                $n = $stream.Read($buf, $read, 9 - $read)
                if ($n -le 0) { break }
                $read += $n
            }
            if ($read -ge 9) {
                # Authentication-request message: type byte 'R' (0x52).
                $stream.Write([byte[]](0x52), 0, 1)
            }
            $client.Close()
        }
    } finally {
        $listener.Stop()
    }
}
try {
    Start-Sleep -Milliseconds 500
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & powershell -NoProfile -ExecutionPolicy Bypass -File $target -Port $barePort -SkipServiceDiscovery
    $code = $LASTEXITCODE
    $sw.Stop()
    if ($sw.Elapsed.TotalSeconds -gt 5) {
        throw "PostgreSQL-protocol responder path took too long: $($sw.Elapsed.TotalSeconds)s"
    }
    Wait-Job $responder -Timeout 10 | Out-Null
    if ($code -ne 0) {
        throw "PostgreSQL-protocol responder path returned exit code $code (job state: $($responder.State))"
    }
} finally {
    Stop-Job $responder -ErrorAction SilentlyContinue
    Remove-Job $responder -Force -ErrorAction SilentlyContinue
}
Write-Host "[PASS] PostgreSQL-protocol responder detected"

# 5) Deterministic fail path: no server + missing pg_ctl must fail, not hang.
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