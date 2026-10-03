# MedFlux integration baseline

Baseline branch: `JAMAL-AHMAD-FULL-INTEGRATION`
Baseline commit: `ca07599052041336578b85aeb5ab32f9fd21a44b`
Recorded: 2026-09-13

This baseline is the recovery point before the next integration hardening sequence.

Acceptance surface:
- backend starts and `/health` is reachable;
- frontend starts on the configured local URL;
- authentication and authenticated scope context work;
- Dashboard, Contracts/Contract 360, Equipment, Work Queue, Users, Admin and Developer surfaces remain reachable;
- organization/hospital/department authorization stays server-side;
- frontend does not recompute backend business truth.

Execution order from this baseline:
1. CI and full backend/frontend tests.
2. Finish frontend domain API migration.
3. Persisted asynchronous document-processing jobs.
4. Intelligence evidence navigation.
5. Intelligence action approval/execution lifecycle.
6. Work Queue 2.0 and operational lifecycle layers.
7. Security, observability, deployment and release gates.

Definition of Done for a feature:
`model/migration -> backend API -> authorization/scope -> frontend domain API -> UI states -> audit -> tests -> documentation -> CI verification`.
