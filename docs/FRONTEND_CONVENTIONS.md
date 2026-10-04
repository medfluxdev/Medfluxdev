# Frontend-Konventionen

Stand 2026-10-04 (UX-Plan U0–U10, `docs/architecture/FRONTEND_UX_ANALYSIS_AND_REFACTORING_PLAN_20261004.md`).
Lebende Referenz der Bausteine: `/developer/components` (nur Entwicklerkonten).

## 1. Schrift und Tokens

- Schriften sind selbst gehostet (`@fontsource-variable/inter`, `@fontsource-variable/jetbrains-mono`), kein Google-Fonts-Abruf.
- Alle Werte kommen aus `app/styles/tokens.css`. Reihenfolge der Ebenen: Primitive (`--neutral-*`, `--teal-*` …) → semantisch (`--color-*`, `--text-*`, `--space-*`, `--radius-*`) → Komponente. Komponenten nutzen **nur semantische Tokens**.
- Typo-Skala (rem, folgt der Benutzer-Textgröße):

  | Token | Größe | Einsatz |
  |---|---|---|
  | `--text-display` | 28–36 px (`clamp`) | höchstens eine Überschrift je Seite |
  | `--text-title-l` | 24 px | Seitentitel |
  | `--text-title-m` | 20 px | Panel-, Dialogtitel |
  | `--text-title-s` | 18 px | Abschnittstitel |
  | `--text-body` | 16 px | Standard-Fließtext, Formulare |
  | `--text-small` | 14 px | dichte Tabellen, Hilfetexte |
  | `--text-caption` | 12 px | nur Metadaten, nie für Pflichtinformation |

- Zahlen in Tabellen: `font-variant-numeric: tabular-nums`; Nummern und Codes in `--font-mono`.
- `stylelint` (Teil von `npm run verify`) verbietet Hex-Farben, freie `font-size`/`font-family`/`z-index`-Werte und `!important` außerhalb von `base.css`.
- Dunkles Design, Textgröße und Dichte schalten über `data-theme`, `data-text-size`, `data-density` am `<html>`. Neue Farben immer für hell **und** dunkel definieren und auf Kontrast ≥ 4,5:1 (Text) bzw. 3:1 (Bedienelemente) prüfen.

## 2. Bausteine statt Eigenbau

Vor jedem neuen UI-Element in `components/ui/` nachsehen:

| Bedarf | Baustein |
|---|---|
| Schaltfläche | `Button` bzw. Klassen `btn`, `btn-primary`, `btn-danger`, `btn-sm`, `btn-ghost` |
| Formularfeld mit Label, Hilfe, Fehler | `Field` |
| Status-Kennzeichen | `Badge` (Text trägt die Bedeutung, Farbe unterstützt) |
| Meldung | `InlineAlert` (`role="status"` für Erfolg/Info, `role="alert"` für Fehler) |
| Kurzfeedback nach Speichern | `useToast()` |
| Laden | `Skeleton` (Struktur) oder `LoadingState` (kurz) |
| Leer | `EmptyState` mit Titel und nächstem Schritt |
| Bestätigung, Unterbrechung | `Dialog` (Fokusfalle, Esc, Rückgabe des Fokus) |
| Vorschau, Details ohne Seitenwechsel | `Drawer` |
| Reiter | `Tabs` + `TabPanel` (Pfeiltasten, `aria-controls`) |
| Kennzahl mit Ziel | `KpiTile` |
| Einfache sortierbare Tabelle | `DataTable` |
| Ungespeicherte Änderungen, Strg+S | `useUnsavedChanges`, `useSaveShortcut` |

Keine Inline-Styles außer für wirklich dynamische Werte (z. B. Breite eines Balkens).

## 3. Seitenaufbau

- Jede Seite: `Breadcrumbs` kommen aus der Shell, die Seite liefert einen `h1`, optional Aktionen rechts, dann Inhalt. Eine Primäraktion je Bereich.
- Navigation in sechs Bereichen (`components/shell/navigation.tsx`). Neue Seite: dort eintragen (Rollen, Stichworte für die Befehlspalette), sonst ist sie weder im Menü noch in Strg+K auffindbar.
- Filter, Reiter und Suchbegriffe, die man teilen oder mit „Zurück“ erreichen will, gehören in die Adresse (`?q=`, `?tab=`, Historienfilter).
- Jeder Datenbereich hat vier Zustände: laden, leer, Fehler (mit „Erneut laden“), keine Berechtigung. Nie Beispielverträge oder Beträge hart einbauen.

## 4. Sprache

- Deutsch, Sie-Form, kurze Sätze. Fachbegriffe der Anwender (Kündigungsfrist, Kostenstelle, Rahmenvertrag), keine Technikbegriffe (Backend, Override, Intelligence, Lifecycle) in der Oberfläche.
- Fehlermeldungen sagen, was passiert ist und was der Benutzer tun kann. Diagnosedetails nur für Admins/Entwickler.
- KI-Werte sind immer als Vorschlag erkennbar (`Badge tone="ai"`, Herkunft, Beleg mit Seite).

## 5. Rollen und Rechte

- Das Backend entscheidet. Das Frontend blendet nur aus, was eine Rolle nicht nutzen kann (`role` aus `useAuth()`).
- „Ansicht als Rolle“ (Kontomenü, nur Admins) ändert nur die Darstellung für diese Sitzung; ein Hinweisband zeigt die Vorschau an. Sie gewährt oder entzieht keine Rechte.
- Entwicklermodus (Kontomenü, nur `is_developer`): Seitenleiste mit Kontext und API-Zeiten (`lib/request-log.ts`, nur Pfade und Dauer, keine Inhalte).

## 6. Barrierefreiheit

- Zielgröße mindestens 24 × 24 px, besser 44 px bei Touch.
- Sichtbarer Fokus (`--color-focus`), Tastaturbedienung für alles, kein Fokusverlust nach Speichern oder Schließen.
- Jeder neue Komponententest enthält `expect(await axe(container)).toHaveNoViolations()`.
- `forced-colors` und `prefers-reduced-motion` werden in `base.css` behandelt; eigene Animationen respektieren sie.

## 7. Tests und Prüfung

- Vitest + Testing Library in `test/`; Abfragen nach Rolle und Name, nicht nach Klassen.
- `npm run verify` = ESLint + stylelint + Vitest + `next build`.
- Ende-zu-Ende: `scripts/run_e2e.ps1` (Playwright-Journeys + axe + Bildvergleich) gegen eine eigene Wegwerf-Datenbank, nie gegen Produktdaten.
- Bildvergleich nach gewollten Layoutänderungen mit `npx playwright test e2e/visual.spec.ts --update-snapshots` erneuern und die Bilder mitcommitten.

## 8. Leistungsbudget

Gemessen mit `next build` (Spalte „First Load JS“). Stand 2026-10-04:

| Messgröße | Ist | Budget |
|---|---|---|
| Gemeinsamer Anteil aller Seiten | 87,8 kB | ≤ 95 kB |
| Größte Seite (`/contracts/[id]`) | 140 kB | ≤ 150 kB |
| Übrige Seiten | 88–108 kB | ≤ 120 kB |

- Was erst in einem Reiter oder nach einer Aktion gebraucht wird, über `next/dynamic` laden (Vorbild: `components/contracts/detail/lazy.tsx`); `pdfjs-dist` lädt erst beim Öffnen eines Dokuments.
- Lighthouse (lokal, Chrome DevTools, Desktop): Ziel Leistung ≥ 90, Barrierefreiheit 100, Best Practices ≥ 95. Prüfen auf `/`, `/register` und einer Vertragsseite, wenn ein PR neue Abhängigkeiten oder große Komponenten bringt.
- Prüf-Build neben laufendem `next dev`: `NEXT_DIST_DIR=.next-verify npx next build`.
- Entwicklermodus (Kontomenü) zeigt API-Zeiten; Anfragen über 1 s sind markiert.
