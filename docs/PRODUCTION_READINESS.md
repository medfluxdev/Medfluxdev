# MedFlux Production Readiness

This is the release/UAT checklist for the integrated MedFlux product. A green build alone is not a production approval.

## Automated release gate

The `.github/workflows/release-gate.yml` workflow must pass:

- Alembic migration from an empty PostgreSQL database to `head`.
- Full backend `pytest` suite against isolated PostgreSQL.
- Frontend lint, Vitest and production build (`npm run verify`).
- `docker compose config` validation.
- Backend and frontend production image builds.

## Golden UAT flow

Complete in a staging installation using non-production documents:

1. Sign in as Developer, Admin, Contract Manager, Reviewer and Viewer.
2. Select organization, hospital and department scopes.
3. Import PDF and DOCX samples.
4. Confirm processing run is visible and errors are diagnosable.
5. Open Contract 360 and verify accepted facts against PDF evidence.
6. Open an Intelligence evidence source and confirm canonical page/highlight navigation.
7. Review/correct facts and confirm audit trail.
8. Assign ownership.
9. Create/acknowledge/resolve Work Queue work; assign user, reminder and comment.
10. Create a contract lifecycle decision and complete/cancel it.
11. Approve/reject an Intelligence Action Proposal; only an approved proposal may be confirmed as executed.
12. Update equipment operational lifecycle and next service date.
13. Verify scoped notification feed and portfolio report.
14. Archive/restore a contract where supported.
15. Export scoped contracts and verify spreadsheet-safe output.

## Authorization matrix

Validate both UI behavior and direct API calls.

- Viewer: read-only in assigned scope.
- Reviewer: review/fact-review operational writes only where allowed.
- Contract Manager: contract/workflow operations in assigned organization/scope.
- Admin: organization administration plus normal scoped product operations.
- Developer: installation-wide administration only for explicitly global developer routes.

For every role verify Hospital A cannot read/write Hospital B through manipulated query parameters. Organization/hospital/department values are context, never authorization credentials.

## Data safety

- Production uses PostgreSQL; SQLite is not a production target.
- Database backups are automated outside the application container.
- Restore is tested before go-live and periodically thereafter.
- Document storage and database backup retention are documented per customer.
- Test suites use isolated schemas and never product data.
- Secrets are environment/runtime configuration and are not committed.
- Pilot/production requires auth enabled, non-default secret, HTTPS and secure auth cookies.

## Security gate

- TLS terminates at the deployment edge.
- Reverse proxy supplies distributed request/login rate limits; application login throttling is an additional local guard.
- Security headers are present.
- CORS allow-list contains only deployment origins.
- Upload size and accepted media types are enforced.
- Session revocation/logout behavior is tested.
- Dependency/security scanning is part of organization deployment policy.
- SSO/MFA is enabled when required by the customer identity architecture; activation requires IdP-specific metadata/credentials and is not hardcoded in MedFlux.

## Observability

- `/live` confirms process liveness.
- `/ready` confirms database readiness.
- `X-Request-ID` is returned for support correlation.
- Deployment captures structured application/container logs without credentials or document contents.
- Alerting monitors unavailable backend/database, repeated processing failures and storage exhaustion.

## AI safety and quality

- AI provider/model configuration is controlled by Admin/Developer routes.
- Accepted contract truth and deterministic calculations remain backend-authoritative.
- AI evidence is never fabricated; unresolved references are shown as unavailable.
- Human approval is required for high-impact Intelligence proposals.
- Production model/provider changes are benchmarked against the maintained evaluation corpus before rollout.

## External integrations

DMS/SharePoint/ERP/CMMS/email connectors must implement `backend/app/integrations` and have:

- provider-specific credentials outside source control;
- least-privilege service account;
- sync cursor/idempotency strategy;
- retries and dead-letter/error visibility;
- mapping tests;
- customer-approved data transfer boundary.

No connector is considered active until its real provider credentials, endpoint and UAT are supplied.

## Go-live record

Record for each release:

- version / git SHA;
- migration head;
- Release Gate run;
- UAT date and tester;
- environment and AI model/provider versions;
- known limitations;
- backup/restore verification date;
- rollback version and procedure.

Release is approved only after automated gates and manual UAT are both complete.
