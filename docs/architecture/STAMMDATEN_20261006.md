# Stammdaten an einem Ort (S1–S5)

Stand 2026-10-06, Branch `feature/stammdaten-hub` (auf `feature/ui-refactor`).

## Ziel

Alle gleichartigen Stammdaten werden an einer Stelle mit derselben Bedienung gepflegt. Vorher lagen sie an drei Orten mit drei Bedienkonzepten: `/partners` (Bereich „Verträge“), `/settings/organization` (Krankenhäuser, Abteilungen, Kostenstellen) und `/settings/catalogs` (Vertragstypen, Kategorien, Auswahllisten, Nummernkreis).

## Aufbau

- **Bereich `/stammdaten`** (Navigation „Verwaltung → Stammdaten“, Tastenkürzel `g d`, alle Datenarten in Strg+K). Links eine Bereichsnavigation, rechts die Datenart.
  - Partner: Vertragspartner
  - Organisation: Krankenhäuser, Abteilungen (Liste oder Strukturbaum), Kostenstellen
  - Vertragsdaten: Vertragstypen, Kategorien, je Auswahlliste eine eigene Seite (`/stammdaten/auswahllisten/<field_key>`)
- **Übersicht** `/stammdaten`: Bestand je Datenart (aktiv/deaktiviert, zuletzt geändert), Hinweise (mögliche Dubletten, Partner ohne Vertrag), Suche über alle Stammdaten, für Administratoren „Fehlende Standardeinträge ergänzen“ und der Link zum Nummernkreis.
- **Nicht in den Stammdaten:** Nummernkreis (`/settings/nummernkreis`), Benutzer und Rollen – das sind Einstellungen, keine Datenerfassung. Geräte bleiben eigene Objekte mit Detailseite.
- Alte Adressen leiten weiter: `/partners` → `/stammdaten/vertragspartner` (Suchbegriff bleibt), `/settings/organization` → `/stammdaten/abteilungen?ansicht=struktur`, `/settings/catalogs` → `/stammdaten/vertragstypen`.

## Bedienung (für jede Datenart gleich)

- Tabelle mit Suche, Filter (z. B. Krankenhaus), „Deaktivierte anzeigen“, sortierbaren Spalten, Spalte **Verträge** (Anzahl, Link in die gefilterte Vertragsliste) und Status. Suchbegriff, Filter, Ansicht und geöffneter Eintrag stehen in der Adresse (`?q=`, `?haus=`, `?ansicht=struktur`, `?id=`, `?neu=1`).
- Anlegen und Bearbeiten in der **Seitenleiste** (Drawer): Pflichtfelder werden vor dem Speichern geprüft, Strg+S speichert, ungespeicherte Änderungen werden vor dem Schließen abgefragt.
- **Deaktivieren statt Löschen.** Wird ein Eintrag in Verträgen verwendet, zeigt die Seitenleiste die Anzahl und fragt vor dem Deaktivieren nach. Abteilungen mit aktiven Verträgen lehnt das Backend weiterhin ab (WP1.7).
- **Änderungsverlauf** je Eintrag (für Rollen mit `audit.view`).
- **Ähnliche Vertragspartner** beim Anlegen: Hinweis mit „Trotzdem anlegen“.
- **Dubletten zusammenführen** (Vertragspartner): Eintrag wählen, der bleibt; Verträge der anderen werden umgehängt, die anderen deaktiviert. Jede Umstellung steht in der Vertragshistorie (`contract.partner_merged`).
- **CSV-Import** (Vertragspartner, Abteilungen, Kostenstellen, Auswahllisten) wie beim Benutzerimport: Vorlage, Spaltenerkennung mit deutschen Aliassen, erst prüfen, Fehler je Zeile, Hinweise (z. B. ähnlicher Partner) blockieren nicht, angelegt wird alles oder nichts. Bestehende Einträge werden nie verändert. Höchstens 1000 Zeilen.
- **CSV-Export** der sichtbaren Zeilen (Rolle mit `export`).
- **Rechte ehrlich anzeigen:** Alle Rollen dürfen lesen; wer nicht ändern darf, sieht die Daten und den Hinweis, wer pflegt. Die Oberfläche liest die Rechte aus `/api/permissions` (berücksichtigt „Ansicht als Rolle“), das Backend prüft jede Änderung selbst.
- **Neu anlegen aus anderen Formularen:** „Neuer Partner“ und „Neuer Typ“ im Formular „Vertrag anlegen“, „Neuer Partner“ in den Vertrags-Stammdaten – gleiches Formular wie in den Stammdaten, der neue Eintrag ist danach ausgewählt.

## Technik

Frontend (`frontend/components/master-data/`):

- `types.ts`: `EntityDefinition<T, C>` beschreibt eine Datenart (Laden, Spalten, Felder, Anlegen/Ändern/Aktivieren, Import-Spalten, Export, Link in die Vertragsliste).
- `definitions/partners.ts`, `definitions/organization.tsx`, `definitions/catalogs.tsx`: die Datenarten. **Neue Datenart = neue Definition + Eintrag in `lib/master-data.ts`.**
- `EntityManager` (Liste + Seitenleiste), `EntityEditor` (Formular, Verwendung, Status, Verlauf), `EntityForm`, `CsvImport`, `PartnerDuplicates`, `OrganizationTree`, `QuickCreate`, `MasterDataHub`, `MasterDataNav`.
- `lib/csv.ts` ist die gemeinsame CSV-Grundlage (auch für den Benutzerimport), `lib/use-permissions.ts` die Rechteabfrage, `lib/domain-api/masterData.ts` der API-Client.

Backend:

- `app/master_data/service.py`: `summary` (Bestand je Art, Auswahllisten, Hinweise; Struktur nach Bereich eingeschränkt wie die Lese-Endpunkte) und `usage` (sichtbare, nicht gelöschte Verträge je Eintrag; Abteilungen über `contract_department`, Kostenstellen über `contract.cost_center_id` und Kostenaufteilung, Krankenhäuser über `contract.hospital_id` und `contract_hospital`, Auswahllisten nur für `storage_location`).
- `app/master_data/imports.py`: CSV-Import, Rechte je Art wie beim Einzelanlegen (`partner.edit`, `organization.admin`, `catalog.admin`); legt über die vorhandenen Helfer an (`catalogs.create_partner`, `catalogs.upsert_lookup`).
- `app/register/catalogs.merge_partners` + `POST /api/catalogs/partners/{id}/merge`.
- `GET /api/history?object_type=&object_id=` für den Verlauf eines Eintrags (nur Stammdaten-Objektarten).
- Doppelte Kürzel bei Krankenhaus, Abteilung und Kostenstelle liefern jetzt 409 mit deutscher Meldung statt eines Serverfehlers.

Endpunkte: `GET /api/master-data/summary`, `GET /api/master-data/usage?kind=`, `POST /api/master-data/import/{partner|department|cost_center|lookup}`. Keine Migration.

## Offen

- Verwendung für weitere Auswahllisten (z. B. Anlagentyp, Terminart) zählen, sobald deren Werte an Dokumenten/Terminen ausgewertet werden.
- Import für Krankenhäuser und Vertragstypen (wenige Einträge, bisher von Hand).
- „Neu anlegen“ auch für Kostenstellen in der Kostenaufteilung und für Abteilungen in der Zuständigkeit.
