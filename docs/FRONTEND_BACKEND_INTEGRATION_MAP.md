# MedFlux Frontend/Backend Integration Map

Status: integrated baseline hardened and UI-wired (2026-09-13)

## Goal
This is the canonical map between backend capabilities and frontend consumers on `JAMAL-AHMAD-FULL-INTEGRATION`. It prevents duplicate business logic and naming collisions while Ahmad's frontend consumes Jamal's backend capabilities.

## Integration rules
1. Backend remains authoritative for calculations, warnings, review state, intelligence, permissions, ownership and scope.
2. Frontend renders backend truth and may only format/present it.
3. `organization_slug`, `hospital_id`, and `department_id` are context, never authorization credentials. Backend scope enforcement is mandatory.
4. Similar names do not imply identical domain concepts.
5. Product pages should use the frontend domain API layer rather than scattering endpoint strings through UI components.

## Capability inventory

| Domain | Backend API | Frontend consumer | State |
|---|---|---|---|
| Authentication | `/api/auth/*`, `/api/me` | login + `AuthProvider` | Connected |
| Dashboard | `/api/dashboard/overview` | dashboard through `domain-api/dashboard.ts` | Connected + scope aware |
| Contracts | portfolio/detail/review/archive/overrides/document content | portfolio/detail/workspace | Connected; detail/review/archive use domain API |
| Documents | import/retry/reanalyze/source-region | import + PDF/evidence | Connected; scope validated before processing and persisted server-side |
| Equipment | list/detail | `/equipment`, detail route, contract/work-queue links | Connected + dedicated master UI |
| Work queue | list + status transition | `/work-queue` | Connected + scoped + audited transitions |
| AI runtime | status/snapshot/test/selection | settings/developer | Status readable; test/selection restricted to Admin/Developer |
| Contract intelligence | graph/obligations/policies/action proposals/events | Contract Intelligence panel + Admin event feed | Connected read-only |
| Operations | contract CSV export | Admin Dashboard export | Connected + role/scope protected + audited |
| Activity/Audit | `/api/activity` + contract audit/review history | `/audit`, Admin Dashboard | Connected + scope aware |
| Ownership | contract/equipment assignment + assignees | Contract Ownership panel | Connected + scope aware + audited |
| Users/scopes | `/api/users`, `/api/user-scopes` | settings/users | Connected; non-admin creation is atomically scoped |
| Organization structure | hospitals/departments/cost centers | scope picker + settings/organization | Connected + server-side read scoping |
| Demo/UAT workspace | `/api/demo/workspace*` | developer tooling only | Developer-only global control |

## Semantic mapping / naming collisions

### Action concepts
- `dashboard.action_items`: read-only dashboard priorities.
- `work_queue.items`: operational tasks with lifecycle (`open`, `acknowledged`, `resolved`).
- `intelligence ActionProposalRecord`: system-generated proposed actions; may require human approval.

They remain separate DTOs and UI semantics.

### Review concepts
- `requires_review`: item/fact needs checking.
- `requires_manual_review`: contract-level review state.
- `requires_human_approval`: intelligence proposal cannot be treated as an automatically executable action.

### Evidence concepts
- Contract detail uses canonical `EvidenceRef` objects with page/document/bbox provenance.
- Intelligence records expose `evidence_refs` and `source_field_refs`.
- The UI does not invent coordinates or source links. Intelligence source navigation must resolve against canonical Contract Detail evidence first.

## Scope/security state

The following product paths enforce organization plus hospital/department visibility where applicable:
- Dashboard.
- Contract portfolio/detail/document content.
- Equipment list/detail.
- Work Queue reads and mutations.
- Contract Intelligence contract reads and event filtering.
- CSV export.
- Document retry/reanalyze/source-region/import.
- Activity feed.
- Ownership reads/mutations and assignee selection.
- Organization-structure and cost-center reads for non-admin users.

### Fail-closed provisioning
A non-admin membership without a valid hospital assignment is not interpreted as organization-wide access. `ScopeContextMiddleware` assigns an impossible sentinel hospital scope until an administrator provisions the user correctly, causing scoped product queries to return no organizational data.

Non-admin user creation requires a valid active hospital and optionally an active department belonging to that hospital. This scope is persisted in the same backend transaction as account/membership creation. An Admin cannot be downgraded to a normal role while remaining organization-wide.

### Import ownership
The backend validates the active hospital/department scope before any document processing starts. New accepted imports then persist that scope on the resulting contract before returning to the frontend. The old client-side ownership PATCH has been removed.

### Global installation controls
AI model/provider mutation and AI test execution are restricted to Admin or Developer. The installation-wide Demo/UAT workspace is Developer-only.

### Audited mutations
Authenticated activity is recorded for:
- contract/equipment ownership changes;
- user-scope changes;
- hospital/department/cost-center administration;
- work-item lifecycle transitions;
- contract export;
- existing contract review/override/archive activity.

CSV exports require Admin/Contract Manager/Developer authorization when auth is enabled, include only visible contracts, neutralize spreadsheet formula prefixes, and create an audit event.

## Canonical contract mutation router

The stale unregistered duplicate `contract_actions_secure.py` was removed. `backend/app/api/routes/contracts.py` is the single canonical contract mutation/read router.

Authorization is layered:
- `LocalAuthMiddleware` blocks viewer writes.
- Reviewer writes are restricted to review/fact-review/work-queue flows.
- Route-level identity logic provides authenticated reviewer names.
- Ownership and administration routes apply explicit role checks.

## Frontend domain API layer

Established under `frontend/lib/domain-api/`:
- `contracts.ts`
- `documents.ts`
- `equipment.ts`
- `workQueue.ts`
- `intelligence.ts`
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
Existing Contract Workspace remains the accepted-truth view. Contract Intelligence now exposes relations, obligations, policy decisions and action proposals. Proposed actions remain read-only until a canonical backend approval/execution lifecycle exists.

### Equipment
The equipment master is exposed in the sidebar and honors the authenticated organization/hospital/department scope for list and detail routes.

### Users and organization
User creation/editing supports role plus hospital/department assignment. Organization settings use a shared domain-backed manager for hospitals, departments and cost centers. The top scope picker consumes the same organization API.

### Audit and administration
Audit surfaces authenticated activity alongside fact reviews and overrides. Admin Dashboard uses domain APIs, includes scoped CSV export, and shows scoped Intelligence Events.

## Verification

`backend/tests/test_integration_scope_guards.py` statically protects integration invariants for Intelligence, exports, document preflight, import ownership, activity, ownership, user scopes, Work Queue, provisioning fail-closed behavior, organization metadata, AI mutations and Developer-only demo mode.

`backend/tests/test_full_integration_static_guards.py` protects multi-organization identity/account semantics and atomic scoped account provisioning.

GitHub Actions workflow `.github/workflows/integration-check.yml` verifies backend Python syntax and runs the frontend `npm run verify` suite on the integration branch.

## Remaining non-blocking cleanup

- The large contract portfolio page still contains legacy local request/query construction. Central `scopedPath()` overrides organization/hospital/department context and the scope picker reloads on scope changes, so authorization remains server-side. Full migration to `domain-api/contracts.ts` is maintainability cleanup.
- Intelligence evidence refs are displayed faithfully but are not converted to viewer navigation unless they can be resolved through canonical Contract Detail evidence.
- Intelligence action proposals remain read-only because no canonical approval/execution mutation contract has been accepted yet.

## Acceptance target

`authenticated scope -> document processing -> accepted contract truth -> deterministic calculations/warnings -> intelligence -> work queue/audit -> frontend domain API -> UI`

No frontend component creates a second calculation, authorization, ownership or intelligence truth.
