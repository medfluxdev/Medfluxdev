# Abschnitte je Vertragstyp (Plan, 2026-10-11)

## Anlass

Leistungsumfang und SLA gehören zu Wartungs- und Serviceverträgen. Bei einem Mietvertrag, einer Versicherung oder einer Mitgliedschaft sind sie leer und erzeugen trotzdem „Offene Punkte“ („Leistungsumfang ungeklärt“, „SLA unvollständig“). Das ist Lärm, und er verdeckt echte Punkte.

## Analyse: Welche Abschnitte brauchen welche Vertragstypen?

Typspezifisch sind vier Abschnitte. Alles andere (Laufzeit, Kündigung, Finanzen, Zuordnung, Dokumente, Verlauf) brauchen alle Verträge.

| Abschnitt | Wo | Wofür |
|---|---|---|
| `scope` Leistungsumfang | Übersicht | enthaltene/ausgeschlossene Leistungen |
| `sla` SLA | Übersicht | Reaktions-/Lösungszeit, 24/7 |
| `maintenance` Wartung | Vertragsdaten | nächste Wartung, Intervall (Erinnerung „Wartung fällig“) |
| `equipment` Geräte | Verknüpfungen | zugeordnete Geräte/Objekte |

Standardprofil je Vertragstyp (Code aus `register/defaults.py`):

| Vertragstypen | scope | sla | maintenance | equipment |
|---|---|---|---|---|
| Wartung, Service | ✓ | ✓ | ✓ | ✓ |
| Dienstleistung, Dienstvertrag, Werkvertrag, Versorgung, Med. Versorgung, Kooperation, Lizenz | ✓ | ✓ | – | – |
| Miete, Leasing, Nutzung, Leihe, Kauf | – | – | – | ✓ |
| Versicherung, Mitgliedschaft, Darlehen, Erbbaurecht, Sponsoring, Drittmittel, AVV, Vertraulichkeit, Vertrauliche Vereinbarung GF, Zulassung, Sonstige | – | – | – | – |

## Entscheidungen

1. **Konfigurierbar je Vertragstyp** (Stammdaten → Vertragstypen, „Abschnitte“): Spalte `sections` (JSON-Liste) an `catalog_contract_type`. `NULL` = Standardprofil nach Code (oben); eigene Typen ohne bekannten Code zeigen alle Abschnitte. „Auf Standard zurücksetzen“ setzt wieder `NULL`.
2. **Ohne Vertragstyp werden alle Abschnitte gezeigt.** Nichts wird geraten. Die Übersicht sagt dazu, dass ein Vertragstyp die passenden Abschnitte auswählt, mit Link zur Zuordnung.
3. **Der Vertragstyp entscheidet** (geändert 2026-10-11 nach Rückmeldung: ein auf Mietvertrag umgestellter Wartungsvertrag zeigte Leistungsumfang/SLA weiter, weil die KI dort Angaben gelesen hatte). Von der KI gelesene Angaben (Leistungsumfang, SLA, im Dokument gefundene Geräte) halten einen Abschnitt nicht mehr sichtbar; der Hinweis nennt sie („mit Angaben aus dem Dokument“) und „Trotzdem anzeigen“ zeigt sie. Nur von einer Person gepflegte Angaben (Wartungsdaten, Gerätearten) halten ihren Kasten sichtbar, weil Erinnerungen und Vergleich daran hängen. Nichts wird gelöscht.
4. **Ausgeblendet heißt sichtbar gemacht:** Unter den Abschnitten der Übersicht steht still „Für Mietvertrag ausgeblendet: Leistungsumfang, SLA“ mit „Trotzdem anzeigen“ (nur für diese Ansicht).
5. **Offene Punkte und „Was fehlt“** zählen ausgeblendete Abschnitte nicht (keine Punkte „Leistungsumfang ungeklärt“ und „SLA unvollständig“ für Mietverträge).
6. **Rechnen bleibt unberührt:** Fristen, Kosten und Warnungen ändern sich nicht; es geht nur um die Darstellung. Die Erinnerung „Wartung fällig“ entsteht weiter nur aus gepflegten Wartungsdaten.

## Umsetzung

- Backend: `app/register/sections.py` (Schlüssel, Standardprofile, `sections_for_type(row)`); Migration `v4e6f8a90014` (Spalte `sections`); Typ-API liefert `sections` (wirksam) und `sections_default` (ob Standard) und nimmt `sections` (Liste oder `null`) an; Vertragsakte liefert `sections = {scope, sla, maintenance, equipment, type_label}` (`null` ohne Typ).
- Frontend: `lib/contract-sections.ts` (`sectionVisible(key, sections, hasData)`); Übersicht (Leistungsumfang, SLA, Hinweis mit „Trotzdem anzeigen“), `OpenPoints`, Vertragsdaten (Kasten Wartung), Verknüpfungen (Geräte); Stammdaten-Formular für Vertragstypen mit Kontrollkästchen „Abschnitte“.
- Tests: Backend (Standardprofil, Anpassung, Zurücksetzen, Detail), Frontend (Übersicht ausgeblendet/eingeblendet mit Daten/ohne Typ, OpenPoints, Formular).
