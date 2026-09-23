# STEP 15 – Production-Grade Medflux UI / Design System & Accessibility-Härtung — Checkpoint

Datum: 01.09.2026 · Fortschritt: **15 / 18 = 83,3 %**

## Zusammenfassung

Frontend-only-Support: kohärentes, professionelles deutsches Krankenhaus-/
Procurement-Enterprise-UI über ein Design-Token-System und wiederverwendbare
Primitives. **Keine Änderung** autoritativer Business-Logik, Provenance-
Semantik, Backend-Trust-Boundaries oder Sicherheitsarchitektur. STEP-12/13/14
Semantik bleibt exakt erhalten (zuständig: Dashboard-KPI/Handlungsbedarf,
Vertrags-Filter/Suche, Detail-/Quellen-/Provenance-Anzeige).

## Grenzen (bewusst eingehalten)

- **Kein Stack-Wechsel**: Next.js 14.2.15 / React 18.3.1 / TS 5.6.2 / bestehende
  CSS-Architektur / lokale pdf.js (pdfjs-dist@3.11.174) bleiben.
- **Keine vollen UI-Frameworks** (MUI, Ant Design, Chakra, Bootstrap, React
  Spectrum, wholesale shadcn). Kein Tailwind in STEP 15.
- **React-Aria: NICHT eingeführt.** Begründung dokumentiert: Alle aktuellen
  interaktiven Muster sind native HTML (kein Dialog/Popover/Menu/ComboBox/
  Select/Tooltip). Einführung ist ein Kosten-/Kern-Refactoring ohne heutigen
  Nutzen; Erweiterungspunkt für spätere komplexe Widgets bleibt STEP 16+.
- **Backend unangetastet** (Baseline 459 passed aus STEP 14). STEP 15 fügt
  keinen Backend-Code hinzu → keine volle Backend-Suite erneut ausgeführt.

## Design-Tokens (globals.css `:root`)

Abwärtskompatible Erweiterung: alte Namen bleiben, hinzu kommen:

- Typografie: `--font-sans`, `--fs-xs…3xl`, `--fw-*`, `--lh-*`
- Abstand: `--space-1…12`; Radii: `--radius-sm/md/lg/pill`
- Fokus: `--focus-width`, `--focus-ring`, `--focus-offset`
- Flächen: `--surface-2`, `--surface-muted`; Schatten: `--shadow-sm/md`
- Layout: `--content-max`, `--content-narrow`
- Statussemantik (nie Farbe allein): `--status-{neutral,info,success,warning,
  critical,review,stale,unknown}` + `-bg`-Töne

## Umsetzung (Dateien)

- `frontend/app/globals.css` — Token-Foundation, Primitives-, Shell-, Import-,
  Settings-Styles
- `frontend/app/layout.tsx` — Skip-Link, `<main id="main-content">`,
  App-Shell-Header, `lang="de"`, per-metadata‑Titles
- `frontend/components/ClientNav.tsx` — 4 Einträge, `aria-current`, „Einstellungen"
  als Route, entferntes `aria-disabled`
- `frontend/app/page.tsx` (Dashboard, Stale-Indikator), `app/contracts/page.tsx`
  (Suche/Filter-Zustände, Pagination), `app/import/page.tsx` (Design-System,
  Keyboard-Dropzone, Fortschritt, deterministisches Ergebnis),
  `app/settings/page.tsx` (NEU)
- `frontend/components/ui/` — `PageHeader`, `SectionCard`, `InlineAlert`,
  `EmptyState`, `LoadingState`, `Button`, `StatusBadge`, `Field`, `DefinitionList`
- `frontend/lib/ai-types.ts` (NEU), `lib/api.ts` (+`apiPost`)
- `frontend/test/{shell,settings,import}.test.tsx` (NEU)

## Testresultate

- Frontend: `npx vitest run` → **43 passed** (28 existierend + 15 neu; jest-axe
  inklusive)
- `npx tsc --noEmit` → grün
- `npx next lint --no-cache` → No warnings/errors
- `npm run build` → produktiver Next-Build kompiliert
- Backend: unverändert

## UI-Assurance-Matrix (Zielrichtung, KEINE formale Konformitätsbehauptung)

| Quelle | Fokus | Status STEP 15 |
|--------|-------|----------------|
| WCAG 2.2 AA | Kontrast, Fokus, Text-Nicht-Farbe, Heading-Hierarchie, `aria-live`, Skip-Link, Tastatur | umgesetzt/geprüft (jest-axe) |
| BITV 2.0 / EN 301 549 | europäische Bezüge | design-/tastaturseitig berücksichtigt |
| B3S / KRITIS-Denkweise | keine Vertragsinhalte in localStorage/URLs, keine Pfade, lokal | erhalten/verstärkt |
| OWASP ASVS | keine externen Skripte/CDN, kein `dangerouslySetInnerHTML`/eval, minimaler CSP | erhalten |

Zur **Playwright-Entscheidung**: Nicht vorhanden in diesem Repo/Projekt.
Einführung wäre ein eigenständiger Wartungsaufwand (Browser-Download,
CI-Pflege); für das MVP bleibt agency-/Keystroke-Testing + manuelle Prüfung
empfohlen. Entscheidung dokumentiert, nicht umgesetzt.

## Sicherheit (erhalten/verstärkt)

- Keine neuen externen Skripte/Fonts/Analytics; kein CDN
- Keine Vertrags-/Evidence-Inhalte in URLs oder localStorage/sessionStorage
- Keine Storage-/Filesystem-Pfade in der UI; nur Anzeigenamen/opaque IDs
- Minimale CSP (`frame-ancestors 'none'` …) erhalten; Voll-CSP + Auth folgt
  STEP 16 (laut next.config.js-Kommentar)

## Bekannte Grenzen & STEP-16-Handoff

- Playwright-E2E nicht eingerichtet (dokumentiert oben)
- Voll-CSP, RBAC/RLS, Login/Audit, Duplikat-Verlinkung pro Org → STEP 16
- Settings sind ehrlich zu den gemeldeten KI-Zuständen (keine erfundenen
  „production suitable"-Werte); Details/Admin-UI → STEP 16+
- benutzer-/rollenbezogene Controls waren laut STEP-15-Grenze NICHT Teil des
  Supports (Erweiterungspunkt im `ClientNav`/Footer vorhanden)

## Nächster Schritt

STEP 16 – Benutzer/Login & Audit Minimalversion (+ Voll-CSP, RBAC/RLS,
Duplikat-Verlinkung pro Org). Startet NICHT automatisch; erst auf Anweisung.
