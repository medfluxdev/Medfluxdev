# MedFlux maintenance scripts

Use the repository-root launchers and the documented local/pilot setup. Do not run a script solely because its name sounds appropriate: some historical scripts are destructive or assume a different database.

## Current local runtime
- `START_MEDFLUX_LOCAL.bat` and `STOP_MEDFLUX_LOCAL.bat` are repository-root launchers. **Do not use the start launcher for the isolated 55432 trial without reviewing it:** its PostgreSQL fallback checks port 5432.
- `scripts/spawn_medflux_backend.ps1`, `scripts/spawn_medflux_frontend.ps1`, `scripts/stop_medflux_runtime.ps1`: launcher runtime helpers.
- `scripts/ollama_models.ps1`, `scripts/set_local_model.py`: locally installed AI model discovery/selection; no model download is required for a trial.
- `scripts/start_local_postgres.ps1`: inspect configuration and target database before running.
- `scripts/verify_local_pilot_preflight.ps1`: read-only pilot configuration checks; specify the expected isolated PostgreSQL port explicitly when applicable.
- See `docs/LOCAL_LAUNCHER_AR.md` and `docs/INSTALLATION_PILOT.md` for their respective operating modes; their database defaults are **not** interchangeable.

## Data protection and recovery
- `scripts/backup_medflux.py`, `scripts/verify_backup.py`, `scripts/restore_backup.py`: current backup/verification/explicit-target restore tooling. Review options and test only on isolated data.
- **Historical destructive recovery tool:** `scripts/restore_from_backup.py` drops the configured database's public schema. Never run it for normal restoration or the local trial; retained temporarily for historical recovery/audit until dependencies and retention are verified.
- Treat `scripts/cleanup_product_db.py`, `scripts/clean_runtime_v2.py`, `scripts/reset_product_data.py` and `backend/scripts/reset_product_data.py` as potentially destructive until individually audited.

## Diagnostic and benchmark scripts
Scripts such as `source_navigation_diagnose.py` and `source_navigation_diagnostics.py` serve **different** historical geometry checks. They are not duplicates merely because their names are similar. Benchmark scripts may require local contract PDFs that must never be committed.

## Repository cleanup
See `docs/GITHUB_CLEANUP_REGISTER_20261001.md` for evidence-based cleanup decisions. Keep the verified stable branch immutable until the complete release gate passes. Do not delete branches, migration files, tests, or historical recovery tooling on naming alone.
