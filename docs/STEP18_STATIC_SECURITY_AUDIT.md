# STEP 18 Static Security / Tenant Boundary Audit

Scope: static review only; no runtime claim is made here.

## Confirmed controls

- `LocalAuthMiddleware` protects non-public API routes when `AUTH_ENABLED` is true.
- The signed auth identity owns the organization binding. If a request supplies an `organization_slug` different from the signed identity, middleware returns 404; the query parameter is not accepted as an authorization credential.
- Viewer role is denied domain writes (`POST`, `PUT`, `PATCH`, `DELETE`) except logout.
- Equipment list/detail resolve the organization first and pass `organization_id` into service queries.
- Document source-region lookup filters `DocumentVersion` by both opaque version ID and organization ID before resolving stored bytes/canonical data.
- Document import responses intentionally avoid leaking protected provider/DB/exception diagnostics through the fallback message.

## Remaining static review work

- Review contracts, dashboard, intelligence, operations and work-queue routes end-to-end for organization binding at every direct-object lookup.
- Confirm service-layer queries always include organization scope, not only route-layer checks.
- Confirm document/evidence storage keys cannot be resolved cross-organization through indirect foreign keys.
- Confirm audit/provenance reads are tenant-scoped and immutable events do not expose another organization.
- Confirm AUTH_ENABLED=false is constrained to local/development deployment and cannot silently become a production posture.
- Add negative cross-tenant tests for every resource family and opaque-ID endpoint.

## Security invariant

`organization_slug` is routing context, never authorization. Authorization derives from the authenticated identity and every direct-object lookup must also be organization-scoped so a leaked UUID cannot cross tenant boundaries.
