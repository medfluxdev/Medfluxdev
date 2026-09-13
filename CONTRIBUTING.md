# Contributing to MedFlux

MedFlux is one product. Backend and frontend changes must preserve a single domain truth and a single authorization model.

## Branch model

- `main`: releasable product only.
- `JAMAL-AHMAD-FULL-INTEGRATION`: integration/staging branch.
- Short-lived feature branches: `feature/<domain>-<change>`.
- Fix branches: `fix/<domain>-<issue>`.

Do not maintain parallel Ahmad/Jamal product implementations after integration. Shared improvements land through the integration branch and graduate together.

## Definition of Done

A feature is complete only when applicable layers are complete:

1. Domain/data model and migration.
2. Backend API/service.
3. Organization + hospital/department authorization scope.
4. Frontend `lib/domain-api` consumer.
5. UI loading, empty, error and permission states.
6. Audit event for meaningful mutations.
7. Backend tests and frontend tests.
8. Documentation / integration map update.
9. CI and Release Gate green.

## Architectural rules

- Backend is authoritative for calculations, warnings, accepted contract truth, permissions, ownership and intelligence.
- Frontend formats and presents; it does not independently recompute business truth.
- `organization_slug`, `hospital_id` and `department_id` are context, never authorization credentials.
- Every backend read/write containing business data must enforce server-side scope.
- Similar DTO names are not permission to merge domain concepts. Dashboard actions, Work Queue items and Intelligence proposals remain distinct.
- Evidence links must resolve to canonical provenance. Never fabricate PDF pages or coordinates.
- AI proposes; deterministic policy and human approval control accepted/high-impact actions.
- External integrations implement the connector boundary in `backend/app/integrations` and never commit credentials.

## Pull requests

Every PR should state:

- Problem / user outcome.
- Backend contract changes.
- Frontend consumer changes.
- Scope/role impact.
- Migration impact.
- Audit impact.
- Tests added/updated.
- Rollback considerations.

Contract/DTO changes that affect both sides should update both sides in the same PR or in explicitly linked PRs.

## Verification

Before merge:

```bash
cd backend && pytest -q
cd frontend && npm run verify
docker compose config
```

For production candidates run the GitHub `Release Gate` workflow and complete the UAT checklist in `docs/PRODUCTION_READINESS.md`.
