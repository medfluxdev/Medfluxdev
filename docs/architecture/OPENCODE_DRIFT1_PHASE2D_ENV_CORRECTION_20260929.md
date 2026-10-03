# Phase 2D environment correction — missing historical databases

The seven historical databases are NOT a prerequisite to the opt-in, rolled-back 2D fixture. They were a non-interference cross-check only. Do not restore, recreate, seed or search the whole disk for them; do not assert they are intact or deleted when unavailable.

TESTING ONLY. First inspect read-only the isolated PostgreSQL 55432 server identity and existing database list. If server identity is ambiguous or the 55432 instance is not the approved isolated disposable test instance, STOP and report. Never switch to port 5432 or 5444. No production access.

If approved isolated PG55432 is available, provision exactly ONE new, uniquely named empty medflux_drift1_* disposable DB on it, following the previously verified creation and deletion guards. Run the migration gate FIRST; run 2D + prior opt-in tests with MEDFLUX_UNIT_ONLY=1 and the explicit disposable URL. Audit committed state in the new DB before/after 2D; the test intentionally issues INSERT/UPDATE inside a transaction, so verify ROLLBACK rather than claiming zero DML statements. Drop ONLY the disposable DB created for this run, after verifying its identity.

Report the seven old DBs as 'historical cross-check unavailable in this environment', with their absence on the observed server and without making any integrity claim. Do not create substitutes or overwrite historical baselines. Keep historical digest verification explicitly UNVERIFIED.

Run baseline and production-shaped security separately, distinguishing the inherited MEDFLUX_INSECURE_DEV environment failure. Return exact PASS/FAIL, including any actual 2D fixture SQL failures. No code changes, migration edits, merges, deploy, Actions, GPU, Ollama, Qwen or existing-process interruption. STOP.
