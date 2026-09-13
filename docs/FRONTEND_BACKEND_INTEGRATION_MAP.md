# MedFlux Frontend/Backend Integration Map

Status: Phase 1-3 baseline active (2026-09-13)

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
| Contracts | `GET /api/contracts`, detail, review, archive, overrides, document content | `contracts.py` | contract list/detail/workspace | Connected; route semantics audit remains |
| Documents | import, retry, reanalyze, source-region | `documents.py` | import + PDF/evidence flows | Partial |
| Equipment | list/detail | `equipment.py` | contract detail and work queue only | Partial; dedicated UI missing |
| Work queue | list + status transition | `work_queue.py` | `/work-queue` | Connected |
| AI runtime | status, snapshot, test, selection | `ai.py` | `/settings` | Connected |
| Contract intelligence | graph, obligations, policies, actions, events | `intelligence.py` | domain adapter added; UI not yet wired | Ready for UI after verification |
| Operations | contract CSV export | `operations.py` | no clear consumer | Backend scope hardened; UI missing |
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

### Scope-aware paths
- Dashboard uses `current_scope_context()` + `scoped_contract_ids()`.
- Contracts apply scope filtering to portfolio/detail visibility.
- Equipment applies hospital/department filtering.
- Work Queue filters by scoped contract IDs.
- Intelligence now rejects contract-bound reads outside the current hospital/department scope and filters graph/event results.
- Operations CSV export now limits rows to current scoped contract IDs.

### Contract action route finding
`backend/app/api/routes/contract_actions_secure.py` is not registered in `backend/app/main.py` and must not be treated as a live API. It also references the current contract workspace helper with an outdated call shape. Until it is reconciled with the live `contracts.py` router, no frontend button may depend on it.

This is important because the live `contracts.py` currently remains the registered contract router. We will decide in a later integration pass whether to merge the role/provenance improvements from the secure file into the live route or remove the stale duplicate.

## Frontend domain API target

A thin adapter layer is being established under `frontend/lib/domain-api/`.

Started:
- `intelligence.ts` — graph, obligations, policies, action proposals, events.

Planned:
- `contracts.ts`
- `documents.ts`
- `equipment.ts`
- `workQueue.ts`
- `operations.ts`
- `organizations.ts`

Responsibilities:
- construct routes/query parameters;
- centralize TypeScript DTOs where practical;
- expose semantic methods (`listWorkItems`, `getContractObligations`, `reanalyzeDocument`) instead of raw endpoint strings;
- preserve semantic differences between dashboard actions, work items and intelligence proposals;
- do not calculate domain values.

## Verification guard
`backend/tests/test_integration_scope_guards.py` protects the integration baseline by checking that Intelligence and CSV export keep their scope dependencies and filters.

## Next implementation slice
1. Finish route-by-route request/response/consumer inventory for Documents, Contracts, Users, Ownership and Activity.
2. Reconcile live `contracts.py` mutation authorization with the unregistered `contract_actions_secure.py` implementation.
3. Add frontend domain adapters for documents/equipment/work queue before moving existing pages to them.
4. Only then wire Intelligence panels into Contract Workspace.
