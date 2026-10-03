# Isolated MedFlux test database

Local Windows backend tests use only the existing WSL PostgreSQL cluster at
`/opt/medflux-test-pg/data`, bound to `127.0.0.1:55432`. Its required identity
is database `medflux_trial_20261001`, role `sr415_flow`, and PostgreSQL cluster
system identifier `7689962266201178762`. The test harness
does not use `DATABASE_URL` or `backend/.env` for this local test path.

The password is never persisted by this helper. If neither
`MEDFLUX_TEST_DATABASE_URL` nor `MEDFLUX_TRIAL_DSN` is provided, an interactive
Windows invocation asks for the password using a hidden prompt and keeps it in
process memory only. Noninteractive runners such as OpenCode should inject one
of those variables into the test process environment. Do not put the DSN in
`.env`, source files, or Git.

## Operations

```powershell
.\scripts\medflux_test_db.ps1 status
.\scripts\medflux_test_db.ps1 prepare
.\scripts\medflux_test_db.ps1 verify
.\scripts\medflux_test_db.ps1 test
```

`prepare` validates the cluster directory, PostgreSQL version and system
identifier, listen address, and port; checks
the exact cluster state, starts that cluster only if stopped and port 55432 is
free, then queries PostgreSQL for database, role, server port, and bound
address. It also checks PostgreSQL's cluster system identifier, so a different
cluster with a copied database name is refused. The pytest session runs the same
preparation before creating its random isolated schema. On Windows, any URL other than the pinned test
identity is rejected before a database connection is attempted. In
particular, port 5432 and any other database are rejected.

After Windows or WSL restarts, run the wrapper or pytest again; WSL starts on
demand and the custom cluster is started by its exact data directory. MedFlux
does not call the generic `postgresql` systemd service or manage Debian's
`18/main` cluster. GitHub Actions is separately restricted to its ephemeral
workflow PostgreSQL service and does not use the local WSL cluster.
