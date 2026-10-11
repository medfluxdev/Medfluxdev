# Frontend-Konventionen

Stand 2026-10-04 (UX-Plan U0–U10, `docs/architecture/FRONTEND_UX_ANALYSIS_AND_REFACTORING_PLAN_20261004.md`).
Lebende Referenz der Bausteine: `/developer/components` (nur Entwicklerkonten).

## 1. Schrift und Tokens

- Schriften sind selbst gehostet (`@fontsource-variable/inter`, `@fontsource-variable/jetbrains-mono`, `@fontsource-variable/source-serif-4`), kein Google-Fonts-Abruf. Inter für alles; *Source Serif 4* (`--font-display`) nur für den einen Seitentitel je Seite. In Tabellen, Eingaben und Codes sind 1, l und I unterscheidbar (`cv05`, `cv08`).
- Farben (seit 2026-10-06, Richtung **„Sachlich-institutionell“**): flacher, kühler Hellgrau-Hintergrund `--color-bg` ohne Lichtflecken und ohne Verläufe; Navy `--color-accent` (`#0f4c81`) ist die einzige Aktionsfarbe (Hauptaktion, Links, aktive Navigation); **Teal nur im Logo** (keine Teal-Flächen, -Töne oder -Texte); Violett nur für KI. Karten und Panels flach (`--shadow-sm: none`), Schatten nur für Menüs, Popover, Dialoge, Drawer. Hervorgehobener Seitenkopf (`PageHeader variant="highlight"`): weiße Fläche mit Haarlinie, Navy-Eyebrow, Titel 24 px. Verläufe nur funktional (Pfeil der Auswahlliste, Skeleton-Schimmer).
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
- Rahmen von Bedienelementen (Eingabefelder, Auswahllisten, Suchfeld, Ghost-Knöpfe): `--color-border-strong` (hell `#7d8c9b` 3,4:1, dunkel `#64768a` 3,6:1 gegen `--color-surface`). Fokus von Feldern: Navy-Rahmen und `--color-focus`.

## 2. Bausteine statt Eigenbau

Vor jedem neuen UI-Element in `components/ui/` nachsehen:

| Bedarf | Baustein |
|---|---|
| Schaltfläche | `Button` bzw. Klassen `btn`, `btn-primary`, `btn-danger`, `btn-sm`, `btn-ghost` |
| Formularfeld mit Label, Hilfe, Fehler | `Field` |
| Signal / Status | `Signal tone="critical|warning|info|done|ai|neutral"` – immer Farbe + Form + Wort; `Badge`/`StatusBadge`/`InlineAlert`/`Toast` nutzen dieselben Formen. Grün (`done`) nur für Bestätigtes, nie für „nichts zu tun“ |
| Status-Kennzeichen | `Badge` (Text trägt die Bedeutung, Form und Farbe unterstützen) |
| Betrag mit Abdeckung | `CoverageValue`: unbekannt bleibt „—“, Teilsummen „bekannt für N von M“, andere Währungen getrennt |
| Meldung | `InlineAlert` (`role="status"` für Erfolg/Info, `role="alert"` für Fehler) |
| Kurzfeedback nach Speichern | `useToast()` |
| Laden | `Skeleton` (Struktur) oder `LoadingState` (kurz) |
| Leer | `EmptyState` mit Titel und nächstem Schritt; in Übersichtskarten „nichts zu tun“ als `variant="calm"` (graue Zeile, kein Grün, ohne gestrichelten Rahmen) |
| Bestätigung, Unterbrechung | `Dialog` (Fokusfalle, Esc, Rückgabe des Fokus) |
| Vorschau, Details ohne Seitenwechsel | `Drawer` |
| Auswahl unter einem Knopf (Filterwerte, Darstellung, kleines Menü) | `Popover`: nicht modal, Esc schließt und gibt den Fokus an den Knopf zurück, Klick daneben schließt; `active` hebt den Knopf bei aktiver Auswahl hervor |
| Reiter | `Tabs` + `TabPanel` (Pfeiltasten, `aria-controls`) |
| Kennzahl mit Ziel | `KpiTile`: mit `href` ist die ganze Kachel ein Link; die Kachel ist immer neutral; Aufmerksamkeit nur über `signal={{ tone, label }}`; `icon` = graues Liniensymbol vor der Beschriftung |
| Einfache sortierbare Tabelle | `DataTable` |
| Ungespeicherte Änderungen, Strg+S | `useUnsavedChanges`, `useSaveShortcut` |

Keine Inline-Styles außer für wirklich dynamische Werte (z. B. Breite eines Balkens).

## 3. Seitenaufbau

- Jede Seite: `Breadcrumbs` kommen aus der Shell, die Seite liefert einen `h1`, optional Aktionen rechts, dann Inhalt. Eine Primäraktion je Bereich.
- Navigation in sechs Bereichen (`components/shell/navigation.tsx`). Neue Seite: dort eintragen (Rollen, Stichworte für die Befehlspalette), sonst ist sie weder im Menü noch in Strg+K auffindbar.
- Filter, Reiter und Suchbegriffe, die man teilen oder mit „Zurück“ erreichen will, gehören in die Adresse (`?q=`, `?tab=`, Historienfilter).
- Jeder Datenbereich hat vier Zustände: laden, leer, Fehler (mit „Erneut laden“), keine Berechtigung. Nie Beispielverträge oder Beträge hart einbauen.
- Jeder Kasten lässt sich einklappen: `lib/box-collapse.ts` (in `ClientNav` eingehängt) versieht jeden Abschnitt im Inhaltsbereich (`section.cw-section`, `.card`, `.panel` u. a.) mit Überschrift als erstem Kind bzw. im Kopf mit einem Knopf rechts oben; der Zustand gilt je Seite (Kennungen in der Adresse zählen nicht) und Kasten. Kästen mit Aktionen im Kopf, die beim Einklappen verschwinden sollen, nutzen `CollapsibleSection`; `data-no-collapse` nimmt einen Kasten aus. Sprünge zu einem Abschnitt rufen vorher `revealBox(element)` auf.

## 4. Sprache

- Deutsch, Sie-Form, kurze Sätze. Fachbegriffe der Anwender (Kündigungsfrist, Kostenstelle, Rahmenvertrag), keine Technikbegriffe (Backend, Override, Intelligence, Lifecycle) in der Oberfläche.
- Fehlermeldungen sagen, was passiert ist und was der Benutzer tun kann. Diagnosedetails nur für Admins/Entwickler.
- KI-Werte sind immer als Vorschlag erkennbar (`Badge tone="ai"`, Herkunft, Beleg mit Seite).
- Produktname immer `MedFlux` (nie `Medflux`, `MEDFLUX`, `Med Flux`).
- Satzschreibung für Überschriften, Knöpfe, Beschriftungen, Tabellenköpfe und Navigation. Großbuchstaben nur im kleinen Eyebrow-Stil (Kicker über dem Seitentitel, Gruppennamen im Menü).
- Kennzahlen ohne echte Zahlen zeigen „—“ mit „Noch keine Daten“: `KpiTile value={null}`; während des Ladens `loading`.

## 5. Rollen und Rechte

- Das Backend entscheidet. Das Frontend blendet nur aus, was eine Rolle nicht nutzen kann. Für Aktionen mit eigenem Recht `usePermissions().can("<recht>")` aus `lib/use-permissions.ts` (Rechte-Matrix des Backends, berücksichtigt die Rollenvorschau) statt fest verdrahteter Rollenlisten.
- Wer lesen, aber nicht ändern darf, sieht die Daten und einen Hinweis, wer pflegt – nicht eine leere Seite.
- „Ansicht als Rolle“ (Kontomenü, nur Admins) ändert nur die Darstellung für diese Sitzung; ein Hinweisband zeigt die Vorschau an. Sie gewährt oder entzieht keine Rechte.
- Entwicklermodus (Kontomenü, nur `is_developer`): Seitenleiste mit Kontext und API-Zeiten (`lib/request-log.ts`, nur Pfade und Dauer, keine Inhalte).

## 5a. Bereiche und Stammdaten

- Ein Thema, eine Stelle: Fristen und Aufgaben unter `/fristen` (Reiter), Vertragslisten sind Ansichten der Vertragsliste (`RegisterGrid` mit `initialViewKey`), Verwaltungsseiten teilen die Bereichsnavigation (`AreaLayout`/`AreaNav` in `components/shell/AreaNav.tsx`). Keine zweite Liste für dieselben Daten bauen.

- Gleichartige Daten (Partner, Organisation, Kataloge, Auswahllisten) leben unter `/stammdaten` und nutzen dieselbe Bedienung: `EntityManager` (Tabelle, Suche, Filter in der Adresse, Seitenleiste zum Bearbeiten, Deaktivieren statt Löschen, Verwendung in Verträgen, Verlauf, CSV-Import/-Export).
- Neue Datenart: `EntityDefinition` in `components/master-data/definitions/` und Eintrag in `lib/master-data.ts`; keine eigene Seite mit eigener Tabelle bauen.
- Fehlt in einem Formular ein Stammdaten-Eintrag, `QuickCreate` mit derselben Definition anbieten (Beispiel: „Neuer Partner“ in „Vertrag anlegen“).
- CSV immer über `lib/csv.ts` lesen und schreiben.

## 5b. Direkt zur Stelle

Jede Meldung, dass etwas fehlt, unbekannt ist oder geprüft werden muss, führt mit einem Klick dorthin, wo es behoben wird. Plan: `docs/architecture/DIREKT_ZUR_STELLE_PLAN_20261011.md`.

- Links nur über `lib/fix-targets.ts`: `contractHref(id, { tab, subtab, field, section })` für die Vertragsakte, `registerHref(filters)` für die Vertragsliste; keine Adressen von Hand bauen.
- Mehrere fehlende Angaben als `MissingList` (jeder Eintrag ein Link oder Knopf, Screenreader „… erfassen“).
- `?feld=<key>` öffnet „Vertragsdaten“ in der Bearbeitung und setzt den Cursor ins Feld (`#rg-<key>`); `?abschnitt=<id>` scrollt zum Abschnitt (`sectionAnchor`). Neue Abschnitte mit Sprungziel bekommen eine Überschrift mit stabiler `id` und einen Eintrag in `SECTION_ANCHORS`.
- Hinweise aus dem Backend tragen ihr Ziel als `target` (`{tab, field?, section?, subtab?}`), gelesen mit `asFixTarget`; der Text bleibt unverändert. Unbekannte Ziele werden ignoriert, nie geraten.
- Aufgaben und Warnungen: `workItemTarget` / `warningTarget` (Backend: `app/work_queue/targets.py` – beide Zuordnungen gleich halten).
- Gefilterte Listen öffnen Verträge dort, wo die gefilterte Lücke behoben wird (`listRowTarget`).
- Was einer Vertragsakte fehlt, steht in „Was fehlt noch?“ und in Strg+K („Dieser Vertrag“, `lib/page-commands.ts`).
- Kann eine fehlende Angabe im Vertragsdokument stehen, gibt es neben „Erfassen“ auch „Im Dokument suchen“ (`documentSearchHref(id, feld)`; alle fehlenden: `MISSING_SEARCH`). Die KI übernimmt dabei nie selbst: Ergebnisse gehen immer durch den Vergleich (`components/contracts/detail/Reextraction.tsx`). Ohne KI: „Angabe aus dem Text übernehmen“ (`SourceCapture.tsx`); ein so übernommener Wert zeigt „S. n“ zur Fundstelle.
- Gibt es keinen Ort zum Beheben (z. B. SLA-Hinweis), bleibt die Meldung Text – dann keinen Link vortäuschen.

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
