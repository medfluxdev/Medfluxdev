# MedFlux Security Review – STEP 18

Stand: 2026-09-12
Branch: `JAMAL`

## Zielbild

MedFlux ist fuer einen lokalen Krankenhaus-Pilot ausgelegt. Vertragsdaten,
Dokumente und KI-Verarbeitung bleiben lokal. Dieses Dokument beschreibt den
technischen Ist-Stand; es ist keine Zertifizierung und keine juristische
Garantie.

## Authentifizierung & Session

- lokale Benutzer in `app_user`
- Rollen `admin`, `reviewer`, `viewer`
- Passwort-Hashes serverseitig, kein Klartextpasswort in DB
- signierte, zeitbegrenzte HttpOnly-Session-Cookies
- `AUTH_ENABLED=true` startet nicht mit dem Default-Secret `change-me`
- Session-Cookie-Name/TTL/SameSite/Secure sind konfigurierbar
- `AUTH_COOKIE_SECURE=true` ist fuer HTTPS-Pilotbetrieb erforderlich

## Organisationsgrenze

- organisation-owned Tabellen tragen `organization_id`
- zentrale Auth-Middleware bindet API-Aufrufe an die Organisation der Sitzung
- ein `organization_slug` aus Query-Parametern ist keine Autorisierungs-Credential
- abweichende Organisations-Slugs werden wie nicht vorhandene Ressourcen behandelt

Hinweis: PostgreSQL Row Level Security ist noch keine zweite Schutzschicht; die
aktuelle Isolation erfolgt deterministisch in Anwendung/Queries. Ein Pilot mit
mehreren voneinander unabhaengigen Mandanten sollte RLS als zusaetzliche
Defense-in-Depth-Massnahme evaluieren.

## Rollen & menschliche Aktionen

- Viewer darf keine fachlichen Mutationen durchfuehren
- Reviewer/Admin koennen Review-Aktionen ausfuehren
- bei aktivierter Authentifizierung wird die Reviewer-Identitaet serverseitig
  aus der Session abgeleitet; der Client ist nicht die Autoritaetsquelle
- Audit ist append-only ausgerichtet; Korrekturen entstehen als neue Events

## CORS / Browser

Backend:

- nur konfigurierte `CORS_ORIGINS`
- keine Wildcard-Origin-Freigabe
- Credentials nur bei aktivierter Authentifizierung
- begrenzte Methoden/Header
- globale Response-Haertung: `nosniff`, `DENY`, `no-referrer`, Permissions-Policy,
  API `Cache-Control: private, no-store`

Frontend:

- CSP mit expliziten Quellen
- `object-src 'none'`
- `frame-ancestors 'none'`
- `base-uri 'self'`
- `form-action 'self'`
- Kamera/Mikrofon/Geolocation/Payment/USB deaktiviert

Rest-Risiko: Next.js benoetigt im aktuellen Build Inline-Skripte/-Styles; die CSP
enthaelt deshalb `unsafe-inline`, im Script-Kontext aktuell auch `unsafe-eval`.
Vor einem internet-exponierten Deployment sollte dies ueber Nonces/production-
spezifische CSP weiter reduziert werden.

## Dokumente & Upload

- nur PDF/DOCX
- Dateiname wird nie als Storage-Pfad vertraut
- Storage-Referenzen sind kanonisch und containment-geprueft
- Originale sind immutable ausgerichtet
- SHA-256 dient als Integritaets-/Duplikatidentitaet
- API gibt keine Storage-Keys oder lokalen Pfade an den Browser aus
- Content-Ausgabe ist org-/vertragsgebunden, `nosniff`, `no-store`

## Datenbank

- PostgreSQL ist Ziel-DB
- Credentials nur ueber Umgebung/.env
- ORM/parametrisierte Statements statt String-SQL fuer Fachabfragen
- Migrationen ueber Alembic
- Backup/Restore ueber `pg_dump`/`pg_restore` ohne Shell-Injection
- Restore in die aktuell konfigurierte Produkt-DB wird vom STEP-17-Skript verweigert

Empfehlung fuer Pilot:

- eigener PostgreSQL-Benutzer mit minimalen Rechten
- keine Superuser-Credentials fuer den App-Prozess
- Backup-Benutzer getrennt, wenn betrieblich moeglich

## Lokale KI

- Provider-Endpunkte sind lokal konfiguriert
- Ollama/LM Studio/llama.cpp/generic OpenAI-compatible URLs werden nicht aus
  Vertragsinhalten dynamisch gebaut
- MedFlux behauptet keine Cloud-Verarbeitung, solange nur lokale Endpunkte
  konfiguriert sind
- fuer Krankenhaus-Pilot muss Egress auf Betriebssystem-/Firewall-Ebene passend
  zur gewuenschten Offline-Policy begrenzt werden

## Backup & Restore

- Custom PostgreSQL dump
- Dokumentmanifest mit SHA-256 und Groessen
- Manifest-Path-Traversal wird verworfen
- kein stilles Ueberschreiben bestehender Backup-Ziele
- Restore verlangt explizites Ziel
- Restore-Test nur gegen isolierte Test-DB

## Vor Pilot zwingend als Runtime Gate

1. frische isolierte DB: `alembic upgrade head`
2. Login -> Review -> Audit Ende-zu-Ende
3. Viewer darf Mutation nicht ausfuehren
4. Organisationswechsel per Query darf keinen Zugriff geben
5. Frontend Production-Build
6. Backup -> Verify -> Restore gegen temporaere DB
7. realer Vertragsbenchmark (Accutron) dokumentieren
8. HTTPS-Betrieb: `AUTH_COOKIE_SECURE=true`
