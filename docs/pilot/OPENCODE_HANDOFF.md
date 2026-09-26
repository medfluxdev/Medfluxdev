# OpenCode handoff: Ahmad reviewer build (26 September 2026)

## Mission
Help prepare an honest, independently runnable **Ahmad hospital product-review candidate within 1–2 days**. Ahmad needs to identify KEEP/CHANGE/REMOVE/MISSING features, not certify hospital production operation. Branch: `review/ahmad-hospital-20260926` (draft PR #10 to JAMAL). Latest isolated frontend job: JAMAL-OC-PC Actions run 36244590337 (success). First inspect log gates and reconcile with GitHub branch before edits.

## Critical workspace protections
- Never reset/clean/checkout/switch/delete/overwrite original `Medflux-Integrated-Test`, local `Medflux-VisualFirst-Experiment`, any uncommitted work, production/hospital documents, PostgreSQL databases or active inference job.
- Make a **new sibling worktree / fresh clone** for this mission with no existing local changes; identify exact target and confirm no cross-branch conflicts with ongoing OpenCode tasks. All test artifacts in project-owned isolated temp paths with explicit allowlist cleanup only.
- Do not send original hospital contract, canonical output, financial ledger or secret to GitHub artifacts/logs. Use synthetic fixtures. Don't start overlapping local Ollama GPU jobs.
- Do not merge PR #10 into JAMAL or install Docker/alter service/migrate live database until user separately authorizes.

## Tasks IN ORDER

### A. Baseline audit, report first
1. Confirm branch `review/ahmad-hospital-20260926`, compare its source to ongoing Visual-First local experimental branch, understand diff without overwriting either.
2. Read `docs/pilot/AHMAD_ACCEPTANCE.md`, `docs/pilot/RELEASE_GATES.md`, `docs/architecture/{CONTRACT_IMPORT_WIZARD,COST_CENTER_INTELLIGENCE,README}.md`.
3. Check actual current frontend/build/test status; verify local PostgreSQL availability using read-only process/service/connection health. **Do not assume Docker is required**. If no safe isolated PostgreSQL instance is readily available, report concrete blocker and use a disposable nonproduction DB only after safe infrastructure plan.
4. Independently inspect current route/processing implementation and confirm critical source-evidence guard.

### B. Prioritized bounded fixes on the review branch only
1. Finish actual **import wizard**: choose a server-authorized hospital/department and (optional) cost center, then three distinct **real** processing modes: manual input, AI + human approval, and policy-governed AI auto-approval. **Never enable incomplete modes; retain explicit disabled badges if backend persistence/authority is unfinished**. Remember a user manually entering a value is not documentary proof.
2. Validate destination + mode **server-side before accepting uploaded bytes**; do not create duplicate orchestrator bypassing current DocumentProcessingService. Persist chosen workflow with import run and retry; per-field provenance AI/manual/both and independent source verification, actor audit. New tests must cover forged hospital/department, disabled modes, scoped batch, retry idempotency.
3. Check cost-center-number UI `/kostenstellen-suche` safely uses existing scoped `GET /api/cost-centers` and does not show placeholder budgets as real. Do not build historical forecasting without approved import data. Provide synthetic example in clearly labeled sample fixture if necessary.
4. Verify in-product `/ahmad-review` and navigation for feedback keep/change/remove, clear reminder to copy notes (no persistence).
5. Propose a local reviewer run command/README that **never connects to production DB** or changes original workspace, and explicitly lists which features are working vs disabled/in development.

### C. Actual acceptance
- Frontend focused and full suite (vitest), TypeScript, lint, production build; backend targeted tests and smoke. Capture exact numeric outcomes with linked log/evidence. New regression tests specific to every changed endpoint or UI flow.
- Before any local e2e, show isolated DB name/port/owner, test-data provenance, backup and rollback, user credentials are test-only, and no collision with existing PostgreSQL service. Do not launch if unsafe.
- Confirm service starts, authenticate sample user, upload a **synthetic** PDF, inspect source/financial labels, manually review fact, test scoped cost center lookup and Ahmad checklist.
- Provide reviewer package instructions, screenshots when feasible, `docs/pilot/AHMAD_ACCEPTANCE.md` update with **verified** capabilities, missing and excess items (excess awaits Ahmad), and a cleanup/test report of only new changed/deleted files.
- Do not mark original Frankfurt nine-page end-to-end success until original-document evidence has truly been compared locally and security approved.

## Report format after initial audit
`Branch and worktree:`; `What actually passed:`; `What is safely runnable now:`; `Highest blocking issue:`; `Exactly what you will change next:`. Work through one gate at a time. Favor tangible reviewer build over another broad architecture rewrite.
