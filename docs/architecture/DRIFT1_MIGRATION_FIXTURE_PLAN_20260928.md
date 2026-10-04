# DRIFT-1 — migration-faithful isolated test fixture

Status: architecture/investigation; NO fixture implementation or migration changes yet.
Base: verified PRE-1 c98f310a44e27c532377b42599076cff2ca17de2.
Do not merge/deploy/alter protected JAMAL.

## Verified source anchors
- backend/conftest.py: disposable schema per pytest run; test-facing search_path=<test>,public, schema-only DDL engine create_all, explicit table-count guard.
- backend/alembic/env.py: Alembic reads settings.database_url and runs online migrations via engine_from_config/NullPool. Its context currently has no explicit version_table_schema or schema-aware extension policy.
- OpenCode PRE-1 report: migration-vs-ORM discrepancy includes 12 missing migration-only indexes, 4 defaults, 2 type divergences, 2 index names. These are reported findings; do not assume they are benign or silently change ORM/migrations.

## Safety-first design gates
1. Prove that Alembic can run ALL historical revisions in a dedicated throwaway PostgreSQL DATABASE (preferred), rather than a search_path-only schema if any migration uses explicit public schema, raw unqualified SQL, extension DDL, or nontransactional operations. No migrations may run against the existing public or real product DB.
2. Inventory every migration, including raw SQL, extension installation, CREATE INDEX CONCURRENTLY, schema assumptions, alembic_version handling, data backfills, and any fixture dependencies. Validate how extensions (pg_trgm) are installed in the disposable database.
3. Keep a non-migration unit-only mode for tests that intentionally have no PostgreSQL; never let it silently fall back to a production DB.
4. In a separate fixture branch, replace ORM create_all with alembic upgrade head only after isolated-DB safety is established. Add explicit DB identity/URL allowlist and fail-closed checks, version-table verification, migration-head check, cleanup and no-production fingerprint assertions.
5. Run ORM-vs-migrated-schema reconciliation as a separately reviewed inventory: identify true ORM defects vs intentionally migration-only structures. Do not auto-edit historical migrations or delete indexes/defaults.
6. Benchmark startup and execute complete baseline/A1/A2 regressions including concurrency and two environment profiles. Verify role unique partial index, check constraints, pg_trgm indexes, source-search GIN indexes, default expressions and type parity.
7. Stop on any migration that could touch shared public, cross-database objects, or any actual user data. OpenCode executes tests only after assistant authors a safe patch and Jamal approves test scope.

This document establishes the separate DRIFT-1 workstream, not a claim that migration fidelity is solved.
