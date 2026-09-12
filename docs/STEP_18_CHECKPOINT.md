# STEP 18 Checkpoint – Release Candidate & Krankenhaus-Pilot

Stand: 2026-09-12
Branch: `JAMAL`
Status: **RC candidate; statische und DB-freie Runtime-Gates gruen; isolierte PostgreSQL-/E2E-/Benchmark-Gates ausstehend**

## Statisch umgesetzt

- STEP 16 lokale Authentifizierung/RBAC/Audit
- STEP 17 CSV-Export, Backup, Integritaetspruefung, isolierter Restore
- Frontend-Sicherheitsheader/CSP
- Backend-Sicherheitsheader und `no-store` fuer API-Antworten
- Security Review: `docs/SECURITY_REVIEW.md`
- Datenschutz-/Datenfluss-Uebersicht: `docs/DATA_PROTECTION.md`
- Pilot-Installationsanleitung: `docs/INSTALLATION_PILOT.md`

## Laufzeitnachweis vom 2026-09-12

Bounded Release-Candidate-Gate auf Branch `JAMAL`, Commit `cb2029645efa9b4c7c2606dfadf0d3853e090cc5`, sauberer Worktree:

- Python-Compile-Gate: **bestanden** fuer 12 relevante Step-16/17/18-Dateien
- Auth-Security-Tests: **5 passed in 0.42s** (`MEDFLUX_UNIT_ONLY=1`)
- Step-17 Backup-Security-Tests: **6 passed in 0.19s**
- UAT Kosten-Semantik: **1 passed in 0.21s**
- Backend Import-/Route-Smoke: **bestanden**
- registrierte Pfade: `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`, `/api/audit`, `/api/operations/contracts.csv`
- Frontend Production-Build: **bestanden** (`Next.js 14.2.15`, Lint/Types OK, 14 statische/dynamische Seiten generiert)

Damit sind Build-, Import- und gezielte DB-freie Regression-Gates belegt. Diese Ergebnisse ersetzen bewusst **nicht** die PostgreSQL-, Restore-, Login-/Provenienz- oder Realvertrags-Gates.

## Release-Kriterien

Ein Release Candidate fuer den Krankenhaus-Pilot wird erst vollstaendig erklaert, wenn die verbleibenden Runtime-Gates belegt sind:

1. frische isolierte PostgreSQL-Test-DB: Migration bis `head`
2. Login → `/me` → Review/Override → Provenienz → Audit Ende-zu-Ende gruen
3. Viewer-Mutationsschutz und Org-Isolation gruen
4. CSV-Export organisationsgebunden gegen echte isolierte DB-Fixture gruen
5. Backup → Verify → Restore gegen isolierte Test-DB gruen
6. bestehende auffaellige Backend-Regressionstests gezielt bzw. die sichere Gesamtsuite gruen
7. realer Vertragsbenchmark (Accutron) mit dokumentierter Evidence-/Feldqualitaet

Bereits bestanden:

- gezielte Auth-/Security-Unit-Tests
- gezielte Step-17 Backup-Security-Unit-Tests
- UAT Kosten-Semantik-Test
- Backend Import-/Route-Smoke
- Frontend Production-Build

## Keine falsche Release-Behauptung

Solange eines der verbleibenden Runtime-Gates fehlt, bleibt der Status `RC candidate / PostgreSQL-E2E + benchmark pending`.
Insbesondere ersetzt ein gruener Unit-Test keinen PostgreSQL-Restore-Test
und kein echter Vertragsbenchmark darf durch synthetische Fixtures ersetzt werden.

## Bekannte Rest-Risiken vor Pilot

- PostgreSQL-RLS ist noch nicht als zweite Mandanten-Isolationsschicht aktiviert.
- CSP enthaelt wegen Next.js derzeit `unsafe-inline` und `unsafe-eval`; fuer
  internet-exponierten Betrieb sollte eine nonce-/production-spezifische CSP folgen.
- Retention-/Loeschfristen sind Betreiberentscheidungen und nicht automatisch
  als rechtliche Policy implementiert.
- HTTPS/TLS ist Deployment-Aufgabe; bei HTTPS muss `AUTH_COOKIE_SECURE=true` sein.
