# Medflux Frontend Project Progress

Created: 2026-09-13
Last updated: 2026-09-13
Status: IN PROGRESS
Progress: 6/10 development steps complete (60%)
Active step: FE-07 — Action-oriented dashboards
Next action: Prioritize urgent actions/cancellation deadlines, make KPI cards actionable, and improve missing-data/scope clarity without inventing unsupported backend data.

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
| FE-06 | Contract detail and source review workspace | P0 | COMPLETE |
| FE-07 | Action-oriented dashboards | P1 | IN PROGRESS |
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
- Existing filters, sorting, pagination and URL state preserved.
- Compact/comfortable density preference persisted locally.
- Column visibility preference persisted locally; hiding all columns is prevented.
- Sticky headers and keyboard-focusable horizontal scrolling.
- Active URL filters shown as individually removable chips with clear-all action.
- Saved views implemented with explicit local-only persistence.
- Quick preview uses already-loaded list data without leaving list context.
- List URL and scroll position are remembered before opening a contract and restored on return.
- Existing filter URL round-trip and pagination tests remained green after integration.
- New list-preference tests cover filter chips, density, columns, quick preview and saved views.

Backend dependency result:
- No verified server API exists for saved-view persistence, bulk contract actions, or filtered export. Unsupported bulk/export controls remain absent instead of being simulated.

Verification result:
- User-reported local frontend test suite: 124/124 passing after final FE-05 test adjustment.
- Production build remained green in the FE-05 verification run.

## FE-06 — Contract detail and source review workspace
Status: COMPLETE
Depends on: FE-05

Implemented / verified:
- Clear summary plus overview/term/finance/services/equipment/documents structure retained.
- Correct document version/page/highlight navigation retained with explicit exact/approximate/page-only source precision.
- Review values distinguish extracted, reviewed, corrected, missing and system-backed provenance without guessing unsupported origin.
- Deterministic calculated end/cancellation/renewal/cost values receive `Berechnet` only when the backend supplies a calculation basis.
- Calculation explanations expose backend inputs and explicitly state that calculations are deterministic rather than AI-generated.
- Correction workflow requires a reason through the verified backend `note` field; previous/effective values and reason remain visible in history.
- Unsaved correction drafts protect browser and organization/hospital/department context changes.
- PDF loading distinguishes forbidden, missing document/version, timeout and server errors with retry; stale source/PDF work is cancellable and cleaned up.
- Evidence confidence is shown only for valid backend values.
- Evidence/PDF review workspace is adjustable on desktop and stacks/resizes vertically on smaller screens.
- Missing-document, source-geometry, evidence presentation, correction, reload/scroll and calculation-basis paths have targeted automated coverage.

Verification result:
- User-reported local frontend tests and production build green after the final FE-06 calculation/split-workspace batch.

## FE-07 — Action-oriented dashboards
Status: IN PROGRESS
Depends on: FE-06

Verified backend foundation:
- Dashboard DTO provides active/current accepted projection state, accepted deterministic calculations and active warnings only.
- `DeadlineBucket` explicitly separates cancellation deadlines from contract-end counts.
- Financial totals are grouped per currency and expose counts of contracts without reliable values.
- Action items expose warning type, severity, review/action flags and optional reliable annual cost.
- Current DTO does not expose a contract ID on action items, so direct per-contract links must not be invented.

Implementation scope:
- [ ] Put urgent actions and cancellation deadlines before lower-priority summaries.
- [ ] Make supported KPI indicators link to corresponding filtered contract views.
- [ ] Keep KPI/financial scope and period/freshness visible.
- [ ] Make missing-data coverage explicit; unknown/unreliable cost must never appear as zero.
- [ ] Keep currencies separate without an approved conversion basis.
- [ ] Improve deadline presentation while preserving cancellation vs contract-end distinction.
- [ ] Use meaningful partial/empty states.
- [ ] Do not add unsupported per-contract links or role-specific data that the DTO cannot identify reliably.

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
