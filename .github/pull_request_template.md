## Was und warum

<!-- Kurz: welches Problem, welche Lösung, welcher Plan-Schritt (z. B. WP2, U9). -->

## Prüfung

- [ ] Backend: `pytest -q` (gegen die Test-DB, nie gegen Produktdaten)
- [ ] Frontend: `npm run verify` (ESLint, stylelint, Vitest, Build)
- [ ] Neue Migration mit `alembic upgrade head` gegen eine Wegwerf-DB geprüft
- [ ] Bei Oberflächenänderungen: `scripts/run_e2e.ps1` (Journeys, axe, Layout, Bildvergleich); Referenzbilder nur bei gewollten Änderungen erneuert

## Definition of Done (CONTRIBUTING.md)

- [ ] Modell + Migration → API → Org/Krankenhaus/Bereich-Scope → `lib/domain-api` → UI
- [ ] UI-Zustände: laden, leer, Fehler mit „Erneut laden“, keine Berechtigung
- [ ] Audit-Ereignis für Änderungen
- [ ] Tests für Backend und Frontend; neue Komponenten mit `axe`
- [ ] Doku/Integrationskarte und `docs/PROJECT_PROGRESS.md` aktualisiert

## Oberfläche (docs/FRONTEND_CONVENTIONS.md)

- [ ] Nur Tokens (keine Hex-Farben, keine freien Schriftgrößen), vorhandene Bausteine aus `components/ui`
- [ ] Deutsch, Sie-Form, keine Technikbegriffe; Fehlermeldungen sagen, was zu tun ist
- [ ] Tastatur: alles erreichbar, sichtbarer Fokus, kein Fokusverlust
- [ ] Hell und dunkel geprüft; Telefonbreite ohne waagerechtes Scrollen
- [ ] Keine Beispielverträge oder Beträge im Code; KI-Werte als Vorschlag mit Beleg erkennbar

## Daten und Sicherheit

- [ ] Keine Vertragsinhalte an externe Dienste, keine neuen Nicht-localhost-KI-Endpunkte
- [ ] Keine Secrets, `.env`, `data/` oder Logs im Commit
- [ ] Rechte prüft das Backend; das Frontend blendet nur aus
