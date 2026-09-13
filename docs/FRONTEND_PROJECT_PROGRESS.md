# Medflux Frontend Project Progress

Created: 2026-09-13
Last updated: 2026-09-13
Status: PLANNED — implementation has not started
Progress: 0/10 development steps complete (0%)
Next action: Start FE-01, audit the running application and record the baseline.

## Purpose

Develop Medflux into a consistent, accessible, reliable application for hospital contract management. Optimize the daily journey: identify required action, find a contract, verify its source, and complete the review.

This is the dedicated frontend execution tracker. It complements `docs/PROJECT_PROGRESS.md`; its ten steps do not replace or change the original 18-step MVP progress calculation. Creating this plan does not count as implementing a development step.

## Working rules

1. Implement the steps in the order below. Maintain one active step at a time.
2. Before each step, inspect the current implementation and applicable project instructions. Reuse working features instead of rebuilding them.
3. Record the concrete scope and backend dependencies before editing. Implement supported behavior; never simulate missing server capabilities as completed features.
4. Verify each step against its acceptance criteria using relevant automated checks and manual browser checks. Use synthetic or approved local data.
5. Before starting the next step, update this file and `docs/PROJECT_PROGRESS.md` with status, date, implementation, files, tests/results, known issues, next action, and progress. Preserve the separate MVP count.
6. Mark a step COMPLETE only when its required tasks and acceptance criteria are verified. Record deferred work explicitly; do not count it as complete.
7. Keep processing, assets, fonts, and runtime dependencies local. Do not introduce external AI APIs, remote fonts, or external telemetry.
8. Keep product copy in German. This engineering plan is in English.
9. Backend authorization remains authoritative. Hidden buttons are not an access-control mechanism.
10. Facts come from extraction and sources. Code calculates costs and deadlines. Missing data must never become invented values or zero by default.

Allowed statuses: PLANNED, IN PROGRESS, BLOCKED, COMPLETE. A blocked step must name the dependency and the exact action needed to resolve it.

## Existing foundation and audit limits

The initial review inspected source files, not every rendered screen. Revalidate findings against the current application in FE-01.

- Shared UI components already include buttons, alerts, loading states, empty states, status badges, and toasts.
- Design tokens exist in `frontend/app/globals.css`.
- Several global stylesheets are imported by `frontend/app/layout.tsx`; audit their overlap before consolidating.
- Contract filtering, sorting, pagination, and URL query state already exist.
- Contract details already include a PDF/source workspace and review components.
- API helpers already support request timeouts and cancellation for applicable requests.
- Organization, hospital, department, and role context already exist.
- Account actions appear in both sidebar and topbar.
- The sidebar label for local AI health currently relies on the general `/health` response. Verify the endpoint semantics and use service-specific evidence for AI status.

## Execution overview

| Step | Deliverable | Priority | Status |
| --- | --- | --- | --- |
| FE-01 | Current-state audit and acceptance baseline | P0 | PLANNED |
| FE-02 | Design system and shared components | P0 | PLANNED |
| FE-03 | Application shell and organization navigation | P0 | PLANNED |
| FE-04 | Loading, errors, authentication, and service states | P0 | PLANNED |
| FE-05 | Contract table and search workflow | P0 | PLANNED |
| FE-06 | Contract detail and source review workspace | P0 | PLANNED |
| FE-07 | Action-oriented dashboards | P1 | PLANNED |
| FE-08 | Import and analysis experience | P1 | PLANNED |
| FE-09 | Tasks, deadlines, and administration | P1 | PLANNED |
| FE-10 | Accessibility, performance, and release verification | P0 release gate | PLANNED |

Initial planning estimate: approximately 6–10 working weeks for one full-time developer, subject to FE-01 findings and backend work. Accessibility and testing apply throughout; FE-10 is the final cross-application check.

## FE-01 — Audit and acceptance baseline

Status: PLANNED
Depends on: None

- [ ] Inventory routes, shared components, stylesheets, API calls, and existing tests.
- [ ] Inspect login, dashboard, contracts, contract details, import, reviews, tasks, settings, and developer screens in the running application.
- [ ] Document representative journeys for contract managers, reviewers, organization admins, and developers; verify actual role definitions before designing visibility rules.
- [ ] Record layout problems, duplicate controls, misleading states, and navigation gaps with reproducible observations.
- [ ] Record representative desktop, laptop, tablet, and mobile layouts.
- [ ] Establish current build, lint, test, and production performance baselines. Distinguish existing failures from new regressions.
- [ ] Map every planned server-dependent feature to an existing endpoint or a required backend change.
- [ ] Define reference layouts for the shell, contract list, and contract workspace before implementing them.

Acceptance: A prioritized audit, route inventory, journey checklist, and dependency list are documented; findings distinguish observed defects from proposed enhancements.

Verification: Read-only browser walkthrough and relevant existing checks. Record commands, results, and environment.

Expected files: frontend route/component inventory; supporting notes under `docs/`; this tracker.

## FE-02 — Design system and shared components

Status: PLANNED
Depends on: FE-01

- [ ] Consolidate semantic tokens for typography, spacing, surfaces, borders, focus, status colors, and elevation.
- [ ] Adopt one locally available or locally bundled font stack and consistent icon treatment.
- [ ] Audit global stylesheet precedence; migrate feature-specific styles incrementally to scoped styles.
- [ ] Standardize existing Button, Field, PageHeader, SectionCard, StatusBadge, InlineAlert, Toast, LoadingState, and EmptyState components.
- [ ] Add reusable dialog, drawer, tabs, and menu primitives only where required by planned screens.
- [ ] Define default, hover, focus, disabled, loading, error, and success states.
- [ ] Define comfortable and compact table density.
- [ ] Create a local component reference for visual verification.

Acceptance: Representative pages share consistent controls and tokens; changed styles do not cause unrelated page regressions. Status is conveyed by text as well as color.

Verification: Inspect component states, keyboard interaction, and representative screenshots; run relevant lint/type/build checks.

Expected files: `frontend/components/ui/`, `frontend/app/globals.css`, feature styles, `frontend/app/layout.tsx`.

## FE-03 — Application shell and organization navigation

Status: PLANNED
Depends on: FE-02

- [ ] Split ClientNav into maintainable shell, sidebar, topbar, and account components.
- [ ] Group navigation around daily work, monitoring, records, organization administration, and developer administration.
- [ ] Preserve role-aware access and provide clear active states and breadcrumbs.
- [ ] Add a collapsible sidebar and persist its non-sensitive display preference.
- [ ] Consolidate account actions into a consistent menu.
- [ ] Clearly display the active organization, hospital, and department.
- [ ] On scope changes, cancel stale requests and prevent previous-scope data from reappearing.
- [ ] Ensure any data cache keys include relevant account and organization scope; clear appropriate state on logout.
- [ ] Provide responsive navigation and accessible search labeling.

Acceptance: Users can identify their active scope on every operational screen. Switching organizations never renders results from a previous scope after the switch completes.

Verification: Role/scope navigation tests, rapid scope-switch checks with delayed responses, logout/login checks, and keyboard/mobile navigation.

Expected files: `frontend/components/ClientNav.tsx`, `frontend/components/OrganizationScopePicker.tsx`, auth provider, API helpers, shell styles.

## FE-04 — Loading, errors, authentication, and service states

Status: PLANNED
Depends on: FE-03

- [ ] Standardize loading placeholders and reduce layout shifts.
- [ ] Distinguish empty datasets from filtered searches with no results.
- [ ] Map API failures to useful German messages and appropriate retry actions.
- [ ] Preserve form inputs and filters after recoverable errors.
- [ ] Handle expired sessions, forbidden actions, and missing resources consistently.
- [ ] Verify login labels, password visibility, paste, autofill, and password-manager compatibility.
- [ ] Prevent duplicate submissions while a request is pending.
- [ ] Separate API availability from Ollama/model availability using verified endpoint data.
- [ ] Clearly represent unknown or stale service status and refresh it appropriately.

Acceptance: Each major journey has a usable loading, empty, success, and failure state. A healthy API does not falsely imply that AI analysis is available.

Verification: Simulate network failure, timeout, 401, 403, empty responses, and service unavailability; verify recovery without losing user input.

Backend dependency: Service-specific health data if not already exposed.

Expected files: shared UI, `frontend/lib/api.ts`, authentication components, login page, service status components.

## FE-05 — Contract table and search workflow

Status: PLANNED
Depends on: FE-04

- [ ] Preserve existing filters, sorting, pagination, and URL state.
- [ ] Improve column priority, table alignment, sticky headers, and density controls.
- [ ] Add column visibility preferences scoped appropriately to the user.
- [ ] Show removable active-filter chips and an explicit reset action.
- [ ] Add saved views; document whether persistence is local or server-backed.
- [ ] Add a quick-preview panel without losing the list context.
- [ ] Restore list filters, page, and scroll position when returning from a contract.
- [ ] Add supported bulk actions with explicit selection scope, permissions, confirmation where needed, and per-item results.
- [ ] Add filtered export if supported; clearly distinguish current-page export from all matching results.

Acceptance: Users can find, compare, preview, and reopen contracts without rebuilding their search. Sorting and totals reflect the complete filtered dataset, not only the loaded page.

Verification: Filter URL round-trips, back navigation, empty results, pagination boundaries, bulk partial failures, and export scope checks.

Backend dependencies: Verify saved-view persistence, bulk operations, and filtered export before implementation. Record unresolved dependencies rather than showing nonfunctional controls.

Expected files: `frontend/app/contracts/page.tsx`, `frontend/components/contracts/ContractTable.tsx`, contract types/API helpers, shared table components.

## FE-06 — Contract detail and source review workspace

Status: PLANNED
Depends on: FE-05

- [ ] Establish a clear summary header with supplier, status, ownership, and key dates.
- [ ] Organize overview, costs/deadlines, equipment, documents, and history into coherent sections or tabs.
- [ ] Improve the existing split workspace with adjustable panels and a small-screen alternative.
- [ ] Open the correct document version, page, and highlight from each supported source link.
- [ ] Distinguish extracted, manually reviewed, missing, and calculated values.
- [ ] Present confidence only when supplied and meaningful; never fabricate a score.
- [ ] Support verified edit/review actions with reason, previous value, and audit information where available.
- [ ] Explain the basis of calculated costs and deadlines without calculating them through AI.
- [ ] Protect unsaved edits during navigation and scope changes.
- [ ] Handle missing documents and failed PDF rendering with useful recovery options.

Acceptance: Users can verify and correct a fact while staying in the workspace. Missing values remain explicit, and every available source link resolves to the intended evidence.

Verification: Representative multi-page documents, document versions, missing evidence, edit failures, unsaved changes, and keyboard source navigation.

Backend dependencies: Verify review/audit payloads, calculation explanations, and source geometry availability.

Expected files: `frontend/components/contracts/detail/`, contract-detail route/types, workspace styles.

## FE-07 — Action-oriented dashboards

Status: PLANNED
Depends on: FE-06

- [ ] Prioritize urgent actions and cancellation deadlines above secondary analytics.
- [ ] Display active contracts, known annual cost, pending reviews, and upcoming deadlines with explicit scope and period.
- [ ] Make summary indicators open the corresponding filtered list.
- [ ] Show missing-data coverage and avoid treating unknown costs as zero.
- [ ] Keep currencies separate unless the backend supplies an approved conversion basis.
- [ ] Display cost distribution and recent activity only where data supports them.
- [ ] Align operational, organization-admin, and developer dashboards with their actual responsibilities.
- [ ] Provide meaningful empty and partially unavailable dashboard states.

Acceptance: A representative user can identify the next important action in approximately ten seconds during a task walkthrough. All displayed totals and links agree with their underlying scope.

Verification: Check dashboard/list consistency, incomplete cost data, multiple currencies, role visibility, and chart text alternatives.

Expected files: `frontend/app/page.tsx`, `frontend/components/dashboard/`, admin/developer dashboards and their styles.

## FE-08 — Import and analysis experience

Status: PLANNED
Depends on: FE-07

- [ ] Improve drag-and-drop and the keyboard-accessible file picker.
- [ ] Explain actual supported file types and limits before upload.
- [ ] Display and confirm target organization/hospital/department before importing.
- [ ] Show per-file upload/import/analysis outcomes and distinguish duplicates.
- [ ] Separate imported documents from successfully analyzed documents.
- [ ] Display real processing stages when the server reports them; otherwise use honest indeterminate progress.
- [ ] Retry eligible failed files without needlessly repeating successful operations.
- [ ] Preserve/recover job tracking across navigation if durable backend jobs exist.
- [ ] Show a completion summary with direct links to results and required reviews.

Acceptance: Every selected file has a clear outcome and next action. A failed analysis is never presented as a failed upload or as a completed review.

Verification: Multiple files, duplicates, invalid formats, partial failures, analysis failure, network interruption, and navigation during processing.

Backend dependencies: Durable job IDs/status, safe retry semantics, per-stage progress, and ownership assignment behavior must be verified.

Expected files: `frontend/app/import/page.tsx`, upload API helpers, import types, shared progress/result components.

## FE-09 — Tasks, deadlines, and administration

Status: PLANNED
Depends on: FE-08

- [ ] Define the relationship between tasks, warnings, and reviews to avoid duplicate work items.
- [ ] Provide useful filters for due date, responsibility, status, and hospital.
- [ ] Link each task to its contract and reason for creation.
- [ ] Distinguish contract end dates from cancellation deadlines in list/timeline views.
- [ ] Implement supported assignment/completion actions with appropriate permissions.
- [ ] Add in-app notifications with actionable links if persistence/read-state APIs are available.
- [ ] Standardize organization structure and user management forms, validation, and feedback.
- [ ] Preserve historical records when entities are deactivated and reflect that state in the UI.
- [ ] Keep developer/system administration separate from scoped operational actions.

Acceptance: Users can understand why a task exists, act on it, and see the persisted outcome. Administrative changes clearly identify their target scope.

Verification: Role matrix, task transitions, deadline labels, deactivated entities, invalid form submissions, and organization switching.

Backend dependencies: Assignment, task transitions, notification persistence/read state, and administrative permissions as applicable.

Expected files: work-queue/review routes, organization settings, user settings, developer routes, relevant types and shared forms.

## FE-10 — Accessibility, performance, and release verification

Status: PLANNED
Depends on: FE-09; verification also occurs during every earlier step

- [ ] Verify core journeys with keyboard-only interaction, visible focus, accessible names, and appropriate focus restoration.
- [ ] Check contrast, zoom, status text, dialog behavior, and representative screen-reader output against the WCAG 2.2 AA target.
- [ ] Check representative widths such as 1440, 1280, 768, and 390 pixels; verify 320-pixel reflow where applicable. Keep necessary table scrolling inside the table region.
- [ ] Load PDF and other heavy features on demand where beneficial.
- [ ] Measure production performance with documented hardware, browser, dataset size, and cold/warm conditions; compare with FE-01 and set concrete release budgets from that baseline.
- [ ] Verify login, scope switching, import, filtering, source navigation, and review end to end.
- [ ] Capture representative visual regression references.
- [ ] Run frontend build, lint, and relevant tests; run backend tests for any changed API behavior.
- [ ] Verify operation without externally hosted fonts, assets, analytics, or AI services.
- [ ] Resolve release-blocking defects and record remaining limitations with follow-up actions.

Acceptance: Core journeys pass, no unresolved cross-organization data exposure or critical functional regression remains, and performance/accessibility evidence is recorded. Do not claim full accessibility conformance from automated checks alone.

Verification commands, from `frontend/`: `npm run build`, `npm run lint`, and `npm run test`. Add browser journey checks using tooling selected during FE-01. Run relevant `pytest` checks from `backend/` when backend behavior changes.

Reference: https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/

## Step completion record template

Append one record for each completed step and update the overview above.

```text
Step: FE-XX — Title
Status: COMPLETE / IN PROGRESS / BLOCKED
Date: YYYY-MM-DD
Implemented:
- Concrete behavior delivered.
Files:
- Actual changed paths.
Tests and results:
- Command or manual scenario; result and relevant evidence.
Known issues / dependencies:
- Remaining issue, impact, and required follow-up; or None.
Next action:
- Exact next task.
Frontend progress: X/10 (Y%)
Original MVP progress: Unchanged by this frontend tracking count.
```

## Activity log

### 2026-09-13 — Plan created

- Recorded ten ordered development steps based on the initial source review.
- Defined acceptance criteria, verification, expected file areas, and backend dependencies.
- No frontend implementation or runtime changes were made as part of creating this plan.
- Documentation verification: checked step IDs, initial status, and completion criteria.
- Known limitation: full visual audit and baseline tests remain FE-01 work.
- Next action: Execute FE-01.
- Frontend progress: 0/10 (0%).

## Deferred enhancements

Reconsider after the core workflow is stable: dark mode, extensive dashboard customization, advanced command palette, cross-entity global search, and additional report layouts. These are not required to complete the ten steps above.
