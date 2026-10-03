# Local-only Ollama model picker for the MedFlux local launcher.
# Lists installed models from the running Ollama server (never pulls/downloads),
# detects vision capability from authoritative /api/show metadata, and writes the
# user's selection to the runtime directory.
#
# Exit codes:
#   0  selection written to selected_model.txt (or "KEEP" for keep-existing)
#   2  Ollama reachable but no models installed
#   3  Ollama not reachable / not running
#   4  invalid input
#   6  models JSON could not be written

param(
    [string]$RuntimeDir = "$env:LOCALAPPDATA\MedFlux\runtime",
    [string]$BaseUrl = "http://127.0.0.1:11434",
    [switch]$ListOnly
)

$ErrorActionPreference = "Stop"

# Families with authoritative multimodal/vision support (supporting source only;
# primary check is the ".vision." keys in /api/show model_info).
$VisionFamilies = @(
    "qwen3vl", "qwen2vl", "llava", "llava-phi3", "bakllava", "command-r-v",
    "moondream", "minicpmv", "internvl", "gemma3", "llava-next"
)

function Get-OllamaTags {
    param([string]$Base)
    try {
        $resp = Invoke-RestMethod -Uri "$Base/api/tags" -Method Get -TimeoutSec 5
    } catch {
        Write-Host "[ERROR] Ollama is not reachable at $Base." -ForegroundColor Red
        exit 3
    }
    return $resp.models
}

function Test-ModelVision {
    param([string]$Base, [string]$Name, [string]$Family)
    try {
        $body = @{ model = $Name } | ConvertTo-Json -Compress
        $show = Invoke-RestMethod -Uri "$Base/api/show" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 5
        $modelInfo = $show.model_info
        if ($modelInfo -is [System.Management.Automation.PSCustomObject]) {
            $names = $modelInfo.PSObject.Properties | ForEach-Object { $_.Name }
            foreach ($key in $names) {
                if ($key -like "*.vision.*") { return $true }
            }
        }
    } catch {
        # enrichment is best-effort; fall back to family list
    }
    if ($Family -and $VisionFamilies -contains $Family) { return $true }
    return $false
}

if (-not (Test-Path -LiteralPath $RuntimeDir)) {
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
}

$modelsRaw = @(Get-OllamaTags -Base $BaseUrl)
if ($modelsRaw.Count -eq 0) {
    Write-Host ""
    Write-Host "[ERROR] Ollama is running but no models are installed yet." -ForegroundColor Red
    Write-Host "        Install a model manually (the launcher never downloads models), e.g.:"
    Write-Host "        ollama pull qwen3-vl:8b-instruct"
    exit 2
}

$installed = @()
foreach ($m in $modelsRaw) {
    $name = [string]$m.name
    if (-not $name) { continue }
    $family = $null
    if ($m.details -and $m.details.family) { $family = [string]$m.details.family }
    $params = $null
    if ($m.details -and $m.details.parameter_size) { $params = [string]$m.details.parameter_size }
    $quant = $null
    if ($m.details -and $m.details.quantization_level) { $quant = [string]$m.details.quantization_level }
    $vision = Test-ModelVision -Base $BaseUrl -Name $name -Family $family
    $installed += [PSCustomObject]@{
        name   = $name
        family = $family
        params = $params
        quant  = $quant
        vision = $vision
    }
}

$jsonPath = Join-Path $RuntimeDir "installed_models.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
try {
    [System.IO.File]::WriteAllText($jsonPath, ($installed | ConvertTo-Json -Depth 3), $utf8NoBom)
} catch {
    Write-Host "[ERROR] Could not write $jsonPath" -ForegroundColor Red
    exit 6
}

Write-Host ""
Write-Host "Installed local models (Ollama):" -ForegroundColor Cyan
for ($i = 0; $i -lt $installed.Count; $i++) {
    $m = $installed[$i]
    $tag = if ($m.vision) { "[VISION]" } else { "[text]" }
    $extra = @()
    if ($m.params) { $extra += $m.params }
    if ($m.quant) { $extra += $m.quant }
    if ($m.family) { $extra += $m.family }
    $suffix = if ($extra.Count -gt 0) { " - " + ($extra -join " ") } else { "" }
    Write-Host ("  {0}. {1} {2}{3}" -f ($i + 1), $m.name, $tag, $suffix)
}
Write-Host ""
Write-Host "Models marked [VISION] can analyse scanned/hybrid PDFs."
Write-Host "Models marked [text] are fine for text-based contracts only."
Write-Host ""

if ($ListOnly) {
    exit 0
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$selectionFile = Join-Path $RuntimeDir "selected_model.txt"
if (Test-Path -LiteralPath $selectionFile) {
    Remove-Item -LiteralPath $selectionFile -Force
}

function Write-Selection {
    param([PSCustomObject]$Model)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($selectionFile, $Model.name, $utf8NoBom)
    Write-Host ""
    Write-Host ("[OK] Selected local model: {0}" -f $Model.name) -ForegroundColor Green
    if (-not $Model.vision) {
        Write-Host "[WARNING] This model is NOT vision-capable. Scanned/hybrid PDFs may not be analysable." -ForegroundColor Yellow
    }
    exit 0
}

# With exactly one installed model, use it by default without prompting.
if ($installed.Count -eq 1) {
    Write-Selection -Model $installed[0]
}

# Opt-in deterministic selection for local CI/smoke tests; user launches remain interactive.
if (-not [string]::IsNullOrWhiteSpace($env:MEDFLUX_LOCAL_MODEL)) {
    $requested = $installed | Where-Object { $_.name -eq $env:MEDFLUX_LOCAL_MODEL } | Select-Object -First 1
    if (-not $requested) {
        Write-Host "[ERROR] Requested MEDFLUX_LOCAL_MODEL is not installed locally." -ForegroundColor Red
        exit 4
    }
    Write-Selection -Model $requested
}
$input = Read-Host "Select a model number (Enter keeps the current selection, 0 = do not change)"
if ([string]::IsNullOrWhiteSpace($input)) {
    [System.IO.File]::WriteAllText($selectionFile, "KEEP", $utf8NoBom)
    Write-Host "[INFO] Keeping the current MedFlux selection (no change)." -ForegroundColor Yellow
    exit 0
}

$idx = 0
if (-not [int]::TryParse($input, [ref]$idx)) { $idx = -1 }
if ($idx -le 0 -or $idx -gt $installed.Count) {
    Write-Host "[ERROR] Invalid selection. Run the launcher again to pick a model." -ForegroundColor Red
    exit 4
}

Write-Selection -Model $installed[$idx - 1]