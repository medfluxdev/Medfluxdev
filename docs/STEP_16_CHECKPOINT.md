# STEP 16 – Benutzer/Login & Audit – Checkpoint

Stand: 2026-09-12
Branch: `JAMAL`
Status: **Implementiert; gezielte DB-freie Runtime-Gates bestanden; PostgreSQL-/E2E-Gate ausstehend**

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

Bounded Gate auf Branch `JAMAL`, Commit `cb2029645efa9b4c7c2606dfadf0d3853e090cc5`, sauberer Worktree:

- Auth-Security-Tests mit `MEDFLUX_UNIT_ONLY=1`: **5 passed in 0.42s**
- `app.main:app` Import ohne Serverstart/DB-Verbindung: **bestanden**
- erforderliche Auth-/Audit-Routen registriert: `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/audit`
- Frontend Production-Build: **bestanden** (`Next.js 14.2.15`, Lint/Types OK, 14 Seiten generiert)
- relevante Python-Dateien wurden mit `py_compile` erfolgreich geprüft

Dieser Nachweis beweist bewusst **nicht** die Migration oder DB-gestützte Auth-/Provenienzpfade.

## Noch zu beweisen (PostgreSQL-/E2E-Gate)

1. Migration `d7e1f2a5b3c6` auf isolierter PostgreSQL-Testdatenbank bis `head`.
2. gezielter Login → `/me` → Review/Override → Provenienz → Audit-Smoke-Test gegen isolierte DB.
3. Viewer-Mutationsschutz und Organisations-Isolation gegen isolierte DB.

## Sicherheitsgrenzen

- Kein externer Identity-/AI-Dienst.
- Session-Secret nie im Repository.
- Keine Testausführung gegen das Produkt-Schema `public`.
- Rollen-/Org-Grenzen werden serverseitig erzwungen; Query-Parameter sind keine Credentials.
- Bestehende unverifizierte Dev-Einträge bleiben ehrlich als `manual_unverified`/`is_development` erkennbar.

Schritt 16 wird in `PROJECT_PROGRESS.md` erst nach bestandenem PostgreSQL-/E2E-Gate auf **ABGESCHLOSSEN** gesetzt.
