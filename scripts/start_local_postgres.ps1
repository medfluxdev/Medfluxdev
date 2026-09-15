$ErrorActionPreference = "Stop"

function Test-MedfluxPort {
    param([int]$Port = 5432)
    try {
        $client = [Net.Sockets.TcpClient]::new()
        $client.Connect("127.0.0.1", $Port)
        $client.Close()
        return $true
    } catch { return $false }
}

if (Test-MedfluxPort) { Write-Host "PostgreSQL already reachable on 127.0.0.1:5432."; exit 0 }

$services = @(Get-Service -Name "*postgres*" -ErrorAction SilentlyContinue)
foreach ($service in $services) {
    if ($service.Status -ne "Running") { try { Start-Service -Name $service.Name -ErrorAction Stop } catch { continue } }
    for ($i=0; $i -lt 20; $i++) { if (Test-MedfluxPort) { exit 0 }; Start-Sleep -Milliseconds 500 }
}

$root = Split-Path -Parent $PSScriptRoot
$pgCtl = Join-Path $root ".pg18\pgsql\bin\pg_ctl.exe"
$log = Join-Path $root ".pg18\pg18-start.log"
$candidates = @()
if ($env:MEDFLUX_PGDATA) { $candidates += $env:MEDFLUX_PGDATA }
$candidates += (Join-Path $root ".pg18\data")
$candidates += "C:\Program Files\PostgreSQL\18\data"

if (Test-Path -LiteralPath $pgCtl) {
    foreach ($dataDir in $candidates | Select-Object -Unique) {
        if (-not $dataDir) { continue }
        if (-not (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION"))) { continue }
        try { & $pgCtl start -D $dataDir -l $log | Out-Host } catch { }
        for ($i=0; $i -lt 30; $i++) { if (Test-MedfluxPort) { exit 0 }; Start-Sleep -Milliseconds 500 }
    }
}

Write-Warning "No existing local PostgreSQL cluster became reachable."
exit 2
