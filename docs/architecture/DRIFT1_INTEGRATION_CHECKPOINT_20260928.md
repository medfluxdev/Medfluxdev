# DRIFT-1 integration checkpoint — 2026-09-28

## Big-picture invariant
MedFlux uses Alembic migrations for deployed databases. A green ORM create_all fixture is not evidence that migrations match production. Keep the existing per-test isolation and never mutate an existing or production database.

## Current implementation
- Based on independently verified operational timestamp fix a75e205.
- Reintroduces the opt-in, empty-disposable-database migration gate from the separate DRIFT-1 branch, with stricter URL rejection for ambiguous query options, empty suffixes and path separators.
- Includes unit tests for URL guards.
- Does NOT yet replace conftest.py or claim full ORM/migration parity. Remaining known drift: three contract_equipment nullabilities, nine defaults, four type differences, thirteen migration-only indexes and two index-name differences; investigate each before changing production schema.
- Do not delete migration-only indexes or defaults just to force ORM metadata equality: production migrations are authoritative until behavior and intent are assessed.

## Verification sequence (OpenCode TESTING ONLY)
1. Confirm base ancestry, diff and single Alembic head b3c5d7e90928. Verify operational migration and application code are unchanged.
2. Run backend/tests/test_drift1_migration_gate.py and backend/tests/test_operational_timestamp_migration.py in unit-only mode.
3. Independently provision ONE EMPTY disposable database named medflux_drift1_<random> on isolated local PG 55432. From backend/ run scripts/verify_migrated_fixture.py with explicit DRIFT1_DISPOSABLE_DATABASE_URL. Confirm migrated head, 45 tables and operational timestamp columns. Drop only that disposable database.
4. Probe URL guards without contacting forbidden endpoints. Do not mutate other databases.
5. Report any failures with precise reproduction. Do not implement fixes, merge, deploy, trigger Actions, launch Ollama/Qwen or use GPU.
6. Report baseline/full suite only if already configured safely; don't change global environment or interrupt other workloads.

## Next engineering phase (assistant-owned)
Add a separate opt-in migrated-schema integration fixture for targeted ORM CRUD/API tests while preserving existing isolated pytest fixtures; make test DB provisioning explicit, fail-closed and independent of existing DBs. Build a structured migration-vs-ORM parity report, categorize genuine blockers versus intentional migration-only artifacts, and fix verified mismatches additively. Do not globally switch the full test suite until evidence supports it.
