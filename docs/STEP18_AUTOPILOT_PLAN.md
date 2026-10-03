# STEP 18 Autopilot Plan

Status: **all currently actionable GitHub/static work completed; local runtime closure pending**.

The rule for STEP 18 is fail-closed: schema-valid model output is never enough to trust a critical hospital-contract fact.

## Static/GitHub work completed

- [x] Unsupported and missing semantic-verifier decisions fail closed.
- [x] Verifier outages/invalid response shapes fail closed.
- [x] Multi-chunk scalar conflicts are surfaced.
- [x] Evidence requires concrete source text.
- [x] Critical claims are centrally inventoried.
- [x] Scalar verifier coverage expanded to parties, money/payment, service booleans and SLA.
- [x] Per-equipment evidence is independently verified.
- [x] Equipment identity/coverage and duplicate-device conflicts are checked.
- [x] Included/excluded service list items are checked individually.
- [x] Residual critical clauses, remaining service booleans, service hours, scheduled prices and variable charges have deterministic gates.
- [x] Adversarial critical-claim tests added.
- [x] Tenant/auth route and service boundaries statically audited.
- [x] Pilot/production auth configuration hardened.
- [x] Authenticated reviewer provenance is server-bound.
- [x] Contract review cannot be completed while critical facts remain unreviewed.
- [x] Contract 360 and Human Review UI distinguish unverified/review-required evidence explicitly.
- [x] Review-list copy no longer overstates human review completion.
- [x] CSV spreadsheet-formula injection is neutralized.
- [x] Focused benchmark harness preserves field-evidence units and can select one contract with a perfect-score exit gate.
- [x] DB-free safety gate expanded to cover all new safety regressions.
- [x] One-command local runtime closure gate added: `scripts/step18_runtime_gate.ps1`.

## Local runtime closure

The next meaningful action now requires the user's machine/environment.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\step18_runtime_gate.ps1
```

The runtime gate performs, in order:

1. DB-free STEP 18 safety tests.
2. DB-backed auth/tenant tests.
3. Frontend TypeScript, tests, lint and production build.
4. One focused Accutron production benchmark at `AI_TEMPERATURE=0`, selected by filename and requiring perfect ground-truth score.
5. Full backend regression only after all earlier gates pass.

The script exits on the first failure and prints `STEP18_RUNTIME_GATE_PASS` only when all stages pass.

## Closure rule

STEP 18 is **not closed** until the runtime gate passes. Static review is complete, but no local pytest/frontend/Ollama/Accutron result is being claimed without execution evidence.
