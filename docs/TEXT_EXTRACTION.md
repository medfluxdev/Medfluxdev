# Medflux – Text-Extraktion (Schritt 5)

Dieses Dokument beschreibt, wie Medflux den Rohtext aus importierten Verträgen
lokal extrahiert – ohne KI. Es geht ausschließlich um Textextraktion und
Seitenzuordnung (Schritt 5). Die KI-basierte Extraktion von Vertragsfeldern
(Anbieter, Kosten usw.) folgt erst in Schritt 7.

## Ziel

Für ein importiertes Dokument eine strukturierte Liste von „Extraction Units“
liefern – jeweils mit Quelle (PDF-Seite bzw. DOCX-Absatz/Tabelle), Reihenfolge
und dem extrahierten Rohtext. Diese Einheiten sind die Grundlage für die spätere
KI-Analyse und für die Quellenanzeige („Welche Seite belegt diese Angabe?“).

## Unterstützte Formate

| Format | Bibliothek    | Extrahierte Einheiten                       |
|--------|---------------|---------------------------------------------|
| PDF    | PyMuPDF (fitz)| eine Einheit pro Seite (echte Seitennummer) |
| DOCX   | python-docx   | eine Einheit pro Absatz + eine pro Tabelle, in Dokumentreihenfolge |

## API-Endpunkt

```
POST /api/documents/{document_id}/extract
```

Übergib die `document_id` eines zuvor importierten Dokuments (aus der
Import-Antwort bzw. dem Index). Der Endpunkt liest **nur** interne
`document_id`-Pfade – Nutzerpfade werden nie akzeptiert.

Beispiel-Antwort (PDF):

```json
{
  "document_id": "abc123…",
  "file_type": "pdf",
  "has_duplicates": false,
  "required_units": 3,
  "text_units": [
    {
      "source_type": "page",
      "index": 1,
      "text": "…Vertragstext der Seite 1…",
      "method": "text"
    }
  ],
  "total_characters": 12345,
  "partial": false,
  "text_available": true,
  "required_ocr_total": 0,
  "required_ocr_failed": 0,
  "ocr_active": false,
  "warnings": []
}
```

- `200` – Erfolg, teilweiser Erfolg oder „fehlgeschlagen“ (graceful)
- `404` – unbekannte `document_id` („Dokument nicht gefunden.“)
- `422` – ungültige `document_id`-Syntax

## Zentrale Konzepte

### Extraction Unit

Eine unteilbare Text-Einheit mit Herkunft:

- `source_type`: `page` (PDF) oder `paragraph` / `table` (DOCX)
- `index`: Seitenzahl ab 1 (PDF) bzw. laufende Absatz-/Tabellen-Nummer (DOCX)
- `method`: `text` (direkt extrahiert) oder `ocr` (nur falls OCR aktiv)
- `text`: der Rohtext

### PDF: Seitenzuordnung & Textarm-Erkennung

- Jede Seite wird einzeln per `get_text("text")` extrahiert und mit der echten
  **Seitennummer** versehen.
- Eine Seite gilt als „textarm“ (potenziell gescannt/Bild), wenn sie weniger als
  `TEXT_POOR_THRESHOLD` (**50**) substantive (Nicht-Leerzeichen-)Zeichen enthält.
- Nur textarme Seiten erhalten einen OCR-Bedarf. OCR ist nur für diese Seiten
  vorgesehen („OCR lokal, nur wenn nötig“).
- Nicht-unterbrechende Leerzeichen (U+00A0) werden in normale Leerzeichen
  normalisiert (häufig bei deutschen Preisen und Datumsangaben).

### DOCX: Absätze + Tabellen in Reihenfolge

- Absätze und Tabellen werden in Dokumentreihenfolge zu Einheiten.
- Tabellen werden tabellenweit als ein Textblock zusammengefasst.
- Paragraph- und Tabellen-Indizes werden getrennt gezählt, damit jede Einheit
  eindeutig referenzierbar ist.

## OCR-Fallback

- `ocr_enabled` (Settings, Standard über `.env.example`): schaltet OCR an/aus.
- `ocr_lang` = `"deu"` (deutsche Verträge).
- Implementierung: `OCRProvider` (pytesseract + Pillow), `tesseract_cmd`-Pfad.
- **Tesseract-Binary nicht installiert:** Es wird kein Absturz verursacht,
  sondern ein deutsches Handlungs-Hinweis-Feld geliefert und die Seite als
  OCR-fehlgeschlagen markiert. Der Rest des Dokuments bleibt nutzbar (teilweiser
  Erfolg, weiterhin `200`).
- OCR ist bewusst nur der Fallback für textarme/gescannte Seiten, nie der
  Standardweg.

## Fehlerbehandlung

- Beschädigte/unlesbare PDF- oder DOCX-Datei → deutsches Handlungs-Hinweis-Feld
  (`ERR_PDF_CORRUPT` / `ERR_DOCX_CORRUPT`), kein Traceback für Nutzer.
- Im Fehlerfall wird ein `TextExtractionResult` mit `total_characters = 0`
  geliefert (kein erfundener Wert).
- Unbekannte `document_id` → `404` „Dokument nicht gefunden.“

## Sicherheitsverhalten

- **Nur interne Pfade:** Der Zugriff erfolgt ausschließlich über die kontrollierte
  `document_id` auf `data/contracts/<document_id>/original.<ext>`.
- **Keine Nutzerpfade:** Client-übergebene Pfade werden nie aufgelöst
  (kein Path-Traversal).
- **Keine Ausführung** von Inhaltscode in extrahiertem Text.
- **Alles lokal:** Keine externen Dienste während der Extraktion.

## Backend-Struktur (Schritt 5)

```text
backend/app/documents/
├─ extraction/
│  ├─ __init__.py      # Exports
│  ├─ schemas.py       # FileType, SourceType, UnitMethod, ExtractionUnit, TextExtractionResult
│  ├─ ocr.py           # OCRProvider, OCRUnavailableError
│  ├─ pdf.py           # PDF-Seiten, Seitenzahlen, Textarm-Erkennung, OCR-Bedarf
│  ├─ docx.py          # DOCX-Absätze + Tabellen mit Indizes
│  └─ service.py       # TextExtractionService (Komposition, Fehler, Warnings)
├─ storage.py          # resolve_document, is_valid_document_id, find_by_document_id
└─ api/routes/documents.py   # POST /api/documents/{document_id}/extract (dünn)
```

## Konfiguration

In `backend/app/core/config.py` (bzw. `.env.example`):

| Variable        | Standard | Bedeutung                                     |
|-----------------|----------|-----------------------------------------------|
| `OCR_ENABLED`   | `false`  | OCR-Fallback aktivieren                       |
| `TESSERACT_CMD` | (auto)   | Pfad zur Tesseract-Engine                      |
| `OCR_LANG`      | `deu`    | OCR-Sprache (deutsche Verträge)               |

## Tests

Backend-Tests abgedeckt (`backend/tests/test_text_extraction.py`):
- Normaler PDF-Text
- Mehrseitiges PDF mit korrekten Seitennummern
- Textarme Seite → OCR-Bedarf gesetzt
- OCR nicht verfügbar → kein Absturz, deutsches Hinweisfeld
- DOCX-Absätze, -Tabellen und Quell-Indizes
- Erhalt deutscher Zeichen (ä ö ü Ä Ö Ü ß)
- Erhalt des Euro-Symbols (€)
- Deutsches Preisformat (5.916,67 €)
- Datumsformat (31.12.2027)
- Beschädigte PDF/DOCX → graceful, deutscher Hinweis
- Unbekannte/ungültige `document_id`
- Quellen-Traceability (Seite/Index korrekt zugeordnet)
- Originaldatei bleibt unverändert
- API-Extraktion end-to-end (`200`) und unbekannte ID (`404`)
