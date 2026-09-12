# STEP 18 Checkpoint – Release Candidate & Krankenhaus-Pilot

Stand: 2026-09-12
Branch: `JAMAL`

## Statisch umgesetzt

- STEP 16 lokale Authentifizierung/RBAC/Audit
- STEP 17 CSV-Export, Backup, Integritaetspruefung, isolierter Restore
- Frontend-Sicherheitsheader/CSP
- Backend-Sicherheitsheader und `no-store` fuer API-Antworten
- Security Review: `docs/SECURITY_REVIEW.md`
- Datenschutz-/Datenfluss-Uebersicht: `docs/DATA_PROTECTION.md`
- Pilot-Installationsanleitung: `docs/INSTALLATION_PILOT.md`

## Release-Kriterien

Ein Release Candidate wird erst erklaert, wenn folgende Runtime-Gates belegt sind:

1. frische isolierte PostgreSQL-Test-DB: Migration bis `head`
2. gezielte Auth-/Security-Tests gruen
3. Frontend Production-Build gruen
4. Login -> Review -> Audit Ende-zu-Ende gruen
5. Viewer-Mutationsschutz und Org-Isolation gruen
6. CSV-Export organisationsgebunden gruen
7. Backup -> Verify -> Restore gegen isolierte Test-DB gruen
8. bestehende auffaellige Backend-Regressionstests gezielt gruen
9. realer Vertragsbenchmark (Accutron) mit dokumentierter Evidence-/Feldqualitaet

## Keine falsche Release-Behauptung

Solange eines dieser Runtime-Gates fehlt, bleibt der Status `RC candidate / runtime pending`.
Insbesondere ersetzt ein gruenes Unit-Test-Ergebnis keinen PostgreSQL-Restore-Test
und kein echter Vertragsbenchmark darf durch synthetische Fixtures ersetzt werden.

## Bekannte Rest-Risiken vor Pilot

- PostgreSQL-RLS ist noch nicht als zweite Mandanten-Isolationsschicht aktiviert.
- CSP enthaelt wegen Next.js derzeit `unsafe-inline` und `unsafe-eval`; fuer
  internet-exponierten Betrieb sollte eine nonce-/production-spezifische CSP folgen.
- Retention-/Loeschfristen sind Betreiberentscheidungen und nicht automatisch
  als rechtliche Policy implementiert.
- HTTPS/TLS ist Deployment-Aufgabe; bei HTTPS muss `AUTH_COOKIE_SECURE=true` sein.
