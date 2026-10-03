# STEP 17 Checkpoint – Export & Backup

Stand: 2026-09-12
Branch: `JAMAL`
Status: **ABGESCHLOSSEN; CSV-Export sowie echter PostgreSQL Backup/Verify/Restore-Gate bestanden**

## Implementiert

### Vertragsportfolio-Export

- `GET /api/operations/contracts.csv`
- organisationsgebunden
- bei aktivierter Authentifizierung ist die signierte Session die Autoritaetsquelle
- optional `include_archived`
- UTF-8 mit BOM, Semikolon-Trennung fuer lokale Excel-Kompatibilitaet
- keine OCR-Rohdaten, Storage-Pfade, Secrets oder internen Modellpayloads

### Backup

`scripts/backup_medflux.py`

- PostgreSQL Custom-Format ueber `pg_dump`
- kein `shell=True`
- Passwort nur ueber `PGPASSWORD` im Child-Environment, nicht in geloggten CLI-Argumenten
- Backup-Ziel wird nie ueberschrieben
- organisationsgebundene Storage-Objekte werden unter ihrem kanonischen `storage_key` gesichert
- SHA-256 wird gegen DB-Metadaten verifiziert, sofern vorhanden
- Manifest enthaelt DB-Dump-Hash/-Groesse sowie kanonische Storage-Objekte mit Hash/Groesse/Quellzeilen
- bei Fehler wird ein unvollstaendiges Backup-Ziel entfernt

### Integritaetspruefung

`scripts/verify_backup.py`

- prueft Backup-Format
- verhindert Manifest-Path-Traversal und absolute Pfade
- prueft Existenz, SHA-256 und Dateigroesse von DB-Dump und Storage-Objekten
- erkennt doppelte `storage_key`-Eintraege
- validiert kanonische Storage-Referenzen

### Restore

`scripts/restore_backup.py`

- Restore-Ziel-DB ist obligatorisch
- Restore in die konfigurierte laufende MedFlux-Datenbank wird explizit verweigert
- `pg_restore` ohne `shell=True`
- `--clean/--if-exists` nur nach explizitem `--clean-target`
- Storage-Target muss leer/neu sein
- Manifest wird vor jeglichem Restore validiert
- kanonische `storage_key`-Struktur wird exakt wiederhergestellt
- Legacy-Manifest ohne rekonstruierbaren `storage_key` wird nicht als vollstaendiger Restore ausgegeben

## Laufzeitnachweis vom 2026-09-12

### Sicherheits-/Import-Gates

Auf Commit `cb2029645efa9b4c7c2606dfadf0d3853e090cc5`:

- `backend/tests/test_step17_backup_security.py`: **6 passed in 0.19s**
- `/api/operations/contracts.csv` ist im importierten FastAPI-Routing registriert
- Backup-/Verify-/Restore-Skripte mit `py_compile`: **bestanden**

### Echter isolierter PostgreSQL Backup/Restore-Gate

Auf Commit `93c5677207cae96445fb8fc3179ebfd93ecbadc7`, ausschließlich gegen disposable PostgreSQL-Datenbanken:

- temporäre Source-DB erstellt: **bestanden**
- Alembic bis `head d7e1f2a5b3c6`: **bestanden**
- `backup_medflux.py` mit realem `pg_dump`: **bestanden**
- `verify_backup.py`: **bestanden**
- zweite temporäre Restore-DB erstellt
- `restore_backup.py` mit realem `pg_restore`: **bestanden**
- Schema-/Alembic-Vergleich nach Restore: **bestanden**
- Source- und Restore-Testdatenbanken danach vollständig entfernt

### Echter organisationsgebundener CSV-E2E-Gate

Auf Commit `e536927216c0d62e5205953064a261745a269aee`, ausschließlich gegen eine disposable PostgreSQL-Datenbank:

- `backend/tests/test_step17_csv_e2e.py`: **3 passed in 1.92s**
- authentifizierter CSV-Export: **bestanden**
- Organisations-Isolation: **bestanden**
- Cross-Org-Abfrage verborgen/404: **bestanden**
- archivierte Verträge standardmäßig enthalten: **bestanden**
- `include_archived=false` filtert archivierte Verträge: **bestanden**
- UTF-8 BOM: **bestanden**
- Semikolon-CSV: **bestanden**
- `Cache-Control: private, no-store` / `X-Content-Type-Options: nosniff`: **bestanden**
- disposable Testdatenbank danach entfernt

Damit sind die fachlichen Runtime-Kriterien von STEP 17 erfüllt.
