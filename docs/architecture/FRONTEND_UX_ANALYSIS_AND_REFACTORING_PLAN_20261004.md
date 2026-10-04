# MedFlux Frontend – UX Analysis and Refactoring Plan

Date: 2026-10-04 · Scope: `frontend/` (Next.js 14, React 18, plain CSS) · Basis: code measurements, a walk-through of the running app (test instance), and a comparison with leading products and design systems.

Goal: the best possible experience for three audiences – **users** (contract managers, reviewers, viewers in a hospital), **admins** (set-up, users, catalogues, audit) and **developers** (building and debugging MedFlux) – without losing what makes MedFlux different: local AI, evidence with page sources, and deterministic deadlines and costs.

---

## 0. Implementation status (2026-10-04)

All phases U0–U10 are implemented on branch `feature/ui-refactor` (stacked on `feature/register-gaps`). Details per phase in `docs/PROJECT_PROGRESS.md`; working rules in `docs/FRONTEND_CONVENTIONS.md`.

| Phase | Status | Notes / deviations |
|---|---|---|
| U0 Baseline | done | Playwright journeys (8), axe, visual references, guarded e2e seed, `docs/ux/BASELINE_20261004.md`. SUS/task times need the real usability round (`docs/ux/USABILITY_TEST_SCRIPT.md`). |
| U1 Tokens, fonts | done | Inter + JetBrains Mono self-hosted, 7-step scale, semantic colours with dark values, stylelint. |
| U2 Components | done | Dialog, Drawer, Tabs, DataTable, Badge, Breadcrumbs, Skeleton, Tooltip, KpiTile, form guards. Not built: Combobox, DateField, MoneyField, Popover, row selection in DataTable (native controls kept). |
| U3 Navigation | done | 6 areas, icon rail, phone drawer, Ctrl+K palette, shortcuts. |
| U4 Key screens | done | Contract page (object header, 7 tabs), one list `/register`, "Mein Tag", import wizard. |
| U5 Roles | done | Plain language, field help, admin set-up checklist, "Ansicht als Rolle", history filters in the URL, developer mode (context + API timings), conventions, style guide. Bulk user import from CSV: the admin sets each first password (from the list, typed or generated), check first, all-or-nothing. |
| U6 Accessibility | done | axe sweep on 25 pages in light, dark and forced colours; catalog tabs fixed; forced-colors rules. |
| U7 Performance | done | Lazy PDF viewer and tab panels: contract page 150 → 140 kB first load. Optimistic updates and hover prefetch not added. INP not measured yet. |
| U8 Personalisation | done | Theme/text size/density/sidebar saved per account (`/api/profile/preferences`); dark mode reviewed on all main pages. |
| U9 Responsive | done | No horizontal page scroll at 1440/900/390 px (automated). Wide tables scroll inside their frame on phones instead of turning into cards. |
| U10 Quality gates | done | PR template, performance budget, refreshed visual references. Lighthouse is a manual check (no CI job yet). |

**Metrics now** (baseline → now): font sizes 69 → 7 tokens; hex colours outside tokens 263 → 0; `!important` 67 → 5 (reduced-motion only); inline styles 35 → 3 (dynamic values); contrast failures 31 → 0; sidebar 19 entries → 6 areas; contract tabs 12 + 4 panels → 7; global CSS 20 files / ~190 KB → 22 files / ~170 KB (375 unused rules removed; target of two files not reached, the rest is still used legacy styling); axe in 22 of 40 component test files plus every page in e2e.

---

## 1. Summary

MedFlux already has a lot of working functionality, and the newer screens (register grid, finance, deadlines, history, search) follow a consistent pattern. The experience suffers from **growth without a design system**:

1. **The intended fonts never load.** CSS asks for Poppins and Inter, but no font file is shipped. Every user sees the Windows fallback (Segoe UI); on other systems the look changes again.
2. **Typography is not a scale.** 69 different font sizes are used, many between 9.5 and 12 px. The base text is 15.2 px (`0.95rem`) and small text is 11.5 px – too small for long working sessions.
3. **The visual foundation is fragmented.** There are 20 global CSS files imported in a fixed order, 263 distinct hex colours, 44 shadows, 33 border radii, 22 breakpoints and 67 `!important` rules. The same token is defined several times with different values (`--muted`, `--text-muted`).
4. **Two ways to do everything.** "Verträge" and "Vertragsregister" are two contract lists with different columns, filters and saved views. The dashboard counts a contract as "0 aktive, 0 € Kosten" while the register shows the same contract with 42.000 €. Two statuses ("In Arbeit" and "Unbekannt") are shown side by side on the contract header.
5. **The contract page is overloaded.** An organisation form sits above the contract title, 12 tabs overflow horizontally, and four panels (Vertragsintelligenz, Backend-Vollanalyse, Rechnungsprüfung, Lebenszyklus) appear under every tab. The floating "KI-Assistent" button covers the tab bar. The page is slow to render.
6. **Technical language reaches users.** Words like "Backend", "autoritativ", "Intelligence", "Lifecycle", "Override" and "unknown" appear in user-facing text (about 130 occurrences).
7. **Accessibility is partly covered.** jest-axe runs in 19 of 40 test files. One text colour (`#8a99ad`, 2.9:1) fails WCAG contrast. There is no dark mode and no "larger text" option.

The plan in §6 fixes this in ten phases, starting with the foundation (fonts, type scale, tokens) because every later step depends on it.

---

## 2. What was measured

| Area | Finding | Target |
|---|---|---|
| Pages | 33 routes (`app/**/page.tsx`) | ~22 after merging duplicates |
| Components | 68 files, 9 439 lines; largest: `ContractDetail.tsx` 1 668 lines (only used by tests), `app/contracts/page.tsx` 542, `ContractRegisterPanel.tsx` 529, `app/settings/page.tsx` 502 | no component > 400 lines; no dead code |
| Global CSS | 20 files, ~190 KB; `globals.css` alone 76 KB; import order matters (`reference-theme`, `desktop-shell-fix`, `release-gate`, `brand-identity` override each other) | 1 token file + 1 base file + component CSS modules |
| Fonts | `Poppins`/`Inter` declared, **no `@font-face`, no `next/font`** → fallback | self-hosted variable font via `next/font/local` |
| Font sizes | **69 distinct values**; most used: 12 px (55×), 13 px (46×), 0.85rem (23×), 11 px (17×), also 10.5, 10, 9.5 px | 8 steps of one type scale |
| Colours | 822 hex uses, **263 distinct**; 73 rgba | ~40 semantic tokens |
| Shadows / radii | 44 / 33 distinct | 3 / 3 |
| Breakpoints | 22 distinct widths | 4 |
| `!important` | 67 | 0 |
| Inline `style={{…}}` | 35 | 0 (tokens or classes) |
| Class families | `cw-` 269, `rg-` 207, `detail-`, `contract-`, `org-`, `fr-`, `fact-`, `kpi-`, `intel`, `audit-` … | one component library |
| UI primitives | `components/ui` exists (Button, Field, EmptyState, …) but `<Button>` is used in 8 files, **`EmptyState` in 0**; 113 ad-hoc `role="status/alert"` messages | primitives used everywhere |
| States | `LoadingState` 14×, `InlineAlert` 18×, rest ad hoc | one loading/empty/error/permission pattern |
| Accessibility | jest-axe in 19/40 test files; 27 `:focus-visible` rules; `prefers-reduced-motion` present; muted text `#8a99ad` 2.9:1 ✗ | axe in every UI test + e2e; all text ≥ 4.5:1 |
| Dark mode | none (0 rules) | full token-based dark theme |
| Navigation | 19 sidebar entries in 3 groups + developer link; topbar has hospital picker, "Analysen" link, contract-number search, bell, account | 6 primary areas + command palette |
| Keyboard | no command palette / shortcuts | `Ctrl+K`, `/`, `g v`, `?` |
| Bundles | first load ~100–105 KB per route (good); PDF viewer and charts are heavy client parts | keep ≤ 120 KB; lazy-load PDF/charts |

---

## 3. Walk-through findings (running app)

**Übersicht (dashboard)**
- A large gradient hero ("Willkommen im intelligenten Vertragsmanagement") takes a third of the screen every day. Leading products show the user's work first, not a welcome message.
- The KPI tiles use the old AI status. A contract that the register shows with 42.000 € per year appears as "Aktive Verträge 0" and "Jährliche Gesamtkosten 0". Numbers that disagree between screens destroy trust quickly.
- The sidebar has its own scrollbar inside the page scrollbar.

**Verträge (classic list)**
- Three stacked toolbars (search, quick filters, sort/views/density) before the first row.
- The status cell shows an empty pill plus "In Arbeit"; "Kündbar bis" shows "–" even when the register can compute it.
- Saved views and filters work differently from the Vertragsregister.

**Vertrag (object page)**
- "Organisationszuordnung" (a form) is the first thing on the page, above the contract name.
- 12 tabs; the tab bar scrolls horizontally on a 1 568 px screen; the floating KI-Assistent button overlaps it.
- Header badges: "Archivieren", "In Arbeit", "Unbekannt", "Risiko: Unbekannt" – an action and three badges with unclear meaning.
- Under every tab, four legacy panels repeat (Lebenszyklus, Vertragsintelligenz, Backend-Vollanalyse with "Analyse: unknown", Rechnungsprüfung).
- Topbar title "Vertrag 360" is internal jargon.

**Strong points to keep**
- Honest empty states ("Keine verlässlichen Kosten verfügbar", "nicht gefunden").
- Provenance badges (KI-Vorschlag, bestätigt, korrigiert) and "Quelle" buttons to the PDF page.
- German plain wording in the newer screens; reduced-motion support; skip-to-content intent.

---

## 4. What the best products do (and what MedFlux takes from each)

| Product / system | What they do exceptionally well | Apply in MedFlux |
|---|---|---|
| **SAP Fiori** (enterprise floorplans) | Fixed patterns: *List Report* (filter bar + table + variants) and *Object Page* (header with key facts, anchored sections, edit per section) | One contract list (register) with "Varianten" = saved views; one object-page layout for contract, partner, device |
| **Salesforce Lightning** | Record page: highlights panel, related lists, activity timeline on the right | Sticky contract header with key facts; "Verlauf" timeline; related lists (Dokumente, Termine, Geräte) |
| **Stripe Dashboard** | Calm, dense tables; filters as removable chips; detail pages with a summary block then sections; superb empty states and copy | Chip filters (already in register), summary block per contract, consistent money/date formatting with tabular numbers |
| **Linear** | Keyboard-first, `Cmd/Ctrl+K` command menu, instant feedback, saved views, minimal chrome | Command palette for contracts, partners, content search and actions; optimistic updates |
| **GitHub Primer** | Token-driven design system, strong accessibility, type scale based on 14/16 px, clear focus rings | Token architecture (primitive → semantic → component), focus ring standard |
| **Microsoft Fluent 2** | Type ramp (Caption 12 → Display 68), Segoe UI Variable, density modes, high-contrast support | Type ramp model, density setting, Windows high-contrast/forced-colors support (hospitals run Windows) |
| **IBM Carbon** | Enterprise data tables (sticky header, batch actions, expandable rows), IBM Plex type family | DataTable component spec; batch actions in the register |
| **GOV.UK Design System** | Plain language, 19 px body text, one thing per page for complex forms, tested with real users including low vision | Plain-language rules, larger base text, step-by-step import wizard and status transitions |
| **Atlassian (Jira)** | Saved filters shared with teams, list/board switch, notification hub | Global vs personal views (done), inbox with clear actions |
| **Notion / Vercel Geist** | Restraint: few colours, generous whitespace, consistent icons | Reduce colour count to tokens; one icon set |

German context: public and many private hospitals fall under accessibility law (BITV 2.0 / Barrierefreiheitsstärkungsgesetz, WCAG 2.1 AA). Google-Fonts CDN embedding has been ruled a GDPR violation in Germany (LG München I, 2022), so fonts must be **self-hosted**, which also fits MedFlux's local-only principle.

---

## 5. Typography recommendation

### 5.1 Fonts

| Role | Font | Why |
|---|---|---|
| UI and body | **Inter (variable)**, self-hosted via `next/font/local` (or the `@fontsource-variable/inter` package) | Designed for screens; excellent at 12–16 px; full German character set; **tabular figures** (`font-feature-settings: "tnum"`) so amounts and dates align in tables; variable weights in one file (~100 KB woff2, cached) |
| Numbers in tables | Inter with `tnum` + `case` | Columns of € values and dates line up without a separate font |
| Codes, IDs, JSON (developer views) | **JetBrains Mono** (or IBM Plex Mono), self-hosted | Clear distinction of 0/O and 1/l/I; used only in developer mode and for contract/register numbers if desired |
| Brand / logo only | Poppins (or none) | Poppins is geometric and weak at small sizes. Use it at most for the logo word mark and the login page heading, never for UI text |

Alternative if a more "institutional" look is wanted: **IBM Plex Sans + IBM Plex Mono** (one family, very legible, open licence). Do not mix more than one UI family.

Fallback stack (unchanged look on Windows if the font fails): `"Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`.

### 5.2 Type scale ("font growth")

Base 16 px, ratio ≈ 1.2 (minor third) for headings, line height decreasing as size grows. Sizes in `rem` so the user's text-size setting and browser zoom scale everything.

| Token | Size / line height | Weight | Use |
|---|---|---|---|
| `--text-caption` | 12 / 16 px (0.75rem) | 500 | Meta only: timestamps, badges, table footers. **Absolute minimum.** |
| `--text-small` | 14 / 20 px (0.875rem) | 400 | Dense tables, secondary text, form help |
| `--text-body` | 16 / 24 px (1rem) | 400 | Default body, inputs, buttons |
| `--text-body-strong` | 16 / 24 px | 600 | Labels, table headers |
| `--text-title-s` | 18 / 26 px (1.125rem) | 600 | Card and section titles |
| `--text-title-m` | 20 / 28 px (1.25rem) | 600 | Panel titles, dialog titles |
| `--text-title-l` | 24 / 32 px (1.5rem) | 650 | Page titles |
| `--text-display` | `clamp(1.75rem, 1.2rem + 1.5vw, 2.25rem)` / 1.2 | 700 | Contract name on object page, dashboard headline (one per page) |

Rules:
- Nothing below 12 px. Body text never below 14 px.
- Line length 60–80 characters for reading text (`max-width: 70ch`).
- Numbers: `font-variant-numeric: tabular-nums` in tables and KPI tiles.
- German: allow hyphenation in narrow cells (`hyphens: auto` with `lang="de"`), as German compounds ("Kündigungsfristberechnung") otherwise overflow.
- Weight contrast instead of size jumps for hierarchy inside cards (400 → 600).
- User setting "Textgröße": 100 % / 112,5 % / 125 % (changes the root font size; all `rem` values follow).

### 5.3 Colour and contrast tokens (summary)

- Primitive palette: 1 brand teal ramp, 1 neutral ramp, status ramps (green, amber, red, blue). Semantic tokens on top: `--color-text`, `--color-text-muted` (≥ 4.5:1, e.g. `#5f6b7a`), `--color-surface`, `--color-surface-raised`, `--color-border`, `--color-accent`, `--color-success/warning/danger/info` (+ `-bg` variants).
- Replace `--muted2 #8a99ad` (2.9:1) everywhere.
- Status colours are always paired with an icon and a word (never colour alone).
- Dark theme = second set of semantic values, selected by `prefers-color-scheme` and a user toggle.

---

## 6. Refactoring plan (phases and steps)

Each phase is one or more PRs on `feature/ui-<topic>`, behind no feature flag unless stated, with screenshots before/after in the PR and an entry in `docs/PROJECT_PROGRESS.md`.

### Phase U0 – Baseline and safety net (S)
1. Add Playwright end-to-end tests for 8 core journeys (login, find contract, open contract, edit Stammdaten, add deadline, import document, run search, export Excel) with **visual snapshots** at 1 440 px and 390 px.
2. Add `@axe-core/playwright` to those journeys; record current violations.
3. Record baseline metrics: Lighthouse accessibility/performance per main route, Web Vitals (LCP, INP), and the numbers in §2.
4. Define UX success metrics (§7) and run a 5-person baseline usability test with real hospital users (tasks: "Find all contracts with notice deadline in 90 days", "Who is responsible for contract 000042?", "Add a cost entry").
- **Done when:** journeys green in CI; baseline report in `docs/ux/`.

### Phase U1 – Foundation: fonts, type scale, tokens (M)
1. Self-host Inter variable (+ JetBrains Mono) with `next/font/local`; expose as CSS variables; remove Poppins from UI text.
2. Create `app/styles/tokens.css` (primitive + semantic tokens: colour, type scale §5.2, spacing on a 4 px grid, radii `4/8/12`, shadows `sm/md/lg`, z-index scale, motion durations, breakpoints `sm 640 / md 960 / lg 1280 / xl 1600`).
3. Create `app/styles/base.css` (reset, body text 16 px, headings, links, focus ring, `tabular-nums` utilities, reduced motion).
4. Codemod: map the 69 font sizes and 263 colours to tokens (script with a mapping table; manual review of outliers). Remove duplicate token definitions.
5. Add **stylelint** with rules: no hex colours outside tokens, no `px` font sizes, no `!important`, allowed z-index values only.
- **Done when:** ≤ 8 font sizes, ≤ 40 colour tokens in use, 0 `!important`, contrast check passes, visual diffs reviewed.

### Phase U2 – Component library (L)
1. Complete `components/ui` with accessible primitives (no UI framework needed; optionally Radix primitives for Dialog/Popover/Tabs focus handling):
   Button/IconButton (primary, secondary, ghost, danger; sizes s/m), TextField, Select, Combobox (partners, users), Checkbox/Switch, DateField (German format, keyboard entry), MoneyField, Tabs (with overflow menu), Badge/StatusBadge (one status vocabulary), Card/Section, PageHeader, ObjectHeader, DataTable (sorting, sticky header, density, column chooser, row selection, keyboard navigation), FilterBar + FilterChip, Pagination, EmptyState, Skeleton, InlineAlert, Toast, Dialog, Drawer (side panel), Tooltip, Popover, Breadcrumbs, KeyValue list, Timeline.
2. Living style guide on `/developer/components` (exists) showing every component, state and token, with copy guidelines.
3. Migrate screens family by family (`rg-*`, `cw-*`, `detail-*`, …) to the primitives; delete the old CSS per family. Move component styles to CSS Modules next to the component.
4. Delete dead code (`ContractDetail.tsx` and its tests after confirming no route uses it; unused CSS files such as `desktop-shell-fix.css`, `release-gate.css` once empty).
- **Done when:** `globals.css` < 10 KB; every screen uses primitives for buttons, fields, tables, states; no component > 400 lines.

### Phase U3 – Information architecture and navigation (M)
1. New sidebar with 6 areas (role-aware):
   - **Start** – Mein Tag (dashboard), Postfach
   - **Verträge** – Vertragsliste (the register grid; the classic list is retired, its saved views migrated), Vertragspartner, Geräte
   - **Fristen** – Termine, Verlängerungen
   - **Prüfung** – Import, Prüfungen, Nachweise, Archiv
   - **Auswertungen** – Analysen, Historie
   - **Verwaltung** (admins) – Organisation, Benutzer & Rollen, Kataloge, System
2. **Command palette** (`Ctrl+K`): jump to contract by number/name, partner, page; run actions ("Vertrag anlegen", "Termin anlegen", "Excel exportieren"); full-text content search as a section. Shortcuts: `/` search, `g v` Verträge, `g t` Termine, `?` help overlay.
3. One global search field in the topbar that opens the palette (replaces "Vertragsnummer…" field and the separate "Analysen" link).
4. Breadcrumbs on all detail pages; page titles in plain language ("Vertrag" instead of "Vertrag 360").
5. Collapse the sidebar to icons below `lg`; single scroll container.
- **Done when:** every task in the usability script reachable in ≤ 3 clicks or one palette command.

### Phase U4 – Key screens (L)
1. **Mein Tag (dashboard):** remove hero banner; show "Heute fällig", "Diese Woche", "Entscheidungen vor Kündigungsfrist", "Zu prüfen", "Ungelesene Erinnerungen", then KPI tiles computed from the **same register/finance data** as the list (fixes the 0 € vs 42.000 € mismatch).
2. **Vertragsliste (List Report):** saved views as tabs at the top, one filter bar with chips, column chooser, density toggle, totals row, batch actions (assign responsible, export), quick-view drawer on row click, full page on open.
3. **Vertrag (Object Page):**
   - Sticky object header: number, title, partner, business status (one badge), next deadline, annual cost, responsible person, primary actions (Bearbeiten, Status ändern, Deckblatt, …) and a "⋯" menu (Archivieren, Löschen vormerken).
   - 7 tabs: Übersicht · Stammdaten (incl. Organisationszuordnung) · Fristen & Entscheidung · Finanzen · Dokumente & Nachweise · Beziehungen (Rahmenvertrag, Geräte, Partner) · Verlauf (Historie + Bemerkungen).
   - Legacy panels move into the matching tab (Lebenszyklus → Fristen & Entscheidung; Rechnungsprüfung → Finanzen; Vertragsintelligenz → Übersicht summary) or into developer mode (Backend-Vollanalyse).
   - Lazy-load the PDF viewer only on the Dokumente tab.
   - KI-Assistent as a side panel opened from the header, not a floating button over content.
4. **Forms:** edit per section with inline validation, German date/number input, unsaved-changes warning, keyboard save (`Ctrl+S`), clear AI provenance with "Quelle anzeigen" popover.
5. **Import:** step-by-step wizard (plan exists in `docs/architecture/CONTRACT_IMPORT_WIZARD.md`): upload → analysis progress → review proposals side by side with the PDF → confirm.
- **Done when:** baseline usability tasks are ≥ 30 % faster and error-free for 4 of 5 users.

### Phase U5 – Experience per role (M)
- **Users:** plain-language pass on all texts (glossary; remove "Backend", "autoritativ", "Intelligence", "Lifecycle", "Override", "unknown"); task-first empty states with one clear next action; help texts on hard fields (Kündigungsfrist "zum Quartalsende").
- **Admins:** admin hub with a **set-up checklist** (organisation structure, users and roles, catalogues, number range, SMTP, local AI model, backups, daily job) showing status; "Ansicht als Rolle" preview; bulk user import; audit with saved filters.
- **Developers:** a **developer mode** switch (only for `is_developer`) that reveals raw IDs, JSON payloads, processing runs, harness diagnostics and API timings in a drawer – hidden from normal users; style guide; `docs/FRONTEND_CONVENTIONS.md` (tokens, components, copy, testing); stylelint/ESLint rules; Storybook-like isolation in `/developer/components`.

### Phase U6 – Accessibility (M, continuous)
1. WCAG 2.2 AA / BITV checklist per component; skip link; landmark structure; visible focus everywhere; target size ≥ 24 px.
2. Keyboard: tables navigable with arrows, dialogs trap focus, tabs with arrow keys.
3. Screen reader: table captions, sort state via `aria-sort`, live regions only through Toast/InlineAlert.
4. Zoom 200 % and text size 125 % without loss; `forced-colors` (Windows high contrast) styles.
5. axe in every component test and every e2e journey; block CI on new violations.

### Phase U7 – Speed and perceived performance (S–M)
1. Skeletons for lists and object pages; optimistic updates for simple edits; prefetch on hover for list → detail.
2. Code-split PDF viewer, charts and the assistant; measure INP < 200 ms on the contract page.
3. Server pagination limits and request de-duplication in `lib/api.ts`.

### Phase U8 – Personalisation and dark mode (S–M)
1. Dark theme from semantic tokens (validated contrast), plus "System / Hell / Dunkel" setting.
2. Density (comfortable/compact) and text size (100/112,5/125 %) stored per account on the server (not only localStorage).
3. Remember last list view per user (server-side views exist).

### Phase U9 – Responsive and tablet (S)
1. Four breakpoints only; sidebar → icon rail → drawer.
2. Tables switch to a card list below `md`; object header wraps; forms single column.
3. Test on a 10" tablet (ward use) and 390 px phone for read-only flows.

### Phase U10 – Quality gates and continuous UX (S, ongoing)
1. CI: stylelint, visual regression (Playwright), axe, Lighthouse budgets (accessibility ≥ 95, performance ≥ 85).
2. Quarterly usability round with 5 hospital users; track SUS score and task times.
3. UX review checklist in PR template (tokens only, primitives only, German copy reviewed, states covered, keyboard tested).

---

## 7. Success metrics

| Metric | Baseline (2026-10-04) | Target |
|---|---|---|
| Distinct font sizes / colours | 69 / 263 | ≤ 8 / ≤ 40 tokens |
| Smallest text | 9.5 px | 12 px (meta only) |
| `!important` / inline styles | 67 / 35 | 0 / 0 |
| Global CSS | 20 files, ~190 KB | 2 files < 25 KB + modules |
| Sidebar entries | 19 (+ developer) | 6 areas, ≤ 14 entries |
| Contract page tabs | 12 + 4 always-visible panels | 7, nothing repeated |
| axe coverage | 19/40 test files | 100 % UI tests + e2e |
| Contrast failures | ≥ 1 token (2.9:1) | 0 |
| Time to find a contract by partner | to be measured in U0 | < 10 s |
| SUS score | to be measured in U0 | ≥ 80 |
| Numbers consistent across screens | dashboard ≠ register | identical source everywhere |

---

## 8. Order and effort

| Order | Phase | Size | Depends on |
|---|---|---|---|
| 1 | U0 Baseline and safety net | S | – |
| 2 | U1 Fonts, type scale, tokens | M | U0 |
| 3 | U2 Component library + migration | L | U1 |
| 4 | U3 Navigation + command palette | M | U2 (primitives) |
| 5 | U4 Key screens | L | U2, U3 |
| 6 | U5 Role experiences | M | U4 |
| 7 | U6 Accessibility | M | runs alongside U1–U5 |
| 8 | U7 Performance | S–M | U4 |
| 9 | U8 Personalisation + dark mode | S–M | U1 tokens |
| 10 | U9 Responsive/tablet | S | U2, U4 |
| 11 | U10 Quality gates | S | from U0 on |

Recommended first sprint: U0 + U1 (fonts and type scale give the largest visible improvement for the least risk), then the contract object page from U4 as the first showcase screen.
