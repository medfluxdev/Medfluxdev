# MedFlux – Installation fuer lokalen Krankenhaus-Pilot

Stand: 2026-09-12

## 1. Voraussetzungen

- Windows/Linux Host im geschuetzten lokalen Netz
- PostgreSQL
- Python mit Backend-Venv
- Node.js fuer das Next.js-Frontend
- Ollama oder anderer explizit lokaler kompatibler Provider
- optional OCR-/Document-Intelligence-Abhaengigkeiten
- `pg_dump` und `pg_restore` fuer Backup/Restore

## 2. Konfiguration

`.env.example` nach `.env` uebernehmen und mindestens setzen:

```text
DATABASE_URL=postgresql+psycopg://<user>:<password>@127.0.0.1:5432/medflux
CORS_ORIGINS=http://localhost:3000
AUTH_ENABLED=true
APP_SECRET_KEY=<langes-zufaelliges-secret>
AUTH_COOKIE_SECURE=false
```

Bei HTTPS-Pilotbetrieb:

```text
AUTH_COOKIE_SECURE=true
```

`APP_SECRET_KEY=change-me` ist bei aktivierter Authentifizierung nicht erlaubt.

Fail-closed-Defaults (Security Phase-1):

- `BACKEND_HOST` lauscht standardmaessig nur auf `127.0.0.1`. Fuer eine
  Exposition im LAN/Pilot explizit auf `0.0.0.0` setzen.
- `AUTH_ENABLED` ist standardmaessig `true`. Ein unauthentifizierter
  Entwicklungs-/Testbetrieb erfordert explizit `AUTH_ENABLED=false` UND
  `MEDFLUX_INSECURE_DEV=true` (nur `development`/`test`; `pilot`/`production`
  lehnen beides ab).
- PostgreSQL-TLS: Bei einer entfernten Datenbank verlangt
  `pilot`/`production` eine gesicherte `sslmode`-Stufe in der `DATABASE_URL`
  (empfohlen `sslmode=verify-full`, bei Bedarf mit `sslrootcert`). Loopback-
  und Unix-Socket-Verbindungen bleiben ohne TLS zulaessig. Beispiel:

  ```text
  DATABASE_URL=postgresql+psycopg://<user>:<password>@db.example.org:5432/medflux?sslmode=verify-full
  ```

## 3. Backend

Aus dem Repository-Root:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

Danach ersten lokalen Admin anlegen:

```powershell
cd ..
.\backend\.venv\Scripts\python.exe scripts\create_local_user.py --organization <slug> --username <name> --role admin
```

Passwort niemals in Commit, Shell-History oder Projektdateien speichern.

Backend starten:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 4. Frontend

```powershell
cd frontend
npm ci
npm run build
npm run start
```

Fuer Entwicklungsbetrieb ist `npm run dev` moeglich, aber der Pilot-Gate muss
mit einem Production-Build bestanden sein.

## 5. Lokale KI

Standardkonfiguration:

```text
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Das konkrete Modell wird ueber die MedFlux-Einstellungen bzw. lokale
Konfiguration festgelegt. Modellserver nicht ungeschuetzt ins externe Netz
binden.

## 6. Smoke-Test

Vor echten Daten:

1. `/health` erreichbar (alternative Liveness-Url `/live`, Readiness-Url `/ready`)
2. Login mit lokalem Benutzer
3. `/api/auth/me` zeigt Benutzer/Organisation/Rolle
4. Testvertrag importieren
5. Analyse/Nachweise sichtbar
6. menschliche Review-Aktion durchfuehren
7. Audit pruefen
8. CSV-Export pruefen
9. Backup in temporaeres Ziel erstellen und verifizieren

## 7. Backup

Beispiel:

```powershell
.\backend\.venv\Scripts\python.exe scripts\backup_medflux.py --organization <slug> --target C:\MedFluxBackups\backup-YYYYMMDD-HHMM
.\backend\.venv\Scripts\python.exe scripts\verify_backup.py C:\MedFluxBackups\backup-YYYYMMDD-HHMM
```

Das Zielverzeichnis darf noch nicht existieren.

## 8. Restore-Test

Nur in eine isolierte Test-Datenbank:

```powershell
.\backend\.venv\Scripts\python.exe scripts\restore_backup.py C:\MedFluxBackups\backup-YYYYMMDD-HHMM --target-database-url postgresql+psycopg://<testuser>:<password>@127.0.0.1:5432/medflux_restore_test --target-documents-dir C:\MedFluxRestoreTest\documents
```

Restore in die aktuell konfigurierte MedFlux-Datenbank wird vom Skript
verweigert.

## 9. Pilot-Hardening

Vor Freigabe fuer echte Krankenhausdaten:

- HTTPS oder vollstaendig geschuetzte lokale Transportstrecke
- `AUTH_COOKIE_SECURE=true` bei HTTPS
- Betriebssystem-/Volume-Verschluesselung
- PostgreSQL-Benutzer mit minimalen Rechten
- Backup-Zugriffsrechte begrenzen
- Firewall/Egress fuer lokale KI festlegen
- Restore-Prozess regelmaessig isoliert testen
- dokumentierte Retention/Loeschregeln
