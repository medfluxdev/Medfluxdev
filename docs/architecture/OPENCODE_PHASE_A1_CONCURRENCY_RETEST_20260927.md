# Phase A1 concurrency fix — OpenCode retest only

Fix commit: 82eea18f1df9fa2a2557fb2263b818961fe8644b
Branch: feature/org-tree-a1-20260927
Reference failed A1: 093b503ba70a56e3648a793329a690f5e2a1d6d1

## Change
In the existing PATCH /departments/{id} route, ONLY when parent_id is explicitly supplied, acquire a transaction-scoped PostgreSQL advisory lock keyed by hospital before validation, expire ORM state after any lock wait, reload the target department, and run the existing cycle/scope validator on fresh state. No schema change, no new migration, no authorization relaxation.

## Mandatory verification
- Fetch the exact fix commit in a NEW isolated worktree; inspect diff against failed A1 reference. Do not touch active worktrees or production PG 5432/Ollama 11434.
- Use disposable test PG 55432 only. Re-run the SAME original authenticated concurrent A->B / B->A reproducer, at least 50 independent races, and assert **zero committed cycles**, one of each conflicting pair must fail with 422. Repeat across at least two independent hospitals to confirm hospital-scoped locks do not accidentally grant cross-scope permissions.
- Check no hanging locks, lock timeout surprises, deadlocks, or inconsistent responses. Include per-run outcomes and exact commands.
- Run A1 hierarchy tests, real API scope/auth cases, contract/scope regression and full backend suite with known environment artifact distinguished, frontend baseline if feasible. Confirm no mutation outside department parent_id and normal unrelated department edits remain compatible.
- Test explicit detach and 3-level reparenting under concurrency; check parent reads after lock are actually fresh at READ COMMITTED. Inspect actual test DB isolation level.
- IMPORTANT: Check whether any OTHER code path can update department.parent_id without the same lock. If so, report it as a release blocker, do not claim global cycle safety.
- STOP if any cycle commits or a new defect appears. Propose smallest correction for assistant review. Do not implement Phase A2, deploy, run GitHub Actions, or merge.
- Report SHA, exact commands, pass/fail/skips, counts, database isolation, concurrent outcomes, and remaining risks.

This test gate establishes correctness only for tested mutation paths; do not claim mathematical impossibility of cycles or production readiness.
