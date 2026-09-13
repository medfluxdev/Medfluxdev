# Medflux Frontend Project Progress

Created: 2026-09-13
Last updated: 2026-09-13
Status: IN PROGRESS
Progress: 4/10 development steps complete (40%)
Active step: FE-05 — Contract table and search workflow
Next action: Verify the first FE-05 implementation batch, then continue list-context and supported actions.

## Purpose

Develop Medflux into a consistent, accessible, reliable application for hospital contract management. Optimize the daily journey: identify required action, find a contract, verify its source, and complete the review.

This tracker complements `docs/PROJECT_PROGRESS.md`; the ten frontend steps do not replace the original MVP progress calculation.

## Working rules

1. Implement steps in order with one active step at a time.
2. Inspect and reuse the current implementation before editing.
3. Do not simulate missing backend capabilities as completed features.
4. Verify each step with relevant automated checks and browser/manual checks.
5. Keep processing, assets, fonts, telemetry, and AI runtime local.
6. Keep product copy in German.
7. Backend authorization remains authoritative.
8. Facts come from extraction and sources; code calculates costs/deadlines; missing data is never invented or converted to zero.

Allowed statuses: PLANNED, IN PROGRESS, BLOCKED, COMPLETE.

## Execution overview

| Step | Deliverable | Priority | Status |
| --- | --- | --- | --- |
| FE-01 | Current-state audit and acceptance baseline | P0 | COMPLETE |
| FE-02 | Design system and shared components | P0 | COMPLETE |
| FE-03 | Application shell and organization navigation | P0 | COMPLETE |
| FE-04 | Loading, errors, authentication, and service states | P0 | COMPLETE |
| FE-05 | Contract table and search workflow | P0 | IN PROGRESS |
| FE-06 | Contract detail and source review workspace | P0 | PLANNED |
| FE-07 | Action-oriented dashboards | P1 | PLANNED |
| FE-08 | Import and analysis experience | P1 | PLANNED |
| FE-09 | Tasks, deadlines, and administration | P1 | PLANNED |
| FE-10 | Accessibility, performance, and release verification | P0 release gate | PLANNED |

## FE-01 — Audit and acceptance baseline

Status: COMPLETE

Implemented / verified:
- Route, component, stylesheet, API and test inventory documented in `docs/FRONTEND_FE01_AUDIT.md`.
- Representative role and journey map documented.
- P0/P1 defects separated from enhancements.
- Backend dependency map and reference layouts recorded.
- Frontend baseline recovered to a green production build.

Key evidence:
- `docs/FRONTEND_FE01_AUDIT.md`
- Production build succeeds.
- Automated frontend suite was repaired and later reached a fully green baseline.

## FE-02 — Design system and shared components

Status: COMPLETE

Implemented:
- Consolidated semantic frontend layer in `frontend/app/design-system.css`.
- Standardized shared control states and loading behavior.
- Added local component reference under `/developer/components`.
- Kept fonts/assets local and retained German product copy.

Key files:
- `frontend/app/design-system.css`
- `frontend/components/ui/Button.tsx`
- `frontend/app/developer/components/page.tsx`
- `frontend/app/layout.tsx`

Verification:
- Frontend build and test suite passed after integration.

## FE-03 — Application shell and organization navigation

Status: COMPLETE

Implemented:
- Split monolithic navigation into `AppSidebar` and `AppTopbar` shell components.
- Grouped role-aware navigation with active states.
- Collapsible sidebar preference persisted locally.
- Consolidated account actions.
- Active organization/scope remains visible in shell controls.
- API and AI status are independent.
- Scope picker responses are hardened against partial payloads.
- Search has an accessible label.
- Duplicate `main-content` ownership was removed.

Key files:
- `frontend/components/ClientNav.tsx`
- `frontend/components/shell/AppSidebar.tsx`
- `frontend/components/shell/AppTopbar.tsx`
- `frontend/components/OrganizationScopePicker.tsx`
- `frontend/app/shell.css`

Verification:
- Shell/navigation tests included in the green frontend suite.

## FE-04 — Loading, errors, authentication, and service states

Status: COMPLETE

Implemented:
- Standardized API errors with `ApiError` and useful German messages for HTTP, timeout, and network failures.
- 401/session expiry dispatches a centralized session-expired event and returns users to login with a clear reason.
- Login supports password visibility, paste/autofill/password managers, accessible busy state, and duplicate-submit prevention while preserving inputs after recoverable errors.
- API and local AI/model health are checked independently.
- Service health requests are cancellable, refresh periodically, refresh on tab focus, and distinguish unknown/stale state.
- Existing major screens retain retry/loading/empty states; contract list distinguishes empty dataset from filtered no-results.

Key files:
- `frontend/lib/api.ts`
- `frontend/components/auth/AuthProvider.tsx`
- `frontend/app/login/page.tsx`
- `frontend/components/shell/AppSidebar.tsx`
- `frontend/test/api-timeout.test.ts`
- `frontend/test/interaction-audit.test.tsx`

Verification:
- Frontend tests and production build reported green after the final FE-04 fixes.
- Remaining React `act(...)` console warnings are non-blocking test-harness cleanup and are tracked for FE-10.

## FE-05 — Contract table and search workflow

Status: IN PROGRESS
Depends on: FE-04

Completed in current implementation batch:
- [x] Preserve existing filters, sorting, pagination and URL state.
- [x] Add compact/comfortable table density preference persisted locally.
- [x] Add user-controlled column visibility persisted locally; prevent hiding every column.
- [x] Add sticky table headers and keyboard-focusable horizontal table scrolling.
- [x] Show active URL filters as individually removable chips plus a clear-filter action.
- [x] Add local saved views with explicit local persistence; no unsupported server persistence is claimed.
- [x] Add a quick-preview panel using already-loaded contract-list data, without leaving the list.
- [x] Remember list URL and scroll position before opening a contract and restore scroll when returning to the same list state.
- [ ] Reverify all filter URL round-trips and pagination boundaries after the new view tools.
- [ ] Add/verify supported bulk actions only if backend APIs exist.
- [ ] Add filtered export only if backend support exists; otherwise keep it absent.

Backend dependency review:
- No verified backend endpoint was found for saved-view persistence, bulk contract actions, or filtered export during this batch. These controls are therefore not presented as server-backed features.

Key files:
- `frontend/components/contracts/ContractTable.tsx`
- `frontend/components/contracts/ContractListViewTools.tsx`
- `frontend/app/contracts-list.css`
- `frontend/test/contract-list-preferences.test.tsx`

Acceptance target:
Users can find, compare, preview, and reopen contracts without rebuilding their search. Sorting and totals must continue to reflect the complete filtered dataset returned by the backend.

## FE-06 — Contract detail and source review workspace

Status: PLANNED
Depends on: FE-05

Planned scope:
- Clear summary header and coherent overview/costs-deadlines/equipment/documents/history structure.
- Adjustable split review workspace and small-screen alternative.
- Correct document version/page/highlight resolution.
- Explicit extracted/reviewed/missing/calculated states.
- Confidence only when supplied.
- Review/edit with previous value, reason and audit information.
- Explain calculated costs/deadlines without AI calculations.
- Unsaved-edit protection and useful missing-document/PDF failure recovery.

## FE-07 — Action-oriented dashboards

Status: PLANNED
Depends on: FE-06

Planned scope:
- Urgent actions and cancellation deadlines first.
- Scope/period-aware KPIs.
- KPIs link to the corresponding filtered list.
- Missing-data coverage and unknown cost remain explicit.
- Keep currencies separate without an approved conversion basis.
- Role-aligned dashboards and meaningful partial/empty states.

## FE-08 — Import and analysis experience

Status: PLANNED
Depends on: FE-07

Planned scope:
- Accessible picker and drag/drop.
- Honest supported types/limits and target scope.
- Per-file upload/import/analysis outcomes.
- Separate import success from analysis success.
- Real server stages or honest indeterminate progress.
- Retry only eligible failures and preserve durable jobs where supported.

## FE-09 — Tasks, deadlines, and administration

Status: PLANNED
Depends on: FE-08

Planned scope:
- Define tasks/warnings/reviews relationship.
- Useful filters and direct links to contract/reason.
- Distinguish contract end from cancellation deadline.
- Assignment/completion only with verified backend support and permissions.
- Standardize organization/user forms and preserve history on deactivation.
- Keep developer administration separate from scoped operational administration.

## FE-10 — Accessibility, performance, and release verification

Status: PLANNED
Depends on: FE-09

Release-gate scope:
- Keyboard/focus/accessibility review against WCAG 2.2 AA target.
- Representative widths 1440/1280/768/390 and 320-pixel reflow.
- Lazy-load heavy features where useful.
- Production performance baseline and budgets.
- End-to-end core journeys and visual regression references.
- Frontend build/lint/tests and backend tests for any changed APIs.
- No external fonts/assets/analytics/AI dependencies.
- Resolve release-blocking defects and document remaining limitations.

## Current verification commands

From `frontend/`:

```bash
npm run test
npm run build
```

Run backend `pytest` only when backend behavior changes.
