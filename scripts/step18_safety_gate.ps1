$ErrorActionPreference = "Stop"

# STEP 18 targeted safety gate.
# This gate is intentionally DB-free so it can run without touching PostgreSQL.
# It validates verifier/evidence/source-grounding and static export-safety changes
# accumulated while the local Big Pickle quota is unavailable.

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Join-Path $repoRoot "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
Set-Location $backend

$env:MEDFLUX_UNIT_ONLY = "1"

Write-Host "[STEP18] Python syntax gate..."
& $python -m py_compile `
    app/ai/groups/critical_policy.py `
    app/ai/groups/equipment_verifier.py `
    app/ai/groups/evidence.py `
    app/ai/groups/extractor.py `
    app/ai/groups/list_claim_verifier.py `
    app/ai/groups/residual_claim_verifier.py `
    app/ai/groups/verifier.py `
    app/api/routes/operations.py `
    app/auth/provenance.py `
    app/core/config.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[STEP18] Targeted fail-closed tests..."
& $python -m pytest -q `
    tests/test_ai_adversarial_critical_claims.py `
    tests/test_ai_critical_policy.py `
    tests/test_ai_critical_verifier_expansion.py `
    tests/test_ai_equipment_claim_verifier.py `
    tests/test_ai_equipment_evidence.py `
    tests/test_ai_service_list_verifier.py `
    tests/test_ai_residual_claim_verifier.py `
    tests/test_ai_evidence_fail_closed.py `
    tests/test_ai_verifier_safety.py `
    tests/test_ai_verifier_fail_closed.py `
    tests/test_ai_verifier_completeness.py `
    tests/test_ai_source_grounding.py `
    tests/test_ai_structured.py `
    tests/test_auth_review_provenance.py `
    tests/test_review_critical_completion.py `
    tests/test_operations_csv_safety.py `
    tests/test_security_runtime_config.py

$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host "STEP18_TARGETED_SAFETY_GATE_PASS"
} else {
    Write-Host "STEP18_TARGETED_SAFETY_GATE_FAIL ($code)"
}
exit $code
