# STEP 18 Checkpoint – Release Candidate & Krankenhaus-Pilot

Stand: 2026-09-12
Branch: `JAMAL`
Status: **RC candidate; PostgreSQL-Migration, Auth-E2E und Backup/Restore gruen; CSV-Fixture, breite Regression und Realbenchmark ausstehend**

## Statisch umgesetzt

- STEP 16 lokale Authentifizierung/RBAC/Audit
- STEP 17 CSV-Export, Backup, Integritaetspruefung, isolierter Restore
- Frontend-Sicherheitsheader/CSP
- Backend-Sicherheitsheader und `no-store` fuer API-Antworten
- Security Review: `docs/SECURITY_REVIEW.md`
- Datenschutz-/Datenfluss-Uebersicht: `docs/DATA_PROTECTION.md`
- Pilot-Installationsanleitung: `docs/INSTALLATION_PILOT.md`

## Laufzeitnachweis vom 2026-09-12

### Build-/DB-freie Gates

Auf Commit `cb2029645efa9b4c7c2606dfadf0d3853e090cc5`:

- Python-Compile-Gate: **bestanden** fuer 12 relevante Step-16/17/18-Dateien
- Auth-Security-Tests: **5 passed in 0.42s** (`MEDFLUX_UNIT_ONLY=1`)
- Step-17 Backup-Security-Tests: **6 passed in 0.19s**
- UAT Kosten-Semantik: **1 passed in 0.21s**
- Backend Import-/Route-Smoke: **bestanden**
- registrierte Pfade: `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/audit`, `/api/operations/contracts.csv`
- Frontend Production-Build: **bestanden** (`Next.js 14.2.15`, Lint/Types OK, 14 statische/dynamische Seiten generiert)

### Isolierter PostgreSQL-Gate

Auf Commit `93c5677207cae96445fb8fc3179ebfd93ecbadc7`:

- PostgreSQL-Verbindung: **bestanden**
- Server: PostgreSQL **18.6**
- Testrolle kann disposable Datenbanken anlegen
- Migration `alembic upgrade head`: **bestanden**
- `alembic current == head == d7e1f2a5b3c6`: **bestanden**
- genau ein Alembic-Head: **ja**
- Step-16 Tabellen/Provenienz-Schema vorhanden: **bestanden**
- bestehende Org-/Audit-/Provenienztests: **bestanden**
- realer `pg_dump` → Verify → `pg_restore` gegen zweite disposable DB: **bestanden**
- Schema- und Alembic-Vergleich nach Restore: **bestanden**
- alle temporären Datenbanken danach entfernt

### Gezielter Auth-E2E-Gate

Auf Commit `5392c049657e8e35c178dee3ede51af1f49a56fa`:

- `backend/tests/test_auth_e2e.py`: **3 passed, 5 warnings in 2.60s**
- Login → `/me` → Audit → Logout: **bestanden**
- Cross-Org-Isolation: **bestanden**
- Viewer-Mutationsschutz: **bestanden**
- Reviewer-Schreibzugriff: **bestanden**
- disposable Testdatenbank danach entfernt

STEP 16 ist damit abgeschlossen. Der echte PostgreSQL Backup-/Restore-Gate von STEP 17 ist ebenfalls erfüllt.

## Verbleibende Release-Kriterien

1. CSV-Export organisationsgebunden gegen echte isolierte PostgreSQL-Fixture mit Auth
2. sichere breitere Backend-Regression bzw. gezielte Rest-Risiko-Suite
3. realer Vertragsbenchmark (Accutron) mit dokumentierter Evidence-/Feldqualitaet

## Bereits bestanden

- gezielte Auth-/Security-Unit-Tests
- PostgreSQL-Migration bis Head
- Login-/Session-/Audit-E2E
- Viewer-Mutationsschutz und Org-Isolation
- gezielte Step-17 Backup-Security-Unit-Tests
- echter Backup → Verify → Restore-Gate
- UAT Kosten-Semantik-Test
- Backend Import-/Route-Smoke
- Frontend Production-Build

## Keine falsche Release-Behauptung

Solange eines der verbleibenden Runtime-Gates fehlt, bleibt der Status `RC candidate`.
Insbesondere darf kein echter Vertragsbenchmark durch synthetische Fixtures ersetzt werden.

## Bekannte Rest-Risiken vor Pilot

- PostgreSQL-RLS ist noch nicht als zweite Mandanten-Isolationsschicht aktiviert.
- CSP enthaelt wegen Next.js derzeit `unsafe-inline` und `unsafe-eval`; fuer
  internet-exponierten Betrieb sollte eine nonce-/production-spezifische CSP folgen.
- Retention-/Loeschfristen sind Betreiberentscheidungen und nicht automatisch
  als rechtliche Policy implementiert.
- HTTPS/TLS ist Deployment-Aufgabe; bei HTTPS muss `AUTH_COOKIE_SECURE=true` sein.
