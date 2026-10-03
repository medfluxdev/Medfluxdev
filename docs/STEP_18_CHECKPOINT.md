# STEP 18 Checkpoint – Release Candidate & Krankenhaus-Pilot

Stand: 2026-09-13
Branch: `JAMAL`
Status: **static implementation complete; current HEAD runtime validation pending**

## Important validation boundary

Earlier STEP 16/17 runtime gates passed on older commits and remain useful historical evidence, but they **do not certify the current STEP 18 HEAD** after the evidence/verifier/review-safety changes made today.

No release/pilot claim may therefore reuse the earlier `750 passed`, frontend build, PostgreSQL or Accutron results as if they were executed against the current commit.

## Current STEP 18 static implementation

Completed on `JAMAL`:

- evidence-first, fail-closed semantic verification;
- central critical-claim policy;
- field-scoped verifier evidence;
- party-role verification;
- expanded money/payment verification;
- service/SLA tri-state verification;
- per-equipment evidence and equipment identity/coverage verification;
- service-list and residual critical-claim deterministic gates;
- adversarial critical-claim regressions;
- multi-chunk conflict surfacing;
- tenant/auth boundary static audit;
- pilot/production auth configuration hardening;
- authenticated reviewer provenance;
- critical-fact review-completion blocking;
- Contract 360 / Human Review unverified-state hardening;
- CSV formula-injection protection;
- focused benchmark selection/perfect-score exit gate;
- one-command local runtime gate.

See:

- `docs/STEP18_CRITICAL_FIELD_AUDIT.md`
- `docs/STEP18_STATIC_SECURITY_AUDIT.md`
- `docs/STEP18_AUTOPILOT_PLAN.md`

## Historical runtime evidence

Before the current STEP 18 safety changes, the project had verified:

- isolated PostgreSQL 18.6 migration/restore gates;
- auth E2E and cross-org isolation;
- CSV E2E;
- frontend production build;
- full backend suite: 750 passed / 0 failed;
- Accutron extraction reaching 27/27 in prior focused runs.

These results establish a strong previous baseline, but current changes must be revalidated.

## Current runtime closure gate

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\step18_runtime_gate.ps1
```

The gate stops on the first failure and executes:

1. DB-free STEP 18 safety gate.
2. DB-backed auth/tenant isolation tests.
3. Frontend TypeScript/tests/lint/build.
4. One focused real Accutron benchmark at `AI_TEMPERATURE=0`, selected by filename and requiring a perfect ground-truth score.
5. Full backend regression.

Only a final `STEP18_RUNTIME_GATE_PASS` on the current HEAD closes STEP 18.

## Release rule

STEP 18 remains **RC candidate / not closed** until the current runtime gate passes.

A real contract benchmark cannot be replaced by synthetic fixtures, and historical green results cannot be relabeled as current validation.
