# Ruhe & Signal – Bestandsaufnahme (Phase 0)

Stand: 2026-10-10, Branch `design/ruhe-signal` (Basis `17e331b`, Mein Tag v2).
Grundlage: Regeln R1–R10 und Signalstufen R3 aus der Projektanweisung „Ruhe & Signal“
(critical · warning · info · done · ai · neutral). Nur Lesen, kein Code geändert.

## 1. Seiten (`app/**/page.tsx`, 40)

| Bereich | Seiten |
|---|---|
| Start | `/` (Mein Tag), `/postfach` |
| Verträge | `/register`, `/contracts` (Weiterleitung), `/contracts/[contract-id]`, `/contracts/new`, `/archiv`, `/fristen`, `/termine`, `/verlaengerungen`, `/work-queue`, `/equipment`, `/equipment/[equipment-id]` |
| Prüfung | `/import`, `/review`, `/nachweise`, `/suche` |
| Auswertungen | `/analysen`, `/audit` |
| Stammdaten | `/stammdaten`, `/stammdaten/[bereich]`, `/stammdaten/auswahllisten`, `/stammdaten/auswahllisten/[liste]`, `/partners` |
| Verwaltung | `/admin`, `/admin/deletion`, `/settings`, `/settings/catalogs`, `/settings/organization`, `/settings/users`, `/settings/roles`, `/settings/nummernkreis`, `/sicherheit`, `/system/organizations`, `/profile` |
| Entwicklung | `/developer`, `/developer/components`, `/developer/processing` |
| Zugang | `/login`, `/select-organization` |

## 2. Bausteine, die heute Status zeigen

| Baustein | Heute | Tone-Satz |
|---|---|---|
| `ui/StatusBadge` | Pill + farbiger Punkt (`sb-dot`) + Text | neutral, information, success, warning, critical, review, stale |
| `ui/Badge` | Pill, Text, Farbe | neutral, success, warning, danger, info, ai |
| `ui/InlineAlert` / `className="alert alert--*"` | Kasten mit farbiger linker Kante, Text | neutral, info, success, warning, critical |
| `ui/Toast` | Kasten, Text | success, error, info |
| `ui/KpiTile` (v2) | `tone` färbt Symbol/Wert | neutral, info, success, warning, danger |
| `ui/EmptyState` (v2) | `compact` mit grünem Haken | – |
| `cw-badge` + `cw-badge-red/amber/green` | Pill, Text, Farbe | – |
| `cw-origin-badge cw-origin-*` (ValueOriginBadge, ContractWorkspace, CalculationBasisPanel, ContractBillingPanel) | Pill, Text, Farbe | extracted, reviewed, corrected, calculated, missing, system |
| `evidence-pill(.ok)` (EvidencePane) | Pill, Text, Farbe | – |
| `my-day-pill(--ai/--danger)` (MyDay v2) | Zahl in getönter Pill, **ohne Wort** | – |

Verwendung: `StatusBadge` 28× in 11 Dateien (davon 15 mit dynamischem Ton), `Badge` 16× in 7 Dateien
(3 dynamisch), `InlineAlert` in 22 Dateien, rohe `alert`-Klassen 10× in 5 Dateien.

## 3. Status nur über Farbe oder Unicode-Zeichen (Verstöße gegen R2/R6)

| Ort | Befund |
|---|---|
| `contracts/detail/FactReviewPanel.tsx:265` | `fr-status-dot` / `.ok`: **nur farbiger Punkt** für bestätigt/offen in der Faktenliste |
| `contracts/detail/FactReviewPanel.tsx:262` | Icon-Knopf „✓“ nur mit `title` – zugänglicher Name ist „✓“ |
| `contracts/detail/FactReviewPanel.tsx:274` | „✓ Bestätigen“ (Zeichen + Wort; Zeichen ersetzen durch Form) |
| `admin/SetupChecklist.tsx:38` | `setup-mark` ✓ / ! / ○ farbig, daneben Badge mit Wort |
| `access/PermissionMatrixView.tsx:34` | ✓ / – mit `aria-label`, sichtbar nur Zeichen |
| `work-queue/TaskQueue.tsx:158` | ✓ im leeren Zustand (`state-icon`) |
| `dashboard/MyDay.tsx` | `my-day-date.is-overdue` (rotes Datum; Badge „Überfällig“ steht daneben), `kpi-ok` ✓, Zahl-Pills ohne Wort, KpiTile-Töne |
| `deadlines/DeadlineList.tsx:73` | `rg-row-overdue`: ganze Zeile eingefärbt (Wort „überfällig“ grau daneben) |
| `deadlines/InboxView.tsx:54` | `rg-deadline-overdue`: nur roter Rahmen der Karte |
| `shell/AppSidebar.tsx:85` | `shell-status-dot` (Punkt + Text „Lokale KI …“) – Wort da, Form fehlt |
| `app/admin/page.tsx:144/148` | `activityDot` in Akzentfarbe (Dekoration in Navy, R4) |
| `register/RegisterGrid.tsx:403`, `ui/DataTable.tsx:54` | ▲ ▼ Sortierpfeile – **bleiben** (mit `aria-sort`) |
| `app/styles/components.css:516/517` | `setup-item.is-ok/.is-todo .setup-mark` Farbe |
| `app/styles/components.css:500` | `wizard-steps li.is-done` Schrittnummer eingefärbt |

## 4. `cw-badge-red/amber/green`, `is-overdue`, `is-ok`

| Ort | Bedeutung | heute |
|---|---|---|
| `ContractRegisterPanel.tsx:149–152,453` | Geschäftsstatus in_arbeit / gueltig / gekuendigt / beendet | amber / green / red / red |
| `ContractWorkspace.tsx:30,384` | derselbe Geschäftsstatus im Kopf (`badge--*`) | warning / success / danger / – / – |
| `ContractRenewalBrief.tsx:11–13,84` + `RenewalOverview.tsx:41` | Dringlichkeit Kündigungsfrist missed / critical (≤ 30 T.) / soon (≤ 90 T.) | red / red / amber |
| `DeadlineList.tsx:66` | „N überfällig“ | red |
| `JobMonitorPanel.tsx:58` | Tagesjob veraltet („Prüfen“) | red |
| `ContractAttachmentsPanel.tsx:98` | „Hauptdokument“ / „Ungültig“ | green / grau |
| `PermissionMatrixView.tsx:33` | „Ihr Recht“ | green |
| `MyDay.tsx:99,114` | `is-overdue` (überfällig bzw. ≤ 30 Tage) | rotes Datum |
| `SetupChecklist` / `components.css:516` | `is-ok` | grüner Haken |

## 5. Alte Token-Namen (Aliase in `tokens.css`)

Alle Verwendungen liegen in `app/globals.css` (sonst nirgends): `--sev-*` 29×, `--status-*` 10×,
`--accent` 22×, `--accent-strong/-soft` 11×, `--muted` 10×, `--muted2` 2×.

`--sev-*`/`--status-*` hängen an diesen Klassen:

| Klasse | noch verwendet? | Alias heute |
|---|---|---|
| `.severity-*`, `.badge-active/-expiring_soon/-expired/-terminated`, `.risk-badge/-low/-medium/-high`, `.audit-set/-void`, `.audit-confirm` | **nein** (toter Stil, Phase 9) | sev-critical/high/medium/low/info, status-* |
| `.notice.error` / `.notice.warning` | ja (RegisterPortfolio, ContractRegisterPanel, contracts/new) | sev-critical, sev-high, status-critical |
| `.fact-review` / `.fact-review.ok` | ja (FactReviewPanel, OverridePanel) | sev-high / status-success |
| `.evidence-pill.ok`, `.evidence-note` | ja (EvidencePane) | sev-low / sev-high |
| `.form-ok` | ja (FactReviewPanel, OverridePanel) | status-success |
| `.equipment-name-btn:focus-visible` (Z. 1216–1224) | prüfen in Phase 5 | status-success, sev-high |

Vorschlag Phase 1: `--sev-critical`→danger, `--sev-high/--sev-medium/--sev-warn`→warning,
`--sev-info`→info. `--sev-low` → **success** bleibt, weil sein einziger lebender Nutzer
`.evidence-pill.ok` „exakte Belegposition bestätigt“ bedeutet (done); alle anderen Nutzer sind tot.
`--status-success`→success (Nutzer: `.form-ok` „gespeichert/bestätigt“, `.fact-review.ok` „bestätigt“),
`--status-critical`→danger, `--status-review/-warning`→warning, `--status-stale/-unknown/-neutral`→neutral.

## 6. Umstellungstabelle (Vorschlag)

❓ = Ihre Entscheidung nötig. Alles andere folgt direkt aus R1/R3.

### Bausteine (aus der Anweisung, unverändert)

| Quelle | → Signal |
|---|---|
| StatusBadge critical / warning, review / information / success / neutral, stale | critical / warning / info / done / neutral |
| Badge danger / warning / info / success / ai / neutral | critical / warning / info / done / ai / (ohne Form) |
| Toast error / success / info | critical / done / info |
| InlineAlert critical / warning / info / success / neutral | critical / warning / info / done / neutral |

### Fachliche Zustände

| Ort | Zustand | heute | Vorschlag | Begründung |
|---|---|---|---|---|
| Register/Kopf | Geschäftsstatus `in_arbeit` | amber | **neutral** „In Arbeit“ | Entwurf = neutral (R3) |
| | `gueltig` | green | **neutral** „Gültig“ | Normalzustand ist grau (R1); done nur für Bestätigtes |
| | `gekuendigt` | red | ❓ **neutral** oder info | gekündigt ist ein normaler Endzustand, kein Fehler |
| | `beendet` / `geloescht` | red / – | **neutral** | archiviert/inaktiv |
| Kündigungsfrist | `missed` „Frist verstrichen“ | red | **critical** | verstrichen |
| | `critical` „≤ 30 Tage“ | red | **warning** „in N Tagen“ | R3: ≤ 30 Tage = warning (wird ruhiger als heute) |
| | `soon` „≤ 90 Tage“ | amber | **neutral** „in N Tagen“ | > 30 Tage braucht noch keine Aufmerksamkeit |
| Termine | überfällig (DeadlineList, Inbox, MyDay) | rot / Zeile / Rahmen | **critical** „Überfällig“ neben Datum, Datum normal, keine Zeilenfarbe | |
| | heute fällig | warning-Badge „Heute“ | **warning** „Heute“ | |
| Tagesjob | `stale` | red „Prüfen“ | **warning** „Prüfen“ | R3: stale = warning |
| Anhänge | Hauptdokument | green | ❓ **neutral** oder info | Kennzeichnung, kein Ergebnis |
| | Ungültig | grau | **warning** „Ungültig“ | braucht Prüfung |
| Rechte | „Ihr Recht“ | green | **info** | Hinweis, kein Ergebnis |
| | ✓ / – Matrix | Zeichen | done-Form „erlaubt“ / neutral-Form „nicht erlaubt“, ohne Grün/Rot (Phase 8) | |
| KI-Risiko (ContractBackendAnalysis, Kopf, AiPortfolioNotes, TaskQueue-Schwere) | high/critical | critical | ❓ **warning** „Risiko hoch“ | R3 kennt „KI-Einschätzung“ nicht als critical; critical bleibt für Überfälliges/Fehler |
| | medium | warning | **warning** | |
| | low / info | success | **neutral** | „kein Risiko“ ist nichts zu tun, kein Bestätigtes |
| | unknown | neutral | **neutral** | |
| Policy-Ergebnis (ContractIntelligence) | pass | success | ❓ **neutral** „erfüllt“ oder done | deterministisch geprüft, aber nichts zu tun |
| | fail / violation | critical | ❓ **warning** oder critical | |
| | review / uncertain | warning | **warning** | |
| Vertragsregeln (ContractRulesSection, Grid `rules_status`) | Erfüllt / pass | success | ❓ wie Policy | |
| | Verstoß / fail | critical | ❓ wie Policy | |
| | Unvollständig / unknown | warning | **warning** | fehlende Daten |
| | na | neutral | **neutral** | |
| KI-Werte | „KI-Werte prüfen“ (Kopf), „Prüfung offen“ (AiFillSummary), Herkunft `extracted` | warning / review / Pill | **ai** „KI-Vorschlag“ bzw. „KI-Prüfung“ | unbestätigter KI-Wert |
| | `reviewed`, `corrected`, „Geprüft“, Fakt bestätigt (`fr-status-dot.ok`, `.fact-review.ok`) | Pill / grün / Punkt | **done** „Bestätigt“ / „Korrigiert“ | bestätigtes Ergebnis |
| | Fakt offen (`fr-status-dot`) | Punkt | **ai** „KI-Vorschlag“ | |
| | `calculated`, `system` | Pill | **neutral** | |
| | `missing` „Fehlt“ | Pill | **warning** | fehlende Daten |
| Beleg (EvidencePane) | exakte Position | grün | **done** | |
| | ohne exakte Position | grau | ❓ **neutral** oder warning | |
| Verarbeitung (/developer/processing, /import) | succeeded / imported | success | **done** | |
| | queued/pending | neutral | **neutral** „wartet“ | |
| | running | neutral | **info** „läuft“ | |
| | partial | warning | **warning** | |
| | failed / rejected / analysis_failed | critical | **critical** | |
| | duplicate | warning | ❓ **info** oder warning | Dublette ist erkannt und nicht importiert; nichts kaputt |
| KI-Modell (/settings) | Bereit | success | ❓ **done** oder neutral | getesteter Zustand |
| | Nicht ausgewählt | neutral | **warning** | System kann nicht analysieren (fehlende Einstellung) |
| | Nicht verfügbar / Nicht erreichbar | warning / critical | **critical** beide | Analyse nicht möglich |
| Seitenleiste | „Lokale KI bereit“ (`shell-status-dot`) | grüner Punkt | **neutral** Form + Text; nur bei Ausfall **critical** | R1 |
| Geräte | Identifikation exakt / sonst | success / review | **done** / **warning** | |
| | Lebenszyklus active / maintenance_due / sonst | success / warning / neutral | **neutral** / **warning** / **neutral** | |
| Einrichtung (SetupChecklist) | ok / todo / optional | success / warning / neutral | **done** / **neutral** „Offen“ / **neutral** | Phase 8 der Anweisung |
| Stammdaten | Aktiv / Deaktiviert | success / – | **neutral** / **neutral** (Wort trägt) | R1 |
| | Vertraulich | warning | ❓ **info** oder neutral | Eigenschaft, kein Handlungsbedarf |
| CSV-/Benutzerimport | Zeile in Ordnung | success | **done** | geprüft |
| | Zeile mit Fehler | Fehlerliste rot | **critical** + Meldung | Phase 6 |
| Aufgaben (TaskQueue) | „Manuelle Prüfung“ | review | **warning** | |
| | Status der Aufgabe | neutral | **neutral**; erledigt → **done** | |
| Mein Tag (v2 → v3) | Handlungsbedarf `no_end` | rot | **critical** „Kritisch“ | macht Vertragsende/Frist unberechenbar |
| | `no_responsible`, `notice_no_reminder`, `no_finance`, `deletion_due` | amber | **warning** „Prüfen“ | fehlende Daten |
| | offene KI-Prüfung | violett | **ai** „KI-Prüfung“ | |
| | KPI-Kacheln | Töne | neutral; nur `signal` (z. B. „Kosten fehlen bei N Verträgen“) | Phase 3 |

### Weitere Funde für spätere Phasen

- Icon-Knopf „✓“ in FactReviewPanel braucht `aria-label="Bestätigen"` (R6).
- `activityDot` (Admin) in Navy → `--color-icon` (R4).
- Toter Stil mit Status-Aliasen (s. Abschnitt 5) wird in Phase 9 entfernt.

## 7. Offene Fragen an Sie

1. Geschäftsstatus `gekuendigt`: neutral oder info?
2. „Hauptdokument“: neutral oder info?
3. KI-Risiko hoch: warning (Vorschlag) oder critical?
4. Policy/Vertragsregel erfüllt: neutral (Vorschlag) oder done? Verstoß: warning oder critical?
5. Beleg ohne exakte Position: neutral (Vorschlag) oder warning?
6. Import-Dublette: info (Vorschlag) oder warning?
7. KI-Modell „Bereit“: done oder neutral?
8. „Vertraulich“: info (Vorschlag) oder neutral?
