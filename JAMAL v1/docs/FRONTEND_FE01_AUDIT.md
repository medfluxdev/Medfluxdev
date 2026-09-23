# FE-01 — Frontend current-state audit

Date: 2026-09-13
Branch: `Ahmad`
Status: IN PROGRESS — source audit complete; runtime/browser and command baselines still require execution on the local Medflux workstation.

## Route inventory

Operational routes found in `frontend/app/`:

- `/` — dashboard
- `/contracts` — contract search/list
- `/contracts/[contract-id]` — contract detail/workspace
- `/work-queue` — To-dos/work queue
- `/import` — document import
- `/review` — reviews
- `/nachweise` — evidence
- `/audit` — audit log
- `/archiv` — archive
- `/equipment` and `/equipment/[equipment-id]` — equipment
- `/profile` — current-user profile
- `/settings`, `/settings/organization`, `/settings/users` — scoped administration
- `/admin` — organization admin dashboard
- `/developer`, `/system/organizations` — developer/system administration
- `/login`, `/select-organization` — authentication/scope entry

## Shared component inventory

Shell and scope:
- `frontend/components/ClientNav.tsx`
- `frontend/components/OrganizationScopePicker.tsx`
- `frontend/components/SettingsNavigation.tsx`
- `frontend/components/auth/AuthProvider.tsx`

Shared UI:
- Button, DefinitionList, EmptyState, Field, InlineAlert, LoadingState, PageHeader, SectionCard, StatusBadge, Toast.

Contract workflow:
- `ContractTable`
- `ContractDetail`
- `ContractWorkspace`
- `ContractOwnershipPanel`
- `EvidencePane`
- `FactReviewPanel`
- `OverridePanel`
- `PageControls`
- `PdfViewer`
- `SourceLink`

Dashboard:
- ActionList, DataQuality, DeadlineDistribution, FinancialOverview, KpiCard.

## Styling inventory and observed architecture

`frontend/app/layout.tsx` imports eight global stylesheets after `globals.css`: `reference-theme.css`, `desktop-shell-fix.css`, `dashboard-reference.css`, `contract-workspace.css`, `auth.css`, `profile.css`, `organization.css`, and `ownership.css`. `globals.css` is approximately 75 KB. This creates a high cascade/precedence risk and makes ownership of shell and feature rules difficult to reason about.

Feature CSS modules currently exist for admin and developer screens, while most other feature styling remains global. FE-02 should consolidate semantic tokens first, then migrate feature rules incrementally rather than performing a one-shot stylesheet rewrite.

## Role and journey baseline

Actual frontend organization roles are:
- `admin` — Administrator
- `contract_manager` — Vertragsmanager
- `reviewer` — Prüfer
- `viewer` — Leser

A separate `is_developer` account flag grants system/developer navigation.

Representative journeys to preserve:

1. Vertragsmanager: dashboard → contracts → filter/search → contract → source evidence → review/correction → return to list.
2. Prüfer: To-dos/review → contract workspace → evidence → confirm/correct fact → next review item.
3. Administrator: operational workflow plus organization/settings/users administration.
4. Leser: dashboard/contracts/evidence read-only journey; no editing/import/admin controls.
5. Developer: developer dashboard → system organizations, while keeping system administration separate from organization-scoped operational work.

## Navigation and layout findings

### Observed defects / risks

P0 — `ClientNav.tsx` owns sidebar, topbar, search, role filtering, health status, account controls, route titles, and shell rendering in one component. This is a maintainability and regression risk and is the direct FE-03 split target.

P0 — Local AI status in the sidebar calls generic `/health` and labels a healthy API as `Lokale KI — Gesund`. This does not prove that the local AI provider/model is available and is therefore a misleading state.

P0 — Account actions are duplicated between sidebar and topbar (profile/account context and logout), increasing visual density and creating two competing interaction locations.

P0 — Scope is injected by `frontend/lib/api.ts` from localStorage at request construction time. Scope switching therefore requires explicit stale-request cancellation/state invalidation in consumers; otherwise a slower previous-scope request can repopulate a screen after a switch.

P1 — Route titles are maintained manually in `titleForPath`, separate from navigation metadata. This can drift as routes are added.

P1 — Topbar global search has a placeholder but no explicit visible/accessibility label in `ClientNav.tsx`.

P1 — The shell contains both a skip-link target div in `layout.tsx` and `id="main-content"` on `<main>` in `ClientNav.tsx`, creating duplicate IDs in authenticated screens. FE-02/03 must leave exactly one main-content target.

P1 — Desktop shell fixes live in a separate global override stylesheet, indicating layout behavior depends on stylesheet order rather than a single shell owner.

### Proposed enhancements (not defects until runtime-verified)

- Collapsible sidebar with persisted non-sensitive preference.
- Breadcrumbs for nested contract/settings/system routes.
- One account menu in the topbar or sidebar, not both.
- Explicit active organization/hospital/department summary.
- Responsive small-screen navigation.

## API/dependency map

Existing frontend API helper capabilities:
- credentialed GET/POST/PUT/PATCH
- default 20-second timeout for JSON helpers
- AbortSignal support on GET
- organization/hospital/department query scoping
- multipart document import
- contract document content URL
- source-region URL

Backend route families already present in source:
- auth/profile/users/user scopes
- organization structure/system organizations
- contracts and secure contract actions
- documents
- ownership
- work queue
- dashboard
- equipment
- activity/audit
- AI
- health

Planned features requiring verification before UI completion:
- service-specific AI/provider/model health semantics (FE-04)
- server-backed saved views (FE-05)
- bulk contract operations and filtered export semantics (FE-05)
- review/audit payload completeness and calculation explanation data (FE-06)
- durable import job IDs, stage progress and safe retry semantics (FE-08)
- notification persistence/read-state APIs (FE-09)

No unsupported control should be presented as implemented until its endpoint contract is verified.

## Test inventory

Frontend uses Vitest + Testing Library + jest-axe. Existing tests cover API timeout, archive confirmation, contract list/detail, detail scroll/layout, dashboard, empty states, equipment, evidence geometry, fact review, formatting, import, interaction audit, review navigation, settings/navigation, shell, source geometry, toast, and work queue.

Configured commands from `frontend/package.json`:
- `npm run build`
- `npm run lint`
- `npm run test`

## Reference layouts for implementation

Shell reference:
- fixed application identity + grouped role-aware navigation
- one top-level account control
- explicit active organization/hospital/department
- labeled global contract search
- responsive/collapsible navigation

Contract list reference:
- page header → search/filter controls → active-filter summary → results metadata → table → pagination
- list state encoded in URL where already supported
- table scrolling contained inside table region on narrow screens

Contract workspace reference:
- compact contract summary header
- fact/review workspace and source document visible together on desktop
- adjustable split panels
- tabs/sections for overview, costs/deadlines, equipment, documents, history
- source links resolve document version/page/highlight
- explicit missing/extracted/reviewed/calculated states

## Runtime acceptance checklist still required

The source audit cannot truthfully establish rendered/browser or performance baselines. Before FE-01 can be marked COMPLETE, run the current branch locally and record:

- Login, dashboard, contracts, contract detail/workspace, import, review, work queue, settings/admin, developer screens.
- Widths: 1440, 1280, 768, 390 px (and 320 px reflow where applicable).
- `npm run lint`
- `npm run test`
- `npm run build`
- production page/load measurements with browser + hardware + representative dataset noted.
- verify role journeys and organization/hospital/department switching, including a rapid switch while requests are pending.

Any failures here are FE-01 baseline findings, not regressions introduced by FE-02.

## Priority summary

1. P0: misleading AI health indicator.
2. P0: split the overloaded ClientNav shell and consolidate account actions.
3. P0: protect scope switches from stale responses.
4. P0: consolidate semantic design tokens and stylesheet ownership before broad visual changes.
5. P1: remove duplicate `main-content` ID and label global search.
6. P1: centralize route/navigation metadata and add breadcrumbs/responsive navigation.
7. P1: verify all server-dependent roadmap controls before exposing them.
