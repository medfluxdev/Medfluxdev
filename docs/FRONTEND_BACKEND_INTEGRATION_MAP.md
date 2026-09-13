# MedFlux Frontend/Backend Integration Map

Status: integration baseline implemented (2026-09-13)

## Goal
This document is the canonical map between backend capabilities and frontend consumers on `JAMAL-AHMAD-FULL-INTEGRATION`. It prevents duplicate business logic and naming collisions while Ahmad's frontend consumes Jamal's backend capabilities.

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
| Dashboard | `/api/dashboard/overview` | dashboard through `domain-api/dashboard.ts` | Connected + auth scope aware |
| Contracts | portfolio/detail/review/archive/overrides/document content | contract portfolio/detail/workspace | Connected; detail uses domain API |
| Documents | import/retry/reanalyze/source-region | import + PDF/evidence | Connected through domain API; scope persisted server-side |
| Equipment | list/detail | `/equipment`, detail route, contract/work queue links | Connected + dedicated master UI |
| Work queue | list + status transition | `/work-queue` | Connected through domain API + audited transitions |
| AI runtime | status/snapshot/test/selection | settings | Connected |
| Contract intelligence | graph/obligations/policies/action proposals/events | Contract Intelligence panel | Connected read-only |
| Operations | contract CSV export | Admin Dashboard export | Connected + role/scope protected + audited |
| Activity/Audit | `/api/activity` + contract audit/review history | `/audit`, Admin Dashboard | Connected + scope aware |
| Ownership | contract/equipment assignment + assignees | Contract Ownership panel | Connected + scope aware + audited |
| Users/scopes | `/api/users`, `/api/user-scopes` | settings/users | Connected through domain API + scope changes audited |
| Organization structure | hospitals/departments/cost centers | settings/organization | Connected through domain API manager |

## Semantic mapping / naming collisions

### Action concepts
- `dashboard.action_items`: read-only dashboard priorities.
- `work_queue.items`: operational tasks with lifecycle (`open`, `acknowledged`, `resolved`).
- `intelligence ActionProposalRecord`: system-generated proposed actions; may require human approval.

They remain separate DTOs and separate UI semantics.

### Review concepts
- `requires_review`: item/fact needs checking.
- `requires_manual_review`: contract-level review state.
- `requires_human_approval`: intelligence proposal cannot be treated as an automatically executable action.

### Identifiers
- Work Queue API uses `id` for a work item.
- Contract detail may expose `work_item_id` in embedded projections.
- Adapters normalize request construction, not domain meaning.

### Evidence concepts
- Contract detail uses `EvidenceRef` with `evidence_id`, `field_ref`, optional page/bbox/document version.
- Intelligence records use `evidence_refs` and sometimes `source_field_refs`.
- Intelligence is currently displayed without inventing evidence geometry. Future source buttons must resolve those refs through canonical contract evidence before opening the viewer.

## Scope/security state

The following product paths enforce organization plus hospital/department visibility where applicable:
- Dashboard.
- Contract portfolio/detail/document content.
- Equipment list/detail.
- Work Queue reads and mutations.
- Contract Intelligence contract reads and event filtering.
- CSV export.
- Document retry/reanalyze/source-region.
- Activity feed.
- Ownership reads/mutations and assignee selection.

New imports persist the current hospital/department ownership on the backend before the response returns. The frontend no longer performs a follow-up ownership PATCH.

CSV exports require Admin/Contract Manager/Developer authorization when auth is enabled, include only visible contracts, neutralize spreadsheet formula prefixes, and create an audit event.

Ownership changes, user-scope changes, cost-center creation and work-item transitions create authenticated activity entries.

## Canonical contract mutation router

The stale unregistered duplicate `contract_actions_secure.py` was removed. `backend/app/api/routes/contracts.py` is the single canonical contract mutation/read router.

Authorization is layered:
- LocalAuthMiddleware blocks viewer writes.
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
Existing Contract Workspace remains the main accepted-truth view. A separate Contract Intelligence panel now exposes:
- contract relations;
- obligations;
- policy decisions;
- proposed actions and whether human approval is required.

Action proposals are deliberately read-only until a canonical backend approval/execution lifecycle is validated; the frontend does not invent one.

### Equipment
The equipment master is exposed in the sidebar and uses the current authenticated organization/hospital/department context for both list and detail routes.

### Audit
Audit now recognizes ownership, user-scope, work-item and export events in addition to review/override/archive events.

### Administration
Admin Dashboard uses domain APIs and provides a scope-filtered contract CSV export.

## Verification guards

`backend/tests/test_integration_scope_guards.py` statically protects the integration invariants for:
- Intelligence scope enforcement;
- CSV export scope/role/audit requirements;
- Document scope enforcement;
- server-side import ownership assignment;
- Activity scope filtering;
- Ownership scope/auditing;
- User-scope auditing;
- Work Queue scope/auditing.

`backend/tests/test_full_integration_static_guards.py` additionally protects multi-organization identity/account semantics.

## Remaining non-blocking cleanup

- The large contract portfolio page still has legacy local request construction. `frontend/lib/api.ts` overrides organization/hospital/department context centrally and the scope picker reloads on hospital/department changes, so visibility remains correct; migrating this page fully to `domain-api/contracts.ts` is a maintainability cleanup, not a security prerequisite.
- Intelligence evidence references are displayed faithfully but are not yet turned into source-navigation buttons unless they resolve through the canonical Contract Detail evidence set.
- Intelligence action proposals remain read-only because no canonical approval/execution mutation contract has been accepted yet.

## Acceptance target

The integrated runtime flow is:

`authenticated scope -> document processing -> accepted contract truth -> deterministic calculations/warnings -> intelligence -> work queue/audit -> frontend domain API -> UI`

No frontend component should create a second calculation, authorization, ownership or intelligence truth.
