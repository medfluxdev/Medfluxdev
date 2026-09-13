param(
    [switch]$SkipBenchmark,
    [switch]$SkipFullRegression
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Join-Path $repoRoot "backend"
$frontend = Join-Path $repoRoot "frontend"
$py = Join-Path $backend ".venv\\Scripts\\python.exe"

if (-not (Test-Path $py)) {
    throw "Backend venv Python not found: $py"
}

function Assert-LastExit([string]$Stage) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Stage failed with exit code $LASTEXITCODE"
    }
}

Write-Host "[STEP18-RUNTIME] 1/5 DB-free safety gate..."
& (Join-Path $PSScriptRoot "step18_safety_gate.ps1")
Assert-LastExit "DB-free safety gate"

Remove-Item Env:MEDFLUX_UNIT_ONLY -ErrorAction SilentlyContinue

Write-Host "[STEP18-RUNTIME] 2/5 DB-backed auth/tenant gates..."
Push-Location $backend
try {
    & $py -m pytest -q tests/test_auth_e2e.py tests/test_auth_route_boundary_e2e.py tests/test_step17_csv_e2e.py
    Assert-LastExit "DB-backed auth/tenant gates"
}
finally { Pop-Location }

Write-Host "[STEP18-RUNTIME] 3/5 Frontend type/test/lint/build gate..."
Push-Location $frontend
try {
    & npx tsc --noEmit
    Assert-LastExit "Frontend TypeScript"
    & npm test
    Assert-LastExit "Frontend tests"
    & npm run lint
    Assert-LastExit "Frontend lint"
    & npm run build
    Assert-LastExit "Frontend build"
}
finally { Pop-Location }

if (-not $SkipBenchmark) {
    Write-Host "[STEP18-RUNTIME] 4/5 Focused Accutron production benchmark..."
    $env:AI_TEMPERATURE = "0"
    Push-Location $repoRoot
    try {
        & $py scripts/benchmark_groups.py --file-contains "Accutorn" --runs 1 --require-perfect --report "data/benchmark/report_step18_accutron.json"
        Assert-LastExit "Accutron benchmark"
    }
    finally { Pop-Location }
}
else {
    Write-Host "[STEP18-RUNTIME] 4/5 Accutron benchmark skipped by caller."
}

if (-not $SkipFullRegression) {
    Write-Host "[STEP18-RUNTIME] 5/5 Full backend regression..."
    Push-Location $backend
    try {
        & $py -m pytest -q tests
        Assert-LastExit "Full backend regression"
    }
    finally { Pop-Location }
}
else {
    Write-Host "[STEP18-RUNTIME] 5/5 Full backend regression skipped by caller."
}

Write-Host "STEP18_RUNTIME_GATE_PASS"
