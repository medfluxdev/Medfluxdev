# STEP 17 Checkpoint – Export & Backup

Stand: 2026-09-12
Branch: `JAMAL`
Status: **Implementiert; Unit-/Import-Gates bestanden; isolierter PostgreSQL Backup/Restore-Gate ausstehend**

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

Bounded Gate auf Branch `JAMAL`, Commit `cb2029645efa9b4c7c2606dfadf0d3853e090cc5`, sauberer Worktree:

- `backend/tests/test_step17_backup_security.py`: **6 passed in 0.19s**
- `/api/operations/contracts.csv` ist im importierten FastAPI-Routing registriert
- Backup-/Verify-/Restore-Skripte wurden mit `py_compile` erfolgreich geprüft

Dieser Nachweis prueft die Sicherheitslogik der Skripte, ersetzt aber **keinen echten `pg_dump`/`pg_restore`-Durchlauf**.

## Noch zu beweisen (isolierter PostgreSQL Runtime Gate)

- `pg_dump`/`pg_restore` gegen eine eindeutig disposable temporaere Test-Datenbank
- Backup → Verify → Restore → Datenabgleich in isoliertem Ziel
- CSV-Export mit echter organisationsgebundener DB-Fixture

Diese Runtime-Gates duerfen keine Produktdatenbank ueberschreiben oder loeschen.
