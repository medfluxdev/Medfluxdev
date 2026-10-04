# GitHub cleanup register — 2026-10-01

Scope: repository hygiene only. This cleanup runs on `chore/github-cleanup-20261001`, **not** on the active integration branch or immutable trial baseline. No deletion of branches, migration history, contract data, tests or recovery scripts is authorized by this register.

## Protected references
- `stable/targeted-verified-20261001` at `7c9c0a0c7a623538a7a16677b1d5f4b0aabd6fd9`: targeted-test-verified trial baseline. **Not** a full production release; full backend suite, frontend and real-contract acceptance were not rerun at this commit.
- `feature/integrated-release-build-20260929`: active integration work. Do not rewrite or update it while OpenCode prepares the isolated trial.
- `main` and user/reviewer branches: preserve unless owners approve archival and dependency checks pass.
- Local `.playwright-mcp/` diagnostics, existing worktrees and all databases: preserve. These are local assets, not GitHub tracked cleanup targets.

## Verified file findings
- `scripts/README.md` previously listed non-existent generic `start-backend`/`start-frontend` commands; updated on the dedicated cleanup branch to document the actual launch and recovery scripts.
- `START_MEDFLUX_LOCAL.bat` can reach or start PostgreSQL on **5432**. It is **not** the approved launcher for the isolated **55432** hands-on trial without review. Do not silently change the active launcher while OpenCode is configuring the trial.
- `scripts/restore_backup.py` and `scripts/restore_from_backup.py` are **not duplicates**. The latter explicitly drops the configured database public schema; retain for audit, exclude from normal launch guidance, and never run against an existing database.
- `scripts/source_navigation_diagnose.py` and `scripts/source_navigation_diagnostics.py` are different historical checks (canonical geometry versus atomic OCR geometry); preserve pending explicit deprecation review.
- `backend/alembic/versions/` is migration history. Never remove older revisions to make the repository look smaller.
- `docs/architecture/` and `docs/STEP_*_CHECKPOINT.md` are traceability artifacts; do not delete without a documented retention and supersession map.
- `.gitignore` already excludes Python/Next dependencies, private env files, runtime logs and contract/database/backup contents. No mass ignore change is needed.

## Remote branch review (no deletion yet)
Potentially superseded branches: `feature/org-tree-a1-20260927`, `feature/contract-department-roles-a2-20260928`, `feature/drift1-phase2b-20260928`, selected `fix/*` branches, and `release/ahmed-pilot-package-20260929`. **Candidate** does not mean safe to delete. Before each deletion, verify commit reachability from a retained reference, open PR references, branch protection, unique changes, and branch owner's need. Keep the release packaging branch until Ahmed's deliverable is explicitly superseded.

## Next cleanup gate
1. Finish isolated trial without changing the current working branch.
2. Review this cleanup branch separately, then merge the documentation update after the trial.
3. Only archive/delete a branch after reachability and open-PR checks; record its original SHA and rationale. Prefer tags for durable historical checkpoints where appropriate.
4. Delete a tracked file only after reference searches, operational safety review and focused verification. No blanket removal based on age, filename or size.

Result of this pass: cleaned up the stale script documentation and separated cleanup work from the active trial; **no source code, databases, PAKs, GitHub branches or historical recovery files were deleted**.
