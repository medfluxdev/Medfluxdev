# MedFlux Produkt- und Umsetzungsplan

Status: Produktreferenz und Umsetzungsreihenfolge

Dieses Dokument bündelt die Anforderungen an Vertragsmanagement und
Organisationsstruktur in umsetzbare Produktphasen. Eine Anforderung in diesem
Plan gilt nicht automatisch als implementiert. Den geprüften Umsetzungsstand
dokumentiert `docs/PROJECT_PROGRESS.md`.

## Produktziel

MedFlux macht aus Originalverträgen verwaltbare Vertragsdaten. Das Original
bleibt die maßgebliche Quelle. Wichtige Fakten müssen auf Belege zurückführbar
sein, von zuständigen Personen geprüft werden können und innerhalb der
Berechtigungen der Organisation verwaltet werden.

## Verbindliche Produktregeln

- Die Organisationsstruktur bildet die tatsächliche Krankenhausorganisation ab.
  Vertragsverantwortung und nutzende Bereiche sind Beziehungen am Vertrag und
  verändern die Baumstruktur nicht.
- Modelle dürfen keine fehlenden Werte oder historischen Rollen erfinden.
  Mehrdeutige Angaben bleiben sichtbar und werden zur Prüfung vorgelegt.
- Explizite Vertragswerte bleiben von berechneten Werten unterscheidbar.
  Finanz- und Fristberechnungen erfolgen deterministisch anhand belegter Eingaben.
- Originaldokumente und frühere akzeptierte Extraktionen bleiben bei erneuter
  Analyse erhalten. Jeder Lauf hat einen eigenen Status und eigene Belege.
- Manuelle Prüfung ist der Standard. Automatische Freigabe ist nur für
  festgelegte Felder zulässig, wenn Qualitätsgrenzen und Auditierbarkeit
  nachgewiesen sind.
- Benutzer- und Organisationsberechtigungen werden vor Suche, Aggregation,
  Retrieval und Modellkontext serverseitig durchgesetzt.
- Echte Scans dürfen lokal als Abnahmeeingaben verwendet werden. Für Training
  oder Qualitätsmessung benötigt jede repräsentative Probe menschlich bestätigte
  Sollwerte mit Seiten- und Textbelegen. Originale, Mitarbeiterdaten und rohe
  OCR-Ausgaben werden nicht ins Repository kopiert.

## Produktumfang

### Einrichtung und Organisationsstruktur

- Eine Einrichtung kann mehrere Krankenhäuser enthalten.
- Jedes Krankenhaus erhält eine flexible Abteilungs- und Einheitshierarchie.
  Bezeichnungen beschreiben die lokale Organisation und schreiben keine feste
  Reihenfolge der Ebenen vor.
- Eine Abteilung kann mehrere Kostenstellen haben. Die Suche nach einer
  Kostenstellennummer zeigt Kostenstelle, Bereich und Krankenhaus.
- Beim Zuordnen eines Vertrags werden Krankenhaus, verantwortlicher Bereich,
  ein oder mehrere nutzende Bereiche und eine Kostenstelle getrennt gewählt.
- Auswahlfelder und Suchergebnisse zeigen vollständige Organisationspfade.
- Berechtigte Organisationsadministratoren können Struktur und Kostenstellen
  verwalten, ohne dafür den Programmcode ändern zu müssen.

### Verträge, Dokumente und Prüfung

- Originaldateien, Versionen, Dublettenprüfung, erneute Analyse und Contract360
  bilden einen nachvollziehbaren Vertragslebenszyklus.
- Text-PDFs und Scans werden anhand ihrer Quellen über Textextraktion, OCR,
  Vision und Tabellen-/Layoutverarbeitung analysiert.
- Extrahiert werden, sofern belegt: Vertragspartner und -identität, Laufzeit,
  Beginn, Ende, Kündigung, Verlängerung, Zahlungsweise, Steuern, Preisänderungen,
  Kosten, Geräte und Leistungen.
- Jede wichtige Angabe erhält Quelle, Seite, Textbeleg, Extraktionsmethode und
  Prüfstatus. Die Selbsteinschätzung des Modells allein ist kein Beleg.
- Korrekturen und Freigaben unterscheiden AI, manuelle Eingabe und menschlich
  bestätigte AI-Werte und bleiben im Audit nachvollziehbar.

### Kosten, Fristen und Benachrichtigungen

- Wiederkehrende Kosten werden von einmaligen Kauf-, Installations- und
  verbrauchsabhängigen Kosten getrennt.
- Netto, Steuer und Brutto werden nur ausgewiesen, wenn Steuerbasis und Steuersatz
  belegt oder ausdrücklich bestätigt wurden.
- Jahreswerte, Vertragsgesamtsummen und Monatsäquivalente werden nicht aus
  Kaufpreisen oder bedingten Einzelpreisen erfunden.
- Fristen und Warnungen entstehen nur aus belegten Vertragsdaten oder
  nachvollziehbar bestätigten manuellen Eingaben.
- Benachrichtigungen gehen standardmäßig an die verantwortliche Person. Weitere
  Empfänger und institutionell freigegebene Kanäle werden konfigurierbar;
  Versand, Fehler und Wiederholungen müssen nachvollziehbar sein.

### Geräte, Analysen, Suche und Assistent

- Ein Modellname wird nicht automatisch mit einem konkreten physischen Gerät
  gleichgesetzt. Serien- und Inventarnummern stützen die Geräteidentität;
  unsichere Beziehungen bleiben prüfpflichtig.
- Geräteansichten zeigen zugehörige Verträge, Bereiche, Services, Kosten,
  Fristen und Belege.
- Managementanalysen umfassen Vertragsstatus, Kosten, Lieferanten, Vertragstypen,
  Kostenstellen und anstehende Entscheidungen mit Drill-down bis zum Vertrag.
- Kosten werden nicht vollständig jedem nutzenden Bereich zugerechnet. Eine
  Aufteilung erfordert eine dokumentierte Allokationsregel.
- Prognosen sind als Schätzungen gekennzeichnet und zeigen Annahmen und Quellen.
- Suche umfasst Vertrag, Nummer, Lieferant, Krankenhaus, Bereich, Kostenstelle
  und Gerät und filtert alle Ergebnisse nach Benutzerrechten.
- Der Assistent arbeitet zunächst lesend, nutzt den aktuellen Seitenkontext und
  darf nur Daten abrufen, die der angemeldete Benutzer sehen darf.
- Vertrags-, Kosten- und Fristantworten verweisen auf Belege. Der Assistent
  führt keine freien SQL-Abfragen oder Änderungen aus.
- Änderungen halten fest, wer was wann geändert, geprüft oder freigegeben hat.

## Umsetzungsphasen

### Phase 1 — Organisationsstruktur in der Oberfläche vervollständigen

Die vorhandenen Backend-Beziehungen als Baum darstellen, Eltern beim Anlegen
einer Untereinheit auswählbar machen und vollständige Pfade in Auswahllisten
anzeigen. Umhängen muss dieselbe Organisation und dasselbe Krankenhaus erzwingen
und Zyklen verhindern. Elternschaft vererbt keine Berechtigungen.

### Phase 2 — Vertragszuordnung in den Arbeitsablauf einbauen

Krankenhaus, einen verantwortlichen Bereich, mehrere nutzende Bereiche und
Kostenstelle am geeigneten Punkt des Import- oder Vertragserstellungsablaufs
auswählen. Die Zuordnung muss in Contract360 angezeigt und bearbeitet werden.
Eine verantwortliche Person bleibt vom verantwortlichen Bereich getrennt.

### Phase 3 — Dokumentenlebenszyklus und zuverlässige Extraktion

Original und Version, Analyse, Gruppierung, Belege, Vertragsidentität, Lieferant,
Daten, Geräte, Kosten, Persistenz und Review müssen zusammenspielen.
Repräsentative Scans erhalten vor Modellanpassungen menschlich bestätigte
Sollwerte; einzelne Verträge dürfen keine Sonderregeln für das Gesamtprodukt
erzeugen.

### Phase 4 — Prüfung, Freigabe und Provenienz

Faktenweise Belege, Korrektur, Freigabe, Status und Historie anzeigen.
Unvollständige Ergebnisse dürfen nicht automatisch zu akzeptierten Vertragsdaten
werden. Frühere freigegebene Werte müssen bei neuen Läufen erhalten bleiben.

### Phase 5 — Kosten, Fristen und Benachrichtigungen

Kostenarten, belegte Berechnungen, Fristen, Empfänger, Kanäle, Deduplizierung
und Versandhistorie zuverlässig umsetzen.

### Phase 6 — Geräte und Services

Physische Geräte, Produktmodelle, Vertragsbeziehungen und Services getrennt
modellieren und jeweils mit Quelle und Prüfstatus verbinden.

### Phase 7 — Suche, Analysen und Finanzplanung

Nur akzeptierte, berechtigungsgefilterte Daten aggregieren. Doppelzählung
verhindern; Prognosen als begründete Szenarien getrennt darstellen.

### Phase 8 — Kontextbezogener Assistent und Evidenz-Retrieval

Berechtigungen vor dem Retrieval anwenden, Antworten mit Quellen verbinden und
Kontext bei Berechtigungsänderungen neu prüfen. Ein Framework wie LlamaIndex
wird erst gewählt, wenn Bedarf und lokale Integration nachgewiesen sind.

## Abschlussregeln pro Phase

- Vor Änderungen Branch, Arbeitsbaum und vorhandene Implementierung prüfen.
  Modelle, APIs und Berechtigungen wiederverwenden.
- Eine Phase begrenzt umsetzen und Regressionen für erlaubte, abgewiesene,
  unvollständige und organisationsübergreifende Fälle ergänzen.
- Den Anwenderpfad prüfen, bevor eine Phase als fertig gilt.
- `docs/PROJECT_PROGRESS.md` mit Status, Datum, Dateien, Tests, Einschränkungen
  und nächstem Schritt aktualisieren.
- Keine echten Krankenhausverträge, Zugangsdaten, Laufzeitprotokolle oder
  Datenbankbestände ins Repository aufnehmen.
