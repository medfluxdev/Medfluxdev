# Medflux — STEP 13 Checkpoint (Production-Grade Contract Portfolio / Search / Filter)

Datum: 31.08.2026 · Fortschritt: **13 / 18 = 72,2 %**

STEP 13 liefert die produktionsreife Vertrags-Portfolio-Liste („Verträge") mit
PostgreSQL-gebundener Suche, strukturierten Filtern, deterministischer
Sortierung, Zählern/Facets und Pagination. Es ist das operative Gegenstück zum
STEP-12-Dashboard: Dort „Handlungsbedarf + Kenngrößen", hier die **vollständige,
durchsuch- und filterbare Vertragsliste** – die Grundlage für die spätere
STEP-14-Detailnavigation.

## 1. Produkt-Zweck & Design-Prinzip

Die Vertragsliste beantwortet: „Welche Verträge haben wir und wo genau steckt
der nächste Handlungsbedarf?" Kernanforderungen:

- **Vollständigkeit** – nicht auf top 12 begrenzt (anders als die STEP-12-Queue).
- **Auffindbarkeit** – Suche über Metadaten (Nummer, Titel, Lieferant, Geräte).
- **Steuerbarkeit** – strukturierte Filter, effizient, deterministisch.
- **Verlässlichkeit** – nie erfundene Werte; fehlende/inkonsistente Finanzdaten
  werden als solche ausgewiesen, nie stumm als 0 € oder aktuell angezeigt.

Design-Prinzip: **PostgreSQL ist die Suchplattform** (kein separater Such-Dienst,
keine Volltext-Suche über OCR-Bodies, kein zweiter Volltext-Kopie kompletter
Verträge). Gesucht wird ausschließlich **Vertrags-Metadaten** – schlank,
org-gebunden, deterministisch.

## 2. Forschung & Design-Rationale

- **PostgreSQL-first statt Such-Service:** Für ein lokales, on-prem,
  krankenhaus-internes MVP ist ein separater Such-Server (Elasticsearch,
  Meilisearch, Typesense, Redis, Vector-DB) nicht gerechtfertigt. Postgres 18
  liefert FTS (GIN-tsvector), pg_trgm (Typo-Toleranz), GIN- und btree-Indexe –
  ausreichend für Metadaten-Portfolios bis produktionsnaher Größe. Keine
  Cloud-/Extern-Abhängigkeit.
- **Stored `search_vector` statt externem, eventually-consistenten Index:**
  Determinismus und Zero-Sync-Risiko. Der generierte tsvector ist per Definition
  immer synchron mit dem Current-State der `contract`-Projektion.
- **Identifikatoren nicht stemmen:** `contract_number` nutzt die `simple`-TS-Config
  (keine linguistische Stemmung auf Kennungen, §5); `supplier`/normalisierte
  Titel-Nutzung nutzt `german`, ohne Vertragstext-Körper zu indexieren.
- **pg_trgm als vertrauenswürdige Erweiterung:** DB-Owner (`medflux`, kein
  Superuser) kann ohne Superuser-Rechte `CREATE EXTENSION pg_trgm` ausführen –
  Deployment-Kriterium verifiziert (§35). Fuzzy nur ab **3 Zeichen**; exakt und
  Präfix rangieren immer vor fuzzy.
- **TanStack Table v9** wurde erneut evaluiert: Für eine server-seitig sortierte
  Liste (≤ 100 Zeilen/Seite ohne Virtualisierung) ist semantisches HTML mit
  kleinen Komponenten simpler, zugänglicher und ohne Zusatz-Abhängigkeit. Nicht
  benötigt, solange keine Messung einen Bedarf zeigt (§21).

## 3. Sucharchitektur

```
HTTP GET /api/contracts?organization_slug=...&q=...&status=...&sort=...&page=1&page_size=25
        -> Route (typf. Parameter, Allowlist-Validierung, org aufloesen, as_of aufloesen)
        -> build_contract_search(session, SearchParams, organization_id, request_as_of)
           (READ-ONLY, org-bound, max. 6 Queries / Seite, keine Joins -> keine Duplikate)
        -> ContractListResponse (Pydantic-DTO)
```

Backend:
- `app/contracts/search/models.py` – minimale, getrennt getypte Response-DTOs
  (`ContractListResponse`, `ContractListItem`, `ContractFinance`,
  `ContractWarningSummary`, `ContractFacets`, `SearchFreshness`).
- `app/contracts/search/service.py` – `build_contract_search()`: deterministischer
  Lese-Dienst; Filter/Ranking/Sortierung ON the DB, aggregierte Zähler-Facets,
  gebundene Folge-Queries (kein N+1).
- `app/api/routes/contracts.py` – dünne GET-Route (PREFIX `/api/contracts`),
  typisierte Query-Params, Allowlists → 422, Register in `app/main.py`.

## 4. Ranking (q-teilweise deterministisch)

Ein numerisches `CASE` markiert Treffer; niedriger Rang = besser; `else_ = NULL`
(kein Match → wird gefiltert):

| Tier | Treffer |
|---|---|
| 0 | exakte `contract_number` |
| 1 | Präfix `contract_number` |
| 2 | exakter Titel (akzeptierte Extraktion `identity.contract_title`) |
| 3 | exakter Lieferant |
| 4 | Titel enthält (small JSONB-Subquery, dokumentiert) |
| 5 | Lieferant-Präfix |
| 6 | Geräte-Treffer (`contract_equipment`-Konkatenation) |
| 7 | FTS `search_vector @@ plainto_tsquery('german', q)` (injektionssicher) |
| 8 | fuzzy (pg_trgm-Similarität, min. 3 Zeichen) |

## 5. Freitext-Matching

- `plainto_tsquery('german', q)` ist injektionssicher (kein rohes SQL).
- Präfix-/fuzzy-Matching auf Kennungen/Lieferant bewusst **ohne Stemmung**.
- LIKE-Wildcards werden escaped (`%`, `_`, `\`) gegen Wildcard-Abuse (§28).
- Equipment: GIN-trigram-Index über `(device_name, system_name, model,
  manufacturer, serial_number)`-Konkatenation unterstützt `ILIKE '%q%'`; fuzzy
  über `similarity()` konservativ.
- Leere/Whitespace-Anfrage → keine Freitext-Bedingung; 1–2-Zeichen-Terme
  erzeugen **keinen** Fuzzy-Scan.

## 6. Filter-Semantik (server-seitig, org-gebunden)

- **Status** (multi-select OR), **Risiko** (multi OR), **Warn-Typ** (multi OR via
  EXISTS), **requires_action/requires_review**, **critical_cancellation**
  (Heute/Verstrichen ODER Annäherung bei kritischem Grad), **automatic_renewal**
  (akzeptierte Extraktions-JSONB `termination.automatic_renewal` = true/false),
  **supplier** (case-insensitive exakt), **Datumsbereiche** (Start aus akzeptierter
  Extraktion `dates.start_date.date`; Ende/Kündigungsfrist aus akzeptierter
  Berechnung `dates.calculated_end_date.value`/`latest_cancellation_date.value`),
  **Jahreskosten min/max + Währung** (akzeptierte Berechnung
  `costs.normalized_recurring.annual`).
- Kategorien-übergreifend **AND**, innerhalb einer Multi-Select-Kategorie **OR**;
  Missing ≠ 0/false/empty. Alle Abfragen org-gebunden auf Query-Ebene
  (kein Python-Nachfilter), also cross-Organisations-sicher.

## 7. Finanz-Sicherheit (§10)

Nur **verlässliche** Jahreskosten werden für Kosten-Filter/Anzeige verwendet:
`value` + `currency` vorhanden, Status `calculated|explicit`, KEIN
`currency_conflict` – gelesen mit `jsonb_extract_path_text` (explizit,
parametrisiert). Niemals Währungs-Mix/FX/MwSt; konflikt- oder unbekannt →
ausgeschlossen und als „Nicht eindeutig"/„Nicht verfügbar" gekennzeichnet
(**nie** 0 €).

## 8. Warn-Semantik (§11)

Filter auf `contract_warning` nutzen **EXISTS/Subqueries** (kein Join → keine
Duplikat-Zeilen). Verstrichene Kündigungsfrist impliziert **nicht** terminated/
renewed/cancelled. Keine Duplikats-Entscheidung, kein zweiter Warn-Engine.

## 9. Daten-Frische (§12)

Identisches Muster wie STEP 12: `freshness.warning_evaluation_as_of_date` = max
`warning_evaluation_run.as_of_date` der Org; `data_freshness` = `current`/`stale`/
`none`. GET bleibt read-only (keine stillen Warn-Persistierungen).

## 10. Sortierung / Pagination / Facets

- **Sortier-Allowlist:** `relevance` (nur mit q), `title`, `supplier`, `end_date`,
  `cancellation_date`, `annual_cost`, `risk`, `updated_at`; `direction` asc/desc.
- **Operationaler Default** (ohne explizite Sortierung): Dringlichkeit (höchste
  aktive Warn-Severity als CASE-Subquery, Fallback risk-level) → nächstes
  relevantes Datum → Titel → `id`. Nie Browser-Sortierung.
- **Pagination:** OFFSET/LIMIT (bei Ranking fragil für Cursor), `page_size ∈
  {25,50,100}`, hartes Max 100, bidirektional gebunden, pathologische Offsets
  → 422; `total_count` + `has_more`.
- **Facets:** eine Aggregate-Query über die gefilterte Basis mit
  `count(*) FILTER (WHERE ...)` für `total`, `status_counts`,
  `requires_action`, `requires_review`, `critical_cancellation` – org-gebunden
  und Filter-respektierend.

## 11. Query-Architektur / Performance

Keine Joins (nur EXISTS/scalar-Subqueries auf `Contract`) → keine Duplikat-Zeilen.
Pro Seite gebundene, kleine Abfragen: (1) Seite `Contract`-ORMs, (2) aktive
`contract_warning` IN-ids, (3) `calculation_run` IN-ids, (4)
`contract_extraction` IN-ids, (5) `contract_equipment` IN-ids, (6) ein
Aggregate-Counts-Query. **Kein N+1.**

## 12. Migration / Schema

Neue Revision **`a3f9c1127305`** (down_revision `81aa19e5d946`):
- `CREATE EXTENSION IF NOT EXISTS pg_trgm` (trusted, ohne Superuser).
- Generierte `search_vector`-Spalte (STORED) auf `contract` mit Weights
  `contract_number`=A/`simple`, `supplier`=B/`german`, `status`=C/`simple`.
- Indexe: `ix_contract_org_lifecycle` (org,lifecycle), `ix_contract_org_status`
  (org,status), `ix_contract_org_end_date` (org,end_date), `ix_contract_search_vector`
  (GIN), `ix_contract_supplier_trgm` (GIN trgm), `ix_contract_number_trgm` (GIN trgm),
  `ix_contract_equipment_trgm` (GIN auf Geräte-Konkatenation),
  `ix_contract_warning_org_active` (org,contract_id,active).
- **upgrade → downgrade → re-upgrade auf PostgreSQL 18.6 verifiziert**; aktueller
  DB-Head = `a3f9c1127305`. ORM: `search_vector` als Computed-Column (TSVECTOR)
  in `app/database/models/contract.py`.

## 13. Frontend-Aufbau

- `app/contracts/page.tsx` – „Verträge" (Client, `useSearchParams`-URL-State mit
  Suspense-Boundary, Debounce 300 ms, Race-Handling via Request-ID).
- `components/contracts/ContractTable.tsx` – semantische Tabelle.
- `components/ClientNav.tsx` – aktive-Navigation über `usePathname`; „Verträge"
  aktiviert → `/contracts`.
- `lib/contract-types.ts` – TS-DTO-Abbild; `lib/format.ts` erweitert
  (`formatAnnualCost`, Status-/Risiko-Labels).
- Quick-Filter (Kritische Kündigungsfrist, Auto-Verlängerung, Handlungsbedarf,
  Manuelle Prüfung), Advanced-Filter (Status, Risiko, Lieferant, Währung,
  Kosten-, Datumsbereiche), aktive Filter, Result-Summary, Sortierung,
  Pagination, Zustände (Laden/Fehler/leer/keine-Treffer).
- URL-Query-State: Back/Forward/Reload/Bookmark-fähig; **keine** lokale
  Speicher-Persistenz, keine OCR-Snippets in URLs.

## 14. Zugänglichkeit (WCAG 2.2 AA ausgerichtet)

`lang="de"`, semantische Such-/Filterform, keyboard-fähige Filter/Chips,
Tabellen-Header mit `scope`, sichtbarer Fokus, kein color-only (Severity/Risiko/
Status immer mit Text-Label), zugängliche Pagination, aussagekräftige
Lade-/Leer-/Fehler-/keine-Treffer-Zustände, `prefers-reduced-motion`. Automatischer
a11y-Check via jest-axe im Normalzustand. Keine WCAG-Zertifizierung behauptet.

## 15. Sicherheit / Datenschutz / DoS / API

- **Org-Isolation** auf Query-Ebene; `contract_id` (uuid) in DTO ist ein stabiler,
  opaque STEP-14-Navigationsschlüssel – **nie** visuell gerendert.
- DTO bounded; **kein** OCR/Body/Pfade/Credentials/DB-Interna.
- DoS-Härtung: Query max. 200 Zeichen, `page_size`-Bounds, Offset-Bounds, Anzahl
  Multi-Select-Werte begrenzt, LIKE-Escaping, kein Fuzzy für kurze Terme,
  parametrisierte Queries, Allowlist-Enums → 422, generischer deutscher Fehler-
  Text (kein Stack/SQL-Leak). Sicherheits-Header/CSP aus STEP 12 **nicht**
  geschwächt. `organization_slug` bleibt reiner Routing-/Context-Scope (keine
  Auth-Credential; Autorisierung folgt STEP 16).

## 16. Tests

**Backend – `tests/test_contract_search.py` (36 Tests, PG-Transaktion-pro-Test,
autoskip ohne DB):** leerer Bestand; exakte Nr./Titel-Suche; exakte Kennung
rangiert vor substring/FTS; Lieferanten-Suche; Geräte-Suche; FTS-Verhalten;
fuzzy; exakt rangiert vor fuzzy; leere/Whitespace-/sehr kurze Anfrage; max.
Query-Länge; SQL-Injection-artige Eingabe; Status-Filter; Multi-Status-OR;
Warn-/Handlungsbedarf-/Kritisch-Kündigungsfrist-Filter; requires_review;
automatic_renewal; Lieferanten-Filter; Start-/Ende-/Kündigungs-Datumsbereiche;
Jahreskosten min/max; Währungs-Isolation; fehlende Kosten ≠ 0 & ausgeschlossen;
Konflikt ausgeschlossen; kombinierte AND-Semantik; Sortierung; deterministischer
Tie-Breaker; page_size-Bounds; Pagination-Stabilität; keine Duplikate aus
Warn-EXISTS; reliable-cost-Reporting; Org-Isolation (inkl. cross-org
FTS/Filter/Zähler-Angriffe); bounded DTO; Route: 422 bei ungültigem page_size/
sort, 404 bei unbekannter Org.

**Frontend – `test/contracts.test.tsx` (11 Tests, Vitest + RTL + jest-axe, mit
`apiGet`-Mock + `next/navigation`-Mock):** Laden; Fehler; leeres Kontingent;
keine-Treffer; normaler Inhalt; deutsche Währungs-/Datums-Formatierung; fehlende
Kosten als „Nicht eindeutig" statt 0 €; Mehrwährungs-Trennung; Warn-Severity
textuell statt nur Farbe; veraltete Warn-Bewertung; Quick-Filter → URL → Refetch;
automatischer a11y-Check.

## 17. Typecheck / Lint / Build / Frontend-Tests

- `tsc --noEmit`: grün (Test-/Vitest-Dateien via `tsconfig.exclude` aus dem
  Next-Build-Typcheck ausgenommen – Standard-Next-Muster; Vitest rümpft Typen).
- `npm run lint`: **No ESLint warnings or errors.**
- `npm run test`: **11 passed.**
- `npm run build`: produktiver Next-Build kompiliert; statische Route
  `/contracts` erzeugt.

## 18. Volle Backend-Regression

**435 passed, 0 Failures** (Baseline 399 + 36 neue Search-Tests); 5 benigne
PyMuPDF-SWIG-Warnungen. Keine Regressionen.

## 19. Bekannte Grenzen / bewusst NICHT in STEP 13

- Kein Volltext-Suche über OCR-Bodies; Suche ist bewusst auf Vertrags-Metadaten
  begrenzt (kein zweiter Volltext-Kopie kompletter Verträge).
- Kein STEP-14-Viewer/Drill-Down (kein Verlinken auf nicht existierende Ansicht).
- Kein Elasticsearch/Meilisearch/Typesense/Redis/Vector-DB/Embeddings/RAG/LLM-
  Ranking/Cloud-Search; keine externen Analytics/Telemetrie.
- Keine neue Finanz-/Warn-/KPI-Semantik; STEP-9-/STEP-11-/STEP-12-Definitionen
  bleiben autoritativ.
- `organization_slug` ist reiner Scoping-Schlüssel; echte Auth/RBAC/RLS folgt
  in STEP 16.

## 20. STEP-14-Erweiterungspunkte

`ContractListItem.contract_id` ist der stabile, opaque Navigationsschlüssel für
den STEP-14-Vertrags-Detailviewer; die Paginierung und der strukturelle Filter-
Bauplan sind auf portierbare Query-Patterns ausgelegt. Es sind keine kaputten
Links eingebaut; der Vertragsname ist bewusst nicht als Sprung markiert, bis
STEP 14 existiert.

## Nächster Schritt

- **STEP 14 – Vertrags-Detailansicht / Quellenanzeige / Document-Viewer**.
  **STOP – kein STEP-14-Start in dieser Sitzung.**
