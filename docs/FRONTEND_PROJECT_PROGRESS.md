# Medflux Frontend Project Progress

Created: 2026-09-13
Last updated: 2026-09-13
Status: IN PROGRESS
Progress: 7/10 development steps complete (70%)
Active step: FE-08 — Import and analysis experience
Next action: Verify the first FE-08 batch, then finish duplicate/partial-result handling and completion/review navigation using only supported backend states.

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
| FE-07 | Action-oriented dashboards | P1 | COMPLETE |
| FE-08 | Import and analysis experience | P1 | IN PROGRESS |
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
Status: COMPLETE
Depends on: FE-06

Implemented / verified:
- Urgent `Handlungsbedarf` and deadline panels are placed before lower-priority KPI/financial summaries.
- Supported KPI cards link to real contract filters: active contracts, approaching contract end and critical cancellation deadlines.
- Cancellation deadlines are summarized separately from contract ends and critical cancellation opens the corresponding filtered list.
- Action rows expose `Aktion erforderlich` / `Prüfung erforderlich` textually; unsupported per-contract chevrons/links are absent because the DTO has no contract ID.
- Financial coverage explicitly reports unreliable/missing annual cost and total-value counts; unknown values are never rendered as 0 €.
- Multi-currency behavior remains separate with no invented conversion.
- Data-quality and cost-coverage panels use supported review filters only.
- Data date and freshness remain visible near the top of the dashboard.
- Empty/partial dashboard states remain meaningful and existing automated accessibility coverage still runs against the dashboard.

Verification result:
- User-reported local frontend tests and production build green after the final FE-07 batch.

## FE-08 — Import and analysis experience
Status: IN PROGRESS
Depends on: FE-07

Verified backend behavior:
- `/api/documents/import` accepts a batch of PDF/DOCX uploads and processes each document through the persisted production orchestrator.
- The endpoint is synchronous from the browser perspective and returns per-file results only after processing; it does not expose live per-stage percentage/status events.
- Per-file results include import status, optional analysis status, review requirement, stored document-version ID and optional contract ID.
- `/api/documents/{document_version_id}/retry` supports retry from a stored document version after failed/incomplete analysis.
- No frontend-verifiable fixed maximum file-size limit is exposed by the current import API, so the UI must not invent one.

Implemented in first FE-08 batch:
- [x] Existing drag/drop area remains keyboard accessible and the native picker restricts to PDF/DOCX.
- [x] Unsupported extensions are rejected before upload with an explicit user-visible message.
- [x] Active organization/working-scope target is shown before import; the selected hospital/department scope continues to be assigned through the verified ownership flow after successful import.
- [x] Removed hardcoded import/retry organization usage in favor of the authenticated active organization scope.
- [x] Import success is presented separately from analysis success/failure for every file.
- [x] `analysis_failed` no longer visually implies that document persistence itself failed.
- [x] Indeterminate processing copy explicitly states that the API has no live stages/percentages; no fake percentage is shown.
- [x] Retry is offered only for failed analysis with a stored document-version ID.
- [x] Result summary separates imported documents, successful analyses, failed analyses and duplicates.
- [x] Direct contract links are shown only when the backend returns a real contract ID.
- [x] Added focused tests for supported-file validation, separated import/analysis states, retry and honest indeterminate processing.

Remaining FE-08 scope:
- [ ] Verify the current import batch with the full frontend suite and production build.
- [ ] Recheck duplicate and partial-analysis presentation with representative backend fixtures.
- [ ] Confirm completion/review navigation for files requiring manual review.
- [ ] Document that durable background job tracking is not available because the current endpoint is synchronous and exposes no job ID/status endpoint.

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
