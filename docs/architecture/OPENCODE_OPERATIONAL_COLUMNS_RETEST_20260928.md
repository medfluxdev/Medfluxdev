# OpenCode operational missing-column blocker: verification only

Target branch: fix/operational-missing-columns-blocker-20260928
Base: verified PRE-1 c98f310a44e27c532377b42599076cff2ca17de2.
Assistant authored an ADDITIVE migration (revision b3c5d7e90928) adding:
- equipment_lifecycle.created_at TIMESTAMPTZ NOT NULL DEFAULT now()
- work_item_collaboration.created_at TIMESTAMPTZ NOT NULL DEFAULT now()
- work_item_comment.updated_at TIMESTAMPTZ NOT NULL DEFAULT now()

**IMPORTANT:** No application or ORM edits, no historical migration rewrites, no merge. DRIFT-1 migration-fidelity work remains separate.

## Mandatory tests
1. Verify diff, single Alembic head, model-vs-migration column types/default/nullability. Run new structural tests and existing operational integration tests.
2. Disposable local PG 55432 ONLY: fresh empty database, apply all migrations to head, verify 3 columns present and 3 relevant entity SELECTs succeed. Exercise 5 registered operational endpoints with authenticated fixtures if feasible; report exact coverage.
3. Independently test upgrade with EXISTING rows: migrate a separate disposable DB only to parent a2b4c6d80928, create valid organization/contract/equipment/work-item/account fixtures using ordinary application constraints, insert records into all 3 affected tables, record row counts/IDs/old timestamps; upgrade to head; prove no data loss, preserved existing columns, populated non-null new timestamps and successful ORM SELECTs. Avoid production data entirely.
4. Downgrade in disposable database to parent and re-upgrade; confirm ONLY new columns removed/re-added, other data preserved. Note that downgrade drops new timestamp values by design; no production downgrade recommendation.
5. Run PRE-1 schema-isolated backend regression, A1 hierarchy/A2 ownership and concurrency tests, production-shaped security tests. Distinguish inherited posture-env failure and known remaining drift.
6. Record all remaining ORM/migration differences, particularly 13 indexes, 9 defaults, 4 type divergences, 3 contract_equipment nullability divergences and 2 index names. Do not assert full migration parity; DRIFT-1 handles fixture transition separately.
7. Do not use GPU, Ollama, Qwen or any AI model. Do not interfere with Jamal's existing processes. No Actions, merge, deploy, PG 5432, or production databases. If resource conflict occurs, STOP and ask Jamal.

Return full report with actual commands, counts, exact SHA and STOP. Never author fixes; assistant handles all changes.
