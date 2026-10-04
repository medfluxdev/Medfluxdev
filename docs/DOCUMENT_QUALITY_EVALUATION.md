# Medflux — Dokumentqualitäts-Evaluation (Benchmark v2, PDF-Korpus)

Status: ABGESCHLOSSEN (Diagnose + Design-Validierung, keine Schritt-Erhöhung)
Fortschritt: 8 / 18 = 44,4 % (unverändert)
Datum: 29.08.2026

Zweck: **Text-/Dokument-Extraktionsqualität vor der KI-Semantik-Extraktion**
bestimmen. Trennung von „Dokument lesbar?“ (dieser Abschnitt) und
„KI extrahiert die Felder korrekt?“ (bewusst NICHT hier bewertet). Damit wird
verhindert, dass OCR-Fehler als KI-Semantikfehler fehlinterpretiert werden.

---

## 1. Korpus & Quelle

- **Archiv:** `Desktop\العقود الجديدة.zip` (79,9 MB, 29.08.2026).
  Das Original-Archiv wurde **nicht verändert**.
- **Extrahierte PDFs:** `data/benchmark_v2/input/` (36 PDF-Dateien, ~81 MB,
  flach, ohne den arabischen Ordner-Namen).
- **Legacy-Benchmark unangetastet:** `data/benchmark/` (inkl.
  `ground_truth.json`, `report_latest.json`, `report_groups.json`) blieb
  unverändert. Explizit **kein neues Ground Truth** erstellt.
- **Werkzeug:** `scripts/document_quality_inspection.py` (nutzt
  PyMuPDF/fitz 1.24.14; nur native Textschicht, keine KI, kein OCR-Aufruf).

## 2. Methodik

Je Dokument wird je Seite deterministisch gemessen:

- substantielle native Zeichen (nicht-Leerzeichen) nach `get_text("text")`
- Seiten mit sinnvollem Text (Schwelle ≥ 50 Zeichen, identisch zur
  TEXT_POOR_THRESHOLD des bestehenden PDF-Extraktors)
- Zahl der Text-Blöcke und Bilder je Seite (strukturelle Hinweise)
- **Abdeckung** = Seiten-mit-sinnvollem-Text / Seitenzahl
- **Dichte** = Gesamtzeichen / Seitenzahl

Klassifikation (deterministische Schwellwerte, `app/documents/quality.py`):

| Klasse | Kriterium | Pfad |
|--------|-----------|------|
| `native_text` | Abdeckung ≥ 0,85 **und** Dichte ≥ 250 **und** gesamt ≥ 2000 | `native_extraction` |
| `partial_text` | Textschicht vorhanden, aber unvollständig / spärlich / nur Kopf-Fragmente | `native_plus_ocr_fallback` |
| `scanned_image` | praktisch keine sinnvolle Textschicht (gescannt/Bild) | `full_ocr_required` |
| `unreadable/error` | PDF nicht parsebar | `manual_review` |

Ausdrücklich **nicht** `native_text`: ein 15-Seitiges PDF, dessen einzige
textreiche Seite 1.000 Zeichen enthält → `partial_text`.

## 3. Ergebnis (36 PDFs, 355 Seiten)

```
PDFs gesamt:            36
Seiten gesamt:          355
native Textzeichen gesamt:  3.095  (Ø 8,7 Zeichen/Seite)
native_text:             0
partial_text:            2  (nur Kopf-/Metadaten-Layer)
scanned_image:          34
unreadable/error:        0
```

**Kernbefund: Das neue PDF-Korpus ist praktisch vollständig ein
Scan-Korpus.** 34 von 36 Dokumenten haben **null** native Textzeichen
(pro Seite genau 1 ganzseitige Bild-XRef, 0 Text-Blöcke) → für jede
KI-Extraktion ist zwingend lokale OCR erforderlich. Nur 2 Dokumente tragen
überhaupt einen Text-Layer:

| Datei | Seiten | Zeichen | Befund | Pfad |
|-------|--------|---------|--------|------|
| BD Service Vertrag (2).pdf | 16 | 1.771 | Text = nur „Docusign Envelope ID …“-Kopfzeilen (~110 Z/S); Vertragsinhalt gescannt | native_plus_ocr_fallback |
| CCE_Full_Service_Konditionen_TW_01-2025.pdf | 1 | 1.324 | echter Text, aber 1-seitiges Konditionsblatt, kein vollständiger Vertrag | native_plus_ocr_fallback |

## 4. Per-Dokument-Liste

Alle übrigen Dokumente: `scanned_image` (0 Zeichen), Pfad
`full_ocr_required`. Vollständige Detailrecords (inkl. `pages_needing_ocr`,
Blöcke/Bilder je Seite, Warnings, Legacy-Match) in
`data/benchmark_v2/document_quality.json`.

| Datei | Seiten | Klassifikation |
|-------|--------|----------------|
| Ysio 2-Detektor-System - Perfomance TOP.PDF | 20 | scanned_image |
| Harmony Servicevertrag 2012.pdf | 19 | scanned_image |
| Servicevertrag Radiosurgery 2021.pdf | 18 | scanned_image |
| Varain Wartungsvertrag 2015.pdf | 18 | scanned_image |
| Rahmenvertrag Abbott.pdf | 17 | scanned_image |
| AXIOM Q Biplane, Axiom Senis Hemo.PDF | 16 | scanned_image |
| BD Service Vertrag (2).pdf | 16 | **partial_text** |
| Magentom Area.pdf | 14 | scanned_image |
| Truebeam Essentials MLC 120-2019.PDF | 14 | scanned_image |
| Truebeam STX.PDF | 14 | scanned_image |
| Axiom Artis one, Axiom Sienes.pdf | 13 | scanned_image |
| Service Vertrag Abiomed.pdf | 13 | scanned_image |
| Artis Zee.pdf | 12 | scanned_image |
| GAMMMED PLUS 2015.pdf | 12 | scanned_image |
| MMM Groupe Servicevertrag.pdf | 12 | scanned_image |
| Servicevertrag Radiosurgery 2024.pdf | 11 | scanned_image |
| Apoplex Vertrag Service.pdf | 10 | scanned_image |
| Service Vertrag Abbottt.pdf | 10 | scanned_image |
| Abiomed Impella.pdf | 9 | scanned_image |
| Frankfurt, Nordwest KH RAV-00074 Optis M Next LFZ 04.06.2025 - 03.06.2029.pdf | 9 | scanned_image |
| IDS Labor lifererung und Wartung.pdf | 9 | scanned_image |
| ADOPS Wartung vertrag.pdf | 8 | scanned_image |
| Phillips IntelliSpace Cardiovascular Protect Extended.pdf | 8 | scanned_image |
| CT Revolution EVO servicevertrag.pdf | 6 | scanned_image |
| GE MACLAB.pdf | 6 | scanned_image |
| Accutorn Service Vertrag.pdf | 5 | scanned_image |
| EVB-IT Servicevertrag 2019.pdf | 5 | scanned_image |
| MFS Wartungvertrag 2016.pdf | 5 | scanned_image |
| OEC ONE CFD 31 - Focus Full Vollservice-Vertrag.PDF | 5 | scanned_image |
| Vision RFD 3D.pdf | 5 | scanned_image |
| Wartung vertrag OEC Elite.pdf | 5 | scanned_image |
| CT Revolution HD servicevertrag.pdf | 4 | scanned_image |
| Bestellung Holmuim laser mit wartung vertrag.pdf | 2 | scanned_image |
| Gessler Gmbh OP lichtgeräte.pdf | 2 | scanned_image |
| Siemens MRT Vida 3T.pdf | 2 | scanned_image |
| CCE_Full_Service_Konditionen_TW_01-2025.pdf | 1 | **partial_text** |

## 5. Sofort KI-benchmarkbar?

**Kein einziges PDF dieses Korpus ist direkt (ohne OCR) für qwen3:8b
nutzbar.** Alle 36 Dokumente benötigen vor der AI-Semantik-Extraktion einen
`OCR`-Schritt. Eine qwen3:8b-Bewertung auf den leeren Textschichten würde
systematisch „fehlend/unlesbar“ liefern und wäre **kein KI-Semantikfehler**,
sondern ein Dokumentqualitäts- / OCR-Problem – daher hier keine AI-Benchmarks
ausgeführt (nur reine Textschicht-Diagnose + fokussierte Klassifikationstests).

## 6. OCR-Fähigkeit von Medflux (Ist-Zustand)

### Vorhandene Abstraktion (vollständig lokal angelegt)
- **`backend/app/documents/extraction/ocr.py`**: `OCRProvider`
  (pytesseract-Wrapper). `is_available()` → prüft `pytesseract.get_tesseract_version()`;
  `image_to_text(image)` → `pytesseract.image_to_string(image, lang=…)`; wirft
  `OCRUnavailableError` bei fehlendem Tesseract (eleganter deutscher Fallback).
- **`backend/app/documents/extraction/pdf.py`**: `extract_pdf_units(path, ocr)`
  — Seite für Seite: native `get_text("text")`; Seiten unter
  `TEXT_POOR_THRESHOLD=50` werden bei verfügbarem OCR mit **300 dpi**
  (`page.get_pixmap`) gerastert und lokal erkannt; sonst
  `requires_ocr_remaining=True` + Warnung + leere Einheit.
- **`backend/app/documents/extraction/service.py` +
  `app/documents/service.py`**: PDF-Pfad existiert; `OCRProvider` wird mit
  `settings.tesseract_cmd`, `settings.ocr_lang` ("deu"), `settings.ocr_enabled`
  (True) injiziert. `config.py:64-66`.
- **Seiten-Evidence bleibt erhalten:** `ExtractionUnit(source_type=PAGE,
  index=Seitennummer 1-basiert, method=TEXT|OCR)`. Die Seitenzahl fließt über
  die `units` in den Beweischschritt der KI-Pipeline ein (Page-Zitat des
  STEP-8B-Evidence-Modells) → OCR-Einheiten sind evidenzfähig.
- **Future-Hook:** `extract_pdf_units(ocr=…)` ist genau der vorhandene
  Trivial-Fallback-Hook für „PDF → native Textschicht → bei Lücken lokaler
  OCR-Fallback je Seite“. Die Qualitäts-Klassifikation in
  `backend/app/documents/quality.py` liefert dafür die
  Vorab-Entscheidung (`partial_text`/`scanned_image` → `*_ocr_fallback`).

### Verfügbarkeit auf dieser Maschine
- `pytesseract` **0.3.13** installiert, `Pillow` **10.4.0**, `pymupdf` **1.24.14**.
- **Tesseract-Binary: NICHT installiert.** Weder `C:\Program Files\Tesseract-OCR\`,
  noch unter `%LOCALAPPDATA%`, nicht auf `PATH`, kein choco/scoop.
  → `OCRProvider.is_available()` = **False**; jeder OCR-Aufruf endet derzeit
  mit `OCRUnavailableError`.
- **Sprachen:** Keine (kein Tesseract ⇒ keine `deu`-Traineddata).
  Konfiguriert ist `ocr_lang="deu"` (deutscher OCR ist Ziel-Layout bereit,
  aber Dateneinheit fehlt).
- **Lokalität:** alles lokal (pytesseract/PyMuPDF/Pillow, kein Cloud-API).
  Die Architektur hält damit die „keine externen Verträge“-Anforderung ein.

### Was genau fehlt (keine Installation durchgeführt)
1. Tesseract-Binary installieren (z. B. `choco install tesseract` oder
   UB-Mannheim-Installer; **ohne Nutzereingriff nicht ausgeführt**), zuletzt
   mit `language-pack deu` (Traineddata `deu.traineddata`).
2. `settings.tesseract_cmd` auf den Installationspfad setzen (z. B.
   `.env` / `tesseract_cmd="C:\Program Files\Tesseract-OCR\tesseract.exe"`).
3. `OCRProvider.is_available()` verifizieren; danach läuft der bestehende
   Seite-für-Seite-Fallback (300 dpi) automatisch.

Technisch geeignete lokale Alternativen (falls ohne Tesseract):
`pyocr + OCRmyPDF`, `RapidOCR (ONNX/Paddle)` oder `easyocr` (PyTorch, CPU) –
alle lokal, alle mit `deu`. Empfehlung bleibt Tesseract (leichtgewichtig,
deutsche Kontrakte mit `deu` gut getestet, passt zum schlanken Medflux-Stack).

## 7. PDF↔DOCX-Vergleichs-Set (Vorschlag, strategisch)

33 der 36 PDFs haben **normalisierte Namens-Treffer** mit dem Legacy-DOCX-Korpus
(Confidence 100: `normalize_name` ohne Suffix). Die 6 STEP-8/8B-Benchmark-Verträge
sind alle enthalten:

| PDF (neu, gescannt) | Legacy DOCX (Text, gebenchmarkt) | Hinweis |
|---------------------|----------------------------------|---------|
| Vision RFD 3D.pdf | Vision RFD 3D.docx | 1:1-Paar |
| Siemens MRT Vida 3T.pdf | Siemens MRT Vida 3T.docx | 1:1-Paar |
| Service Vertrag Abiomed.pdf | Service Vertrag Abiomed.docx | „Abiomed_FullService“ |
| Apoplex Vertrag Service.pdf | Apoplex Vertrag Service.docx | 1:1-Paar |
| GE MACLAB.pdf | GE MACLAB.docx | 1:1-Paar |
| Truebeam STX.PDF | Truebeam STX.docx | 1:1-Paar |

Weitere 27 Namens-Treffer (Abiomed Impella, Accutorn, Artis Zee, Axiom …,
BD Service, CT Revolution EVO/HD, EVB-IT, GAMMMED, Gessler, Harmony, IDS,
Magentom, MFS, MMM, Phillips, Rahmenvertrag Abbott, Service Vertrag Abbottt,
Servicevertrag Radiosurgery 2018/2021/2024, Truebeam Essentials, Varain,
Wartung vertrag OEC Elite …). Ohne Namens-Treffer (nur im neuen Korpus):
`ADOPS Wartung vertrag.pdf`, `CCE_Full_Service_Konditionen_TW_01-2025.pdf`,
`OEC ONE CFD 31 - Focus Full Vollservice-Vertrag.PDF` und
`Frankfurt, Nordwest KH RAV-00074 …` (Legacy-DOCX dort mit verkürztem
Dateinamen `…LFZ 04.06.2025 - 03.06.docx` → sehr wahrscheinlich dasselbe
Dokument, Confidence automatisiert 0 → **narrativ als Treffer notiert**).

> Diese Paare sind strategisch wertvoll: **Original-PDF (Scan/OCR) vs.
> konvertiertes DOCX (Text)** desselben Vertrags erlauben später eine
> ehrliche Gegenüberstellung der Extraktionsqualität beider Pfade.
> Erst **nach** erfolgreicher OCR kann ein neues Ground Truth / Vergleich
> gegen `ground_truth.json` entstehen. Jetzt: **kein neues Ground Truth.**

## 8. Empfohlene nächste Schritte (NICHT ausgeführt in dieser Aufgabe)

1. **Tesseract + `deu`-Traineddata installieren** (vorzugsweise choco oder
   UB-Mannheim-Installable; nur auf Freigabe), `tesseract_cmd` in `.env`.
2. OCR-Smoke-Test auf 2–3 gescannte PDFs (z. B. Vision RFD 3D.pdf,
   GE MACLAB.pdf): Seite→Image(300 dpi)→deu→Units, Seiten-Evidence prüfen.
3. Danach entscheiden: Benchmark v2 mit OCR-Textelektuell + dieselbe
   `ground_truth.json`-Bewertungslogik – das trennt nachweislich
   OCR-Qualität von KI-Qualität.
4. Optional: `quality.py`-Klassifikation am `TextExtractionResult`
   (`requires_ocr`, `extraction_status`), nicht nur an Roh-PDFs, reaktivieren –
   der Hook dafür ist vorhanden.

## 9. Geänderte/neu erzeugte Dateien

- **neu:** `backend/app/documents/quality.py` (Klassifikationsmodul, testbar)
- **neu:** `backend/tests/test_document_quality.py` (9 fokussierte Tests)
- **neu:** `scripts/document_quality_inspection.py` (Inspektions-Runner)
- **neu:** `data/benchmark_v2/input/*.pdf` (extrahierte 36 PDFs; in `.gitignore` via `data/benchmark_v2/input/`)**
- **neu:** `data/benchmark_v2/document_quality.json` (Maschinenreport)
- **neu:** `docs/DOCUMENT_QUALITY_EVALUATION.md` (dieses Dokument)
- **geändert:** `docs/PROJECT_PROGRESS.md` (nur Notiz unter STEP-8B/bis
  dokument-Ingestion; Fortschritt bleibt 8/18)

**Nicht angefasst:** `data/benchmark/` (inkl. ground_truth.json, report_latest.json,
report_groups.json), das Original-Archiv auf dem Desktop, keine OCR-Installation,
keine AI-Benchmarks, kein STEP-9-Start.

## 10. Tests

- `pytest tests/test_document_quality.py` → **9 passed** (0,03 s; rein
  deterministische Klassifikationslogik, keine KI/OCR/PDF-Abhängigkeit).
- **Bewusst NICHT** ausgeführt: 6-Vertrags-AI-Benchmarks, wiederholte
  AI-Tests (Anweisung).

- Projektfortschritt bleibt **8 / 18 = 44,4 %**.