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
| Contracts | portfolio/detail/review/archive/overrides/document content | `contracts.py` | contract list/detail/workspace | Connected; domain adapter added |
| Documents | import, retry, reanalyze, source-region | `documents.py` | import + PDF/evidence flows | Scope hardened; domain adapter added |
| Equipment | list/detail | `equipment.py` | contract detail and work queue only | Domain adapter added; dedicated UI missing |
| Work queue | list + status transition | `work_queue.py` | `/work-queue` | Domain adapter added; page migration pending |
| AI runtime | status, snapshot, test, selection | `ai.py` | `/settings` | Connected |
| Contract intelligence | graph, obligations, policies, actions, events | `intelligence.py` | domain adapter added; UI not yet wired | Ready for UI after verification |
| Operations | contract CSV export | `operations.py` | no clear consumer | Backend scope hardened; UI missing |
| Activity/Audit | activity + auth audit APIs | activity/auth routes | audit/profile surfaces | Activity scope hardened; UI audit remains |
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
- Intelligence rejects contract-bound reads outside the current hospital/department scope and filters graph/event results.
- Operations CSV export limits rows to current scoped contract IDs.
- Document retry/reanalyze/source-region now fail closed for scoped users unless the document is linked to a visible contract.
- New imports persist the current hospital/department ownership on the backend before the response returns; the frontend no longer performs a follow-up ownership PATCH.
- Activity now filters contract events by visible contract IDs and non-contract events by persisted hospital/department scope.

### Contract action route resolution
The unregistered duplicate `backend/app/api/routes/contract_actions_secure.py` was removed. It was stale and referenced outdated helper signatures. The registered `contracts.py` router remains canonical.

Mutation authorization is enforced by the active `LocalAuthMiddleware` plus route-level reviewer identity logic:
- viewers cannot mutate;
- reviewers may mutate fact-review/review and work-queue paths only;
- archive/override/import/ownership mutations remain limited to broader roles through middleware/route checks.

No frontend code should target a second contract mutation router.

## Frontend domain API layer

Established under `frontend/lib/domain-api/`:
- `intelligence.ts` — graph, obligations, policies, action proposals, events.
- `contracts.ts` — portfolio/detail/review/archive/override/document URL.
- `documents.ts` — import/retry/reanalyze/source-region URL.
- `equipment.ts` — list/detail.
- `workQueue.ts` — list/status lifecycle.

Still planned:
- `operations.ts`
- `organizations.ts`
- optional `activity.ts` once the audit UI contract is finalized.

Responsibilities:
- construct routes/query parameters;
- centralize TypeScript DTOs where practical;
- expose semantic methods instead of raw endpoint strings;
- preserve semantic differences between dashboard actions, work items and intelligence proposals;
- do not calculate domain values.

## Verification guards
`backend/tests/test_integration_scope_guards.py` protects the integration baseline by checking that Intelligence, CSV export, Documents and Activity keep their scope dependencies and filters.

## Next implementation slice
1. Audit and harden Ownership/Users/Organization Structure against hospital/department scope edge cases.
2. Migrate existing Work Queue and Import consumers to the new domain adapters without changing UI behavior.
3. Add Operations adapter + scoped CSV download surface.
4. Then wire Intelligence panels into Contract Workspace using the canonical evidence model.
