# Review: source-region PDF 415

**Datum:** 2026-10-02
**Branch:** `review/source-region-pdf-content-415-20261002`
**Fix-Commit:** `33c0c5a77c9855dc85f7a584a5128eb28b33c21f`
**Scope:** nur Review + isolierte Verifikation. KEIN Merge, KEINE Bereitstellung.
**Git-History:** unverändert. `33c0c5a` bleibt unangetastet; diese Notiz und die
Regressionstests liegen als separater Commit obendrauf.

## 1. Der gemeldete Fehler

`GET /api/documents/{document_version_id}/source-region` lieferte fuer ein
echtes Vertrags-PDF konstant **415** `Quell-Geometrie nur fuer PDF verfuegbar.`

## 2. Tatsaechliche Ursache (korrigiert)

Die Commit-Beschreibung vermutete eine *fehlende* Dateiendung. Das war falsch.
Die Endung war vorhanden und korrekt als `".pdf"` (mit Punkt) gespeichert.

Der Endpunkt verglich jedoch mit einem Wert **ohne** Punkt:

```python
ext = (version.file_extension or "").lower().strip()
if ext != "pdf":            # ".pdf" != "pdf" -> immer True -> 415
    raise HTTPException(415, ...)
```

Der Endungs-Wert war also **nicht leer**, sondern **`".pdf"`** – und wurde gegen
`"pdf"` verglichen. Jedes echte importierte PDF traf dadurch zwangslaeufig den
415-Zweig, unabhaengig vom Inhalt.

Das ist konsistent mit dem Rest der Codebasis, der Endungen durchgaengig mit
Punkt fuehrt (z. B. erlaubte Endungen `{".pdf", ".docx"}`). Der undotted Literal
war die Ausnahme, nicht die Regel.

**Nicht die Ursache:** fehlende/fehlerhafte Endungs-Metadaten.

## 3. Verifikation (isoliert, read-only)

- Metadaten des betroffenen Dokuments read-only geprueft: `file_extension=".pdf"`,
  `mime_type="application/pdf"`, SHA-256 passt zum Original, Magic-Bytes `ok`.
- Der 415 liess sich gegen den Parent-Commit `7c9c0a0` reproduzieren
  (echte DB-Zeile + echtes PDF).

## 4. Der Fix

`33c0c5a` entfernt die Endungs-Sperre und validiert stattdessen die echten
Bytes (`content.startswith(b"%PDF-")`). Das ist die richtige Richtung: Nicht der
Dateiname, sondern der Inhalt entscheidet.

Zusaetzlich deckt der Fix echte PDFs mit fehlender Endung ab – ein echter
Nebenfall, aber **nicht** der gemeldete.

## 5. Regressionstests

`backend/tests/test_source_region_pdf_content.py` (22 Tests, im Branch
beigefuegt) sichert ab:

- echtes PDF wird unabhaengig von der Endungs-Metadaten ausgeliefert
  (`.pdf`, leer, fehlend, `pdf`, `.PDF`, `.docx`, `.txt`);
- Nicht-PDF-Inhalt wird auch dann mit 415 abgelehnt, wenn die Metadaten PDF
  behaupten (leer, kaputt, DOCX, PNG, Klartext);
- Organisations-/Konto-Zugriffsbeschraenkungen greifen weiterhin und leaken
  nie eine 415 (fremde Org, anonym, ohne Membership/Scope, Admin).

Verifikationsstand (nicht in diesem Commit ausgefuehrt, aus dem Review-Lauf):

- gegen **Fix** `33c0c5a`: **22 passed**;
- gegen **Parent** `7c9c0a0`: **11 failed / 11 passed** – die Tests greifen die
  Regression also nachweislich.

## 6. Verbleibende Luecken (nicht durch den Fix behoben)

- **Geschwister-Endpunkt** (`contracts.py`) prueft weiterhin Endung **und** MIME;
  ein echtes PDF ohne Endung kann dort weiter 415 bekommen.
- **Endungs-Konvention nicht zentralisiert** – dotted/undotted ist weiter an
  mehreren Stellen handgeschrieben (Einheitlichkeit zentralisieren).
- **Magic-Byte-Pruefung** nur am Dateianfang (`%PDF-` bei Offset 0); ein
  abgeschnittenes PDF passiert das Gate und scheitert erst spaeter.
- Kein Whitespace/BOM-Toleranz bei Offset 0 (bewusst so, aber undokumentiert).

## 7. Empfehlung

- Als **Review-Empfehlung** fuehren: korrekt, minimal,Autorisierung unveraendert.
- Commit-Beschreibung korrigieren bzw. ergaenzen: Ursache war `'.pdf'` vs `'pdf'`,
  nicht eine fehlende Endung.
- Die in Abschnitt 6 genannten Luecken als Folge-Tickets fuehren.