# DRIFT-1 phase 2B — decisions before schema changes

Base: verified phase 2A commit 9666867. All changes here are opt-in tests and documentation, NOT application or schema migrations.

## Reviewed discrepancies
1. contract_equipment.identification_quality, relationship_quality, requires_review: ORM says NOT NULL; historical migration c91e4f02a3b7 adds them nullable, because it expands a pre-existing populated table. **Do not ALTER NOT NULL blindly.** First measure actual NULL rows on a disposable copy of representative populated data, identify legacy meaning, verify deterministic backfill behavior and API compatibility. If safe, implement a separately tested additive backfill + constraint migration; never fabricate AI identification or relationship quality. No production data access for this decision.
2. contract.responsible_account_id: ORM index ix_contract_responsible_account versus migration's composite ix_contract_org_responsible_account (organization_id, responsible_account_id). The composite index is tenant-scoped and intentionally useful for org-filtered queries. Keep it. Do not add a redundant single-column index without EXPLAIN/actual workload evidence. Inventory must label semantic/index-design differences, not automatically classify missing single-column index as a bug.
3. The 37 remaining inventory entries include unique-constraint backing indexes, dialect type aliases, and server default representation differences. Preserve full raw inventory for audit; add reviewed classification separately rather than hiding it.
4. Historical seven-database row-count discrepancy was inclusion of alembic_version. Prior digest equality remains UNVERIFIED. Do not call old snapshots bit-identical; version any future checksum script and record whether alembic_version is included.

## New opt-in migrated integration smoke
backend/tests/test_drift1_migrated_integration.py is deliberately read-only and requires DRIFT1_MIGRATED_TEST_DATABASE_URL, a separately provisioned, already-migrated local disposable medflux_drift1_* DB on PG55432. It asserts DB identity and revision and compiles real mapped ORM SELECT LIMIT 0. It does not replace the normal isolated pytest fixture or provision/drop any database.

Important: normal pytest conftest may still initialize its own isolated test schema unless MEDFLUX_UNIT_ONLY=1 is set; run opt-in smoke with unit-only mode and explicit migrated URL, then run baseline tests separately. A green SELECT smoke does NOT prove write compatibility, tenant ACL or migration safety on populated production data.

## OpenCode testing-only handoff
- Fetch exact HEAD from this branch. Verify only one new test and this doc relative to 9666867.
- Run unit-only guard tests. On ONE fresh isolated empty medflux_drift1_* DB at PG55432, first run verified migration gate, then opt-in smoke with MEDFLUX_UNIT_ONLY=1 and explicit migrated URL. Verify 44/44 entity SELECTs and no writes.
- Run normal relevant regression tests separately; distinguish inherited env failure.
- Report the three nullability fields and index-design decision; do not alter schema or app.
- No edits, merge, deploy, GitHub Actions, GPU/Ollama/Qwen, 5432/11434 or other DB writes. Drop only the disposable DB you created. STOP with report.
