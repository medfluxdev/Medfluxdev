# STEP 18 Static Security / Tenant Boundary Audit

Scope: static review only. No runtime pass is claimed until the local PostgreSQL/auth test gates execute.

## Confirmed controls

- `LocalAuthMiddleware` protects every non-public API route when `AUTH_ENABLED=true`.
- The signed session identity owns the organization binding. A request supplying a different `organization_slug` receives a generic 404; the query parameter is routing context, never an authorization credential.
- Viewer role is denied domain writes (`POST`, `PUT`, `PATCH`, `DELETE`) except logout.
- `APP_ENV=pilot|production` now refuses startup unless `AUTH_ENABLED=true` and `AUTH_COOKIE_SECURE=true`; an authenticated deployment also refuses the default `APP_SECRET_KEY`.
- Contract portfolio/detail/review/archive/document-content routes resolve the organization before domain access and pass `organization_id` into their read/write services.
- Dashboard queries are organization-scoped.
- Intelligence graph/obligation/policy/action/event queries filter `organization_id`.
- Work-queue list/update resolves the organization and uses organization-scoped work-item queries; DTO enrichment queries contracts/equipment by organization.
- Equipment list/detail scopes the equipment row and contract relationships by organization. The detail relationship join now also explicitly requires `Contract.organization_id == organization_id` as defense in depth.
- Operational CSV export is organization-scoped, authenticated-org bound, private/no-store, and neutralizes spreadsheet formula prefixes (`=`, `+`, `-`, `@`) including whitespace-prefixed values.
- Document source-region lookup filters `DocumentVersion` by opaque version ID + organization before resolving protected bytes/canonical data.
- `DocumentPersistenceService.resolve_bytes_for_version` scopes `DocumentVersion`, optional contract linkage, and the contract itself to the organization before reading the storage reference.
- Canonical artifact storage references are server-generated from UUIDs; clients never provide filesystem paths.
- Audit-event reads are scoped by authenticated `organization_id`.
- Human-review provenance has server-side ORM hooks: when an authenticated identity is bound, client-supplied reviewer names are overwritten with signed user identity (`authenticated_local` + `app_user.id`). DB-free spoof-resistance tests were added.
- Contract 360 now obtains `/api/auth/me` for review actions and displays the authenticated reviewer; unauthenticated development mode remains explicitly `manual_unverified`.
- Review-required evidence is now presented as `Unbestätigt · Menschliche Prüfung erforderlich`, not as a merely recommended review.

## Negative regression coverage added

- Cross-organization slug is expected to return 404 for contracts, dashboard, equipment, work queue, intelligence events and CSV export.
- Cross-organization opaque document source-region lookup is expected to return 404 before object lookup.
- Cross-organization contract write is expected to return 404.
- Pilot/production cannot start in unauthenticated or insecure-cookie posture.
- Authenticated review provenance overrides spoofed client reviewer names.
- CSV formula-injection values are neutralized.

These tests are committed but are **runtime-pending** until the local isolated PostgreSQL / frontend gates run.

## Lower-level observations

- Current production document import uses `DocumentPersistenceService`, whose duplicate lookup is organization-scoped. Some older low-level persistence helpers predate the org-scoped uniqueness migration and should not be promoted as alternate production paths; the production orchestrator remains the sole supported document path.
- Several child tables carry both `organization_id` and a parent FK. Application queries reviewed here enforce the organization explicitly; a future PostgreSQL-hardening phase can add composite org+parent foreign-key constraints/RLS as a second database-level boundary. This is defense in depth, not a discovered route bypass.
- No route reviewed in this STEP exposed a storage key or absolute filesystem path to the browser.

## Runtime-only closure checks

1. Run DB-free `scripts/step18_safety_gate.ps1`.
2. Run DB-backed auth/tenant regression tests, including `test_auth_route_boundary_e2e.py` and existing auth E2E.
3. Run the full backend suite against the isolated test schema.
4. Run frontend TypeScript/lint/build after the Contract 360 identity/evidence UI changes.

## Security invariant

`organization_slug` is routing context, never authorization. Authorization derives from the signed identity, and direct-object reads/writes in the supported production paths are organization-scoped so a leaked UUID alone cannot cross tenant boundaries.
