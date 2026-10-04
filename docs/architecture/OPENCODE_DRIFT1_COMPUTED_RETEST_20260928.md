# DRIFT-1 Computed fix retest — 2026-09-28

OpenCode TESTING ONLY. Assistant owns all code.

1. Confirm diff since 43eaa35 is limited to drift1_schema_inventory.py and new test_drift1_schema_inventory.py. No migration/application/conftest changes.
2. Unit-only run: test_drift1_schema_inventory.py, test_drift1_migration_gate.py and test_operational_timestamp_migration.py. Verify the new test actually exercises SQLAlchemy Computed.
3. Use ONE newly provisioned EMPTY disposable medflux_drift1_<random> database on local isolated PostgreSQL port 55432. Run the full verify_migrated_fixture.py gate, requiring exit 0, structured JSON inventory, head b3c5d7e90928, 45 tables, no missing ORM columns. Independently check computed column contract.search_vector and identify any remaining false-positive entries. Do not change schema based solely on inventory.
4. Run relevant regressions and baseline suite only with safe baseline environment. Separate inherited production posture env failure.
5. PRE-EXISTING DATABASE FINGERPRINTS: the previous 'bit-identical' claim was not reproducible. Do not mutate or run writes against any pre-existing DB to investigate. Identify exact seven DB names, timestamped original and current snapshot source, checksum algorithm/script VERSION, table filters, per-DB counts and discrepancies. If original algorithm or snapshots cannot be reproduced, explicitly mark historical integrity UNVERIFIED; do not manufacture a new baseline as proof of past integrity. Report +1 total_rows observations as unresolved, not caused by this code unless evidence proves it.
6. Drop ONLY newly provisioned disposable DB. Clean worktree. No implementation edits, commits, merges, deployment, GitHub Actions, GPU/Ollama/Qwen, 5432/11434 or interruption of existing AI workloads. STOP with report.
