# Medflux Frontend Project Progress

Created: 2026-09-13
Last updated: 2026-09-13
Status: IN PROGRESS
Progress: 5/10 development steps complete (50%)
Active step: FE-06 — Contract detail and source review workspace
Next action: Verify the current FE-06 provenance/source batch, then continue calculated-value clarity and remaining workspace acceptance checks.

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
| FE-05 | Contract table and search workflow | P0 | COMPLETE |
| FE-06 | Contract detail and source review workspace | P0 | IN PROGRESS |
| FE-07 | Action-oriented dashboards | P1 | PLANNED |
| FE-08 | Import and analysis experience | P1 | PLANNED |
| FE-09 | Tasks, deadlines, and administration | P1 | PLANNED |
| FE-10 | Accessibility, performance, and release verification | P0 release gate | PLANNED |

## FE-01 — Audit and acceptance baseline
Status: COMPLETE

Implemented / verified:
- Route, component, stylesheet, API and test inventory documented in `docs/FRONTEND_FE01_AUDIT.md`.
- Representative roles and journeys documented.
- P0/P1 defects separated from enhancements.
- Backend dependency map and reference layouts recorded.
- Production build baseline recovered.

## FE-02 — Design system and shared components
Status: COMPLETE

Implemented:
- Consolidated semantic frontend layer in `frontend/app/design-system.css`.
- Standardized shared controls and loading behavior.
- Added local component reference under `/developer/components`.
- Kept assets/fonts local and product copy German.

## FE-03 — Application shell and organization navigation
Status: COMPLETE

Implemented:
- Split navigation into sidebar/topbar shell components.
- Grouped role-aware navigation with active states.
- Persisted collapsible sidebar preference.
- Consolidated account actions.
- Active scope remains visible.
- API and AI status are independent.
- Scope picker responses are hardened and stale structure requests are cancellable.
- Search has an accessible label and duplicate `main-content` ownership was removed.

## FE-04 — Loading, errors, authentication, and service states
Status: COMPLETE

Implemented:
- Standardized German API/network/timeout errors.
- Central session-expiry handling for 401.
- Login password visibility/autofill/busy-state/double-submit protection.
- Independent API and local AI/model health with refresh/stale handling.
- Retry/loading/empty behavior verified on major journeys.

Verification:
- Frontend suite and production build green after final FE-04 fixes.
- React `act(...)` warnings remain non-blocking test-harness cleanup for FE-10.

## FE-05 — Contract table and search workflow
Status: COMPLETE
Depends on: FE-04

Implemented / verified:
- [x] Existing filters, sorting, pagination and URL state preserved.
- [x] Compact/comfortable density preference persisted locally.
- [x] Column visibility preference persisted locally; hiding all columns is prevented.
- [x] Sticky headers and keyboard-focusable horizontal scrolling.
- [x] Active URL filters shown as individually removable chips with clear-all action.
- [x] Saved views implemented with explicit local-only persistence.
- [x] Quick preview uses already-loaded list data without leaving list context.
- [x] List URL and scroll position are remembered before opening a contract and restored on return.
- [x] Existing filter URL round-trip and pagination tests remained green after integration.
- [x] New list-preference tests cover filter chips, density, columns, quick preview and saved views.

Backend dependency result:
- No verified server API exists for saved-view persistence, bulk contract actions, or filtered export. Unsupported bulk/export controls remain absent instead of being simulated.

Verification result:
- User-reported local frontend test suite: 124/124 passing after final FE-05 test adjustment.
- Production build remained green in the FE-05 verification run.

Key files:
- `frontend/components/contracts/ContractTable.tsx`
- `frontend/components/contracts/ContractListViewTools.tsx`
- `frontend/app/contracts-list.css`
- `frontend/test/contract-list-preferences.test.tsx`

## FE-06 — Contract detail and source review workspace
Status: IN PROGRESS
Depends on: FE-05

Existing foundation already present:
- Clear contract summary header and tabbed overview/term/finance/services/equipment/documents structure.
- Source navigation to document version/page/highlight.
- Evidence, fact review, override and history views.

Implemented in current FE-06 batches:
- [x] Correction workflow requires a reason and sends it through the verified backend `note` field.
- [x] Previous/effective values and correction reason remain visible in review history.
- [x] Unsaved correction drafts trigger browser navigation protection.
- [x] Organization/hospital/department scope changes are cancelable before local scope is mutated, allowing review drafts to block accidental context switches.
- [x] PDF source loading distinguishes forbidden, missing version/document, server error and timeout states with a real retry action.
- [x] PDF/source refinement requests are cancellable; previous PDF documents/render tasks are cleaned up when switching.
- [x] Fact review now labels actual backend-supported provenance as `Extrahiert`, `Geprüft`, `Korrigiert`, `Fehlt` or `Systemwert`; labels are not guessed from UI state.
- [x] Evidence confidence is shown only for finite values within 0..1; invalid confidence is suppressed instead of presented as meaningful.
- [x] Evidence precision wording distinguishes exact, approximate, page-only and missing-position source states.
- [x] Review/source workspace receives a stacked small-screen layout with non-sticky evidence/PDF panels and touch-friendly document switching.
- [x] Added targeted tests for correction reason, provenance labels and evidence confidence/precision presentation.

Remaining FE-06 scope:
- [ ] Add explicit `Berechnet` provenance to deterministic calculated dates/costs where the backend DTO identifies the value as calculated.
- [ ] Continue review/edit audit clarity and verify all previous-value/reason paths.
- [ ] Explain calculated costs and deadlines from deterministic backend/code inputs, never AI calculation.
- [ ] Evaluate adjustable desktop split workspace without regressing source navigation.
- [ ] Reverify missing-document/PDF recovery, document versions, source geometry and keyboard source navigation after the current batch.

Key files in current batches:
- `frontend/components/contracts/detail/FactReviewPanel.tsx`
- `frontend/components/contracts/detail/ValueOriginBadge.tsx`
- `frontend/components/contracts/detail/EvidencePane.tsx`
- `frontend/components/contracts/detail/PdfViewer.tsx`
- `frontend/components/OrganizationScopePicker.tsx`
- `frontend/app/contract-workspace-enhancements.css`
- `frontend/test/fact-confirm-reviewer.test.tsx`
- `frontend/test/value-origin-badge.test.tsx`
- `frontend/test/evidence-pane-presentation.test.tsx`

## FE-07 — Action-oriented dashboards
Status: PLANNED
Depends on: FE-06

Planned scope:
- Urgent actions and cancellation deadlines first.
- Scope/period-aware KPIs.
- KPI links to filtered lists.
- Explicit missing-data coverage and unknown cost.
- Currencies stay separate without an approved conversion basis.
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
- Useful filters and direct contract/reason links.
- Distinguish contract end from cancellation deadline.
- Assignment/completion only with verified backend support/permissions.
- Standardize organization/user forms and preserve historical records on deactivation.
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
