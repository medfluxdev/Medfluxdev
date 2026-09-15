# Medflux – Strukturierte KI-Extraktion

> **Produktionsstand:** Der produktive Importpfad verwendet standardmäßig den
> provider-neutralen Contract Intelligence Harness (aktuell `v2`, optional
> `v3`) auf Basis des kanonischen `DocumentIntelligenceResult`.
> `StructuredContractExtractor` / `ContractAnalysisOrchestrator` bleiben als
> kontrollierter Legacy-/Testpfad erhalten, sind aber **nicht** der Default des
> Endpunkts `POST /api/documents/import`.

## Produktiver Pipeline-Pfad

```text
Upload PDF/DOCX
  -> DocumentProcessingService
  -> geschütztes Original + DocumentVersion
  -> Document Intelligence (PDF: Docling, DOCX: python-docx)
  -> DocumentIntelligenceResult (canonical)
  -> Analyzierbarkeits-Gate (Text/Units müssen vorhanden sein)
  -> HarnessV2/HarnessV3
  -> AIService.harness_runtime()
  -> lokaler AIProvider (z. B. Ollama / qwen3:8b)
  -> source-grounded Facts + Evidence
  -> ContractAnalysisResult
  -> deterministische Berechnung/Warnungen
  -> atomare Persistenz + akzeptierte Contract Truth
```

Wenn keine belastbar belegte Vertragsinformation entsteht, liefert der Harness
`contract=None`. Der Orchestrator persistiert den Fehllauf und erzeugt nur
einen sichtbaren Draft/Placeholder ohne `accepted_extraction_id`, damit
Quelle und Fehlerlage in der UI erreichbar bleiben. Ein Placeholder ist **kein
erfolgreich analysierter Vertrag**.

### Diagnose-Metriken

Die Felder `chunk_count` und `truncated_chunks` gehören ausschließlich zum
Legacy-`StructuredContractExtractor`. Für Harness-Läufe werden sie als
`NULL` persistiert. Für den produktiven Harness sind insbesondere
`prompt_version=harness-...`, `model`, `ai_call_count`,
`groups_processed` sowie die Harness-Diagnostics maßgeblich.

### Legacy-/Testpfad

Der ältere strukturierte Pfad arbeitet weiterhin so:

```text
TextExtractionResult
  -> ContractAnalysisOrchestrator
  -> StructuredContractExtractor
  -> chunk_units()
  -> GroupPipeline
  -> AIService / lokaler Provider
  -> ContractAnalysisResult
```

Er wird verwendet, wenn `DocumentProcessingService` explizit ein
`analysis`-Objekt injiziert bekommt (z. B. kontrollierte Tests). Er darf nicht
zur Interpretation produktiver Harness-Metriken herangezogen werden.

## Kernkomponenten

### `StructuredContractExtractor` (`backend/app/ai/contract_extractor.py`)

Hauptklasse für die Extraktion. Arbeitet ausschließlich über die vorhandene
`AIProvider`-Abstraktion (`AIService`), es gibt **keine** abweichenden oder
Cloud-Aufrufe.

- `extract(extraction_units)` → liefert ein `ContractAnalysisResult`
- `_extract_chunk(chunk, total)` → extrahiert+validiert EINEN Chunk;
  bei ungültigem JSON kontrollierter Retry (max. `max_retries`), nie endlos
- `_merge(base, incoming)` → deterministisches Zusammenführen mehrerer Chunks
- `_finalize_review(...)` → setzt Prüfinformationen (requires_review etc.)

### `ContractAnalysisResult` (`backend/app/ai/contract_extractor.py`)

Ergebnis-Modell einer vollständigen Analyse:

- `document_id`, `status` (ExtractionStatus), `validation_status`
  (ValidationStatus: VALID / INVALID / UNKNOWN), `requires_review`
- `contract` (Contract | None), `message`, `error`
- `model`, `prompt_version` (z. B. `contract_extraction_v1`), `chunk_count`,
  `processing_duration`

### `ContractAnalysisOrchestrator` (`backend/app/ai/contract_extractor.py`)

Orchestriert die Analyse eines bereits extrahierten Dokuments (Schritt-5-
Ergebnis) und setzt die `document_id` auf das Ergebnis. Keine Berechnungslage.

## Chunking (`chunk_units`)

Texteinheiten (Seiten bei PDF; Absätze/Tabellen bei DOCX) werden in
Dokumentreihenfolge zu Chunks zusammengefasst, bis die Zeichen-Grenze
(`ai_max_chunk_characters`, Standard 6000) erreicht ist.

- Eine einzelne **über-große Einheit bildet allein einen eigenen Chunk**
  (sie wird NICHT zerstückelt) – dadurch bleibt die Quellzuordnung erhalten.
- Chunks sind deterministisch und in sich geschlossen.
- Jede Einheit erhält einen Kopf wie `[Seite 3]` (PDF) bzw. `[Absatz 4]` /
  `[Tabelle 2]` (DOCX) als Orientierung für das Modell.

## JSON-Parsing (`_parse_json`)

- Primär wird die **gesamte** (getrimmte) Antwort als JSON gelesen.
- Defensiv wird – nur als Notlösung, nicht als primärer Mechanismus – bei
  Bedarf der **erste ausgeglichene `{...}`-Block** extrahiert. Es gibt
  **keinen** Markdown-Cleanup-/Hack-Mechanismus.

## Validierung & Fehlerbehandlung

Nach dem Parsing wird das JSON mit `Contract.model_validate(...)` gegen das
vollständige Pydantic-Vertrags-Schema (Schritt 3) validiert. Deutsche
Nutzer-Meldungen (keine Tracebacks):

- `MSG_AI_UNAVAILABLE` – lokale KI nicht erreichbar
- `MSG_AI_INVALID_JSON` – Modell-Ausgabe war kein gültiges JSON
- `MSG_VALIDATION` – Daten konnten nicht vollständig validiert werden
- `MSG_NO_TEXT` – kein Text extrahiert / Analyse nicht möglich

Ergebnis-Status:

- `VALID` / `SUCCESS`, wenn alle Chunks ein valides Modell liefen
- `INVALID` / `PARTIAL`, wenn einzelne Chunks fehlschlugen
  (dann `requires_review = true`)

## Multi-Chunk-Merging

Mehrere Chunks werden in der `_merge`-Methode deterministisch zusammengeführt:

- ein **nicht-null** Wert wird nie durch `null` überschrieben
- **identische** Werte bleiben erhalten
- **widersprüchliche** Werte (z. B. anderer Vertragsbeginn) führen zu
  `requires_review = true` + `review_reasons` (CONFLICT) + `risk_notes`;
  es gibt **kein stilles Auflösen**
- **Listen** (equipment, Leistungen) werden vereinigt und nach Inhalt
  dedupliziert

## Anti-Halluzination

Der Prompt (Version `contract_extraction_v1`) erzwingt:

- ausschließlich **durch das Dokument belegte** Fakten
- **fehlende Werte als `null`** – keine Platzhalter wie `"unknown"`, `"nicht
  gefunden"`, `"n.a."`
- **ereignisbasierte Daten** als `condition` (z. B. `"Übergabedatum"`) statt
  erfundener Kalenderdaten
- keine Berechnung von Kündigungsterminen, Restlaufzeiten oder Warnungen
- semantische Geld-Klassifikation (annual/monthly/once/total), keine
  automatische Wartungskosten-Zuordnung

Bei mehrdeutigen/indirekten Angaben setzt das Modell zusätzlich
`requires_review = true` und einen `review_reasons`-Eintrag (z. B. `vague`).

## Confidence & Quellen-Nachweis (evidence)

- Confidence konservativ: `0.90–1.00` eindeutig explizit; `0.75–0.89` stark
  gestützt; `0.50–0.74` mehrdeutig/indirekt; unter `0.50` zusätzlich
  `requires_review`.
- **`source_text` darf nur wörtlich** aus dem Dokument stammen (nie erfunden)
  und wird auf **maximal ca. 120 Zeichen** begrenzt, damit das JSON nicht
  abgeschnitten wird.
- PDF: `page` = echte Seitennummer. DOCX: `page = null`, stattdessen
  `source_type` + `paragraph_index` / `table_index` (+ optional `cell_index`) –
  keine erfundenen Seiten (Schritt 5 erzeugt diese Indizes).

## Konfiguration (`.env` / `config.py`)

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `AI_EXTRACTION_MAX_TOKENS` | `2048` | eigenes Ausgabe-Budget für das volle Vertrags-JSON (größer als `AI_MAX_TOKENS=256`). Notwendig, da das vollständige `Contract`-JSON nicht in 256 Tokens passt. |
| `AI_MAX_CHUNK_CHARACTERS` | `6000` | deterministische Chunk-Größe (Zeichen) für lange Verträge |
| `OLLAMA_THINK` | `false` | Thinking-Modus von Qwen3-artigen Modellen aus |

`AI_EXTRACTION_MAX_TOKENS=2048` statt 1024: Ein realer `qwen3:8b`-Smoke-Test
zeigte, dass 1024 Tokens bei ausführlichen `source_text`-Belegen unzureichend
sind – das JSON wurde mitten im String abgeschnitten (`done_reason: length`).
Mit 2048 Tokens wird die Antwort vollständig (`done_reason: stop`).

## API

- `POST /api/documents/{document_id}/analyze` – führt die strukturierte
  Analyse für ein zuvor extrahiertes Dokument aus.
- `404` bei unbekannter `document_id`.

## Lokal & sicher

- Es werden **ausschließlich** lokale KI-Aufrufe an den konfigurierten
  Ollama-Endpunkt (`127.0.0.1:11434`) gesendet – keine externen Dienste.
- Logging enthält Provider/Modell/Dauer/Erfolg, aber **nicht** den vollen
  Vertragstext.

## Versionierung des Prompts

Der Prompt ist versioniert (`PROMPT_VERSION = "contract_extraction_v1"`) und
wird im Analyse-Ergebnis mitgeliefert. So lassen sich spätere Prompt-Änderungen
in Schritt 8 (Benchmark) eindeutig nachvollziehen und vergleichen.

## Realer Smoke-Test (Ergebnis)

Ein synthetischer PDF-Wartungsvertrag (`vertrag_smoke.pdf`) wurde importiert
und analysiert:

- Modell: `qwen3:8b`, Prompt: `contract_extraction_v1`, Chunks: 1
- Dauer: ~38,6 s, Ausgabe: gültiges JSON, `status: success`,
  `validation_status: valid`, `requires_review: false`
- Extrahiert u. a.: Vertragsnummer `WM-2024-0001`, Lieferant
  `Siemens Healthineers GmbH`, Vertragstyp `maintenance`, 2 Geräte
  (CT SOMATOM go.Top + MRT MAGNETOM Vida mit Seriennummern), Laufzeit
  2024-07-01 bis 2027-06-30 (36 Monate), 6-Monats-Kündigungsfrist,
  automatische Verlängerung (12 Monate), Jahreskosten 24.500 EUR,
  Monatskosten 2.041,67 EUR, Gesamtwert 294.000 EUR, Zahlungs-/Leistungsdaten,
  SLA (4h Reaktionszeit, 24/7). Quellen-Nachweis Seite 1, Confidence 1.0.
- Thinking-Modus bestätigt aus (`thinking_key_present: False`).

## Grenzen / bekannte Probleme

- **Keine echten Verträge** im Repository (nur `.gitkeep`); der Smoke-Test lief
  mit einem synthetischen PDF-Fixture. Formale Benchmark folgt in Schritt 8.
- Der Prompt erlaubt zusätzliche, nicht im Schema vorhandene Schlüssel; diese
  werden von Pydantic ignoriert (kein hartes Ausgabeschema des Modells
  erzwungen). Ggf. im Benchmark prüfen, ob ein `strict`-Modus gewünscht ist.
- Das Modell schreibt gelegentlich ausführlichere `source_text`-Belege; die
  120-Zeichen-Begrenzung ist eine Prompt-Anweisung (weich), kein harter Zwang.
- `source_text`-Länge + Token-Ausgaben sind modellabhängig – der konkrete
  `AI_EXTRACTION_MAX_TOKENS`-Wert ist für `qwen3:8b` kalibriert und wird in
  Schritt 8 formal gebenchmarkt.

## Nächster Schritt

- Schritt 8 – Benchmark mit echten Verträgen (2025er Testfälle manuell
  vergleichen, Prompt/Schema iterativ verbessern, Halluzinationsrate messen).
