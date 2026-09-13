# Medflux Frontend Project Progress

Created: 2026-09-13
Last updated: 2026-09-13
Status: IN PROGRESS
Progress: 9/10 development steps complete (90%)
Active step: FE-10 — Accessibility, performance, and release verification
Next action: Record representative real-browser reflow/focus checks at 1440/1280/768/390/320. Automated lint/test/build gate is clean.

## Purpose
Develop Medflux into a consistent, accessible, reliable application for hospital contract management. Optimize the daily journey: identify required action, find a contract, verify its source, and complete the review.

This tracker complements `docs/PROJECT_PROGRESS.md`; the ten frontend steps do not replace the original MVP progress calculation.

## Governing visual reference

All new or modified frontend work must follow `docs/VISUAL_IDENTITY.md`. It is the authoritative reference for MedFlux naming, logo usage, color, typography, spacing, component language, accessibility, and visual pull-request review. Existing implementation files remain the technical source for reusable tokens and components, but must converge toward that reference when they conflict.

## Working rules
1. Implement steps in order with one active step at a time.
2. Inspect and reuse the current implementation before editing.
3. Do not simulate missing backend capabilities as completed features.
4. Verify each step with relevant automated checks and browser/manual checks.
5. Keep processing, assets, fonts, telemetry, and AI runtime local.
6. Keep product copy in German.
7. Backend authorization remains authoritative.
8. Facts come from extraction and sources; code calculates costs/deadlines; missing data is never invented or converted to zero.
9. Review every visual change against `docs/VISUAL_IDENTITY.md`.

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
| FE-08 | Import and analysis experience | P1 | COMPLETE |
| FE-09 | Tasks, deadlines, and administration | P1 | COMPLETE |
| FE-10 | Accessibility, performance, and release verification | P0 release gate | IN PROGRESS |

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

## FE-07 — Action-oriented dashboards
Status: COMPLETE
Depends on: FE-06

Implemented / verified:
- Urgent `Handlungsbedarf` and deadline panels precede lower-priority summaries.
- Supported KPI cards link to real contract filters.
- Cancellation deadlines are separated from contract ends.
- Unsupported per-contract action links remain absent where the DTO has no contract ID.
- Missing/unreliable costs are explicit and never displayed as zero.
- Currencies remain separate with no invented conversion.
- Data date and warning freshness remain visible.
- User-reported local frontend tests and production build were green after FE-07.

## FE-08 — Import and analysis experience
Status: COMPLETE
Depends on: FE-07

Implemented / verified:
- Keyboard-accessible drag/drop and native picker accept PDF/DOCX; unsupported extensions are rejected before upload.
- Active organization/working scope is shown before import and existing verified ownership assignment is retained.
- Import and analysis results are separate per file; `analysis_failed` does not imply persistence failure.
- Partial analysis is explicit and can link directly to manual review when a real contract ID is returned.
- Duplicate files are shown as not re-analyzed and do not receive an invalid retry action.
- Retry is limited to failed analysis with a stored document-version ID.
- Processing is honestly indeterminate because the synchronous backend exposes no live stages/percent or durable job endpoint.
- Result summary distinguishes imported, analyzed, failed and duplicate files.
- Focused tests cover validation, partial analysis, duplicate handling, retry and manual-review navigation.

Backend limitation documented:
- Durable background job tracking is not available from the current synchronous import API; the UI does not simulate it.

## FE-09 — Tasks, deadlines, and administration
Status: COMPLETE
Depends on: FE-08

Implemented:
- Work queue uses verified backend filters for status, severity and item type.
- Each task exposes its backend reason (`why_de`) and next-step hint (`action_hint_de`) when present.
- Contract links use real contract IDs; review tasks can open the contract review workspace directly.
- `Kündigungsfrist`, `Vertragsende` and `Verlängerung` are distinguished textually instead of relying on color.
- A filtered-empty state is distinct from an actually empty active queue.
- Existing acknowledge/resolve actions remain limited to the backend-supported status transitions.
- No assignment or notification controls were added because no verified backend API exists for them.
- User/organization administration continues to deactivate/reactivate records instead of deleting history.
- Developer/system administration remains separate from organization-scoped operational administration.
- Added focused work-queue tests for filters, direct review navigation, deadline-type clarity and next-step context.

Verification note:
- Final whole-application automated/build verification is consolidated into the FE-10 release gate.

## FE-10 — Accessibility, performance, and release verification
Status: IN PROGRESS
Depends on: FE-09

Implemented in release-gate batches:
- Removed the known profile `<img>` production-build warning by using local/data-URL-compatible `next/image`.
- Added generic visible focus safeguards and reduced-motion behavior.
- Added reflow safeguards for dense tables/tabs and 390/320-pixel layouts; horizontal overflow is contained inside dense regions instead of the page.
- PDF.js remains lazy through dynamic import and only initializes while the source workspace is active.
- Account menu supports Escape dismissal and restores focus to the menu trigger.
- Removed the persistent topbar's duplicate semantic `h1`; main page content now owns the top-level heading.
- Added shell tests for account-menu keyboard dismissal/focus restoration and accessible global search submission.
- Added a single `npm run verify` command that runs lint, tests and production build sequentially.
- Fixed the final production Autoprefixer warning in `work-queue.css` by using `flex-end`.
- Updated `docs/FRONTEND_RELEASE_VERIFICATION.md` with automated, journey, reflow, accessibility, performance and data-integrity gates.

Automated verification on 2026-09-13:
- [x] `next lint`: no ESLint warnings or errors.
- [x] Vitest: 28/28 test files, 145/145 tests passed.
- [x] Production build: compiled successfully.
- [x] Static generation: 22/22 pages.
- [x] No application production-build warning remains.
- [x] Reported route first-load JS remains below the 150 kB budget (`/contracts` 105 kB; `/contracts/[contract-id]` 109 kB).

Remaining release gate:
- [ ] Record representative real-browser reflow checks at 1440 / 1280 / 768 / 390 / 320.
- [ ] Recheck keyboard/focus visually on login, dashboard, contracts, source review, import, work queue and admin journeys.

Non-blocking cleanup:
- React `act(...)` diagnostics remain in parts of the legacy test harness. They do not fail lint, tests, type checking or production build.

## Current verification command
From `frontend/`:

```bash
npm run verify
```

Run backend `pytest` only when backend behavior changes.
