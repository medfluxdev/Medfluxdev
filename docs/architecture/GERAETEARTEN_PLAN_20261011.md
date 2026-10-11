# Gerätearten an Verträgen (Plan, 2026-10-11)

## Anlass

Die Seite „Geräte“ (`/equipment`) zeigt Geräte, die die KI aus Dokumenten liest. Im Alltag bleibt sie leer und beantwortet die eigentliche Frage nicht: **Was kosten uns alle Wartungsverträge für unsere CTs, und wie unterscheiden sie sich?** Dafür braucht jeder Vertrag eine gepflegte Einordnung „welche Geräteart(en) deckt er ab, wie viele Geräte“, und diese Einordnung muss filterbar und vergleichbar sein.

## Entscheidungen

1. **Gerätearten sind Stammdaten** (Stammdaten → Gerätearten), gegliedert nach **Bereich**: Medizintechnik, IT, Haustechnik, Sonstiges. Jede Geräteart kann einer **zuständigen Abteilung** gehören (z. B. CT → Medizintechnik, Server → IT). Pflegen dürfen Administration und Vertragsmanagement (`device_type.edit`), also auch die Vertragsverantwortlichen der Medizintechnik und der IT. Standardliste je Organisation (CT, MRT, Röntgen …; Server, Netzwerk, Drucker …; Aufzug, Klima/Lüftung …), danach frei änderbar.
2. **Am Vertrag:** „Gerätearten“ mit optionaler **Anzahl Geräte** und Notiz (mehrere je Vertrag). Gepflegt im Reiter Verknüpfungen → Geräte (dort stehen auch die von der KI im Dokument gefundenen Geräte). Die Auswahl zeigt die Gerätearten des Bereichs der verantwortlichen Abteilung zuerst. Sichtbar in der Übersicht (Karte „Zuständigkeit“).
3. **KI schlägt nur vor:** Passen Name oder Kategorie eines im Dokument gefundenen Geräts zu einer Geräteart (Bezeichnung oder Suchbegriffe, z. B. „Computertomograph, Somatom“ für CT), erscheint „Vorschlag: CT – Übernehmen“. Übernommen wird nur durch eine Person.
4. **Vertragsliste:** Spalte und Schnellfilter „Geräteart“ (echter Mehrfachwert: ein Vertrag mit CT und MRT erscheint unter beiden).
5. **Analysen → „Gerätearten vergleichen“:** Übersicht je Geräteart (laufende Verträge, Geräte, jährliche Kosten mit Abdeckung). Eine Geräteart wählen → alle laufenden Verträge nebeneinander: Vertragspartner, Krankenhaus/Abteilung, Vertragsende, jährliche Kosten, Anzahl, **Kosten je Gerät**. Kosten je Gerät nur, wenn Jahreskosten und Anzahl gepflegt sind und der Vertrag nur diese eine Geräteart abdeckt; sonst „nicht berechenbar“ mit Grund. Nichts wird geschätzt.
6. **Menü:** „Geräte“ verschwindet aus der Seitenleiste. `/equipment` leitet zu Analysen → Gerätearten weiter; die Gerätedetails (`/equipment/<id>`) bleiben aus dem Vertrag erreichbar.

## Umsetzung

- Backend: `catalog_device_type` (code, label, area, department_id, keywords, description, is_active, sort_order) und `contract_device_type` (contract, device type, quantity, note), Migration `w5f7a9b01015`. `app/register/device_types.py` (Standardliste, Upsert, Vertragszuordnung, Vorschläge), Routen `/api/catalogs/device-types` (GET alle Rollen; POST/PATCH `device_type.edit`) und `GET/PUT /api/contracts/{id}/device-types` (`contract.edit`, Verlauf „Gerätearten geändert“). Rasterspalte `device_types` mit Mehrfachwert-Filter, Fingerabdruck um beide Tabellen ergänzt. Bericht `GET /api/register/reports/device-types[?device_type=]` mit `MoneyTotals`.
- Frontend: Stammdaten-Definition „Gerätearten“, Panel am Vertrag, Zuständigkeitskarte, Schnellfilter, Analysen-Abschnitt, Menü/Weiterleitung.
- Tests: Backend (Standardliste, Rechte, Zuordnung + Verlauf, Vorschlag, Filter, Vergleich inkl. „nicht berechenbar“), Frontend (Panel, Vergleich, Stammdaten), Playwright-Listen angepasst.
