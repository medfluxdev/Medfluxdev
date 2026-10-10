# Ruhe & Signal – Fortschritt

Branch `design/ruhe-signal`, abgezweigt von `design/mein-tag-v2` (`17e331b`).
Nach jeder Phase: `npm run verify`, Eintrag hier, ein Commit „feat(ux): Ruhe & Signal – Phase N: …“,
Stopp bis zur Freigabe. Bestandsaufnahme und Umstellungstabelle: `RUHE_SIGNAL_INVENTORY.md`.

| Phase | Inhalt | Status | Datum | Commit |
|---|---|---|---|---|
| 0 | Sicherung und Bestandsaufnahme | erledigt; Fragen D4–D11 mit den Vorschlägen beantwortet | 2026-10-10 | d9216f1 |
| 1 | Grundlage: Tokens, `Signal`, Badge/StatusBadge/InlineAlert/Toast, EmptyState `calm`, KpiTile `signal` | erledigt (= Restructure B) | 2026-10-10 | |
| 2 | Rahmen: Seitenleiste, Kopfleiste, Benachrichtigungen, Befehlspalette | offen | | |
| 3 | Mein Tag (v3 ersetzt v2) | offen | | |
| 4 | Listen und Tabellen | offen | | |
| 5 | Vertragsseite und Gerätedetail | offen | | |
| 6 | Import, Prüfung, Verarbeitung | offen | | |
| 7 | Analysen und Diagramme | offen | | |
| 8 | Formulare, Einstellungen, Verwaltung, Anmeldung | offen | | |
| 9 | Abschluss: Aliase, Nachsuche, Doku, Farbsehschwäche, Dunkelmodus, Tastatur, e2e-Bilder | offen | | |

## Phase 0 – 2026-10-10

- Vorher gesichert auf `design/mein-tag-v2`: `52675d4` (Stammdaten-Hub, Vertragsregeln, Fristen, Admin-Layout)
  und `17e331b` (Mein Tag v2). Nicht committet: `Claude outputs/` (Referenzen) und
  `design-reference/hospital-workflow/*.zip` (bewusst aus dem Index genommen).
- Mein Tag v2: `npm run verify` grün; e2e-Bildreferenzen nicht erneuert (folgen in Phase 9).
- Bestandsaufnahme: `RUHE_SIGNAL_INVENTORY.md`, 8 offene Fragen in Abschnitt 7.

## Zusammenlegung mit dem Restructure-Plan (2026-10-10)

Die weiteren Phasen laufen im Plan `docs/architecture/MEDFLUX_RESTRUCTURE_PLAN_20261010.md` mit:
R&S 1 = B · R&S 2 (Rahmen) = C · R&S 3 (Mein Tag) = G · R&S 4 (Listen) = D · R&S 5 (Vertrag, Geräte) = E/H ·
R&S 6 (Import, Prüfung) = E · R&S 7 (Analysen) = G · R&S 8 (Formulare, Verwaltung) = H · R&S 9 = I.
Fortschritt dort: `docs/medflux-restructure-progress.md`.
