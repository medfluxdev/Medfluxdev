# STEP 17 Checkpoint – Export & Backup

Stand: 2026-09-12
Branch: `JAMAL`

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
- organisationsgebundene Originaldokumente werden aus dem kanonischen Storage gelesen
- SHA-256 des Originaldokuments wird gegen die DB-Metadaten verifiziert
- `manifest.json` enthaelt SHA-256 und Dateigroesse von DB-Dump und Dokumenten
- bei Fehler wird ein unvollstaendiges Backup-Ziel entfernt

### Integritaetspruefung

`scripts/verify_backup.py`

- prueft Backup-Format
- verhindert Manifest-Path-Traversal
- prueft Existenz, SHA-256 und Dateigroesse aller Artefakte
- erkennt doppelte Dokument-IDs im Manifest

### Restore

`scripts/restore_backup.py`

- Restore-Ziel-DB ist obligatorisch
- Restore in die konfigurierte laufende MedFlux-Datenbank wird explizit verweigert
- `pg_restore` ohne `shell=True`
- `--clean/--if-exists` nur nach explizitem `--clean-target`
- Dokument-Target muss leer sein
- Manifest wird vor jeglichem Restore validiert

## Tests

`backend/tests/test_step17_backup_security.py`

- gueltiges Manifest
- manipuliertes SHA-256
- Path-Traversal im Manifest
- Verbot des Restore in die laufende konfigurierte Datenbank

## Noch zu beweisen (Runtime Gate)

- Step-17 Unit-Tests mit `MEDFLUX_UNIT_ONLY=1`
- CSV-Route Import/Registration-Smoke
- `pg_dump`/`pg_restore` gegen eine isolierte temporaere Test-Datenbank
- Backup -> Verify -> Restore -> Datenabgleich in isoliertem Ziel

Diese Runtime-Gates duerfen keine Produktdatenbank ueberschreiben oder loeschen.
