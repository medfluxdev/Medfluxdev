# Einmalige Initialisierung für Medflux (Windows / PowerShell)
# Legt .env an, erstellt das Backend-venv und installiert Abhängigkeiten.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== Medflux Setup =="

if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item -Path (Join-Path $root ".env.example") -Destination (Join-Path $root ".env")
    Write-Host "[OK] .env aus .env.example erstellt."
} else {
    Write-Host "[..] .env existiert bereits."
}

$venv = Join-Path $root "backend\.venv"
if (-not (Test-Path $venv)) {
    Write-Host "[..] Erstelle Python-venv ..."
    Push-Location (Join-Path $root "backend")
    python -m venv .venv
    Pop-Location
    Write-Host "[OK] venv erstellt."
} else {
    Write-Host "[..] venv existiert bereits."
}

Write-Host "[..] Installiere Backend-Abhängigkeiten ..."
Push-Location (Join-Path $root "backend")
& ".\.venv\Scripts\pip.exe" install -r requirements.txt
Pop-Location

Write-Host "[..] Installiere Frontend-Abhängigkeiten ..."
Push-Location (Join-Path $root "frontend")
npm install
Pop-Location

Write-Host ""
Write-Host "Setup abgeschlossen."
Write-Host "Backend starten : .\backend\.venv\Scripts\activate; uvicorn app.main:app --reload --port 8000"
Write-Host "Frontend starten: cd frontend; npm run dev"
