# STEP 16 – Benutzer/Login & Audit – Checkpoint

Stand: 2026-09-12
Branch: `JAMAL`
Status: **ABGESCHLOSSEN – PostgreSQL-Migration, Auth-E2E, Rollen- und Org-Grenzen bestanden**

## Implementiert

### Lokale Benutzer
- organisationsgebundene `app_user`-Entität
- Rollen `admin`, `reviewer`, `viewer`
- aktiv/inaktiv, Anzeigename, letzter Login
- PBKDF2-SHA256 mit zufälligem Salt und versioniertem Hashformat
- interaktives lokales Bootstrap-Script ohne Passwort in CLI/History

### Sitzung
- signierte HMAC-SHA256-Session mit Ablaufzeit
- HttpOnly-Cookie
- SameSite konfigurierbar
- Secure-Cookie für HTTPS-Pilot konfigurierbar
- `AUTH_ENABLED=true` verweigert Start mit `APP_SECRET_KEY=change-me`

### Autorisierung
- zentrale API-Auth-Grenze bei aktiviertem Auth-Modus
- `organization_slug` darf nicht von der authentifizierten Organisation abweichen
- Viewer sind read-only
- Reviewer/Admin dürfen fachliche Mutationen
- bestehender `AUTH_ENABLED=false`-Entwicklungsmodus bleibt kompatibel

### Provenienz/Audit
- `fact_review.authenticated_actor_id` → `app_user.id`
- `contract_review.authenticated_actor_id` → `app_user.id`
- `contract_override.actor_id` → `app_user.id`
- serverseitige Request-Provenienz überschreibt clientseitige Review-Namen mit der authentifizierten Identität
- `authenticated_local` kennzeichnet diese Provenienz
- `audit_event` ist append-only und organisationsgebunden
- Login/Logout erzeugen persistente Audit-Ereignisse
- `/api/audit` liefert nur Ereignisse der eigenen Organisation

### Frontend
- `/login`
- Credentials/Cookies auf API-Aufrufen
- authentifizierter Benutzer + Rolle im Sidebar-Footer
- Abmelden
- System-Audit zusätzlich zum Vertrags-Audit

## Laufzeitnachweis vom 2026-09-12

### DB-freie Gates

Auf Commit `cb2029645efa9b4c7c2606dfadf0d3853e090cc5`:

- Auth-Security-Tests mit `MEDFLUX_UNIT_ONLY=1`: **5 passed in 0.42s**
- `app.main:app` Import ohne Serverstart/DB-Verbindung: **bestanden**
- erforderliche Auth-/Audit-Routen registriert: `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/audit`
- Frontend Production-Build: **bestanden** (`Next.js 14.2.15`, Lint/Types OK, 14 Seiten generiert)
- relevante Python-Dateien mit `py_compile`: **bestanden**

### Isolierter PostgreSQL-Gate

Auf Commit `93c5677207cae96445fb8fc3179ebfd93ecbadc7`, ausschließlich gegen disposable Testdatenbanken:

- Migration `alembic upgrade head`: **bestanden**
- `alembic current == head == d7e1f2a5b3c6`: **bestanden**
- genau ein Alembic-Head: **ja**
- Tabellen `organization`, `contract`, `app_user`, `audit_event`: **vorhanden**
- Provenienz-Schema/FKs: **bestanden**
- Auth-Security: **5 passed**
- bestehende Org-Isolation: **bestanden**
- bestehende Audit-/Provenienz-Tests: **bestanden**
- temporäre Datenbanken nach dem Gate vollständig entfernt

### Gezielter Auth-E2E-Gate

Auf Commit `5392c049657e8e35c178dee3ede51af1f49a56fa` wurde `backend/tests/test_auth_e2e.py` gegen eine eigene disposable PostgreSQL-Datenbank ausgeführt:

- Ergebnis: **3 passed, 5 warnings in 2.60s**
- Login → `/api/auth/me` → Audit → Logout: **bestanden**
- Cross-Org-Isolation: **bestanden**
- Viewer-Schreibschutz: **bestanden**
- Reviewer-Schreibzugriff: **bestanden**
- temporäre Testdatenbank: **erfolgreich entfernt**

Damit ist der für Schritt 16 definierte PostgreSQL-/E2E-Gate erfüllt.

## Sicherheitsgrenzen

- Kein externer Identity-/AI-Dienst.
- Session-Secret nie im Repository.
- Tests laufen ausschließlich gegen isolierte PostgreSQL-Testumgebungen; Produktdaten werden nicht für Test-Fixtures verwendet.
- Rollen-/Org-Grenzen werden serverseitig erzwungen; Query-Parameter sind keine Credentials.
- Bestehende unverifizierte Dev-Einträge bleiben ehrlich als `manual_unverified`/`is_development` erkennbar.

Schritt 16 ist auf Basis der dokumentierten Runtime-Nachweise **ABGESCHLOSSEN**.
