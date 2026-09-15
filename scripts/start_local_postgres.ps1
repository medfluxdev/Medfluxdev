$ErrorActionPreference = "Stop"

function Test-MedfluxPort {
    param([int]$Port = 5432)
    try {
        $client = [Net.Sockets.TcpClient]::new()
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $task.Wait(1000)) {
            $client.Dispose()
            return $false
        }
        $client.Dispose()
        return $true
    } catch {
        return $false
    }
}

if (Test-MedfluxPort) {
    Write-Host "PostgreSQL already reachable on 127.0.0.1:5432."
    exit 0
}

$services = @(Get-Service -Name "*postgres*" -ErrorAction SilentlyContinue)
foreach ($service in $services) {
    if ($service.Status -ne "Running") {
        try {
            Start-Service -Name $service.Name -ErrorAction Stop
        } catch {
            continue
        }
    }
    for ($i = 0; $i -lt 20; $i++) {
        if (Test-MedfluxPort) { exit 0 }
        Start-Sleep -Milliseconds 500
    }
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

        # If this exact cluster is already running, do not invoke 'pg_ctl start'
        # again. This avoids the "another server might be running" branch and,
        # more importantly, avoids keeping the launcher attached to a second
        # startup attempt.
        $status = & $pgCtl status -D $dataDir 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "PostgreSQL cluster already running: $dataDir"
            if (Test-MedfluxPort) { exit 0 }
        }

        Write-Host "Starting PostgreSQL cluster: $dataDir"
        & $pgCtl start -w -t 15 -D $dataDir -l $log | Out-Host
        if ($LASTEXITCODE -ne 0) {
            continue
        }

        for ($i = 0; $i -lt 20; $i++) {
            if (Test-MedfluxPort) { exit 0 }
            Start-Sleep -Milliseconds 500
        }
    }
}

Write-Warning "No existing local PostgreSQL cluster became reachable on 127.0.0.1:5432."
exit 2
