# DRIFT-1 Phase 2C: legacy-null probe retest

Assistant-authored changes since a8d5ced: expected mapper count assertion in migrated smoke; new synthetic legacy-null classification and read-only migrated catalog/NULL-count probe. No migration, app, global conftest or production schema change.

OpenCode TESTING ONLY. Verify exact HEAD, diff, and test imports (including the sibling test module import in pytest). Run unit-only tests, including the synthetic all-NULL, all-recorded and mixed cases. Independently review that 'unknown_legacy' is TEST classification only, never persisted and never presented as an AI verdict.

Provision ONE new empty disposable medflux_drift1_* database on isolated local PostgreSQL port 55432. Gate FIRST, then opt-in smoke and legacy-null probe with MEDFLUX_UNIT_ONLY=1 and explicit DRIFT1_MIGRATED_TEST_DATABASE_URL. Verify expected 44 mapper assertion, 44 ORM SELECTs, actual three column nullable flags, measured NULL counts and absence of any DML/DDL during both opt-in tests. Run normal regressions separately.

Coverage limitation: this is a synthetic semantic fixture and read-only catalog/count probe, NOT an actual inserted legacy-row CRUD test. Do not report populated migration/backfill safety as proven. For the NEXT assistant-owned phase, specify the minimum valid foreign-key fixture chain for a real contract_equipment row and the exact rollback/isolation mechanism, but DO NOT create data, implement tests or alter code. Do not propose an automatic NOT NULL migration.

Keep composite org/responsible index as reviewed; do not treat the missing redundant single-column index as a defect. Seven-DB old digest integrity remains unverified.

Do not edit code, merge, deploy, trigger Actions, run GPU/Ollama/Qwen, touch 5432/11434 or any pre-existing DB. Drop only the new disposable DB you provisioned. Report and STOP.
