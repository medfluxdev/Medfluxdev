# MedFlux Harness Hardening Task List

Date: 2026-09-13
Branch: `JAMAL-harness-hardening`
Base: `JAMAL`

## Goal

Close concrete safety gaps in the contract-analysis harness before adding new product features.

## Tasks

- [x] **Wire the residual critical-claim verifier into the production group pipeline.**
  - Problem: `verify_residual_critical_claims()` existed with direct unit tests, but `GroupPipeline.run()` did not invoke it.
  - Result: residual critical claims now run deterministically for every pipeline execution, even when the optional semantic/LLM verifier is disabled.

- [x] **Fail closed when the semantic verifier omits an expected critical decision.**
  - Problem: the contract was marked for manual review, but section evidence could keep a high confidence and `requires_review=false`.
  - Result: missing verifier decisions now downgrade the affected section evidence to `requires_review=true` and confidence <= 0.5.

- [x] **Add regression coverage for both safety boundaries.**
  - Added a section-evidence downgrade regression.
  - Added a pipeline integration regression proving the residual verifier still runs with semantic verification disabled.

- [x] **Add the new pipeline regression to the STEP 18 DB-free safety gate.**
  - `scripts/step18_safety_gate.ps1` now includes the residual pipeline integration test.

- [ ] **Runtime validation on the local development machine.**
  - Run `scripts/step18_safety_gate.ps1`.
  - Then run `scripts/step18_runtime_gate.ps1` with the isolated PostgreSQL test environment.
  - This item remains open until actual command output confirms success.

## Files changed

- `backend/app/ai/groups/extractor.py`
- `backend/tests/test_ai_verifier_completeness.py`
- `backend/tests/test_ai_pipeline_residual_integration.py`
- `scripts/step18_safety_gate.ps1`

## Safety invariant after this change

A critical claim may not escape review merely because it belongs to a specialized residual field or because the semantic verifier returned an incomplete decision set.
