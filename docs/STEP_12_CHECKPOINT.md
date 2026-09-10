# Medflux — STEP 12 Checkpoint (Production-Grade Procurement Dashboard)

Datum: 31.08.2026 · Fortschritt: **12 / 18 = 66,7 %**

STEP 12 liefert ein ernsthaftes, krankenhaus-taugliches Operations-Dashboard
(„Übersicht") für Einkauf/Finanzen/Vertragsmanagement. Es beantwortet die
Kernbeschaffungsfragen: Welche Wartungsverträge haben wir, was kosten sie, wo
besteht jetzt Handlungsbedarf, welche Kündigungs-/Verlängerungsentscheidung
steht als Nächstes an und wie zuverlässig sind die Daten?

## 1. Produkt-Zweck & Design-Prinzip

Priorität (nicht dekorativ):

```
ACTION -> DEADLINE -> FINANCIAL IMPACT -> CONTRACT -> EVIDENCE/DATA QUALITY
```

Der visuell prominenteste Bereich ist **HANDLUNGSBEDARF**. Das Dashboard ist
ein Beschaffungs-/Vertrags-Arbeitstool, kein allgemeines EXEC-BI-Board.

## 2. Forschung & Design-Rationale

- Deutschsprachige Krankenhaus-Verwaltung: mehrere deutschen Datensätze hinterlegt
  (DB: 375+ Bestandstests, PG 18.6; Frontend Next 14 App-Router).
- **Keine dekorativen Charts:** Für eine kleine Fristen-Verteilung rechtfertigt ein
  Chart-Lib keinen Nutzen; eine kompakte, semantische HTML-Balkenliste ist
  verlässlicher und eben zugänglicher (§11).
- **Keine Server-State-Lib nötig:** Das Dashboard ist ein einzelner Read-only-Fetch;
  ein simpler `useEffect`-Fetch hat minimales Client-JS (§12-Wunsch „weniger
  Client-JavaScript").
- **TanStack Table v9** ist eine bewertete Option für die STEP-13-Vertragsliste,
  NICHT für den kleinen Handlungsbedarf (§13).

## 3. Dashboard-Architektur

```
HTTP GET /api/dashboard/overview?organization_slug=...&as_of_date=YYYY-MM-DD
        -> Route (Grenze: as_of_date explizit aufloesen, org aufloesen, org-bound)
        -> build_dashboard_overview(session, organization_id, as_of_date)
           (READ-ONLY, no write, low-queries)
        -> DashboardOverview (Pydantic-DTO, validiert)
```

Backend:
- `app/dashboard/models.py` – getrennte, explizit getypte Response-DTOs
  (`DashboardOverview`, `KpiCard`, `ActionItem`, `DeadlineBucket`,
  `FinancialSummary`, `DataQualityItem`, `DataFreshness`).
- `app/dashboard/service.py` – `build_dashboard_overview()`: deterministischer,
  org-gebundener Lese-Dienst (KEINE Schreiboperation, KEINE KI).
- `app/api/routes/dashboard.py` – dünne Route; löst `as_of_date` an der
  API-Grenze (kein verstecktes `date.today()` in der Fachlogik) und die
  Organisation (`organization_slug` → org.id) server-seitig.

## 4. Datenquellen / Akzeptanz-Semantik

Aggregiert NUR den aktuell akzeptierten Zustand:
- `contract` (Projektions-Zeiger: `accepted_calculation_run_id`,
  `accepted_extraction_id`, `status`/`risk_level` als Current-Projektion),
  gefiltert `lifecycle_state == 'active'` (nicht gelöscht).
- akzeptierte STEP-9-Berechnung: `calculation_run.result_snapshot` →
  `ContractCalculationResult` (nur der AKZEPTIERTE Lauf; **nie** fehlgeschlagen/
  abgelehnt/superseded).
- akzeptierte Extraktion: `contract_extraction.contract_snapshot` (nur für
  `total_contract_value` als `Money`; STEP 9 trägt dort nur den Status).
- aktive STEP-11-Warnungen: `contract_warning` mit `active = TRUE`.

NEIN: keine KI im Dashboard, keine Neuberechnung von Warnungen/Fristen im
Dashboard (Warn-Semantik kommt ausschließlich aus der materialisierten
STEP-11-Projektion, es wird kein zweiter Warn-Engine in SQL/Frontend
geschrieben).

## 5. Daten-Frische (§4) – explizit & nicht still

STEP 11 nutzt bewusst explizite `as_of_date`. Die persistierten Warn-/Status-
Projektionen beziehen sich auf den Stichtag der letzten `run_warning_evaluation`.
Das Dashboard **zeigt veraltete Dringlichkeit nie still als aktuell**:

- `freshness.requested_as_of_date` = angefragter Stichtag.
- `freshness.warning_evaluation_as_of_date` = max. `as_of_date` aller
  Warn-Evaluationsläufe der Org.
- `freshness.data_freshness` = `current` / `stale` / `none`.
- UI zeigt im Kopf „Datenstand: … · Warnungen bewertet zum … (veraltet)".

Der GET-Request führt **keine dauerhaften Zustands-Mutationen** durch (read-only).

## 6. KPI-Definitionen (eine autoritative Backend-Definition)

| KPI | Definition |
|---|---|
| **Aktive Verträge** | Anzahl Verträge mit `contract.status ∈ {active, expiring_soon}` (Operatives Portfolio; TERMINATED/EXPIRED ausgeschlossen). Unterwerte: aktiv vs. bald auslaufend. |
| **Bald auslaufende** | Anzahl distinkte Verträge mit aktiver `CONTRACT_END_APPROACHING`-Warnung (STEP-11-Semantik, keine eigene 90-Tage-Regel). |
| **Kritische Kündigungsfristen** | Anzahl distinkte Verträge mit aktiver `CANCELLATION_DEADLINE_TODAY`/`PASSED` oder `APPROACHING` bei kritischem Schweregrad. Keine Kündigungs-/Terminierung-Annahme aus verstrichener Frist. |
| **Jährliche Gesamtkosten** | Anzahl Währungen mit verlässlicher jährlicher Kosten (mehr dazu §8). |
| **Gesamtvertragswert** | Anzahl Währungen mit verlässlich erfasstem `total_contract_value`. |

KPI-Logik existiert NUR im Backend (keine Duplikierung in React).

## 7. HANDLUNGSBEDARF (primäre Queue)

Kompakte, priorisierte Queue aus aktiven STEP-11-Warnungen
(`requires_action` oder `requires_review`), deterministisch sortiert nach
STEP-11-Semantik (Severity → Typ-Priorität → Ziel-Datum → Fingerprint):

1. verstrichene/heutige Kündigungsfristen (critical),
2. sehr nahe Kündigungsfristen (critical),
3. Auto-Verlängerungs-Entscheidungen (medium),
4. bevorstehende Vertragsenden,
5. materielle Konflikte/manuelle Prüfungen (review).

Jedes Element: Severity-Textlabel, deutscher Titel, Vertragstitel/-Nr.,
Lieferant, Ziel-Datum, Tage-Rest/überfällig, Typ, verlässliche Jahreskosten
als Kontext (§7). **Finanzwert überschreibt nie rechtliche/zeitliche Dringlichkeit**;
bei unzuverlässiger Kostenlage „Kosten nicht verlässlich ermittelt".
`total_action_items` = Gesamtzahl; geliefert werden maximal **top 12**
(`ACTION_QUEUE_LIMIT`). Vollständige Liste = STEP 13. Kein zweites Frontend-
Prioritätssystem; genutzt wird die persistierte/aktuelle Warn-Identität
(`logical_fingerprint`, keine Duplikate).

## 8. Finanzielle Aggregation / Mehrwährung

Aus der AKZEPTIERTEN STEP-9-Berechnung (`normalized_recurring.annual`):
- verlässlich nur wenn `value` + `currency` vorhanden, Status
  `CALCULATED|EXPLICIT`, KEIN `recurring_cost_conflict`, KEIN
  `currency_conflict`.
- Summe pro Währung (`MoneyTotal`); **nie** Währungen mischen, **kein** FX,
  **nie** unbekannt als 0, **keine** MwSt-Annahme.
- `financial.multi_currency = true` → UI „Mehrere Währungen – getrennt
  ausgewiesen".
- Ausgeschlossene Verträge werden **explizit** gezählt
  (`contracts_without_reliable_annual_cost`, `contracts_without_reliable_total_value`).

**Gesamtvertragswert:** nur STEP-9-`total_contract_value_status == CALCULATED`
UND `total_contract_value.amount/currency` aus der akzeptierten Extraktion.
Keine neue Finanzformel in STEP 12 (kein `annual × Dauer`), unknown ≠ 0.

## 9. FRISTENÜBERSICHT

Verteilung über die STEP-11-Policy-Buckets (Kalendertage): **Verstrichen, Heute,
7, 14, 30, 60, 90, 180** – kompakt als semantische Balkenliste. Kündigungsfristen
sind von reinen Vertrags-Enden getrennt (Spalten `cancellation` vs. `contract_end`);
**nie nur Farbe** (Zahlen immer lesbar).

## 10. MANUELLE PRÜFUNG / DATENQUALITÄT

Aus aktiven STEP-11-Warnungen, kompakte Zähler: Unklare Vertragsdaten,
Berechnungskonflikte, Kostenkonflikte, Fehlende Kostenangaben, Währungskonflikte.
Keine Extraktions-Validierungslogik dupliziert; finanziell ausgeschlossene
Verträge werden in der Kostenübersicht explizit sichtbar.

## 11. Chart-/Library-Entscheidung

- **Apache ECharts: NICHT hinzugefügt.** Es gibt keine vorhandene Chart-Lib und
  keine Entscheidungs-Verbesserung rechtfertigt die Abhängigkeit; die kleine
  Fristen-Verteilung ist zuverlässiger als semantisches HTML (§11). Kein CDN,
  keine externen Assets – alles lokal.
- **TanStack Query: NICHT hinzugefügt.** Ein einziger Read-only-Fetch braucht
  keine Server-State-Schicht. Natives `fetch` via `apiGet` (weniger Client-JS).
- **TanStack Table v9: für STEP 13 evaluiert, NICHT in STEP 12** (kleine Queue
  = zugängliches HTML).
- Keine Cloud-Analytics, kein externes Font (system-ui), kein Remote-Script.

## 12. Frontend-Aufbau

- `app/page.tsx` – Übersicht (Client-Komponente, fetch + Zustände).
- `components/dashboard/KpiCard.tsx`, `ActionList.tsx`,
  `DeadlineDistribution.tsx`, `FinancialOverview.tsx`, `DataQuality.tsx`
  – wiederverwendbare Primitive statt einzeln gestylter Karten.
- `lib/dashboard-types.ts` – TS-Abbild der DTOs; `lib/format.ts` – deutsche
  Präsentationshelfer (ID-Nummer → DD.MM.YYYY, Intl-Währung „42.500,00 €",
  „in 14 Tagen"/„heute"/„seit 3 Tagen überfällig").
- `lib/api.ts` (bestehend) für den Fetch.
- Navigation: Layout mit **Übersicht** (aktiv), **Import** (Link),
  **Verträge**/**Einstellungen** als NICHT verlinkbare Platzhalter (keine
  kaputten Links; STEP 13/16).
- Keine globalen Browser-Persistenz von Sensiblen (kein localStorage/
  sessionStorage/IndexedDB).

## 13. Zugänglichkeit (WCAG 2.2 AA ausgerichtet)

- Semantisches HTML, korrekte Überschriften-Hierarchie (h1 → h2; KPI-/Geld-
  Labels als non-heading), sichtbarer Fokus (`:focus-visible`), keine Traps.
- Span-deutscher `lang="de"`, deutsche UI-Texte.
- Severity: immer Text-Label („Kritisch") + unterstützende Farbe, nie Farbe allein;
  `visually-hidden`-Statusbeschreibungen für KPI/role=status.
- `prefers-reduced-motion` respektiert; minimale Animation.
- Automatischer a11y-Test via **jest-axe** (`axe(container)` →
  `toHaveNoViolations`) im normalen Zustand; Lade-/Fehler-/Leer-/teilweise
  Daten-/Mehrwährungs-/Kritisch-/Überfällig-/deutsche-Formatierung-Zustände
  getestet. **Keine WCAG-Zertifizierung behauptet.**

## 14. Sicherheit / Datenschutz / API

- Organization-Ownership: alle Dashboard-Abfragen org-gebunden; `organization_slug`
  wird server-seitig aufgelöst; DTO minimal (keine DB-IDs von Verträgen, kein
  OCR/Vertragstext/Modellinterna/Pfade/Credentials).
- Keine externen Assets; kein Analytics/Telemetrie; kein Vertragstext in
  Konsole-Logs; Backend-Fehler → generischer deutscher Text („Dashboard konnte
  nicht geladen werden.") mit Sicherer interner Diagnose.
- Typisierte Validierung der Query-Parameter; SQLAlchemy-parametrisiert; Ergebnis
  bounded (kein ALL-Contracts-Abruf).
- Sicherheits-Header per `next.config.js`: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`,
  `Permissions-Policy`, `CSP: frame-ancestors 'none'`. Ein vollumfängliches
  restriktives `default-src`-CSP würde die aktuelle App (Inline-Styles, Cross-
  Origin-Dashboard-Fetch) brechen → wird zusammen mit Auth/STEP 16 realisiert.
  Build-Verhalten mit Headers getestet (produktiv kompiliert).
- KEIN Fake-Role/Fake-User/Owner-FK; STEP 16 übernimmt Auth vollständig.
  Dashboard-Query bleibt sauber für spätere server-seitige Autorisierungsfilter
- (§21: Einkauf/IT/Finanzen/Vertragsmanagement/Administration dokumentiert).

## 15. Datenbank / Query / Performance

- Wenige, gebundene Abfragen statt N+1: Verträge (org+lifecycle) → aktive
  Warnungen (IN contract_ids) → akzeptierte CalculationRuns (IN calc_ids) →
  akzeptierte Extraktions-Snapshots (IN ext_ids) → max Warn-eval-Stichtag.
- Kein SELECT-alle-dann-Python-Aggregat, wo SQL es kann; ABER ES wird STEP-9/11-
  Fachlogik NICHT in SQL neu geschrieben.
- Bestehende Indexe genutzt; **keine neue Schema-/Index-Migration** nötig –
  STATUS aller vorhandenen Tabellen unverändert. Kein Redis/Elasticsearch/Bi-Server.

## 16. Tests

**Backend – `tests/test_dashboard.py` (24 Tests, PG-Transaktion-pro-Test):
- leerer Datenbestand; aktives Portfolio inkl. expiring_soon; TERMINATED/EXPIRED
  ausgeschlossen; expiring_soon-Semantik; kritische Kündigungsfristen-Zählung;
  verstrichene Frist korrekt + KEINE Terminierung-Inferenz; Jahreskosten-
  Aggregation; Mehrwährungs-Trennung; fehlende Kosten ≠ 0 (ausgeschlossen &
  gemeldet); Kostenkonflikt ausgeschlossen & gemeldet; Gesamtvertragswert-
  Semantik; nur akzeptierter Lauf / superseded ausgeschlossen; Organisations-
  Isolation; Handlungsbedarf-Reihenfolge; Queue-Limit (≤12 bei >12); kein
  Duplikat in der Queue; kein Handlungsbedarf; Determinismus bei explizitem
  Stichtag; stale/fresh-Verhalten; kein unbegrenztes Payload; partielle Daten;
  manueller-Review-Zähler; Fristen-Bucket-Verteilung; Vertrag ohne Warn-Auswertung.

**Frontend – `test/dashboard.test.tsx` (11 Tests, Vitest + RTL + jest-axe):
Laden, Fehler, leeres Kontingent, normaler Inhalt, deutsche Währungs-/Datums-
Formatierung, überfällige Frist textuell, kritischer Handlungspunkt, unzuverlässige
Kosten, mehrere Währungen, automatischer a11y-Check (`toHaveNoViolations`).

## 17. Typecheck/Lint/Build/Frontend-Tests

- `tsc --noEmit`: grün. Test-/Vitest-Dateien sind aus dem Next-Build-Typcheck
  ausgenommen (`tsconfig.exclude` – Standard-Next-Pattern; Vitest rümpft Typen).
- `npm run lint` (neu: `eslint`+`eslint-config-next@14.2.15`+`.eslintrc.json`):
  **No warnings or errors.**
- `npm run test`: **11 passed**.
- `npm run build`: produktiver Next-Build kompiliert, statische Routen `/` und
  `/import` erzeugt; Sicherheits-Header-Konfiguration kompiliert.

## 18. Volle Backend-Regression

**399 passed, 0 Failures** (Baseline 375 + 24 Dashboard), 5 benigne
PyMuPDF-SWIG-Warnungen. Keine Regressionen.

## 19. Bekannte Grenzen / bewusst NICHT in STEP 12

- Kein volle STEP-13-Liste/Suche/Filter – Handlungsbedarf ist auf top 12
  begrenzt; `total_action_items` liefert die Gesamtzahl.
- Kein STEP-14-Document-Viewer/Drill-Down (keine kaputten Links).
- Operator-/: `action_state`-Transitionen (acknowledge etc.), Owner/Escalation,
  Notification, volles RBAC = später (STEP 16).
- Kein vollumfängliches CSP (nur frame-ancestors) bis Auth/STEP 16; Inline-Styles
  der bestehenden Import-Seite unverändert.
- `organization_slug` ist der aktuelle, reine Scoping-Schlüssel (lokal/on-prem);
  eine echte Auth-Schicht übernimmt STEP 16.

## 20. STEP-13-Erweiterungspunkte

- Die Action-Queue und KPI-Karten sind so modelliert, dass spätere Filter
  (Stephan 13) und Detail-Navigation (Stephan 14) server-seitig angebunden
  werden können; die DTOs enthalten stabile, fachliche Referenzen, keine
  fragilen UI-Pfade. TanStack Table v9 ist für STEP-13 evaluiert.

## Nächster Schritt

- **STEP 13 – Vertragsliste / Suche / Filter**. **STOP – kein STEP-13-Start in
  dieser Sitzung.**
