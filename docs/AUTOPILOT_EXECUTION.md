# MedFlux Autopilot – Abschlusskette

Stand: 2026-09-12
Arbeitsbranch: `JAMAL`

Diese Datei ist die operative Abschlusskette bis zum Krankenhaus-Pilot. Sie ergänzt `docs/PROJECT_PROGRESS.md`; dessen 18 Hauptschritte bleiben maßgeblich.

## Arbeitsprinzip

1. GitHub zuerst: Analyse, Architektur, Code, Tests und Dokumentation werden dort erledigt.
2. Big Pickle/OpenCode wird nur für lokale Laufzeit-Gates verwendet, die sich statisch nicht beweisen lassen.
3. Keine Produktionsdaten werden für Tests verändert. Datenbanktests müssen das isolierte pytest-Schema verwenden.
4. Evidence-first bleibt verbindlich: KI extrahiert Fakten; Berechnungen, Zuordnung, Berechtigungen und Zustandsübergänge bleiben deterministischer Code.
5. Ein Hauptschritt wird erst als abgeschlossen markiert, wenn Implementierung, Tests/Dokumentation und bekannte Rest-Risiken festgehalten sind.

## Phase A – Baseline schließen

- Branch/HEAD und sauberen lokalen Stand verifizieren.
- Die drei zuletzt auffälligen Backend-Tests nach Wiederherstellung der PostgreSQL-Testisolation gezielt ausführen.
- Kein Full-Suite-Lauf, solange gezielte Gates ausreichen.

Runtime-Gate: lokal, nur wenn PostgreSQL-Testisolation benötigt wird.

## Phase B – Schritt 16: Benutzer/Login & Audit

### B1 Datenmodell
- organisationsgebundener Benutzer
- Rollen: `admin`, `reviewer`, `viewer`
- aktiver/inaktiver Status
- versionierter Passwort-Hash
- append-only AuditEvent mit Benutzer, Organisation, Aktion, Entität, Zeitstempel und Details

### B2 Lokale Authentifizierung
- lokaler Login/Logout/`me`
- signierte, zeitbegrenzte HttpOnly-Session
- keine externen Identity-Provider
- `AUTH_ENABLED=true` darf nicht mit Default-Secret starten

### B3 Autorisierung/Org-Grenze
- authentifizierte Organisation ist die Autoritätsquelle
- ein Query-`organization_slug` darf nie Zugriff auf eine andere Organisation verleihen
- Mutationen nach Rolle absichern
- bestehender `AUTH_ENABLED=false`-Entwicklungsmodus bleibt für vorhandene Tests kompatibel

### B4 Menschliche Prüfung/Audit
- Reviewer-Identität bei aktivierter Authentifizierung serverseitig aus der Session ableiten
- Client darf den Prüfernamen dann nicht fälschen
- Login, Logout und relevante Vertragsänderungen auditieren
- Audit-API organisationsgebunden bereitstellen

### B5 UI
- lokale Login-Seite
- Institution/Benutzer/Rolle im Shell-Bereich
- Audit-Seite an persistentes System-Audit anbinden

### B6 Tests
- Passwort-Hash/Verifikation
- Token: gültig, abgelaufen, manipuliert
- Login-Cookie und `/me`
- Org-Isolation und Rollen
- serverseitige Reviewer-Identität
- Audit-Anlage

Runtime-Gate: nur gezielte Backend-/Frontend-Tests, anschließend ein kleiner Login→Review→Audit-Smoke-Test.

## Phase C – Schritt 17: Export & Backup

- CSV-Export des organisationsgebundenen Vertragsportfolios
- Excel-Export nur mit expliziter lokaler Abhängigkeit und identischer Datenbasis
- PostgreSQL-Backup über `pg_dump` ohne Shell-Injection
- Dokument-Backup mit Manifest + SHA-256
- Restore nur mit explizitem Ziel und Integritätsprüfung
- niemals stillschweigend eine laufende Produktions-DB überschreiben
- vorhandenes `scripts/restore_from_backup.py` wiederverwenden/härten statt Duplikate bauen

Runtime-Gate: Backup in temporäres Ziel, Restore-Verifikation, niemals Produktdatenbank als Testziel.

## Phase D – Schritt 18: Release Candidate & Krankenhaus-Pilot

### D1 Security Review
- Auth/Session/Cookie/CORS/CSP
- Organisationsgrenzen
- Upload/Pfad-Sicherheit
- SQL/DB-Rechte
- Secrets/Defaults
- lokale AI-Endpunkte

### D2 Datenschutz-Dokumentation
- lokale Verarbeitung
- Datenarten und Speicherorte
- Rollen/Zugriff
- Audit
- Backup/Restore
- Aufbewahrung/Löschung
- keine juristischen Garantien behaupten

### D3 Installation/Betrieb
- PostgreSQL
- Backend-Venv
- Frontend
- Ollama + Modell
- optionale OCR-/Dokument-Intelligence-Komponenten
- Migrationen
- ersten lokalen Admin sicher anlegen

### D4 Offline-/Pilot-Gate
- Backend/Frontend ohne externe KI-API
- lokaler Login
- Import → Analyse → Evidence → Review → Aktion
- Backup/Restore-Smoke
- Accutron/realer Vertrag erst nach funktionalem Abschluss

## Finales Release-Gate

Ein Release Candidate wird nur erklärt, wenn folgende Punkte belegt sind:

- Migration auf frischer Test-DB erfolgreich
- gezielte Backend-Sicherheits-/Auth-Tests grün
- Frontend Tests + Build grün
- Login→Review→Audit Ende-zu-Ende grün
- Backup→Restore in isoliertem Ziel grün
- realer Vertragsbenchmark dokumentiert
- offene Human-Verification-Gates explizit als solche markiert

Big Pickle wird für diese Runtime-Gates gebündelt und sparsam eingesetzt; statische Analyse und Änderungen erfolgen über GitHub.
