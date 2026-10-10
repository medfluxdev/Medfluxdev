# MedFlux Frontend/Backend Integration Map

Status: integrated operational baseline (2026-09-13)

## Goal
This is the canonical map between backend capabilities and frontend consumers on `JAMAL-AHMAD-FULL-INTEGRATION`. It prevents duplicate business logic and naming collisions while Ahmad's frontend consumes Jamal's backend capabilities.

## Integration rules
1. Backend remains authoritative for calculations, warnings, review state, intelligence, permissions, ownership and scope.
2. Frontend renders backend truth and may only format/present it.
3. `organization_slug`, `hospital_id`, and `department_id` are context, never authorization credentials. Backend scope enforcement is mandatory.
4. Similar names do not imply identical domain concepts.
5. Product pages should use the frontend domain API layer rather than scattering endpoint strings through UI components.
6. AI may propose actions; high-impact operational state changes remain human controlled and audited.

## Capability inventory

| Domain | Backend API | Frontend consumer | State |
|---|---|---|---|
| Authentication | `/api/auth/*`, `/api/me` | login + `AuthProvider` | Connected + login throttle/request IDs |
| Dashboard | `/api/dashboard/overview` | dashboard through `domain-api/dashboard.ts` | Connected + scope aware |
| Contracts | portfolio/detail/review/archive/overrides/document content | portfolio/detail/workspace | Connected; accepted truth remains authoritative |
| Contract lifecycle | `/api/lifecycle/contracts/*` | Contract 360 lifecycle panel | Connected + audited human decisions |
| Documents | import/retry/reanalyze/source-region | import + PDF/evidence | Connected; scope validated before processing and persisted server-side |
| Processing diagnostics | `/api/processing-jobs*` | Developer processing page | Connected to canonical `ProcessingRun`, no second job truth |
| Equipment | list/detail | `/equipment`, detail route, contract/work-queue links | Connected + dedicated master UI |
| Equipment lifecycle | `/api/lifecycle/equipment/*` | equipment detail | Connected + audited operational state |
| Work queue | list + status transition | `/fristen?ansicht=aufgaben` (`/work-queue` redirects) and the contract tab „Fristen & Aufgaben“ | Connected + scoped + audited transitions |
| Work queue collaboration | collaboration/comments | Aufgaben organize panel | Connected; assignment/reminder/escalation/comments survive reconcile |
| AI runtime | status/snapshot/test/selection | settings/developer | Status readable; test/selection restricted to Admin/Developer |
| Contract intelligence | graph/obligations/policies/action proposals/events | Contract Intelligence panel + Admin event feed | Connected |
| Intelligence action lifecycle | `/api/intelligence/actions/{id}` | Contract Intelligence panel | Human approve/reject/cancel/execute confirmation + audit |
| Intelligence evidence | canonical Contract Detail evidence | inline Intelligence source viewer | Resolved to canonical PDF provenance or fails closed |
| Notifications | `/api/notifications` (Arbeitsvorrat, true total), `/api/inbox` (+`offset`/`unread_only`/`total`), `/api/inbox/summary` | bell „Für mich“ / „Arbeitsvorrat“, `/postfach` = full log | Badge = unread personal notifications with the same query and scope as the list |
| Register | `/api/register/grid` (`totals` with coverage), `/grid/counts`, `/reports/portfolio` (`amounts`, `definitions`), `/renewals` (`not_evaluable`) | `/register` tabs, Mein Tag, Analysen, Fristen | One running definition, unknown never summed as 0 |
| Partner linking | `/api/catalogs/partners/unlinked`, `/partners/link-supplier` | Stammdaten → Vertragspartner „Lieferanten zuordnen“ | Suggestions only; linking via the register update path (manual origin, history per contract) |
| Reporting | `/api/reports/portfolio` | domain API / reporting consumer | Connected + scoped |
| Operations | contract CSV export | Admin Dashboard export | Connected + role/scope protected + audited |
| Activity/Audit | `/api/activity` + contract audit/review history (`field_labels`) | `/audit` „Aktivitäten & Protokoll“ (admin area), contract „Verlauf“, Admin Dashboard | Connected + scope aware |
| Ownership | contract/equipment assignment + assignees | Contract Ownership panel | Connected + scope aware + audited |
| Users/scopes | `/api/users`, `/api/user-scopes` | settings/users | Connected; non-admin creation is atomically scoped |
| Organization structure | hospitals/departments/cost centers | scope picker + settings/organization | Connected + server-side read scoping |
| Demo/UAT workspace | `/api/demo/workspace*` | developer tooling only | Developer-only global control |
| Integrations | `backend/app/integrations` connector contract | provider-specific future adapters | Stable boundary; live activation requires provider credentials/UAT |
| Health/readiness | `/health`, `/live`, `/ready` | deployment/runtime | Connected |

## Semantic mapping / naming collisions

### Action concepts
- `dashboard.action_items`: read-only dashboard priorities.
- `work_queue.items`: deterministic operational tasks (`open`, `acknowledged`, `resolved`).
- `WorkItemCollaboration`: human assignment/reminder/escalation/comments layered on a derived Work Item.
- `intelligence ActionProposalRecord`: AI/system proposed action with a separate human approval lifecycle.
- `ContractLifecycleDecision`: explicit human business decision about renew/renegotiate/terminate/monitor.

They remain separate DTOs and persistence concepts.

### Review concepts
- `requires_review`: item/fact needs checking.
- `requires_manual_review`: contract-level review state.
- `requires_human_approval`: intelligence proposal cannot be treated as an automatically executable action.

### Evidence concepts
- Contract detail uses canonical `EvidenceRef` objects with page/document/bbox provenance.
- Intelligence records expose `evidence_refs` and `source_field_refs`.
- Intelligence source buttons resolve those refs against canonical Contract Detail evidence.
- Unresolvable evidence explicitly shows unavailable; the UI never invents coordinates or pages.

## Scope/security state

The following product paths enforce organization plus hospital/department visibility where applicable:
- Dashboard.
- Contract portfolio/detail/document content and lifecycle decisions.
- Equipment list/detail and lifecycle state.
- Work Queue reads/mutations/collaboration.
- Contract Intelligence reads/action lifecycle/event filtering.
- Notifications and portfolio reports.
- Processing-run diagnostics.
- CSV export.
- Document retry/reanalyze/source-region/import.
- Activity feed.
- Ownership reads/mutations and assignee selection.
- Organization-structure and cost-center reads for non-admin users.

### Fail-closed provisioning
A non-admin membership without a valid hospital assignment is not interpreted as organization-wide access. `ScopeContextMiddleware` assigns an impossible sentinel hospital scope until an administrator provisions the user correctly, causing scoped product queries to return no organizational data.

Non-admin user creation requires a valid active hospital and optionally an active department belonging to that hospital. This scope is persisted in the same backend transaction as account/membership creation. An Admin cannot be downgraded to a normal role while remaining organization-wide.

### Import ownership
The backend validates the active hospital/department scope before document processing starts. New accepted imports persist that scope on the resulting contract before returning to the frontend. The old client-side ownership PATCH has been removed.

### Global installation controls
AI model/provider mutation and AI test execution are restricted to Admin or Developer. The installation-wide Demo/UAT workspace is Developer-only.

### Security infrastructure
- Request correlation uses `X-Request-ID`.
- Login has an application-local conservative throttle; deployment edge must provide distributed rate limiting.
- Pilot/production configuration validation requires authentication, a non-default secret and secure cookies.
- `/ready` fails closed if the primary database is unavailable.

### Audited mutations
Authenticated activity is recorded for:
- contract/equipment ownership changes;
- user-scope changes;
- hospital/department/cost-center administration;
- work-item lifecycle and collaboration/comment changes;
- contract lifecycle decisions;
- equipment lifecycle changes;
- intelligence action transitions;
- contract export;
- contract review/override/archive activity.

CSV exports require Admin/Contract Manager/Developer authorization when auth is enabled, include only visible contracts, neutralize spreadsheet formula prefixes, and create an audit event.

## Canonical contract mutation router

The stale unregistered duplicate `contract_actions_secure.py` was removed. `backend/app/api/routes/contracts.py` is the canonical accepted-contract mutation/read router. Operational lifecycle and Intelligence approval have their own narrowly scoped routers because they represent different domain state, not duplicate contract truth.

Authorization is layered:
- `LocalAuthMiddleware` blocks viewer writes.
- Reviewer writes are restricted to review/fact-review/work-queue flows.
- Route-level identity logic provides authenticated reviewer names.
- Ownership, lifecycle and administration routes apply explicit role checks where required.

## Frontend domain API layer

Established under `frontend/lib/domain-api/`:
- `contracts.ts`
- `documents.ts`
- `equipment.ts`
- `workQueue.ts`
- `workQueueCollaboration.ts`
- `intelligence.ts`
- `lifecycle.ts`
- `processingJobs.ts`
- `notifications.ts`
- `reports.ts`
- `dashboard.ts`
- `activity.ts`
- `operations.ts`
- `ownership.ts`
- `organizations.ts`
- `users.ts`

Responsibilities:
- construct routes/query parameters;
- centralize DTO contracts where practical;
- expose semantic operations rather than raw URLs;
- preserve domain distinctions;
- never recompute backend business truth.

## Main UI integration

### Contract 360
Contract Workspace remains the accepted-truth view. Contract lifecycle decisions, Intelligence relations/obligations/policies/action proposals and canonical Intelligence evidence navigation are layered around it without mutating extracted truth.

### Work Queue
Derived work items keep their canonical three-state lifecycle. Human assignment, reminders, escalation notes and comments are separate collaboration records so deterministic reconcile cannot erase them.

### Equipment
The equipment master is exposed in the sidebar and honors authenticated scope. Equipment detail now carries a distinct operational lifecycle and next-service state.

### Users and organization
User creation/editing supports role plus hospital/department assignment. Organization settings use a shared domain-backed manager for hospitals, departments and cost centers. The top scope picker consumes the same organization API.

### Audit and administration
Audit surfaces authenticated activity alongside fact reviews and overrides. Admin Dashboard uses domain APIs, includes scoped CSV export, and shows scoped Intelligence Events. Developer tooling includes Processing Run diagnostics with provider/OCR/error metadata.

## Verification

- `backend/tests/test_integration_scope_guards.py`: integration/scope invariants.
- `backend/tests/test_full_integration_static_guards.py`: multi-organization identity/account semantics and atomic provisioning.
- `backend/tests/test_operational_integration_guards.py`: operational routers, human action lifecycle, processing-run reuse, collaboration separation, security/readiness and release gate.
- `.github/workflows/integration-check.yml`: full backend pytest against isolated PostgreSQL plus frontend `npm run verify`.
- `.github/workflows/release-gate.yml`: migrations, backend tests, frontend verification, Compose validation and production image builds.
- `docs/PRODUCTION_READINESS.md`: manual role/scope/security/backup/AI/external-integration UAT gate.

## Deployment architecture

`docker-compose.yml` uses PostgreSQL 18 as the database target and readiness-based startup ordering. SQLite is not the production target. External infrastructure still owns HTTPS termination, distributed rate limiting, automated backups, monitoring/alert delivery and customer-specific identity/integration credentials.

## Remaining cleanup / external activation

- The large contract portfolio page still contains legacy local URL/query construction, although all requests are server-authorized and `scopedPath()` injects selected scope. Migration to `domain-api/contracts.ts` remains maintainability-only cleanup.
- Real DMS/SharePoint/ERP/CMMS/email adapters require the target provider endpoint, credentials and mapping/UAT; the connector boundary exists but MedFlux must not fabricate those integrations.
- Customer SSO/MFA activation requires actual IdP metadata/credentials and deployment policy.
- Production approval additionally requires the manual staging/UAT and backup/restore checks in `PRODUCTION_READINESS.md`.

## Acceptance target

`authenticated scope -> document processing -> accepted contract truth -> deterministic calculations/warnings -> intelligence + evidence -> human approval/lifecycle -> work queue/collaboration -> notifications/audit/reporting -> frontend domain API -> UI`

No frontend component creates a second calculation, authorization, ownership, accepted-contract or intelligence truth.
