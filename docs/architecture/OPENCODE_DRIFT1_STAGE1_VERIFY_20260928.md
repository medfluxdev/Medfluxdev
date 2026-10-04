# OpenCode DRIFT-1 stage 1: safe opt-in migration gate verification

Target branch fix/migration-fixture-drift1-20260928; this branch adds a standalone migration verification script and target-guard tests, not a replacement for conftest.py. PRE-1 and A2 remain unchanged. **TEST ONLY**.

1. Confirm branch diff and run backend/tests/test_drift1_migration_gate.py in an appropriate unit-only environment; inspect safety guard carefully.
2. Before ANY migration run, independently audit ALL backend/alembic/versions revisions for raw SQL, extensions, schema-qualified writes, assumptions, autocommit, destructive data backfills, UUIDv7 support and dependencies. Check script for any unsafe condition. If any, STOP and report; do not execute migrations.
3. If safe, independently CREATE a new, empty, random-named database medflux_drift1_<random> on disposable isolated PostgreSQL port 55432 only. Confirm actual server/database identity and verify that the regular medflux/public schema is untouched. NEVER use existing medflux, postgres, real hospital data, PG 5432 or any nonlocal server.
4. Run from backend/ with DRIFT1_DISPOSABLE_DATABASE_URL pointing to that exact throwaway database: python scripts/verify_migrated_fixture.py. Record migration head, actual tables, indexes, server defaults, column types, extension availability, runtime and any failures. A failed migration is a reportable result, not permission to patch code.
5. Compare actual migrated schema against ORM metadata: enumerate the previously reported 12 indexes, 4 defaults, 2 type divergences, 2 index naming differences. Do not claim parity simply because migrations reach head.
6. Do NOT change conftest.py or switch the full pytest suite to the new fixture in this stage. That switch requires separately reviewed safety and performance evidence. Preserve current verified PRE-1 isolation.
7. Drop ONLY the disposable database YOU created after collecting evidence, after confirming exact identity. If uncertain, leave it intact and report. No merges, deploy, Actions, Ollama changes, production operations, or OpenCode-authored implementation.

Report PASS/FAIL/NOT RUN with exact SHA and commands; STOP for assistant review.
