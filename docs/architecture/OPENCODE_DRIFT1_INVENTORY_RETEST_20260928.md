# DRIFT-1 phase 2A: schema inventory retest

Assistant-authored code. OpenCode: TESTING ONLY; do not fix code.

Branch fix/drift1-integration-20260928. Verify exact HEAD before running.

Changes since prior PASS 1ba4d0d: path-based script import in test_drift1_migration_gate.py; new read-only drift1_schema_inventory.py; verification gate now prints JSON inventory and fails closed for missing ORM columns. No conftest replacement, production migration edits, application changes or merges.

1. Review diff and syntax; test import shadowing by creating an unrelated importable scripts package if practical without mutating repository.
2. Unit-only test_drift1_migration_gate.py and test_operational_timestamp_migration.py.
3. Provision one new EMPTY, disposable medflux_drift1_<random> DB on local isolated PG 55432. Run the existing migration gate. Confirm one Alembic head b3c5d7e90928, 45 tables, 44/44 ORM SELECTs and printed JSON inventory.
4. Independently compare inventory categories against actual migrated PostgreSQL catalog and ORM; report counts AND full item lists. Type aliases, default expression spellings, unique constraint indexes and index renames can be false positives. Identify them; do not automatically change schema to match inventory.
5. Run relevant regressions and report exact outcomes; distinguish inherited environment split.
6. Drop only your disposable DB. Verify pre-existing DB fingerprints. No edits, commits, merges, deployments, Actions, GPU/Ollama/Qwen or touching 5432/11434. STOP and report.

Future phase 2B, assistant-owned: after inventory review, add an opt-in migrated-database pytest integration fixture and targeted API tests; do not globally replace conftest until validated.
