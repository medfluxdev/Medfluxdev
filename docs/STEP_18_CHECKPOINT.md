# STEP 18 Checkpoint – Release Candidate & Krankenhaus-Pilot

Stand: 2026-09-13
Branch: `JAMAL`
Status: **RC candidate; alle Build-/PostgreSQL-/Auth-/CSV-/Backup-/Regression-Gates gruen; Realbenchmark ausstehend**

## Statisch umgesetzt

- STEP 16 lokale Authentifizierung/RBAC/Audit
- STEP 17 CSV-Export, Backup, Integritaetspruefung, isolierter Restore
- Frontend-Sicherheitsheader/CSP
- Backend-Sicherheitsheader und `no-store` fuer API-Antworten
- Security Review: `docs/SECURITY_REVIEW.md`
- Datenschutz-/Datenfluss-Uebersicht: `docs/DATA_PROTECTION.md`
- Pilot-Installationsanleitung: `docs/INSTALLATION_PILOT.md`

## Laufzeitnachweis

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
- alle temporaeren Datenbanken danach entfernt

### Gezielter Auth-E2E-Gate

Auf Commit `5392c049657e8e35c178dee3ede51af1f49a56fa`:

- `backend/tests/test_auth_e2e.py`: **3 passed, 5 warnings in 2.60s**
- Login → `/me` → Audit → Logout: **bestanden**
- Cross-Org-Isolation: **bestanden**
- Viewer-Mutationsschutz: **bestanden**
- Reviewer-Schreibzugriff: **bestanden**
- disposable Testdatenbank danach entfernt

### Gezielter CSV-E2E-Gate

Auf Commit `e536927216c0d62e5205953064a261745a269aee`:

- `backend/tests/test_step17_csv_e2e.py`: **3 passed in 1.92s**
- authentifizierter Export: **bestanden**
- Organisations-Scope / Cross-Org-404: **bestanden**
- Archiv-Default und `include_archived=false`: **bestanden**
- UTF-8 BOM und Semikolonformat: **bestanden**
- No-store-/Nosniff-Header: **bestanden**
- disposable Testdatenbank danach entfernt

### Breiter Backend-Regression-Gate

Auf Commit `46e9eed7f66615bcaf7a318fef819e8f4447686a` gegen eine eigene disposable PostgreSQL-Datenbank:

- komplette Backend-Suite `pytest -q`: **750 passed, 0 failed, 0 skipped**
- Laufzeit: **29.44 s**
- Warnungen: **5**
- keine optionale AI-Runtime fuer die Tests erforderlich
- keine externen Netzwerkzugriffe
- disposable Testdatenbank danach entfernt

Damit sind STEP 16 und STEP 17 abgeschlossen und die breite Backend-Regression ist gruen.

## Verbleibendes Release-Kriterium

1. realer Vertragsbenchmark (Accutron) mit dokumentierter Evidence-/Feldqualitaet

## Bereits bestanden

- gezielte Auth-/Security-Unit-Tests
- PostgreSQL-Migration bis Head
- Login-/Session-/Audit-E2E
- Viewer-Mutationsschutz und Org-Isolation
- organisationsgebundener CSV-E2E-Gate
- gezielte Step-17 Backup-Security-Unit-Tests
- echter Backup → Verify → Restore-Gate
- UAT Kosten-Semantik-Test
- Backend Import-/Route-Smoke
- Frontend Production-Build
- komplette Backend-Regression: 750/750 gruen

## Keine falsche Release-Behauptung

Solange der reale Vertragsbenchmark fehlt, bleibt der Status `RC candidate`.
Ein echter Vertragsbenchmark darf nicht durch synthetische Fixtures ersetzt werden.

## Bekannte Rest-Risiken vor Pilot

- PostgreSQL-RLS ist noch nicht als zweite Mandanten-Isolationsschicht aktiviert.
- CSP enthaelt wegen Next.js derzeit `unsafe-inline` und `unsafe-eval`; fuer internet-exponierten Betrieb sollte eine nonce-/production-spezifische CSP folgen.
- Retention-/Loeschfristen sind Betreiberentscheidungen und nicht automatisch als rechtliche Policy implementiert.
- HTTPS/TLS ist Deployment-Aufgabe; bei HTTPS muss `AUTH_COOKIE_SECURE=true` sein.
