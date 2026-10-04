# Medflux Frontend Release Verification

Date: 2026-09-13
Scope: FE-10 release gate

## Automated gate

Run from `frontend/`:

```bash
npm run verify
```

`verify` runs lint, the full Vitest suite, and the production build in sequence. Release is blocked by any failing test, TypeScript error, lint error, prerender error or unresolved production-build warning introduced by application code.

Verified on 2026-09-13 against branch `Ahmad` after commit `dc9e8386376a22c2073557bea4924830fe874362`:

- `next lint`: PASS — no ESLint warnings or errors.
- Vitest: PASS — 28/28 test files, 145/145 tests.
- Next.js production build: PASS — compiled successfully.
- Static generation: PASS — 22/22 pages.
- Production build warning gate: PASS — no application build warning remains after replacing `align-items: end` with `flex-end` in the work-queue filter bar.
- First-load JS remains below the 150 kB release budget for the reported routes; `/contracts` is 105 kB and `/contracts/[contract-id]` is 109 kB in the verified build.

The Vitest run still emits non-failing React `act(...)` test-harness diagnostics in several legacy tests. They do not fail lint, tests, type checking or the production build and are tracked as test-harness cleanup rather than a release-blocking application defect.

Backend `pytest` is required whenever backend behavior or API contracts change. FE-09/FE-10 changes in the current batch are frontend-only.

## Core journeys

Verify with keyboard and pointer input:

1. Login -> dashboard -> filtered contract list.
2. Contract list -> quick preview -> contract detail -> back to preserved list context.
3. Contract detail -> source/evidence -> PDF page/highlight -> review -> correction with reason -> history.
4. Import -> file selection -> processing -> per-file result -> retry failed analysis -> manual review link.
5. To-dos -> status/severity/type filter -> contract -> manual review -> acknowledge/resolve supported task.
6. Settings -> organization/users as admin; verify viewer/reviewer cannot reach admin-only actions.
7. Scope switch -> organization/hospital/department -> stale requests canceled and unsaved review draft can block the switch.
8. Account menu -> open with keyboard -> Escape closes the menu and restores focus to the trigger.

Automated coverage exists for the critical interaction logic above; the remaining release step is a representative real-browser spot check for focus order, visual clipping and reflow.

## Responsive/reflow matrix

Check the core journeys at these viewport widths without page-level horizontal scrolling:

- 1440 px: full desktop shell and split review workspace.
- 1280 px: desktop shell, contract tables and dashboard cards.
- 768 px: tablet stacking for dashboard and source/PDF workspace.
- 390 px: mobile navigation, forms, import and review controls.
- 320 px: minimum supported reflow; dense tables may scroll inside their own labeled scroll region but the page itself must not overflow horizontally.

## Accessibility gate

Target: WCAG 2.2 AA for the supported frontend journeys.

- All interactive controls reachable by keyboard.
- Visible `:focus-visible` state on links, buttons, form fields, tabs and custom focusable regions.
- Skip link reaches the unique `#main-content` region.
- Main page content owns the semantic `h1`; the persistent top bar route label is visual context only and does not create a duplicate top-level heading.
- Forms have programmatic labels; errors use `role=alert`; background/status updates use `role=status` where appropriate.
- Information is never conveyed by color alone: severity, review, deadline and provenance states include text.
- Menus/dialog-like interactions support predictable dismissal/focus return where custom behavior is required.
- Dialog-like/browser confirmation paths preserve user edits or explicitly ask before discarding.
- Reduced-motion preference disables nonessential transitions/animations.
- Automated axe coverage remains green on dashboard, import, work queue and other existing covered pages.

## Performance gate

Current product constraints:

- No external fonts, analytics or external AI calls.
- PDF rendering is a heavy feature and executes only when the source workspace is active; `pdfjs-dist` is loaded by dynamic import inside the viewer.
- Do not add client-side libraries for functionality already available from platform/React/Next.js.

Budget targets for production build review:

- Shared first-load JavaScript should remain below 150 kB unless a documented framework change requires adjustment.
- A route-specific increase over 25 kB must be justified by user-visible functionality.
- No avoidable image lint warnings; profile images use `next/image` while remaining local/data-URL based.
- No fake progress timers or polling loops where the backend exposes no durable job/state endpoint.

Verified production baseline (2026-09-13):

- `/`: 101 kB first load.
- `/contracts`: 105 kB first load.
- `/contracts/[contract-id]`: 109 kB first load.
- `/import`: 102 kB first load.
- `/profile`: 97.8 kB first load.
- `/settings/users`: 99.8 kB first load.

All reported routes remain below the 150 kB release budget.

## Data-integrity gate

- Missing costs/deadlines remain unknown, never zero.
- Currencies remain separate without an approved conversion source.
- `Berechnet` is shown only for deterministic values with backend calculation basis.
- Confidence is shown only when supplied as a valid backend value.
- Import success and analysis success are distinct states.
- Unsupported backend features (bulk export/actions, task assignment, notifications, durable import jobs) remain absent instead of simulated.

## Implemented FE-10 safeguards

- Global focus-visible fallback for links, buttons, fields and custom focusable elements.
- Reduced-motion fallback for transitions and animations.
- 390/320 px reflow safeguards and local horizontal scrolling for dense table regions.
- Account menu closes on Escape and returns focus to its trigger.
- Persistent topbar route title no longer creates a duplicate `h1`.
- Profile image uses `next/image` and remains unoptimized/local for data URLs.
- PDF.js remains route/feature-lazy through dynamic import.
- `npm run verify` provides one reproducible release command.
- Work-queue flex alignment uses `flex-end`, eliminating the final Autoprefixer production-build warning.

## Release decision

Automated release gate: PASS.

FE-10 can be marked COMPLETE after the representative real-browser reflow/focus spot checks at 1440/1280/768/390/320 have been recorded. No automated or production-build blocker remains on the current verified head.
