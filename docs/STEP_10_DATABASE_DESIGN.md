# Medflux – STEP 10A Design-Gate (Datenbankarchitektur & Persistenz-Schema)

Datum: 30.08.2026 · Fortschritt: **9 / 18 = 50,0 %** (STEP 10 NICHT abgeschlossen)

**Revisionsstand:** Nach dem ersten STEP-10A-Review revidiert (UUIDv7-PK-Policy,
JSONB/Artifact-Policy §7, Evidence-Ownership §10, `contract_document`-n:m-Beziehung,
Entscheidungen in §20). Nach dem Kompatibilitäts-Check korrigiert: UUID-Generierung
**database-side** (PostgreSQL `uuidv7()`), da die Backend-Laufzeit Python 3.10.11
ohne Stdlib `uuid.uuid7` ist (§2A, §20). Nur Design-Dokument geändert – keine
Implementierung.

Dieses Dokument ist das **Design-Gate** für die Datenbankarchitektur und das
Persistenz-Schema von Medflux. Es wurde **nur Design-inspiziert und dokumentiert**
– **keine Implementierung** (keine SQLAlchemy-Modelle, keine Alembic-Migrationen,
keine PostgreSQL-Abhängigkeiten, kein Laufzeitverhalten geändert). Es dient als
Genehmigungsgrundlage für STEP 10B (Implementierung).

---

## 1. Architektur-Entscheidung (Grundsatz)

| Entscheidung | Wert |
|---|---|
| Produktions-DB | **PostgreSQL** (lokaler / on-prem Instanz) |
| ORM | **SQLAlchemy 2.x** (Typed / Declarative-style) |
| Migrationen | **Alembic** ab DB-Version 1 |
| Test-/Dev-DB | SQLite **nur optional** für isolierte, deterministische Tests |
| Suchindex | **Kein ES/Meilisearch** – Volltext via PostgreSQL `tsvector`/`to_tsvector` (later) |
| Primärschlüssel | **UUIDv7** (PostgreSQL `UUID`; PostgreSQL 18 native `uuidv7()`) |
| Dokumente/BLOBs | Original-PDF/DOCX + große Verarbeitungs-Artefakte im **lokalen geschützten Artifact-Storage** (`data/contracts/`), referenziert aus der DB (nicht als BLOBs) |
| Große kanonische Payloads | **Geschützter Artifact-Storage** (siehe §7B) – **keine** Pauschal-Regel „große Payloads → JSONB" |
| Architektur | Monolith, lokal/on-prem, KI-Schicht austauschbar – **keine** Microservices/Event-Sourcing/Redis/Vector-DB |

**Warum PostgreSQL statt SQLite (MVP-Annahme der Vergangenheit überholt):**
- Produktionsreife ACID-Transaktionen mit mehreren parallelen Schreib-/Lese-Läufen.
- Echte Multi-User-/Zugriffskontrolle (Rollen, row-level security später möglich).
- Volltextsuche (`tsvector`) nativ, ohne externen Index-Dienst.
- Numerics/DECIMAL exakt (Kosten, siehe §7), robuste Datum-/Zeitzonen-Typen.
- Alembic-Migrationen on top; SQLite bliebe ein weniger ausdrucksstarkes Subset.

SQLite bleibt **nur** als optionaler, isolierter Test-Speicher nutzbar (In-Memory/
Tempfile) für deterministische Unit-Tests – nie für die Laufzeit-Datenhaltung.

---

## 2. Designgrundsätze (Persistence-Hauptprinzip)

Die gesamte Schemastruktur folgt der Trennung von **Original → Dokument-Version →
Verarbeitungs-/kanonische Repräsentation → Extraktions-Lauf/Vertrags-Snapshot →
Berechnungs-Lauf/Resultat → aktueller Anwendungszustand**:

```
ORIGINAL SOURCE ──▶ DOCUMENT VERSION ──▶ PROCESSING RUN ──▶ EXTRACTION RUN ──▶ CALCULATION RUN
(document_file)     (document_version)    /CANONICAL         /CONTRACT SNAPSHOT   /RESULT
                     (immutable file      (document_intel-    (contract_extraction) (calculation_run)
                     identity + metadata) ligence_result)
                                                     │
                                                     ▼
                                        CURRENT APPLICATION STATE
                                        (contract/contract_version + status)
```

**Kernregeln**
1. **Reproduzierbarkeit & Provenienz** – „Woher kommt dieser Wert …?“ ist immer
   beantwortbar: jeder aktuelle Wert führt über seine Lauf-/Versions-Kette zum
   Original-Dokument und der Quelle (Seite/Paragraph/Absatz/Zelle + Offset).
2. **Kein neuer Lauf zerstört still Vorheriges** – Lauf- und Versions-Reihenfolge
   bleiben erhalten; aktuelle Zustände sind materialisierte Zeiger auf den
   jeweils akzeptierten Lauf, nicht in-place überschriebene Daten.
3. **Berechnungen macht Code, nie die KI** (Konvention aus AGENTS.md + STEP 9):
   Die DB speichert Fakt-/Extraktionsdaten und Berechnungs-Resultate getrennt.
4. **Keine erfundenen Werte** – fehlende/Widersprüchliche Werte bleiben `NULL` bzw.
   mit Status `NOT_CALCULABLE`/`REVIEW_REQUIRED`/`CONFLICT`, nie Halluzination.

---

## 2A. Primärschlüssel-Policy (UUIDv7)

**Vorgabe:** PostgreSQL `UUID`-Typ, **UUIDv7** als bevorzugter Schlüsseltyp für
alle **neu erzeugten persistierten Entity-IDs**, erzeugt **database-side** über
PostgreSQL 18 natives `uuidv7()`. UUIDv7 ist **zeitgeordnet** (bei B-Tree-Indizes
auf PK ist die Einfüge-Ordnung DB-freundlich) und kollisionsfrei ohne
Verteilungs-Synchronisation.

Regeln:
- **UUID-Typ durchgängig** – auch alle Fremdschlüssel nutzen `UUID` (konsistent
  mit dem jeweiligen PK-Typ).
- **Keine Geschäftslogik in IDs** kodieren; IDs sind reine Identifikatoren.
- `created_at` bleibt immer eine **explizite `TIMESTAMPTZ`-Spalte**; die in
  UUIDv7 eingebettete Unix-Millisekunden-Zeit wird **nicht** als maßgebliche
  Erzeugungszeit verwendet.

**Ownership-Modell (eindeutig, konsistent):** **database-side** als Default.
Neue persistierte DB-Entity-IDs werden per **PostgreSQL 18 `uuidv7()`** (DB-generiert)
erzeugt. Begründung:
- Die aktuelle Backend-Laufzeit ist **Python 3.10.11** – Stdlib `uuid.uuid7()`
  existiert erst ab Python 3.14 und ist hier **nicht verfügbar**.
- Es wird **keine dritte UUID-Bibliothek** nur für diesen Zweck hinzugefügt
  (Vorgabe: keine unnötige Abhängigkeit).
- PostgreSQL 18 liefert nativ `uuidv7()`; das nutzt die Zeitgeordnetheit direkt
  und hält **ein** konsistentes Ownership-Modell (DB-seitig).
- Ausnahme (bewusst, mit explizitem Grund): Bestehende, von der Anwendung heute
  erzeugte Handlungs-IDs (z. B. `document_id`) bleiben unverändert – sie werden
  **nicht** auf UUIDv7 umgeschrieben (siehe Kompatibilität unten). Es wird für
  **dieselbe Entity** nicht zwischen App- und DB-Generierung gemischt, ohne dass
  dafür ein expliziter Grund dokumentiert ist.

PostgreSQL `uuidv7()` ist damit die maßgebliche Quelle für neue persistierte
Entity-IDs; ein app-seitiger Fallback (z. B. `uuid.uuid4()`) ist **nicht** Teil
des Modells und wird nur in definierten, dokumentierten Ausnahmen (Tests,
vorhandene IDs) verwendet.

**Kompatibilität vorhandener IDs:** Bereits von der Anwendung erzeugte IDs
(z. B. bestehende `document_id`s) bleiben **kompatibel** – sie werden **nicht**
umgeschrieben oder „auf UUIDv7 konvertiert“, nur weil das neue Schema neu
erzeugte IDs mit UUIDv7 erzeugt. Neue persistierte Entities (z. B. `document_version`,
`contract`, Läufe) erhalten UUIDv7-PKs; existierende String-/UUID-IDs bleiben
gültige Fremdschlüssel-Werte. Es gibt keine aufwändige Daten-Migration nur zur
UUID-Konvertierung bestehender IDs in STEP 10.

---

## 3. Entity-Modell (Übersicht)

| Entity | Art | Persistenz |
|---|---|---|
| `document_file` | immutable Quelldatei (Original) | DB-Zeile + Datei im Artifact-Storage |
| `document_version` | Version einer Quelldatei (Re-Import, Hash) | DB-Zeile |
| `document_processing_result` (Canonical) | Document-Intelligence-Ergebnis (kanonisch) | DB-Zeile (Header) + **Artifact immutabel** im Protected Storage (Referenz) |
| `document_artifact` | externes, immutables Verarbeitungs-/Rendered-/Diagnose-Artefakt | DB-Zeile (Metadata/Referenz) + Datei im Artifact-Storage |
| `processing_summary` | Statistik einer Verarbeitung (Dauer, Seiten, OCR-Konfidenz …) | DB-Zeile |
| `contract_extraction` (ExtractionRun) | ein strukturierter KI-Extraktions-Lauf → ContractSnapshot | DB-Zeile (Header) + immutable ContractSnapshot (klein: JSONB; groß: Artifact) + Evidence-Tabelle |
| `extraction_evidence` | Quelle eines extrahierten Wertes (Seite/Paragraph/Zelle, source_text, bbox, Konfidenz) | DB-Zeile (relational, navigierbar) |
| `calculation_run` | ein deterministischer STEP-9-Berechnungs-Lauf | DB-Zeile |
| `calculation_result` | Ergebnis eines einzelnes berechneten Feldes/MoneyWert | DB-Zeile (relationale Schlüssel + schlüsselindizierte Felder; verschachtelte Blöcke ggf. JSONB) |
| `calculation_review_flag` | Review-/Konflikt-Status eines Runs | DB-Zeile |
| `contract` / `contract_version` | **Current Application State** – akzeptierter Vertrag + Status | DB-Zeilen (relational) |
| `contract_document` | Zuordnung **vieler Dokumente** zu **einem logischen Vertrag** (future-safe) | DB-Zeile (Association, n:m) |
| `contract_equipment` | Geräte eines akzeptierten Vertrags | DB-Zeile (child) |
| `contract_service` | Leistungsumfang-Einträge | DB-Zeile (child, ggf. JSONB) |
| `user` / `review_action` | Multi-User & manuelle Korrektur (Audit) | DB-Zeile |

---

## 4. Mermaid-/Text-Diagramm

```text
 document_file (1) ──(1..n)── document_version (1) ──(0..n)── document_processing_result
     │                                   │                       │
     │ (Storage-Pfad, Hash)              │ (Verweis auf Original) │→ document_artifact (großes kanon.
     │                                   │                       │   payload/Diagnose/Rendered, immutabel)
     │                                   │                       │
     │                                   │──(0..n)── contract_extraction (ExtractionRun)
     │                                   │               │ header + (id, status, prompts…)
     │                                   │               ├── immutable contract_snapshot (klein: JSONB;
     │                                   │               │                            groß: Artifact)
     │                                   │               └──(1..n)── extraction_evidence
     │                                   │                                  │ (relational, navigierbar)
     │                                   │──(0..n)── calculation_run (CalculationRun)
     │                                                   │ as_of_date, version, status
     │                                                   ├── result (relational + verschachtelte Blöcke)
     │                                                   ├──(0..n)── calculation_review_flag
     │                                                   └──(1..1)──>> contract (accepted, current)
     │
     └──▶ contract / contract_version (CURRENT STATE)
                    │  status (ACTIVE/EXPIRED/TERMINATED/…), accepted → contract_extraction + calculation_run
                    ├──(1..n)── contract_equipment
                    ├──(n..m)── contract_document ──▶ document_version  (ZUGORDNUNG: mehrere Dok. je Vertrag)
                    └──(1..1)── review_action (manuelle Korrektur, Auditor)
```

Abkürzungs-Konvention (in Textblockdiagramm je Entität vererbte Schlüssel):
Jede aktuelle `contract`-Zeile trägt Zeiger auf die *akzeptierten* Runs und damit
auf die Quelle. Kein Lauf ist destruktiv.

---

## 5. Tabellen-Verantwortlichkeiten (je Tabelle ein Zweck)

| Tabelle | Zweck | Schlüssel / Besonderheit |
|---|---|---|
| `document_file` | Eine eingelesene, unveränderbare Quelldatei (Original-BLOB als Pfad + Hash) | `document_id` PK; `sha256` unique; `storage_key` (relativ) |
| `document_version` | Eine erkannte Version einer Datei (gleiche Datei mit neuem Hash / Re-Import) | `version_id` PK; `document_id` FK; `sha256` |
| `document_processing_result` | Kanonisches Document-Intelligence-Ergebnis je (Version, Config) | `processing_id` PK; `document_version_id` FK; `schema_version`; `provider`; Referenz auf immutables kanonisches Artifact |
| `document_artifact` | Ein immutables, reproduzierbares Daten-/Diagnose-Artefakt (PDF-Original, großes kanonisches JSON, OCR-/Layout-Diagnose, Render) | `artifact_id` PK; `document_version_id` FK (bezugs); `processing_run_id` FK (falls bezugs); `artifact_type`; `storage_key` (relativ); `sha256`; `size_bytes`; `format_version`; `created_at`; `lifecycle_state` |
| `processing_summary` | Flaches Statistik/Pfadfeld eines Verarbeitungs-Laufs | `summary_id` PK; `processing_id` FK 1:1 |
| `contract_extraction` | Ein vollständiger strukturierter Extraktions-Lauf | `extraction_id` PK; `document_version_id` FK; `status`, `prompt_version`, `model`; `snapshot_loc` (JSONB Bei kleinem Snapshot, sonst Artifact-Referenz) |
| `extraction_evidence` | Eine Quellen-Nachweis-Zeile (Wert → Quelle) | `evidence_id` PK; `extraction_id` FK; `source_type`, `page`, `paragraph_index`, `table_index`, `bounding_box` (JSONB), `source_text`, `ocr_confidence`, `confidence` |
| `calculation_run` | Ein deterministischer Berechnungs-Lauf (STEP 9) | `run_id` PK; `extraction_id` FK; `as_of_date`, `calculation_version` |
| `calculation_result` | Berechnete Felder eines Runs (Dates/Costs) | `result_id` PK; `run_id` FK; relationierte Schlüssel + verschachtelte Blöcke |
| `calculation_review_flag` | Review-/Konflikt-/Erklärungs-Zeilen eines Runs | `flag_id` PK; `run_id` FK; `reason`, `explanation`, `inputs` (JSONB) |
| `contract` | **Aktueller** akzeptierter Vertrag (Current State) | `contract_id` PK; `extraction_id` FK (accepted source); `calculation_run_id` FK |
| `contract_document` | **n:m**-Zuordnung logischer Vertrag ↔ Dokument(e) (future-safe Mehrdokument) | `contract_id` FK; `document_version_id` FK; `association_id` PK; `role` (z. B. `main|amendment|appendix|renewal|price_adjustment|sla_attachment`), `created_at` |
| `contract_equipment` | Geräte des akzeptierten Vertrags | `contract_id` FK; `equipment_id` PK |

Jede aktuelle `contract`-Zeile ist ein **Zeiger** (acceptance), keine Kopie des
Extraktions- oder Berechnungs-Ergebnisses. Das hält die Provenienzkette intakt.

---

## 6. Spalten & Typen (Haupttabellen, Entwurf)

### `document_file`
```text
document_id          UUID PK
original_filename    TEXT  (nur Anzeige, nie als Storage-Pfad)
stored_filename      TEXT
file_extension       TEXT
mime_type            TEXT
file_size_bytes      BIGINT
sha256               TEXT UNIQUE NOT NULL
storage_key          TEXT NOT NULL   (relativer Schlüssel im Storage-ROOT)
imported_at          TIMESTAMPTZ NOT NULL
import_status        TEXT  (imported|rejected|failed|duplicate)
duplicate_detected   BOOLEAN
duplicate_of_id      UUID NULL
```

### `document_version`
```text
version_id           UUID PK
document_id          UUID FK
version_no           INTEGER
sha256               TEXT
storage_key          TEXT   (relativer Schlüssel im Storage-ROOT)
created_at           TIMESTAMPTZ
```

### `document_processing_result` (Canonical / ProcessingRun)
```text
processing_id        UUID PK
document_version_id  UUID FK
schema_version       TEXT   (CANONICAL_SCHEMA_VERSION "1.2.0")
provider             TEXT
provider_version     TEXT
ocr_engine           TEXT
ocr_engine_version   TEXT
do_ocr               BOOLEAN
do_table_structure   BOOLEAN
dpi                  INTEGER
geometry_provider    TEXT
processing_duration  DOUBLE PRECISION
created_at           TIMESTAMPTZ
canonical_artifact_id UUID FK  (→ document_artifact; immutables, versionsbezogenes
                                 kanonisches Payload im Protected Storage, KEIN
                                 BLANKETT-JSONB-Regel)
```

### `document_artifact` (Protected Artifact-Storage)
```text
artifact_id          UUID PK
document_version_id  UUID FK        (Kontext-Dokumentversion)
processing_run_id    UUID FK NULL   (falls artefakt-spezifisch je Verarbeitung)
artifact_type        TEXT   (canonical|ocr_diagnostics|layout_diagnostics|
                             rendered|preview|debug|original_pdf|contract_snapshot|...)
storage_key          TEXT   (RELATIVER Schlüssel im Storage-ROOT; NIE maschinen-
                             abhängiger absoluter Pfad)
sha256               TEXT            (Integritäts-Hash)
size_bytes           BIGINT
format_version       TEXT            (Schema-/Format-Version, z. B. canonical "1.2.0")
created_at           TIMESTAMPTZ
lifecycle_state      TEXT   (active|orphan|pending_deletion|deleted)
deletion_owner       TEXT            (wer/wohin für Lösch-Lebenszyklus zuständig)
```

### `contract_extraction` (ExtractionRun / ContractSnapshot)
```text
extraction_id        UUID PK
document_version_id  UUID FK
status               TEXT  (success|partial|failed)
validation_status    TEXT  (valid|invalid|unknown)
requires_review      BOOLEAN
message              TEXT
error                TEXT
model                TEXT
prompt_version       TEXT
chunk_count          INTEGER
processing_duration  DOUBLE PRECISION
timeout_count        INTEGER
retry_count          INTEGER
truncated_chunks     INTEGER
ai_call_count        INTEGER
groups_processed     INTEGER
evidence_issues      INTEGER
verifier_issues      INTEGER
normalization_issues INTEGER
created_at           TIMESTAMPTZ
# Immutabler Contract-Snapshot: klein → `contract_snapshot JSONB`;
# groß/voluminös → `contract_snapshot_artifact_id UUID FK` (→ document_artifact).
# Entscheidung über JSONB vs. Artifact nach §7B-Policy, NICHT pauschal.
contract_snapshot            JSONB NULL
contract_snapshot_artifact_id UUID FK NULL
```

### `extraction_evidence` (relational, für Quell-Navigation)
```text
evidence_id          UUID PK
extraction_id        UUID FK
field_ref            TEXT   (stabiler Pfad, z. B. "identity.contract_number")
source_type          TEXT   (page|paragraph|table)
page                 INTEGER
paragraph_index      INTEGER
table_index          INTEGER
source_text          TEXT
bounding_box         JSONB  (x0,y0,x1,y1 PDF-Punkte; deterministisch)
ocr_confidence       DOUBLE PRECISION NULL
confidence           DOUBLE PRECISION NULL   (semantisch, getrennt von OCR)
requires_review      BOOLEAN
extraction_method    TEXT   (ai|manual|programmatic)
```

### `calculation_run` (CalculationRun)
```text
run_id               UUID PK
extraction_id        UUID FK
as_of_date           DATE NOT NULL   (explizit; heutiges Datum NIE in Semantik versteckt)
calculation_version  TEXT   ("step9-1.0")
overall_review_required BOOLEAN
created_at           TIMESTAMPTZ
# Ergebnis je §7-Policy: verschachtelte, abfragbare Felder relational
# (calculation_result child) bzw. kleine, selten einzelne JSONB-Blöcke.
# KEINE Pauschal-"groß → JSONB"-Regel.
```

### `contract` (Current Application State)
```text
contract_id          UUID PK
accepted_extraction_id UUID FK  (→ contract_extraction)
accepted_calculation_run_id UUID FK (→ calculation_run)
status               TEXT  (active|expiring_soon|expired|terminated|draft|unknown)
risk_level           TEXT  (low|medium|high|unknown)
created_at / updated_at TIMESTAMPTZ
```
> **Denormalisierte Such-/Current-Felder (APPROVED)** – `contract` darf zusätzlich
> abfragbare Projektions-Spalten tragen (z. B. `supplier`, `contract_number`,
> `start_date`, `end_date`), die für Liste/Dashboard/Status denormalisiert werden.
> Diese sind **Projektionen/Current-State**, **keine Provenienz-Quelle**: Die
> historische `contract_extraction.contract_snapshot` bleibt maßgeblich dafür,
> **was ein Lauf erzeugt hat**.

### `contract_equipment` (child)
```text
contract_id          UUID FK
device_name, manufacturer, model, serial_number, system_name, equipment_category ...
```

### `contract_document` (Zuordnung logischer Vertrag ↔ Dokument[e], future-safe)
```text
association_id       UUID PK
contract_id          UUID FK   (→ contract)
document_version_id  UUID FK   (→ document_version)
role                 TEXT NULL (main|amendment|appendix|renewal_letter|
                               price_adjustment|sla_attachment|unknown)
created_at           TIMESTAMPTZ
UNIQUE(contract_id, document_version_id)
```
> **Kardinalität:** Ein logischer Vertrag darf **mehrere** Dokumente referenzieren
> (Hauptvertrag + Amendment + Anlage + Verlängerungsschreiben + Preisänderung +
> SLA-Anlage). Die Zuordnung verläuft über die n:m-Association – **kein** „ein
> Vertrag = ein PDF“-Zwang im Schema. Eine Interpretation/Verarbeitung der
> Amendments ist **nicht** Teil von STEP 10; das Modell wird nur future-safe
> gemacht.

---

## 7. Relational vs. JSONB vs. Artifact – deliberate Größen-/Zugriffs-/Lebenszyklus-Grenze

**Grundsatz (Review-Vorgabe):** Es gibt **keine** Pauschal-Regel „große Payloads
→ JSONB". Stattdessen bestimmen die Kriterien **Abfrage-/Zugriffsmuster,
Transaktions-Konsistenzbedarf, Payload-Größe, Reproduzierbarkeitskosten,
Backup/Restore-Einfluss, Lösch-/Security-Lebenszyklus**, ob ein Inhalt in
**PostgreSQL (relational/JSONB)** oder im **Protected Artifact-Storage** liegt.
Eine willkürliche Size-Schwelle (z. B. „> 1 MB → Artifact") wird **nicht**
festgelegt, bevor sie nicht gemessen ist.

### 7A – Was PostgreSQL speichert (relational + begrenzt JSONB)

PostgreSQL hält:
- **Transaktionalen Zustand** & **Entity-Beziehungen** (Kopfzeilen, FKs).
- **Current/Accepted-Zeiger** (`accepted_extraction_id`, `accepted_calculation_run_id`).
- **Abfragbare/indizierbare Geschäftsfelder** (Status, Risiko, Equipment, und
  die genehmigten denormalisierten `contract`-Projektions-Spalten).
- **Verarbeitungs-/Extraktions-/Berechnungs-Metadaten** (Header, Status,
  prompt_version, model, as_of_date, calculation_version, Diagnose-Zähler).
- **Angemessen dimensionierte, immutablable Snapshots, wo transaktionale
  DB-Konsistenz wertvoll ist** – z. B. kleine/lose `JSONB`-Blöcke für den
  Contract-Kopf bzw. verschachtelte Ergebnisse, **wenn** sie abfragbar/klein
  bleiben und keine nennenswerten Backup-/Reproduzierbarkeitskosten verursachen.
- **Evidence/Provenienz-Beziehungen** für exakte Quell-Navigation (relationale
  `extraction_evidence`-Zeilen: page, paragraph_index, table_index, source_text,
  bounding_box, Konfidenzen).

**JSONB nur, wenn:** Inhalt ist (a) klein/Grenzwertig, (b) wird selten
einzeln abgefragt bzw. nur ganzheitlich gelesen/geschrieben, (c) transaktionale
Konsistenz mit den umgebenden Zeilen ist wertvoll, (d) Backup-/Restore-Aufwand
vertretbar ist. Sonst → Artifact (7B).

### 7B – Protected Artifact-Storage (große, reproduzierbare Artefakte)

Geeignet für:
- **Original-PDF/DOCX** (`data/contracts/<document_id>/original.<ext>`).
- **Sehr große kanonische/Document-Intelligence-Payloads** (voluminales
  Seiten-/Element-/Geometrie-JSON – für normale relationale Abfragen uninteressant).
- **Umfangreiche OCR-/Layout-Diagnosen** und **Rendered/Debug-Artefakte**.
- **Andere große, reproduzierbare Verarbeitungs-Artefakte**, die keine normale
  relationale Abfrage benötigen.

Für **jedes** externe Artefakt wird in `document_artifact` persistiert:
- stabile `artifact_id` (UUIDv7)
- `document_version_id` / `processing_run_id` (je nach Bezug)
- `artifact_type`
- `storage_key` (**relativer** Storage-Schlüssel, **nie** maschinenabhängiger
  absoluter Pfad)
- `sha256` (Integritäts-Hash), `size_bytes`
- `format_version` / Schema-Version
- `created_at`
- `lifecycle_state` + `deletion_owner` (Lösch-/Security-Lebenszyklus)

**Wahrscheinliche Erstzuordnung (Entwurf, ggf. nach Messung verfeinert):**
| Inhalt | Ort |
|---|---|
| Transaktionaler Kopf, Beziehungen, accepted-Zeiger | PostgreSQL relational |
| Abfragbare Geschäftsfelder (Status/Risiko/Equipment/Projektionen) | PostgreSQL relational |
| `extraction_evidence` (exakte Quell-Navigation) | PostgreSQL relational |
| Kleine/lose Contract-Snapshot-oder-Result-`JSONB` | PostgreSQL JSONB nur bei kleinen, ganzheitlich gelesenen Inhalten |
| Original-PDF/DOCX | Protected Artifact-Storage |
| Großes kanonisches Processing-Payload | Protected Artifact-Storage |
| OCR-/Layout-Diagnose, Rendered/Debug, große Snapshots | Protected Artifact-Storage |

**Quell-Navigations-Korrektheit:** Die exakte Quell-Navigation (Seite/Zelle/
bbox → Original-PDF) darf **nicht** von temporären/debug-Dateien abhängen. Die
**authoritative Geometrie/Evidence-Repräsentation wird dauerhaft** persistiert –
entweder relational (`extraction_evidence` mit bounding_box) **oder** in einem
**durabelen, versionierten kanonischen Artifact**, das die DB referenziert
(`document_artifact` + `canonical_artifact_id`). Nach einem Neustart bleibt die
atomare Geometrie damit verfügbar; temporäre Render-/Diagnose-Dateien sind
immer nur ergänzende Artefakte, nie die Quelle der Wahrheit.

### 7C – Per-Entität-Zuordnung (Zusammenfassung)

| Bereich | Ansatz | Begründung |
|---|---|---|
| **Dokument-Original, Versions-Metadaten** | **Relational** | kleine, stabile Kardinalitäten; Indizierbar (sha256, import_dat), Duplikaterkennung |
| **Canonical/Processing-Payload** | **Protected Artifact-Storage** (immutabel, referenziert) | voluminal, keine relationale Abfrage nötig; Header/Metadaten relational für Navigation |
| **ContractSnapshot (Extraktion)** | **Immutable**: klein → `JSONB` DB; groß → **Artifact** | Contract-Modell ist hochvariabel & verschachtelt; relationale Normalisierung unverhältnismäßig. Entscheidung JSONB-vs-Artifact nach §7-Policy. Evidence bleibt **relational** für Navigation |
| **Calculation/Result** | **Relational** Schlüssel + **begrenzt JSONB** je §7 | Stabile Top-Level-Felder relational; tief verschachtelte, selten einzeln abgefragte Resultat-Blöcke als JSONB; Review-/Konflikt-Zeilen relational |
| **Current State (`contract`)** | **Relational** (Kopfzeile) + child **relational** | klein, stabil, hochabfragbar |
| **Equipment/Services/SLA** | **Relational** (child) bzw. JSONB für rein deklarative Listen | Equipment abfragbar; rein beschreibende Service-Listen in JSONB |

**Währungen / Geld:** Alle Geldbeträge (`Money.amount`, `MoneyFieldResult.value`,
Kostenfeld) werden als **NUMERIC/DECIMAL(18,2)** gespeichert, **nie** als
Binary-FLOAT (Konvention; vermeidet Rundungsfehler bei 0,1-artigen Summen).
`Money.currency` als `CHAR(3)`/`TEXT` (oberer Fall, validiert).

**Technische Zeitstempel** sind immer **TIMESTAMPTZ** (zeitzeonen-bewusst, UTC
gespeichert). Fachliche Daten (`as_of_date`, Vertragsstart/-ende) sind `DATE`
und **nicht** mit Zeitzonen-/Uhrzeit-Semantik vermischt.

---

## 8. Dokument-/Artifact-Storage (PDF/DOCX & große Artefakte)

- Original-Dateien liegen im **Protected Artifact-Storage** (`data/contracts/<document_id>/original.<ext>`),
  nicht in der DB (keine BLOBs). DB hält nur `storage_key` (relativ) + `sha256`.
- Der Einzelpfad wird **intern aus `document_id`** gebildet; `original_filename`
  wird nie als Pfadteil verwendet (nur Anzeige) – sichere Pfadbehandlung bleibt
  wie in `app/documents/storage.py`.
- SHA-256-Duplikaterkennung bleibt bestehen (Index über `document_file.sha256`).
- **Große/großvolumige Payloads** (kanonische Document-Intelligence-JSON,
  OCR-/Layout-Diagnosen, Rendered/Debug, große Snapshots) liegen im
  **Protected Artifact-Storage** als immutablable, versionierte Artefakte und
  werden via `document_artifact` (artifact_id, document_version_id /
  processing_run_id, artifact_type, relativer storage_key, sha256, size_bytes,
  format_version, created_at, lifecycle_state/deletion_owner) referenziert.
- **NICHT pauschal** als JSONB in der DB ablegen (siehe §7B). Ob ein Inhalt in
  die DB oder in den Artifact-Storage gehört, entscheiden die §7-Kriterien
  (Zugriff, Transaktions-Konsistenz, Größe, Reproduzierbarkeit, Backup, Leben).
- Exakte Quell-Navigation hängt **nie** von temporären/debug-Dateien ab; die
  authoritative Geometrie/Evidence ist relational (`extraction_evidence`) oder
  in einem durable versionierten kanonischen Artifact persistiert (§7B, §10).

---

## 9. Processing / Extraction / Calculation-Versionierung

- **Verarbeitungs-Lauf** (`document_processing_result`): neuer Lauf je
  (document_version, Konfig/Provider/OCR-Einstellungen) → eigene Zeile; keine
  Überschreibung. `schema_version` + `provenance` machen Ergebnisse
  reproduzierbar und Cache-Invalidierung deterministisch.
- **Extraktions-Lauf** (`contract_extraction`): erfasst je Lauf `prompt_version`,
  `model`, Chunking-/Diagnose-Metriken (timeout_count, retry_count,
  truncated_chunks, ai_call_count, groups_processed, evidence/verifier/normalization issues –
  exakt die Felder aus `ContractAnalysisResult`). Jeder Lauf erzeugt seinen
  **immutabelen** `contract_snapshot` (klein → JSONB in DB, groß → immutables
  `document_artifact`, §7) + relationale `extraction_evidence`.
- **Berechnungs-Lauf** (`calculation_run`): jeder Lauf bindet `as_of_date` +
  `calculation_version` explizit; das Ergebnis bleibt **immutabel** je Lauf
  (relationale Schlüssel + ggf. begrenzte JSONB-Blöcke gemäß §7).
- **Kein Lauf ist destruktiv:** ein neuer Extraktions-/Berechnungs-Lauf fügt eine
  neue Zeile hinzu; „aktuell akzeptierte“ Werte verweisen nur auf die jeweilige
  neueste/akzeptierte Zeile. Abgebrochene Prozesse lassen sich sauber als
  `failed`-Status abbilden, ohne Vorheriges zu verlieren.

---

## 10. Evidence / Source-Navigation („Woher kommt dieser Wert“)

Jedes KI-extrahierte Feld trägt im `Contract` bereits `SourceEvidence`. Die
Duplikation „Evidence im JSONB + relational“ ist **nur mit expliziter
Ownership** genehmigt:

- **Ownership:**
  - Das **immutablable Extraction-Snapshot** (`contract_snapshot`, JSONB/Artifact)
    enthält die **ursprüngliche Evidence-Repräsentation** – für Reproduzierbarkeit
    („was hat der Lauf ausgegeben“). Es ist die **Quelle** der Wahrheit des Laufs.
  - Die **relationale `extraction_evidence`**-Tabelle ist die **operative,
    abfragbare Quell-Navigations-Projektion** (source_type, page,
    paragraph_index, table_index, bounding_box, source_text, ocr_confidence,
    confidence, requires_review, extraction_method, field_ref) – für Abfragen
    und Navigation, nicht die autoritative Lauf-Wahrheit.
- **Synchronisations-/Integritätsregel (können nicht still auseinanderlaufen):**
  - Beide werden **im selben Extraktions-Lauf, atomar in einer Transaktion**
    geschrieben (siehe §14) – es gibt kein Fenster, in dem sie abweichen.
  - `field_ref` ist der **stabile** Schlüssel, der die relationale Zeile an das
    Feld im Snapshot bindet (`$`-Pfad, z. B. `identity.contract_number`).
  - Ein **Konsistenz-/Verifikations-Schnelltest** (ein deterministischer
    Assert/Unit-Test in STEP 10B) vergleicht für einen Extraktions-Lauf:
    jede relationale `extraction_evidence`-Zeile ist im Snapshot unter
    `field_ref` vorhanden und stimmt (source_type, page, source_text) überein –
    und umgekehrt repräsentiert der Snapshot alle Evidence.
  - Es gibt **eine** Schreibstelle (Service, die den Lauf persistiert); es wird
    **nie** „nur JSONB“ oder „nur relational“ geschrieben.
- Diese relationale Sicht ermöglicht:
  - Navigation zur **Original-PDF-Seite** (Koordinaten in PDF-Punkten, y nach
    unten, deterministisch aus OCR/kanonischem Raum) → Rendering/Highlighting.
  - Abfragen wie „alle Werte auf Seite 3“, „alle Felder mit ocr_confidence < X“.
- **WICHTIG:** OCR-/Recognition-Konfidenz (`ocr_confidence`) bleibt **streng
  getrennt** von semantischer `confidence` (Konvention aus
  `app/documents/intelligence/evidence.py`). Beide Spalten sind getrennt.
- Deterministische Geometrie: echte Wort-/Zeilen-Boxen (WORD/LINE/TABLE_CELL)
  gelten als exakt; grobe Element-Boxen/ESTIMATED nie als exakt (nur grob
  markiert) – wie `GeometryPrecision` es vorschreibt.
- **Dauerhafte Quell-Navigation:** Für die exakte Navigation (inkl. atomarer
  Geometrie nach einem Neustart) ist die autoritative
  Geometrie/Evidence-Repräsentation dauerhaft persistiert – entweder relational
  (`extraction_evidence`-bbox) oder in einem durable versionierten kanonischen
  Artifact (`document_artifact`), das die DB referenziert. Temporäre
  Render-/Diagnose-Dateien sind nie die Quelle der Wahrheit (§7B, §8).

---

## 11. Current/Accepted-Strategie (wie wird „der aktuelle Stand“ bestimmt)

- **Materialisiert** in der `contract`-Tabelle: `accepted_extraction_id` und
  `accepted_calculation_run_id` zeigen auf die jeweils akzeptierten Läufe; der
  Anwendungszustand (Status, Risiko, Equipment) wird daraus bei Bedarf abgelesen.
- Extraktions-Wahl: Standardmäßig wird der neueste **erfolgreiche** Lauf
  (`status=success`) verwendet; bei manueller Korrektur wird explizit ein Lauf
  akzeptiert (Audit in `review_action`).
- Berechnungs-Wahl: der Lauf zum relevanten `as_of_date` (meist heutiges Datum),
  bei Bedarf ein anderer (historischer) `as_of_date` → ohne die Berechnungs-
  Semantik zu verstecken.
- **Terminierung (Regel aus STEP 9):** `Contract.status == TERMINATED` ist die
  **einzige** privilegierte Quelle für den Zustand TERMINATED; kein separates
  strukturiertes „Term-Evidence-Feld“ im Schema (konservativ beibehalten, als
  **bekannte Schema-Limitierung akzeptiert**). In STEP 10 wird **kein**
  Term-Evidence erfunden; das konservative STEP-9-Verhalten wird beibehalten.
  Abgelaufenes Ende → EXPIRED.

---

## 12. Manuelle Korrektur (Review-Actions)

- `review_action`-Tabelle (Audit): Dok-Nr., Reviewer, Zeitpunkt, geändertes
  `field_ref`, alter → neuer Wert, `reason`, optional Link auf
  Quellen-Evidence.
- Korrekturen erzeugen **keine** Mutation des Original-`contract_snapshot`
  (immutabel); sie legen einen neuen akzeptierten Zustand bzw. einen
  „override“-Wert an, der die Provenienz (original + manuell) sichtbar hält.
- `ReviewStatus` (`reviewed|needs_review|auto_accepted`) und `ReviewFlag`
  (`missing|conflict|vague|event_based|low_confidence|other`) bleiben im
  `contract`-Kopf bzw. als `calculation_review_flag` abbildbar.

---

## 13. Lösch-Lebenszyklus

- **Keine harten Löschungen im Normalbetrieb** – Lauf-/Versionsdaten bleiben
  für Audit & Reproduzierbarkeit erhalten (Soft-Delete-Flag `deleted_at`/`is_active`
  auf dokument-/vertrags-Ebene, falls überhaupt nötig).
- Eine „Löschung“ eines Vertrags im UI entfernt nur den **Current-State**-Zeiger;
  die Lauf-Daten bleiben als Historie (bewusst nicht zerstörend).
- Re-Import einer Datei alter Version oder mit neuem Hash → neue
  `document_version`-Zeile (kein In-Place-Overwrite).
- Tatsächliche physische Bereinigung (`document_file`/Canonical-Payload) nur
  über ein explizites, dokumentiertes Cleanup-Utility (Test-/Entwicklungszwecke);
  nie implizit aus einer Fach-Aktion. Für **Artifacts** (`document_artifact`) wird
  der Lebenszyklus über `lifecycle_state` (`active|orphan|pending_deletion|deleted`)
  und `deletion_owner` verbucht – Wer-Aspekt und wohin zur (Security-)Löschung
  zuständig ist, ist damit dokumentiert; eine Referenzierte Datei wird nie ohne
  Klärung der zugehörigen DB-Zeile gelöscht (siehe §14).
  nie implizit aus einer Fach-Aktion.

---

## 14. Transaktionsgrenzen

- **Import & Processing:** (speichere datei) + (schreibe `document_file`/
  `document_version`) + (schreibe `document_processing_result`) + (referenziere
  `document_artifact`) in **einer** Transaktion – teilweiser Import wird zurückgerollt.
- **Extraktion:** (`contract_extraction` + alle `extraction_evidence` +
  `contract_snapshot`) atomar. Bei ggf. großem Snapshot im Artifact-Storage:
  Die **DB-Referenz** wird atomar committet; der Artifact-Datei-Write folgt dem
  Muster „zuerst Datei schreiben + hash, dann DB-Zeile committen; bei DB-Fehler
  Datei als `orphan` markieren (via `lifecycle_state`), nie eine referenzierte
  Datei löschen, ohne die DB zu klären“.
- **Berechnung:** (`calculation_run` + Ergebnis + `calculation_review_flag`) atomar.
- **Akzeptanz (Current-State):** Update `contract` (Zeiger + Status) + ggf.
  `review_action` atomar.

Kein schreibender Lauf wird unvollständig committet; isolierte Cursor beim
Lesen (READ COMMITTED reicht); für stark konkurrierende Akzeptanz auf einen
Vertrag ggf. optimistisches Locking über `updated_at`/Versions-Spalte.
Artifact-Dateien sind **kein** Teil transversaler DB-Rollbacks – ihre Konsistenz
wird über die `document_artifact.lifecycle_state`-Verbuchung erhalten (§13).

---

## 15. Multi-User / Security

- **Auth** bleibt zunächst deaktiviert (`auth_enabled=False`); Schema trägt aber
  bereits `created_by`/`updated_by`-Referenzen (Optional) auf relevanten
  Tabellen, damit Mehrbenutzer-Audit später ohne Schema-Bruch möglich ist.
- **Keine Secrets in der DB / im Repo** – DB-URL nur über `.env`/`.env.example`.
- **PostgreSQL:** Anwendung verbindet sich mit einem dedizierten, minimal
  privilegiertem DB-Rollen-Account (kein Superuser); Passwörter nur über
  Env-Variablen.
- RLS (Row-Level-Security) bleibt bewusst **offen** (später, falls mehrere
  Krankenhäuser/Mandanten). Lokal/on-prem führt keine Mandantentrennung im MVP.

---

## 16. Suchbereitschaft

- PostgreSQL **Volltextsuche** (`tsvector` + `to_tsvector('german', …)` +
  `@@`-Operator) über den kanonischen Seitentext wird **vorbereitet**
  (Index-Spalte/Generated Column), aber **nicht** in STEP 10A implementiert.
  Für kleine/DB-seitige Snapshots aus dem `JSONB`; für große kanonische
  Payloads im Artifact-Storage wird der Text bei Bedarf in einen normalisierten,
  DB-abfragbaren Ableitungs-Index hydriert (kein Volltext über Artifact-Dateien).
- Kein externer Index-Dienst (ES/Meilisearch/Redis) im MVP – konsistent mit
  der lokalen/on-prem-Architektur.
- Strukturierte Suche (Feldwerte) läuft über die relationalen Spalten
  (Equipment, Status, Risiko, Kosten-Kategorie, denormalisierte `contract`-Projektion).

---

## 17. Migrationsstrategie

- **Alembic** ab DB-Version 1: jede Schema-Änderung als revisable Migration
  (upgrade/downgrade), benannt nach Entität + Änderung.
- Reihenfolge: `document_file`, `document_version`, `document_processing_result`,
  `document_artifact`, `processing_summary`, `contract_extraction`,
  `extraction_evidence`, `calculation_run`, `calculation_result`,
  `calculation_review_flag`, `contract`, `contract_document`, `contract_equipment`.
- Backfill-/Datenmigrations-Skripte getrennt von Schema-Migrationen (nur
  Daten-Umzug, kein Schema-Effekt).
- SQLite→PostgreSQL-Entwicklungstests: SQLAlchemy-Vergleichs-Tests gegen
  In-Memory-SQLite als Lockertest; Produktionspfad ist `postgresql+psycopg`.

---

## 18. Backup / Consistency

- **DB-Backup:** `pg_dump` (PostgreSQL) auf `data/backups/` (nicht eingecheckt).
- **Dokumente/Speicher:** Datei-Sync/Kopie von `data/contracts/` in den
  Backup-Ordner.
- **Konsistenz:** Logische Konsistenz zwischen DB-Zeigern und Datei-Storage wird
  durch die Transaktionsgrenzen (§14) gewährleistet (Datei + DB-Zeile atomar).
- Ein Konsistenz-Prüf-Skript (Optional, STEP später) vergleicht `sha256`/
  `storage_key` gegen die Dateien; fehlt derzeit und ist kein STEP-10-Ziel.

---

## 19. Indizes (Entwurf)

```text
document_file.sha256              UNIQUE  (Duplikaterkennung)
document_file.imported_at                 (Chronologie)
document_version.document_id              (Versionen je Datei)
document_processing_result.document_version_id  (Processing je Version)
document_artifact.document_version_id     (Artefakte je Version)
document_artifact.artifact_type           (Artefakt-Kategorien)
contract_extraction.document_version_id    (Extraktionen je Version)
extraction_evidence.extraction_id          (Evidence je Lauf)
extraction_evidence.page                   (Seiten-Navigation)
extraction_evidence.field_ref              (Feld-Navigation)
calculation_run.extraction_id + as_of_date (Läufe je Extraktion/Datum)
contract.status                            (Statusfilter, Dashboard/Liste)
contract.risk_level                        (Risikoaggregation)
contract.accepted_extraction_id           (Current-State-Zeiger)
contract_document.contract_id              (Dokumente je logischem Vertrag)
contract_document.document_version_id      (Verträge je Dokument)
```

Indizes werden in STEP 10B als Alembic-`op.create_index` angelegt; übermäßiges
Indexieren wird vermieden (nur auf abfragerelevante Spalten/Sortierungen).

---

## 20. Offene Fragen – nach STEP-10A-Review

### Vom Review entschieden

1. **Denormalisierte Such-/Current-Contract-Spalten** – **APPROVED** (§6 `contract`):
   de-normalisierte Projektions-/Current-State-Felder (supplier, contract_number,
   start_date, end_date, …) sind erlaubt für Liste/Dashboard; sie sind
   **Projektion, nicht Provenienz-Source-of-Truth**. Historischer
   ExtractionSnapshot bleibt maßgeblich dafür, **was ein Lauf erzeugt hat**.
2. **Evidence-JSONB + relationale Duplikation** – **APPROVED nur mit expliziter
   Ownership** (§10): immutablable Snapshot = Lauf-Wahrheit (Reproduzierbarkeit);
   relationale `extraction_evidence` = operative/abfragbare Quell-Navigations-
   Projektion. Synchronisations-/Integritätsregel: atomarer Write im selben
   Lauf + `field_ref`-Bindung + Verifikations-Test (kein stilles Auseinanderlaufen).
3. **TERMINATED-Limitierung** – **ACCEPTED** als bekannte Schema-Limitierung;
   kein Term-Evidence wird in STEP 10 erfunden; konservatives STEP-9-Verhalten
   beibehalten (§11).
4. **UUID-PK-Policy** – **UUIDv4 → UUIDv7** ersetzt; **database-side** UUIDv7
   (PostgreSQL 18 `uuidv7()`) als konsistentes Ownership-Modell (§2A), da die
   Backend-Laufzeit Python 3.10.11 ist (kein Stdlib `uuid.uuid7`, keine dritte
   UUID-Bibliothek).

### Verbleibende offene Fragen (keine Blocker fürs Gate, für STEP 10B zu klären)

5. **SQLite im Test vs. PostgreSQL im CI** – isoliertes In-Memory-SQLite für
   deterministische Unit-Tests ist erlaubt; die Frage, ob CI zusätzlich gegen
   echtes PostgreSQL läuft, hängt von der Pipeline-Ressource ab.
6. **Zeitzonen-Konvention** – alle technischen Timestamps als TIMESTAMPTZ in UTC,
   anzeigesetig konvertiert (Bestätigt, kein Blocker).
7. **Backup-Häufigkeit/Retention** – offen; nur Konzept in §18, keine konkrete
   Policy/Retentions-Metrik (kein STEP-10-Implementierungs-Blocker).
8. **Exakte JSONB-vs-Artifact-Schwelle/Erstzuordnung** – die §7B-Erstzuordnung ist
   ein Entwurf; eine **messungsgestützte** Feinjustierung (Payload-Größen im
   Benchmark/Smoke-Test) erfolgt während/ nach STEP 10B, **nicht** als willkürliche
   feste Schwelle vorab.

**Kein weiterer offener Punkte, der das STEP-10B-Gate blockiert.**

---

## 21. Bewusst NICHT implementiert in STEP 10

- **Keine** SQLAlchemy-Modelle, **keine** Alembic-Migrationen, **keine**
  PostgreSQL-Abhängigkeiten (`psycopg`/`asyncpg`) installiert.
- **Kein** Laufzeitverhalten geändert (Import/Extraktion/Berechnung/API unverändert).
- **Kein** Artifact-Storage-/Write-Code, **keine** `document_artifact`/
  `contract_document`-Implementierung (nur Schema-Design future-safe).
- **Keine** Amendment-/Mehrdokument-Interpretation implementiert.
- **Kein** Volltext-Suchindex, **kein** Start des Berechnungs-Orchestrators.
- **Keine** RLS, **keine** Auth-Teile, **kein** manuelles Korrektur-Workflow-Code.
- **Keine** `tsvector`-Generated-Columns.
- **Keine** Migrations-/Backfill-Skripte.
- Explizit **nicht** ausgeführt: Qwen/OCR/Docling/Benchmarks.
- **Nicht** umgeschrieben: bestehende app-erzeugte `document_id`s (Kompatibilität,
  §2A) – keine Konvertierungs-Migration auf UUIDv7.

STEP 10A hat **nur** die bestehende Architektur inspiziert (Dokument-Import/
Storage, Canonical/Processing-Modell, SourceEvidence/BoundingBox, Contract-
Extraktion, STEP-9-Berechnungs-Resultate, API-Routen, Config/Speicherpfade) und
diesen Design-Vorschlag erzeugt. **STEP 10 gilt NICHT als abgeschlossen.**

---

## Nächster Schritt (nach Genehmigung)

- STEP 10B: SQLAlchemy-Modulstruktur unter `backend/app/database/` anlegen
  (session, base, models), PostgreSQL-Treiber, Alembic-Bootstrap mit
  `op.create_table`/Indizes, minimale Service-Anbindung – jeweils mit Tests.
- Fortschritt erst danach über 9/18 hinaus (STEP 10-Status wird im Moment des
  Abschlusses gesetzt und in `docs/PROJECT_PROGRESS.md` aktualisiert).

**Stop: auf Genehmigung für STEP 10B warten.**
