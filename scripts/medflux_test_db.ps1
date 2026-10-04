param(
    [ValidateSet('status', 'start', 'verify', 'prepare', 'test')]
    [string]$Action = 'prepare'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $RepoRoot 'backend'
$Python = Join-Path $BackendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

$PreviousLocation = Get-Location
try {
    Set-Location -LiteralPath $BackendRoot
    $env:PYTHONPATH = $BackendRoot
    if ($Action -eq 'test') {
        & $Python -m pytest -q
        exit $LASTEXITCODE
    }
    & $Python -m app.testing.test_database $Action
    exit $LASTEXITCODE
}
finally {
    Set-Location -LiteralPath $PreviousLocation
}
