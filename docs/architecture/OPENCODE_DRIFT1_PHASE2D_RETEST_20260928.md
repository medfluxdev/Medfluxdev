# OpenCode: DRIFT-1 Phase 2D — testing-only handoff

Exact target is this branch HEAD. Assistant authored backend/tests/test_drift1_real_legacy_rollback.py. No app, conftest, migrations or normal database changes.

**Resources:** CPU/RAM and one fresh disposable local PostgreSQL18 database on port 55432 only. No GPU/Ollama/Qwen.

1. Fetch exact HEAD and inspect the new test for transactional and FK correctness. Run ordinary unit/regression suite with the opt-in test skipped; distinguish the known MEDFLUX_INSECURE_DEV environment failure.
2. Create ONE fresh empty medflux_drift1_* database on PG55432, confirm identity and empty schema. Run the existing migration gate FIRST. Do not run the new test before the gate.
3. With MEDFLUX_UNIT_ONLY=1 and explicit DRIFT1_MIGRATED_TEST_DATABASE_URL, run the new Phase 2D test plus the earlier 2B/2C opt-in modules. The new test intentionally performs INSERT/UPDATE within ONE explicit transaction and always ROLLS BACK; therefore do not expect zero DML statement count during its execution. Verify no committed changes and 45-table census before/after.
4. Inspect the fixture chain organization -> contract + document_file -> document_version -> contract_extraction -> contract_equipment. Test one fully NULL legacy row and one explicit recorded row, 2/1/1/1 measured counts, legacy device-name update without altering NULL verdicts, full rollback and no persisted org.
5. Independently verify all seven pre-existing databases are unchanged by read-only counts/revisions. Historical digest equality remains UNVERIFIED. Clean up only the disposable DB you created.
6. Report precise PASS/FAIL and any FK/default/check constraint failure. Do not fix code, create migrations, change indexes, invent AI verdicts, merge, deploy or start GitHub Actions. STOP.

A green synthetic fixture does NOT establish representative historical NULL distribution or justify NOT NULL migration. Do not use any real contract document, production storage or non-disposable DB.
