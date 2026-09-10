# Medflux — STEP 14 Checkpoint (Production-Grade Contract Detail + Quellenanzeige / Document-Viewer)

Datum: 01.09.2026 · Fortschritt: **14 / 18 = 77,8 %**

STEP 14 liefert die produktionsreife Vertrags-Detailansicht mit **sicherer
Quellen-/Provenienz-Anzeige** und **lokalem PDF-Viewer (pdf.js)**. Er ist das
operationale Gegenstück zu STEP 13 („Verträge") und STEP 12 (Dashboard). Der
Schritt setzt zuerst die **Storage-/Provenance-Grenze** sauber um (einziger
Produktions-Schreib-/Lesepfad), baut darauf ein **org-gebundenes Detail-Read-
Model aus den akzeptierten Runs** und liefert die Originaldokumente über einen
**sicheren, byte-ausliefernden Content-Endpoint** an den Browser.

## 1. Nutzerentscheidung (Storage-/Provenance-Grenze)

Kernbefund vor der Implementierung: Es gab **keinen** Produktions-Aufrufer, der
Bytes (via `DocumentStorage.save`) UND DB-Zeilen (`save_document_file`/
`create_document_version`) koordiniert – nur Tests erfanden `storage_key`. Diese
Lücke verursachte die Storage-/Provenance-Unschärfe. Entscheidung (verbindlich):

- **Autoritative Kette:** Contract → ContractDocument → DocumentVersion →
  DocumentFile → server-generierte **kanonische Storage-Referenz** →
  DocumentStorage → Original-Bytes.
- `DocumentFile.storage_key` wird wiederverwendet; **keine Migration nötig**.
- **Ein einziger Produktions-Storage-Service** koordiniert: SHA-256-Identität,
  DocumentFile/DocumentVersion-Persistenz, Bytes via DocumentStorage, kanonische
  storage_key-Generierung, STEP-10-Integritäts-Metadaten, deterministisches
  Kompensations-/Fehlschlagen.
- Dateisystem + PostgreSQL sind **nicht ACID-atomar** → explizite Kompensation.
- Browser/API erfährt **nie** storage_key oder Dateisystempfade.
- `DocumentStorage` ist der **einzige** Referenz→Pfad-Übersetzer.
- Legacy/nicht-deterministische Einträge → als **unavailable/unlinked** melden
  (Bug für STEP 16/Upgrade dokumentiert), nie raten.

## 2. Kanonische Storage-Referenz

Format: `<document_file_id_hex>/original.<ext>` mit `document_file_id` =
UUID.hex (32 Hex-Zeichen). Regex `^[0-9a-f]{32}/original\.(pdf|docx)$`.

`DocumentStorage` bietet referenz-basierte Operationen (`validate_reference`,
`safe_path`, `write_reference`, `exists_reference`, `read_reference`,
`delete_reference`). `safe_path` erzwingt Containment über
`resolve()`/`relative_to` (kein `..`, kein Absolut-/Drive-/UNC-Escape) – jede
Referenz, die den Root verlässt, wird abgelehnt. Nur diese Methoden übersetzen
kanonische Referenz → Dateisystempfad.

## 3. Storage-Service (`app/documents/persistence.py`)

`DocumentPersistenceService` (`store_original`, `resolve_bytes_for_version`,
`link_to_contract`, `canonical_storage_key`, `StoredDocument`):

1. Validieren (Typ/MIME/Size) → **vor** jeglicher Persistenz.
2. `sha256` des Inhalts → **Duplikat-Dedup** (global nach Bytes).
3. DocumentFile anlegen mit leerem `/`-Platzhalter, `flush` für id.
4. Kanonische Referenz aus der id ableiten; `storage_key` setzen; `flush`.
5. Bytes via `write_reference` auf das Dateisystem schreiben.
6. DocumentVersion anlegen (verweist auf DocumentFile).
7. **Kompensation:** DB-Fehler nach File-Write → `delete_reference` (Rollback
   der Datei); Storage-Fehler → Es bleibt **keine** akzeptierte DB-Beziehung
   (deterministisches Fehlschlagen, kein teil-konsistenter Zustand).

`resolve_bytes_for_version(organization_id, version_id, contract_id=None)` ist
org- (und optional vertrags-) gebunden: Cross-Org / unlinked / missing →
`StorageError` → generische 404. Der Duplikat-Fall zeigt auf die zuerst
importierende Org; Content-Zugriff bleibt org-gebunden (korrektes Sicherheits-
verhalten; Upgrade-Verlinkung pro Org in STEP 16 geplant).

## 4. Detail-Read-Model (`app/contracts/detail/`)

`build_contract_detail(session, organization_id, contract_id)`:
- org-gebunden + active-Lifecycle; fehlend/cross-org → `None` (generische 404).
- **Kein N+1:** gebundene Queries (Vertrag, akzeptierte Extraction+Evidence,
  akzeptierte Berechnung, aktive Warnungen, Equipment, Document-/Version-/File-Map).
- **GET rechnet nichts neu:** Warnungen kommen aus der STEP-11-Persisted-Current-
  Projektion; keine stille Warn-Neuberechnung.
- Aus der **akzeptierten** Extraktion (Snapshot): identity, scope, sla +
  Evidence-Provenienz. Aus der **akzeptierten** STEP-9-Berechnung (try/except
  validiert): dates, costs, Status, Konflikte. Dazu Equipment + sichere
  Dokumentliste (nur `id`/Rolle/Filename/MIME/Size/`viewer_supported`).

### Evidence-/Geometrie-Policy (ehrlich, nie erfunden)

- `extraction_evidence` trägt nur Element-/Seiten-Ebene (paragraph/table/page)
  → feinste ehrliche `precision` = **"coarse"** (mit bbox) / **"none"** (ohne).
- `geometry_normalized == True` (alle bbox-Koordinaten in [0,1]) ist der
  **einzige** Fall, in dem das Frontend pixelgenau hervorheben darf
  (`supports_exact_navigation`). 
- bbox numerisch validiert (finite, geordnet, nicht negativ); invalid → keine
  Koordinaten, Seiten-/Snippet-Fallback.
- Kein Word-/Line-Level, keine erfundene Geometrie, kein Frontend-Nachrechnen
  autoritativer Werte.

## 5. Sicherer Dokument-Bytes-Endpoint

`GET /api/contracts/{contract_id}/documents/{document_version_id}/content`
- org + Vertrag + Version gebunden via `resolve_bytes_for_version`.
- MIME-Allowlist (PDF/DOCX; andere → 415).
- HTTP-Range (206/416, bounded; Client-Tests decken beide ab).
- `X-Content-Type-Options: nosniff`; `Cache-Control: private, no-store`.
- `Content-Disposition` mit RFC-5987/Base-name-Sanitize: **inline** für PDF,
  **attachment** für DOCX.
- Generische 404 für fehlend/cross-org/unlinked; **keine** storage_keys/Pfade
  im Response.
- Briefebene nur opaque IDs (`contract_id`, `document_version_id`).

## 6. Frontend

- `app/contracts/[contract-id]/page.tsx` – Client-Route (Breadcrumb, Laden-/
  Fehler-/Erneut-Zustand; navigiert via opaque `contract_id` aus STEP 13).
- `components/contracts/detail/ContractDetail.tsx` – Abschnitte (Vertragsdaten,
  Kosten, Leistungsumfang, SLA, Geräte, Warnungen & Handlungsbedarf) +
  Quellen-Seitenleiste.
- `EvidencePane.tsx` – listen der Quellenangaben mit ehrlicher Präzision
  ("Exakt lokalisierbar" vs "Quelle nicht exakt lokalisierbar"), Seite, Snippet,
  Konfidenz, Prüf-Hinweis; Klick navigiert den Viewer.
- `PdfViewer.tsx` – **pdf.js lokal** (kein CDN), Worker aus
  `public/pdfjs/pdf.worker.min.js`; Bytes ausschließlich vom Content-Endpoint;
  bbox-Overlay **nur** bei `supports_exact_navigation`; Seiten-/Zoom-Steuerung;
  automatischer Seiten-Sprung bei Navigation. Kein iframe als primärer Viewer,
  kein DOCX-Fake-Reconvert, kein localStorage für Dokumentinhalte.
- `PageControls.tsx`, `SourceLink.tsx` (PDF → Viewer; DOCX → ehrlicher Hinweis).
- `lib/contract-detail-types.ts` – TS-Abbild der Step-14-DTOs; `lib/api.ts` +
  `contentUrl`.

`pdfjs-dist@3.11.174` deterministisch gepinnt (Next 14.2.15/React 18.3.1/
TS 5.6.2-kompatibel); Worker/Runtime-Assets lokal in `public/pdfjs/` kopiert.

## 7. Sicherheit / Datenschutz / DoS

- Verträge/Originals/Evidence = HIGHLY SENSITIVE: kein Cloud-AI/Telemetrie/CDN/
  externer Viewer/externe Fonts/Analytics/Content-Upload.
- Kein `dangerouslySetInnerHTML`, kein eval, keine secrets/rohen Exceptions an
  den Browser. Keine Document-Content in localStorage; URL nur opaque IDs.
- Strict-Referenz-Validierung (Traversal/Absolut/UNC abgewehrt; in Tests
  verifiziert). Content-Zugriff cross-org failt (Test).

## 8. Tests

**Backend – `tests/test_storage_boundary.py` (12, PG + echte Temp-Dateien):**
write/read/SHA-/Dedupe-Idempotenz, cross-org, unlinked, missing-file-safe,
Traversal/Absolut-/UNC-Refs abgelehnt, DB-Fehler nach File-Write kompensiert,
Storage-Fehler lässt keine akzeptierte DB-Beziehung, unsupported-type vor
Persistenz. Assertionen org-scoped.

**Backend – `tests/test_contract_detail.py` (12 Detail + Content, PG + Temp):**
Detail korrekt (org), missing/cross-org 404, bbox-Precision coarse/none,
invalid-bbox-Fallback, keine storage_keys/Pfade im Detail, nur-akzeptierte
(superseded ignoriert), Content-Bytes+Headers, cross-org 404, unlinked 404,
unsupported-mime 415, Range 206, invalide-Range 416.

**Volle Backend-Suite:** **459 passed** (435 Baseline + 24 neue, 0 Regressionen;
5 benigne PyMuPDF-SWIG-Warnungen).

**Frontend – `test/contracts-detail.test.tsx` (6, Vitest + RTL + jest-axe, mit
`apiGet`-/`contentUrl`-/`pdfjs-dist`-Mock + `fetch`-Mock):** lädt+zeigt
Detaildaten aus akzeptierter Wahrheit, PDF-Quelle unterstützt / DOCX ehrlich
nicht darstellbar, Quellenangaben mit ehrlicher Präzision, ausgewählte PDF-
Quelle markiert + Viewer-Toolbar, Navigation zu exakt lokalisierter Quelle,
automatischer a11y-Check.

`npm run test` → **28 passed**; `npx tsc --noEmit` grün; `npm run lint` →
No warnings/errors; `npm run build` → produktiver Next-Build (Route
`/contracts/[contract-id]` als `ƒ Dynamic`).

## 9. Bekannte Grenzen / bewusst NICHT in STEP 14

- DOCX-Quelle: ehrlich "nicht als PDF-Vorschau" (`viewer_supported` nur `.pdf`),
  kein stiller Reconvert.
- Kein Voll-CSP für den pdf.js-Worker (aktuelle CSP bleibt minimal aus STEP 12);
  vollumfängliches CSP + Auth folgt STEP 16.
- `store_original`-Dedup global nach Bytes; Upgrade-Verlinkung pro Org in STEP 16.
- Kein Fake-RBAC/User; `organization_slug` purer Scoping-Schlüssel (Auth/RLS
  STEP 16).
- Keine neue Finanz-/Warn-/KPI-Semantik; STEP-9-/11-/12-/13-Definitionen
  bleiben autoritativ.

## Nächster Schritt

- **STEP 15 – Benutzeroberfläche & Design.**
  **STOP – kein STEP-15-Start in dieser Sitzung.**
