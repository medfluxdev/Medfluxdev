# Medflux Frontend Release Verification

Date: 2026-09-13
Scope: FE-10 release gate

## Automated gate

Run from `frontend/`:

```bash
npm run test
npm run build
```

Release is blocked by any failing test, TypeScript error, lint error, prerender error or unresolved production-build warning introduced by the application code.

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
- Forms have programmatic labels; errors use `role=alert`; background/status updates use `role=status` where appropriate.
- Information is never conveyed by color alone: severity, review, deadline and provenance states include text.
- Dialog-like/browser confirmation paths preserve user edits or explicitly ask before discarding.
- Reduced-motion preference disables nonessential transitions/animations.
- Automated axe coverage remains green on dashboard, import, work queue and other existing covered pages.

## Performance gate

Current product constraints:

- No external fonts, analytics or external AI calls.
- PDF rendering is a heavy feature and should only execute when the source workspace is active.
- Do not add client-side libraries for functionality already available from platform/React/Next.js.

Budget targets for production build review:

- Shared first-load JavaScript should remain below 150 kB unless a documented framework change requires adjustment.
- A route-specific increase over 25 kB must be justified by user-visible functionality.
- No avoidable image lint warnings; profile images use `next/image` while remaining local/data-URL based.
- No fake progress timers or polling loops where the backend exposes no durable job/state endpoint.

## Data-integrity gate

- Missing costs/deadlines remain unknown, never zero.
- Currencies remain separate without an approved conversion source.
- `Berechnet` is shown only for deterministic values with backend calculation basis.
- Confidence is shown only when supplied as a valid backend value.
- Import success and analysis success are distinct states.
- Unsupported backend features (bulk export/actions, task assignment, notifications, durable import jobs) remain absent instead of simulated.

## Release decision

Mark FE-10 COMPLETE only after:

- full frontend tests pass,
- production build passes without release-blocking warnings,
- representative 1440/1280/768/390/320 reflow checks pass,
- keyboard/focus checks pass for the core journeys,
- no new external runtime dependency is present,
- all P0 defects found during the gate are fixed or explicitly documented as blockers.
