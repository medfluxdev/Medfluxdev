param(
    [int]$Port = $(if ($env:MEDFLUX_PG_PORT) { [int]$env:MEDFLUX_PG_PORT } else { 5432 }),
    [string]$PgCtlPath = $env:MEDFLUX_PG_CTL,
    [string]$DataDirOverride = $env:MEDFLUX_PGDATA,
    [switch]$SkipServiceDiscovery
)

$ErrorActionPreference = "Stop"
# Explicit managed PostgreSQL service takes priority on the local MedFlux machine.
# Never silently fall back to a different cluster when the managed service exists.
if ($Port -eq 5432) {
    $managed = Get-Service -Name "MedFluxPostgres18" -ErrorAction SilentlyContinue
    if ($managed) {
        $readyExe = "C:\ProgramData\MedFlux\postgres18\bin\pg_isready.exe"
        $dataVersion = "C:\ProgramData\MedFlux\postgres18\data\PG_VERSION"
        if (-not (Test-Path $readyExe) -or -not (Test-Path $dataVersion)) {
            Write-Error "Managed PostgreSQL files missing. Do not initialize or overwrite existing data."
            exit 4
        }
        if ($managed.Status -ne "Running") {
            Start-Service -Name "MedFluxPostgres18" -ErrorAction Stop
        }
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            & $readyExe -h 127.0.0.1 -p 5432 -t 1 *> $null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Managed MedFlux PostgreSQL service is ready (127.0.0.1:5432)."
                exit 0
            }
            Start-Sleep -Milliseconds 500
        }
        Write-Error "Managed PostgreSQL service did not become ready; inspect MedFluxPostgres18 service."
        exit 4
    }
}

function Test-MedfluxPort {
    param([int]$TargetPort)
    $client = $null
    try {
        $client = [Net.Sockets.TcpClient]::new()
        $task = $client.ConnectAsync("127.0.0.1", $TargetPort)
        if (-not $task.Wait(1000)) { return $false }
        return $client.Connected
    } catch {
        return $false
    } finally {
        if ($null -ne $client) { $client.Dispose() }
    }
}

function Wait-MedfluxPort {
    param(
        [int]$TargetPort,
        [int]$Attempts = 20,
        [int]$DelayMilliseconds = 500
    )
    for ($i = 0; $i -lt $Attempts; $i++) {
        if (Test-MedfluxPort -TargetPort $TargetPort) { return $true }
        Start-Sleep -Milliseconds $DelayMilliseconds
    }
    return $false
}

if (Test-MedfluxPort -TargetPort $Port) {
    Write-Host "PostgreSQL already reachable on 127.0.0.1:$Port."
    exit 0
}

if (-not $SkipServiceDiscovery) {
    $services = @(Get-Service -Name "*postgres*" -ErrorAction SilentlyContinue)
    foreach ($service in $services) {
        if ($service.Status -ne "Running") {
            try {
                Start-Service -Name $service.Name -ErrorAction Stop
            } catch {
                continue
            }
        }
        if (Wait-MedfluxPort -TargetPort $Port -Attempts 20) { exit 0 }
    }
}

$root = Split-Path -Parent $PSScriptRoot
if (-not $PgCtlPath) {
    $PgCtlPath = Join-Path $root ".pg18\pgsql\bin\pg_ctl.exe"
}
$log = Join-Path $root ".pg18\pg18-start.log"

$candidates = @()
if ($DataDirOverride) {
    $candidates += $DataDirOverride
} else {
    $candidates += (Join-Path $root ".pg18\data")
    $candidates += "C:\Program Files\PostgreSQL\18\data"
}

if (Test-Path -LiteralPath $PgCtlPath) {
    foreach ($dataDir in $candidates | Select-Object -Unique) {
        if (-not $dataDir) { continue }
        if (-not (Test-Path -LiteralPath (Join-Path $dataDir "PG_VERSION"))) { continue }

        & $PgCtlPath status -D $dataDir *> $null
        $statusCode = $LASTEXITCODE
        if ($statusCode -eq 0) {
            Write-Host "PostgreSQL cluster already running: $dataDir"
            if (Wait-MedfluxPort -TargetPort $Port -Attempts 10) { exit 0 }
            Write-Warning "Cluster is running but port $Port is not reachable: $dataDir"
            continue
        }

        Write-Host "Starting PostgreSQL cluster: $dataDir"

        # Do not pipe or redirect this native process. PostgreSQL inherits the
        # standard handles from pg_ctl. A PowerShell pipeline here can remain
        # open after pg_ctl prints "server started", which caused the launcher
        # to hang even though PostgreSQL itself was already running.
        & $PgCtlPath start -w -t 15 -D $dataDir -l $log
        $startCode = $LASTEXITCODE

        if ($startCode -ne 0) {
            Write-Warning ("pg_ctl failed with exit code {0}: {1}" -f $startCode, $dataDir)
            continue
        }
        if (Wait-MedfluxPort -TargetPort $Port -Attempts 20) { exit 0 }

        Write-Warning "PostgreSQL start returned successfully, but port $Port did not become reachable."
    }
}

Write-Warning "No existing local PostgreSQL cluster became reachable on 127.0.0.1:$Port."
exit 2
