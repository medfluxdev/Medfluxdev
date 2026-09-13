# MedFlux Frontend/Backend Integration Map

Status: Phase 1-2 audit baseline (2026-09-13)

## Goal
This document is the canonical map between backend capabilities and frontend consumers on `JAMAL-AHMAD-FULL-INTEGRATION`. It prevents accidental duplicate business logic and naming collisions while Ahmad's frontend is connected to Jamal's backend work.

## Integration rules
1. Backend remains authoritative for calculations, warnings, review state, intelligence, permissions and scope.
2. Frontend renders backend truth and may only format/present it.
3. `organization_slug`, `hospital_id`, and `department_id` are context, not authorization credentials. Backend scope enforcement is mandatory.
4. Similar names do not imply identical domain concepts.
5. New frontend calls should go through a domain API adapter instead of scattering endpoint strings across pages.

## Capability inventory

| Domain | Backend API | Main backend source | Current frontend consumer | Status |
|---|---|---|---|---|
| Authentication | `/api/auth/*` | `backend/app/api/routes/auth.py` | `AuthProvider`, login/profile flows | Connected |
| Dashboard | `GET /api/dashboard/overview` | `dashboard.py` | `frontend/app/page.tsx` | Connected |
| Contracts | `GET /api/contracts`, detail, review, archive, overrides, document content | `contracts.py` | contract list/detail/workspace | Connected; audit remaining |
| Documents | import, retry, reanalyze, source-region | `documents.py` | import + PDF/evidence flows | Partial |
| Equipment | list/detail | `equipment.py` | contract detail and work queue only | Partial; dedicated UI missing |
| Work queue | list + status transition | `work_queue.py` | `/work-queue` | Connected |
| AI runtime | status, snapshot, test, selection | `ai.py` | `/settings` | Connected |
| Contract intelligence | graph, obligations, policies, actions, events | `intelligence.py` | no complete consumer | Missing |
| Operations | contract CSV export | `operations.py` | no clear consumer | Missing |
| Activity/Audit | activity + auth audit APIs | activity/auth routes | audit/profile surfaces | Partial |
| Organizations/users | system organizations, org structure, users/scopes | system/users/organization routes | developer/admin/settings | Connected; scope audit remaining |

## Semantic mapping / naming collisions

### Action concepts
- `dashboard.action_items`: read-only dashboard priorities.
- `work_queue.items`: operational tasks with lifecycle (`open`, `acknowledged`, `resolved`).
- `intelligence ActionProposalRecord`: system-generated proposed actions; may require human approval.

These must not be merged into one DTO or list.

### Review concepts
- `requires_review`: item/fact needs checking.
- `requires_manual_review`: contract-level review state.
- `requires_human_approval`: intelligence action cannot execute automatically.

### Identifiers
- Work Queue API uses `id` for a work item.
- Contract detail may expose `work_item_id` in embedded work-item projections.
- Both identify a work item, but they belong to different response DTOs; adapters should normalize only at presentation boundaries.

### Evidence concepts
- Contract detail uses `EvidenceRef` with `evidence_id`, `field_ref`, optional page/bbox/document version.
- Intelligence records use `evidence_refs` and sometimes `source_field_refs`.
- Frontend must resolve intelligence refs through the canonical contract evidence collection before opening the document viewer.

## Scope/security findings

### Already scope-aware
- Dashboard uses `current_scope_context()` + `scoped_contract_ids()`.
- Contracts apply scope filtering to portfolio/detail visibility.
- Equipment applies hospital/department filtering.
- Work Queue filters by scoped contract IDs.

### Requires backend hardening before UI exposure
- Intelligence routes are organization-scoped but must also enforce hospital/department contract visibility.
- CSV export must apply the same contract scope when hospital/department scope is active.
- Any action-execution route must be checked before wiring Action Proposals to buttons.

## Frontend domain API target

Create a thin adapter layer under `frontend/lib/domain-api/`:
- `contracts.ts`
- `documents.ts`
- `equipment.ts`
- `workQueue.ts`
- `intelligence.ts`
- `operations.ts`
- `organizations.ts`

Responsibilities:
- construct routes/query parameters;
- centralize TypeScript DTOs where practical;
- expose semantic methods (`listWorkItems`, `getContractObligations`, `reanalyzeDocument`) instead of raw endpoint strings;
- do not calculate domain values.

## Phase 3 gate
Intelligence and Operations UI work is blocked until backend hospital/department scope enforcement is verified by tests.
