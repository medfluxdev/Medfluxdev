# MedFlux Datenschutz-/Datenverarbeitungs-Uebersicht

Stand: 2026-09-12

Dieses Dokument beschreibt den technischen Datenfluss von MedFlux fuer einen
lokalen Krankenhaus-Pilot. Es ersetzt keine Datenschutz-Folgenabschaetzung,
keine Rechtsberatung und keine organisatorischen Richtlinien des Krankenhauses.

## Verarbeitete Datenarten

MedFlux kann insbesondere verarbeiten:

- Vertragsparteien und Lieferanten
- Vertragsnummern, Laufzeiten, Kuendigungsfristen
- Preise, Kosten- und Zahlungsinformationen
- Leistungs-/SLA-Inhalte
- Geraete-/Inventarbezug
- Originaldokumente (PDF/DOCX)
- Extraktionsnachweise und Seitenreferenzen
- menschliche Review-/Korrekturaktionen
- Benutzer-/Auditinformationen

Personenbezogene Inhalte koennen in Vertragsdokumenten vorkommen. MedFlux darf
deshalb nicht pauschal als systematisch "personenbezugsfrei" betrieben werden.

## Speicherorte

- PostgreSQL: strukturierte Vertrags-, Review-, Audit- und Systemdaten
- `data/contracts`: geschuetzte lokale Dokument-/Artifact-Ablage
- konfiguriertes Backup-Ziel: PostgreSQL-Dump + Dokumentkopien + Manifest
- lokaler Modellserver (z. B. Ollama): Verarbeitung im lokalen Netz/Host gemaess
  dessen eigener Laufzeitkonfiguration

## Externe Uebertragung

Die Standardarchitektur ist lokal. MedFlux selbst benoetigt fuer die
Vertragsanalyse keine externe KI-API. Werden spaeter externe Provider-Endpunkte
konfiguriert, muss dies als eigene Betriebsentscheidung mit Datenschutzpruefung
behandelt werden.

## Zugriff

- lokale Benutzerkonten
- Rollen: Admin, Reviewer, Viewer
- organisationsgebundene Datenabfragen
- fachliche Aenderungen werden auditierbar protokolliert
- authentifizierte Reviewer-Identitaet wird serverseitig aus der Sitzung
  abgeleitet

## Nachvollziehbarkeit

Evidence-first bedeutet:

- extrahierte materiale Fakten sollen auf Quelldokument/Nachweis zurueckfuehren
- Unsicherheit oder fehlende Evidenz bleibt sichtbar
- menschliche Korrekturen ersetzen die Historie nicht, sondern werden
  nachvollziehbar hinzugefuegt

## Backup

STEP 17 sichert:

- PostgreSQL als Custom-Dump
- organisationsgebundene Originaldokumente
- SHA-256/Dateigroesse jedes Backup-Artefakts

Restore erfolgt nur in ein explizites Ziel; ein Testrestore darf nicht die
laufende Produktdatenbank ueberschreiben.

## Aufbewahrung und Loeschung

Die technische Plattform unterstuetzt derzeit vor allem nicht-destruktives
Archivieren und append-only Audit-Historie. Eine rechtlich/organisatorisch
verbindliche Retention- und Loeschrichtlinie muss fuer den jeweiligen Betreiber
festgelegt werden. Dabei sind insbesondere zu klaeren:

- Aufbewahrungsdauer von Originalvertraegen
- Aufbewahrungsdauer von Audit-/Reviewhistorien
- Backup-Retention
- Verfahren fuer berechtigte Loeschanforderungen
- dokumentierte Freigabe fuer harte Loeschung

## Pilot-Voraussetzungen

Vor Verarbeitung echter Krankenhausdaten sollte der Betreiber mindestens:

1. Datenkategorien und Zweck festlegen,
2. Rollen/Berechtigungen freigeben,
3. Backup-Retention definieren,
4. Host/DB/Backup-Speicher verschluesseln,
5. HTTPS bzw. geschuetzten lokalen Zugriff sicherstellen,
6. Firewall/Egress-Policy fuer lokale KI festlegen,
7. organisatorische Incident-/Restore-Verfahren dokumentieren.
