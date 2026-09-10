# Medflux — STEP 10 Checkpoint (Datenbank-Persistenz, PostgreSQL + SQLAlchemy + Alembic)

Datum: 31.08.2026 · Fortschritt: **10 / 18 = 55,6 %**

STEP 10 setzt das genehmigte Design `docs/STEP_10_DATABASE_DESIGN.md` um
(STEP 10B). Es legt die **Persistenz-Fundament** für Import, Verarbeitung,
Extraktion, Berechnung, Contract-Projektion und Quell-Navigation auf
**PostgreSQL 18.6** – nativ auf Windows (nach instabilem WSL2-Netzwerk).

## 1. Architektur-Überblick

```
                        backend/app/database/
 config (DB-URL)  ──►   session.py (Session/engine)
 │                       base.py   (Declarative Base + Naming-Convention)
 │                       columns.py(CommonColumnMixin, JSONB, MoneyMixin)
 └──► models/            services.py (EINZIGER Schreibpfad)
      ├─ organization     │  create_organization / get_organization (idempotent)
      ├─ document         │  save_document_file (SHA-256-Dedup, external_id)
      ├─ artifact         │  create_document_version / save_artifact
      ├─ processing       │  create/finish_processing_run, upsert_processing_summary
      ├─ extraction       │  save_extraction (atomar Run+Snapshot+Evidence, SHA-256)
      ├─ calculation      │  verify_extraction_integrity (Snapshot↔Evidence)
      ├─ contract         │  save_calculation (atomar Run+Result+Flags, Decimal)
      ├─ review           │  create_contract, project_contract, accept_* , link_document
      └─ __init__ (15)    │  add_equipment, resolve_source_navigation (STEP-8B-Kette)
                           └─ flock über PG-Transaktionen (rollback-per-Test)

 Alembic: backend/alembic/ (env.py nutzt settings.database_url)
   versions/20260831_4d930fb1d75e_initial_schema.py  (16 Tabellen + zirkulärer FK)
   -> native PG 18.6 (Service postgresql-x64-18, Port 5432, 127.0.0.1)
```

Einstieg:

```python
from app.database.services import save_extraction, resolve_source_navigation
status = save_extraction(db, run_id=..., payload=...)  # -> atomar Run+Snapshot+Evidence
nav = resolve_source_navigation(db, contract_id=...)
```

## 2. Grundprinzipien

- **Design ist autoritativ** (`docs/STEP_10_DATABASE_DESIGN.md`): 15 ORM-
  Entitäten, an §6 angeglichen.
- **Transaktionsgrenzen (§14):** inidividuelle kurzlebige Transaktionen für
  Status/koordinierende Schritte; teure Verarbeitung (KI/OCR) liegt **außerhalb**
  tiefer DB-Transaktionen; Ergebnis-Records werden am Ende kurz/atomar
  persistiert.
- **UUIDv7 datenbank-seitig** (`uuidv7()` aus PG 18, ORM `server_default`,
  Abruf per RETURNING). Keine Drittbibliothek. Bestehende app-erzeugte IDs
  bleiben kompatibel (`document_file.external_id`, kein Konvertierungs-Migration).
- **SHA-256-Idempotenz:** `document_file.sha256` und `document_version.sha256`
  UNIQUE → Retry erzeugt keine Duplikat-Historie, markiert `duplicate_detected`.
- **Kein Blankett-JSONB (§7):** große Payloads / Original → `document_artifact`,
  relativer `storage_key` + sha256; Lösch-Lifecycle (§13).
- **Money/Decimal:** NUMERIC(18,2), als `Decimal` zurückgelesen (nie Binär-
  Float); Währung separat. `as_of_date` explizit persistent (kein substituiertes
  „heute" in gespeicherter Berechnung).
- **TERMINATED nur explizit (§11):** `Contract.status` kommt nur aus Modell-
  Status, nie aus abgelaufenem Ende abgeleitet.
- **Quell-Navigation (§8B):** Contract → extraction_evidence → contract_
  extraction → document_version → document_file → `storage_key`/original_filename.
  `bounding_box` bleibt `None`, wenn die Quelle keine Geometrie liefert.
- **Credentials nur in gitignored `backend/.env`;** Settings-Default ohne Passwort.

## 3. Implementierte Persistenz-Services (`services.py`)

- **Organisation**: `create_organization` / `get_organization` (idempotent über slug).
- **Dokument**: `save_document_file` (SHA-256-Dedup, `import_status`-Validierung,
  `external_id`), `create_document_version` (setzt `organization_id`),
  `save_artifact` (Typ/Lifecycle-Validierung, relativer `storage_key`).
- **Verarbeitung**: `create_processing_run`, `finish_processing_run`,
  `upsert_processing_summary`.
- **Extraktion (atomar)**: `save_extraction` schreibt Lauf + immutablen
  `contract_snapshot` (JSONB, `snapshot_sha256`) + relationale `extraction_
  evidence` mit `field_ref`-Bindung in EINEM Lauf; `verify_extraction_integrity`
  prüft Snapshot-Index ↔ evidence_rows.
- **Berechnung (atomar)**: `save_calculation` schreibt Run + Result-Rows +
  Review-Flags; Beträge via `_to_decimal` (Decimal, nie Binary-Float).
- **Contract**: `create_contract`, `project_contract` (deterministische
  Projektion; Status lowercase; TERMINATED nur explizit), `accept_extraction` /
  `accept_calculation` (Current-Zeiger), `link_document` (n:m idempotent mit
  Rollenliste), `add_equipment`.
- **Quell-Navigation**: `SourceNavigation`-Dataclass + `resolve_source_navigation`
  (voller STEP-8B-Pfad; Kette verläuft jetzt über `extraction.document_version_id`).

## 4. Datenmodell (15 ORM-Entitäten)

| Bereich | Entitäten |
|---------|-----------|
| Organisation | `organization` (slug unique) |
| Dokument | `document_file`, `document_version` |
| Artifakt/PNG | `document_artifact` (storage_key relativ, lifecycle_state) |
| Verarbeitung | `document_processing_result`, `processing_summary` |
| Extraktion | `contract_extraction` (snapshot JSONB + sha256), `extraction_evidence` (field_ref) |
| Berechnung | `calculation_run` (as_of_date), `calculation_result`, `calculation_review_flag` |
| Contract | `contract` (accepted_*-Zeiger), `contract_document` (n:m, Rollen), `contract_equipment` |
| Log | `review_action` |

- Kurze Constraint-Namen (Naming-Convention `ck_<table>_<constraint>`).
- Zirkulärer FK `document_artifact.processing_run_id` → `document_processing_
  result` via `op.create_foreign_key` NACH beide create_table (Alembic
  `sorted_tables`-Zyklus erwartet).
- 5 überlange FK-Identifier (>63 Zeichen) auf kompakte Namen gekürzt.

## 5. Alembic-Migration

- `alembic.ini` / `env.py` (nutzt `settings.database_url`,
  `target_metadata = Base.metadata`, `compare_type=True`, sys.path 0=".").
- Initiale Migration `20260831_4d930fb1d75e_initial_schema.py`:
  korrekte create-Reihenfolge (organization → document_file → document_version
  → document_artifact (ohne zirkulären FK) → document_processing_result →
  `fk_artifact_processing_run_id_result` → contract_extraction →
  processing_summary → calculation_run → extraction_evidence →
  calculation_result → calculation_review_flag → contract → contract_document →
  contract_equipment → review_action).
- Verifikation gegen native PG 18.6: **upgrade → downgrade → re-upgrade
  bestanden**; 16 Tabellen (15 Domain + alembic_version) + zirkulärer FK.
- Alembic-Hinweis: `sorted_tables`-Zyklus zwischen document_artifact und
  document_processing_result ist erwartet (deshalb manuelle Migration).

## 6. Test-Suite

- **25 fokussierte PG-Tests** in `backend/tests/test_database_persistence.py`
  (Fixture `engine`/`db`/`_require_pg`; PostgreSQL-Transaktion-pro-Test mit
  Rollback; Skip, wenn PG nicht erreichbar). Abdeckung: UUIDv7-PK, Org-
  Idempotenz, document_file + document_version SHA-256-Dedup, invalid
  import_status rejected, relativer storage_key, Artifact-Typen/Lifecycle,
  Processing-Run/Summary, atomare Extraktion + Integrity, invalid extraction
  status rejected, atomare Berechnung + **Decimal statt Float** + as_of_date,
  Contract-Projektion, TERMINATED-Regel, Accept-Zeiger, n:m-Idempotenz +
  invalid role rejected, Equipment, Quell-Navigation-Kette (storage_key +
  original_filename + bounding_box None), None ohne akzeptierten Lauf,
  JSONB-Snapshot-Roundtrip, Evidence-Cascade.
- **Volle Backend-Suite: 316 passed** (291 Bestand + 25 neue, 0 Regressionen;
  5 PyMuPDF-SWIG-Warnungen, benign).

## 7. Bekannte Probleme / nächster Schritt

- **Grenzen:** kein RBAC/RLS (nur Ownership-Foundation), kein STEP-16-Audit,
  kein STEP-17-Backup/Export; Berechnungs-/Import-Orchestrator und APIBindung
  folgen; Artifact-Anbindung an bestehende `DocumentStorage`-Logik später.
- **Nächster Schritt:** Schritt 11 – Warnsystem (EXPIRING_SOON, Warnstufen,
  Handlungsbedarf).
