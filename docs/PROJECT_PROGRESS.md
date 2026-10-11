# Medflux â€“ Projektfortschritt

## Projektziel
Ein lokales, schlankes KI-System fÃ¼r deutsche KrankenhÃ¤user zur Analyse und Ãœberwachung von Wartungs- und ServicevertrÃ¤gen.

Das System soll:
- VertrÃ¤ge lokal als PDF/DOCX importieren
- Inhalte vollstÃ¤ndig lokal analysieren
- wichtige Vertragsdaten strukturiert extrahieren
- Vertragsende und KÃ¼ndigungsfristen Ã¼berwachen
- jÃ¤hrliche/monatliche/Gesamtkosten auswerten
- Warnungen und Handlungsbedarf anzeigen
- Quellen/Seiten fÃ¼r extrahierte Angaben anzeigen
- ohne externe KI-API funktionieren

## Technische Grundentscheidung
- Frontend: Next.js / React / TypeScript
- Backend: Python + FastAPI
- Lokales KI-Runtime: Ollama
- Erstes Modell: Qwen3 8B Q4
- Datenbank MVP: SQLite
- Produktionsziel: PostgreSQL
- PDF: PyMuPDF
- DOCX: python-docx
- OCR: lokal, nur wenn nÃ¶tig
- Zielhardware MVP: RTX 3070 8 GB VRAM, Ryzen 7 5800X, 32 GB RAM
- Architektur: KI-Schicht austauschbar, damit spÃ¤ter ein stÃ¤rkeres Krankenhaus-Modell verwendet werden kann

---

# Gesamtplan

## Schritt 1 â€“ Projektdefinition & Architektur
Status: ABGESCHLOSSEN

Ergebnisse:
- Projektumfang festgelegt
- MVP bewusst klein gehalten
- lokale KI als Kern festgelegt
- AI-Backend von UI/Business-Logik getrennt
- grundlegender Tech-Stack gewÃ¤hlt

## Schritt 2 â€“ Repository & OpenCode-Grundstruktur
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Git-Repository im Projekt-Root `Medflux` angelegt (eigene `.git`-Historie)
- Ordnerstruktur nach AGENTS.md erstellt (frontend, backend, data, docs, scripts)
- `docs/PROJECT_PROGRESS.md` mit vollstÃ¤ndig erhaltener Historie
- `.env.example` als Vorlage erstellt sowie `.gitignore` (schÃ¼tzt `data/` und Secrets)
- `README.md` mit ProjektÃ¼berblick, Tech-Stack und Quickstart
- `docker-compose.yml` fÃ¼r Backend + Frontend (optional Ollama)
- Backend-GerÃ¼st: FastAPI-App, Settings (pydantic-settings), Health-Route, Tests
- Frontend-GerÃ¼st: Next.js 14 / React 18 / TypeScript, strikte Typisierung, API-Helper
- `AGENTS.md` als maÃŸgebliche Projektanweisungen
- `scripts/setup.ps1` als Einmal-Initialisierung

GeÃ¤nderte Dateien:
- AGENTS.md, README.md, .env.example, .gitignore, docker-compose.yml
- backend/: requirements.txt, app/main.py, app/core/config.py, app/api/routes/health.py,
  app/ (Package-GerÃ¼st), tests/test_health.py, pytest.ini, Dockerfile, README.md, .gitignore
- frontend/: package.json, tsconfig.json, next.config.js, app/, lib/api.ts,
  Dockerfile, README.md, .gitignore
- docs/PROJECT_PROGRESS.md (Projektname: Medflux, Historie erhalten)
- scripts/: setup.ps1, README.md
- data/: contracts, database, backups mit .gitkeep

Tests/Ergebnis:
- Backend: `pytest` â†’ 2 Tests bestanden (root, health) in ~0,5 s
- Frontend: `npm run build` â†’ kompiliert erfolgreich, statische Seite erzeugt
- `.env` aus `.env.example` erzeugt (nicht eingecheckt)

Bekannte Probleme:
- Python 3.10/venv: keine
- Hinweis: `pytest.ini` setzt asyncio-Loop-Scope auf `function` (Zukunftssicherheit)

NÃ¤chster Schritt:
- Schritt 3 â€“ Vertrags-Datenmodell definieren (Kernfelder, CONTRACT_SCHEMA.md)

## Schritt 3 â€“ Vertrags-Datenmodell definieren
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Stark typisiertes Vertrags-Datenmodell mit Pydantic-Modellen im Backend
- Wiederverwendbare Werte: Money, Duration, TimeValue, FlexibleDate (explizit/ereignisbasiert/unbekannt)
- Quellen-Nachweis: SourceEvidence (Seite, Quelltext, Confidence, Methode, PrÃ¼fbedarf)
- Abschnittsmodelle: Identity, Equipment (mehrere pro Vertrag), Dates, Termination,
  Costs, Payment, Services, SLA, Review, AnalysisMetadata
- Enums: ContractStatus, ContractType, ReviewStatus, RiskLevel, TimeUnit,
  BillingInterval, ExtractionStatus, ValidationStatus u. a.
- Validierung: Confidence in [0,1], BetrÃ¤ge >= 0, Seiten >= 1, keine negativen Fristen
- Unbekannte Werte als null (kein Platzhalterstring)
- EXTRACTED vs. CALCULATED klar getrennt; Berechnungen (latest_cancellation_date,
  Warnstufen, Kostenaggregation) bewusst NICHT enthalten
- Umfangreiche Doku in docs/CONTRACT_SCHEMA.md

Wichtigste technische Entscheidungen:
- FlexibleDate (nicht rohes Datum) erlaubt explizit/unbekannt/ereignisbasiert
- Money als eigener Typ (nicht nur String) fÃ¼r strukturierte Geldangaben
- model_name behalten (KI-Metadata) via protected_namespaces=()
- latest_cancellation_date ist KEIN Extraktionsfeld (Schritt 9 berechnet es)

GeÃ¤nderte Dateien:
- backend/app/models/enums.py (neu)
- backend/app/models/evidence.py (neu)
- backend/app/models/values.py (neu)
- backend/app/models/contract.py (neu)
- backend/app/models/__init__.py (Exports)
- backend/tests/test_contract_models.py (neu)
- docs/CONTRACT_SCHEMA.md (neu)

Tests/Ergebnis:
- `pytest` â†’ 15 Tests bestanden in ~0,6 s, keine Warnungen
  (vollstÃ¤ndiger Vertrag, Minimalvertrag, ereignisbasierter Beginn,
   Geldwerte, Quellennachweis, ungÃ¼ltige Confidence, negative Frist,
   negative BetrÃ¤ge, Seitenzahl, TimeValue, FlexibleDate)

Bekannte Probleme:
- Keine offenen Schritte-3-Probleme
- Hinweis: Berechnete Felder bewusst noch nicht vorhanden (folgen in Schritt 9)

NÃ¤chster Schritt:
- Schritt 4 â€“ Dokument-Import (PDF/DOCX)

## Schritt 4 â€“ Dokument-Import
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Lokaler Import von PDF/DOCX-Dateien (mehrere pro Request, unabhÃ¤ngig verarbeitet)
- Validierung: Endung + MIME (wo erkennbar), leere Datei, GrÃ¶ÃŸenlimit
- Lokale, sichere Ablage unter data/contracts/<document_id>/original.<ext>
- SHA-256-Berechnung fÃ¼r jede Datei (IntegritÃ¤t, Duplikat-Erkennung, Audit)
- Duplikat-Erkennung Ã¼ber lokalen JSON-Manifest-Index (.index.json), kein Ãœberschreiben
- Pfadsicherheit: Nutzerdateiname nie als Pfad; kein Path-Traversal
- Deutschsprachige Meldungen, keine Tracebacks fÃ¼r Nutzer
- API: POST /api/documents/import (multipart, Mehrfachdatei, strukturierte Antwort)
- Frontend: /import-Seite (deutsch) mit Dateiauswahl, Drag & Drop, â€žImport startenâ€œ,
  Ergebnisliste pro Datei (Importiert/Duplikat/Fehlgeschlagen)
- GrÃ¶ÃŸenlimit konfigurierbar Ã¼ber MAX_UPLOAD_SIZE_MB (Settings, nicht hartkodiert)
- python-multipart fÃ¼r Multipart-Uploads hinzugefÃ¼gt

GeÃ¤nderte Dateien:
- backend/app/documents/schemas.py (neu)
- backend/app/documents/storage.py (neu)
- backend/app/documents/service.py (neu)
- backend/app/api/routes/documents.py (neu)
- backend/app/main.py (Router registriert)
- backend/requirements.txt (python-multipart)
- backend/tests/test_document_import.py (neu)
- frontend/app/import/page.tsx (neu)
- frontend/lib/api.ts (apiUpload-Multipart-Helper)
- frontend/lib/types.ts (neu)
- docs/DOCUMENT_IMPORT.md (neu)

Tests/Ergebnis:
- Backend: `pytest` â†’ 28 Tests bestanden in ~0,6 s, keine Warnungen
  (13 STEP-3-Modelle, 13 STEP-4-Import, 2 Health)
  STEP 4: PDF, DOCX, Batch, unsupported Ext, leere Datei, zu groÃŸ,
  Duplikat, sicherer Pfad, SHA-256, partieller Batch, MIME-Konflikt, API-Endpunkt
- Frontend: `npm run build` â†’ kompiliert erfolgreich, /import-Seite erzeugt

Bekannte Probleme:
- Keine offenen Schritte-4-Probleme
- Hinweis: Duplikat-Index ist eine reine JSON-Datei (keine DB) â€“ wird in Schritt 10
  durch echte Persistenz abgelÃ¶st
- Hinweis: uuid-Kollision bei der ID-Vergabe praktisch ausgeschlossen

NÃ¤chster Schritt:
- Schritt 5 â€“ Text-Extraktion (PDF/DOCX, Seitenzuordnung, OCR-Fallback)

## Schritt 5 â€“ Text-Extraktion
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Lokale Textextraktion ohne KI: PDF Ã¼ber PyMuPDF, DOCX Ã¼ber python-docx
- PDF seitenweise mit echten Seitennummern (Seitenzuordnung fÃ¼r spÃ¤tere Quellenanzeige)
- DOCX in Dokumentreihenfolge: AbsÃ¤tze + Tabellen mit Indizes (Paragraph/Tabelle-ZÃ¤hlung)
- Deterministische Erkennung textarmer/gescannter Seiten Ã¼ber `TEXT_POOR_THRESHOLD = 50`
  (substantive Nicht-Leerzeichen-Zeichen pro Seite)
- OCR-Fallback nur fÃ¼r textarme Seiten; OCRProvider mit `enabled`-Flag, tesseract_cmd, ocr_lang ("deu")
- Graceful Degradation: Tesseract nicht installiert â†’ `OCRUnavailableError`, deutsches Handlungs-Hinweis-
  Feld, Partieller Erfolg bleibt 200
- Deutsche Fehlermeldungen (ERR_PDF_CORRUPT/ERR_DOCX_CORRUPT), keine Tracebacks fÃ¼r Nutzer
- Normalisierung nicht-unterbrechender Leerzeichen (U+00A0 â†’ Leerzeichen, bei deutschen Preisen/Datum)
- API: POST /api/documents/{document_id}/extract (200 Erfolg/teilweise/fehlgeschlagen, 404 unbekannte ID)
- Pfadsicherheit: nur interne document_id-Pfade; SourceType PAGE fÃ¼r PDF / PARAGRAPH+TABLE fÃ¼r DOCX
- OCR-Konfiguration in Settings (config.py) und .env.example (OCR_ENABLED/TESSERACT_CMD/OCR_LANG)

GeÃ¤nderte Dateien:
- backend/app/documents/extraction/schemas.py (neu: FileType, SourceType, UnitMethod, ExtractionUnit,
  TextExtractionResult)
- backend/app/documents/extraction/ocr.py (neu: OCRProvider, OCRUnavailableError)
- backend/app/documents/extraction/pdf.py (neu: extract_pdf_units, Seiten/Schwellwert/OCR-Warnung)
- backend/app/documents/extraction/docx.py (neu: extract_docx_units, AbsÃ¤tze+Tabellen)
- backend/app/documents/extraction/service.py (neu: TextExtractionService, Komposition, Fehler)
- backend/app/documents/extraction/__init__.py (neu: Exports)
- backend/app/documents/storage.py (erweitert: resolve_document, is_valid_document_id, find_by_document_id)
- backend/app/api/routes/documents.py (POST /extract-Endpunkt, Docstring)
- backend/app/core/config.py (ocr_enabled, tesseract_cmd, ocr_lang)
- backend/requirements.txt (pytesseract, Pillow)
- .env.example (OCR_ENABLED/TESSERACT_CMD/OCR_LANG)
- backend/tests/test_text_extraction.py (neu)
- docs/TEXT_EXTRACTION.md (neu)

Tests/Ergebnis:
- Backend: `pytest` â†’ 46 Tests bestanden in ~1,3 s
  (STEP 5: Normal-PDF, Mehrseiten-PDF+Seitennummern, textarmâ†’OCR, OCR nicht verfÃ¼gbar,
   DOCX-AbsÃ¤tze/-Tabellen/-Indizes, Umlaute, â‚¬, Preisformat 5.916,67 â‚¬, Datum, beschÃ¤digte
   PDF/DOCX (graceful), unbekannte ID, Quellen-Traceability, Originaldatei unverÃ¤ndert,
   API-Extraktion + 404)
- Frontend: `npm run build` â†’ kompiliert erfolgreich (keine Frontend-Ã„nderungen nÃ¶tig)

Bekannte Probleme:
- Tesseract-Binary nicht installiert â†’ OCR deaktiviert (graceful, deutsches Hinweisfeld).
  OCR wird erst nach Installation von Tesseract funktionieren (Konfiguration steht bereit).
- PyMuPDF/swig DeprecationWarnings bei Import (nicht blockierend)
- Hinweis: KI-Extraktion von Vertragsfeldern bewusst NICHT Teil von Schritt 5 (folgt in Schritt 7)

NÃ¤chster Schritt:
- Schritt 6 â€“ Local-AI-Anbindung (Ollama, Qwen3 8B Q4, Health Check, ModelProvider-Schnittstelle)

## Schritt 6 â€“ Local-AI-Anbindung
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- AusschlieÃŸlich lokale KI (Ollama) â€“ keine externen KI-APIs (OpenAI, Anthropic, Gemini, Azure)
- Provider-Abstraktion `AIProvider` (base.py): health_check(), model_info(), generate()
- `OllamaProvider` Ã¼ber httpx: GET /api/tags (Modell-Liste), POST /api/chat (Generierung)
- Nur der konfigurierte lokale Ollama-Endpunkt (127.0.0.1:11434) wird angesprochen
- Default-Modell `qwen3:8b` (konfigurierbar Ã¼ber OLLAMA_MODEL); nicht Qwen-spezifisch gebaut
- ZeitÃ¼berschreitung, Verbindungsfehler, HTTP-Fehler, ungÃ¼ltiges JSON, leere Antwort behandelt
- Saubere interne Exceptions (AIProviderError + Unterklassen) mit deutschen Nutzer-Meldungen
- Modell nicht installiert â†’ â€žDas lokale KI-Modell qwen3:8b ist nicht installiert.â€œ (kein Modellwechsel/-Download)
- Ollama nicht erreichbar â†’ â€žDie lokale KI ist derzeit nicht verfÃ¼gbar.â€œ (keine Roh-Exceptions)
- Status-API: GET /api/ai/status (provider, available, model, model_available, message)
- Test-API: POST /api/ai/test (dev only, minimal deutsches System-Prompt, kein STEP-7-Prompt)
- Konservative Generierung: AI_TEMPERATURE=0.1, AI_MAX_TOKENS=256, Timeout=120 s
- Thinking-Modus (Qwen3) standardmÃ¤ÃŸig aus: `ollama_think=false` â†’ Antwort direkt in
  `message.content` (kein Aufzehren des Token-Budgets durch Gedankenschritt)
- Logging von Provider/Modell/Dauer/Erfolg â€“ NICHT von vollem Vertragstext
- Router in main.py registriert; kein RAG/Embeddings/Vektor-DB
- Keine Vertrags-Extraktion umgesetzt (folgt in Schritt 7)

GeÃ¤nderte Dateien:
- backend/app/ai/base.py (neu: AIProvider)
- backend/app/ai/schemas.py (neu: AIStatus, ModelInfo, AITestRequest/Response)
- backend/app/ai/exceptions.py (neu: AIProviderError + spezifische Fehler)
- backend/app/ai/service.py (neu: AIService, Status/Generierung, Logging)
- backend/app/ai/providers/__init__.py (neu)
- backend/app/ai/providers/ollama.py (neu: OllamaProvider)
- backend/app/ai/__init__.py (Exports)
- backend/app/api/routes/ai.py (neu: GET /status, POST /test)
- backend/app/main.py (AI-Router registriert)
- backend/app/core/config.py (ai_provider, ollama_model=qwen3:8b, base_url 127.0.0.1,
  ai_temperature, ai_max_tokens, ollama_think=false)
- .env.example (AI_PROVIDER, OLLAMA_MODEL, OLLAMA_BASE_URL, AI_REQUEST_TIMEOUT_SECONDS,
  AI_TEMPERATURE, AI_MAX_TOKENS, OLLAMA_THINK)
- backend/tests/test_ai.py (neu)
- docs/LOCAL_AI.md (neu)

Tests/Ergebnis:
- Backend: `pytest` â†’ 70 Tests bestanden in ~1,3 s
  (inkl. neuem Test, der das Senden von `think`- und Streaming-Optionen prÃ¼ft;
   Alle mit gemockter Ollama-API via httpx.MockTransport, ohne echte Verbindung)
  STEP 6: Provider-Konfiguration, Ollama verfÃ¼gbar/nicht verfÃ¼gbar, Modell
  verfÃ¼gbar/fehlt, erfolgreiche Generierung, Timeout, HTTP-Fehler, ungÃ¼ltige Antwort,
  leere Antwort, Status-API, Test-API, deutsche Meldungen, â€žkein externer Providerâ€œ,
  ungÃ¼ltige Eingabe (422)
- Frontend: `npm run build` â†’ kompiliert erfolgreich (keine AI-UI gebaut, wie gefordert)

Bekannte Probleme:
- Hinweis: Qwen3-Modelle haben einen â€žThinkingâ€œ-Modus. Ist er aktiv, kann das
  Token-Budget aufgezehrt werden und die Antwort landet nicht in `message.content`
  (â†’ â€žkeine Antwortâ€œ). Deshalb ist `OLLAMA_THINK=false` (Standard) gesetzt; das
  Modell antwortet dann direkt.
- Hinweis: Kein weiteres Modell automatisch bezogen; ein Wechsel erfolgt nur Ã¼ber
  `OLLAMA_MODEL`.

NÃ¤chster Schritt:
- Schritt 7 â€“ Strukturierte KI-Extraktion (JSON-Schema, deutsche Prompts,
  Quelle + Seite + Confidence, â€žnicht gefundenâ€œ statt Halluzination)

## Schritt 7 â€“ Strukturierte KI-Extraktion
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- VollstÃ¤ndig lokale Pipeline: TextExtractionResult (Schritt 5) â†’ deterministisches
  Chunking â†’ strukturierte Extraktion je Chunk Ã¼ber die lokale KI (AIService/AIProvider
  â†’ Ollama, qwen3:8b) â†’ strikte JSON-Ausgabe â†’ Parsing â†’ Pydantic-Validierung gegen
  das Contract-Schema (Schritt 3) â†’ deterministisches Multi-Chunk-Merging â†’ Contract-Modell
- KEINE DB-Persistenz (folgt in Schritt 10); KEINE Berechnungen (KÃ¼ndigungstermin,
  Kostenaggregation, Warnstufen) â€“ reine Fakten-Extraktion durch die KI (folgt in Schritt 9)
- Versionierter Extraktions-Prompt `contract_extraction_v1` (deutsch, JSON-only,
  Anti-Halluzination: fehlende Werte als null, keine Platzhalter, ereignisbasierte
  Daten als condition statt erfundener Kalenderdaten, semantische Geld-Klassifikation)
- Quelle + Seite/Confidence/PrÃ¼fhinweis: SourceEvidence fÃ¼r PDF (Seite) und DOCX
  (Absatz/Tabelle/Zelle, page=null, keine erfundenen Seiten); Confidence 0..1,
  unter 0.50 zusÃ¤tzlich requires_review; source_text nur wÃ¶rtlich und kurz (â‰¤ ~120 Zeichen)
- Robustes JSON-Parsing (_parse_json) + kontrollierter Retry bei ungÃ¼ltigem JSON
- Deterministiches Chunking (chunk_units): Einheiten bis 6000 Zeichen gebÃ¼ndelt,
  Ã¼ber-groÃŸe Einheit bildet allein einen eigenen Chunk (Quellzuordnung bleibt erhalten)
- Multi-Chunk-Merging (_merge/_deep_merge): kein Ãœberschreiben durch null,
  Listen-Deduplizierung, widersprÃ¼chliche Werte â†’ requires_review (kein stilles AuflÃ¶sen)
- Ergebnis-Modell ContractAnalysisResult (status, validation_status, requires_review,
  contract, model, prompt_version, chunk_count, processing_duration) + Orchestrator
- API: POST /api/documents/{document_id}/analyze (404 bei unbekannter ID)
- Konfiguration: AI_EXTRACTION_MAX_TOKENS=2048, AI_MAX_CHUNK_CHARACTERS=6000
  (config.py + .env.example)
- Umgang mit dem â€žThinkingâ€œ-Modus von Qwen3 bestÃ¤tigt (OLLAMA_THINK=false):
  Antwort landet direkt in message.content (thinking_key_present: False)

GeÃ¤nderte Dateien:
- backend/app/ai/contract_extractor.py (neu: chunk_units, _parse_json,
  StructuredContractExtractor, ContractAnalysisResult, _merge/_deep_merge,
  ContractAnalysisOrchestrator)
- backend/app/ai/prompts/__init__.py (neu)
- backend/app/ai/prompts/contract_extraction_v1.py (neu: versionierter Prompt)
- backend/app/ai/base.py + service.py + providers/ollama.py (max_tokens-Param,
  AIService.generate_text)
- backend/app/core/config.py (ai_extraction_max_tokens=2048, ai_max_chunk_characters=6000)
- backend/app/models/evidence.py (SourceEvidence: source_type, paragraph_index,
  table_index, cell_index fÃ¼r DOCX; protected_namespaces=())
- backend/app/ai/schemas.py (AIStatus protected_namespace-Warnung behoben)
- backend/app/api/routes/documents.py (POST /analyze-Endpunkt)
- backend/tests/test_contract_extraction.py (neu)
- docs/STRUCTURED_AI_EXTRACTION.md (neu)
- .env.example (AI_EXTRACTION_MAX_TOKENS, AI_MAX_CHUNK_CHARACTERS)

Tests/Ergebnis:
- Backend: `pytest` â†’ 96 Tests bestanden in ~1,15 s
  (STEP 7: Chunking deterministisch/Ã¼ber-groÃŸe Einheit, JSON-Parsing, Retry bei
   ungÃ¼ltigem JSON, Validierung, Merge ohne Ãœberschreiben, Listen-Deduplizierung,
   Konflikt â†’ requires_review, Fehlermeldungen, Orchestrator, /analyze-Endpunkt +
   404; alles mit gemockter Ollama-API via httpx.MockTransport)
- Frontend: `npm run build` â†’ âœ“ Compiled successfully, statische Seiten erzeugt
- Realer lokaler Smoke-Test (synthetischer PDF-Wartungsvertrag, qwen3:8b):
  status: success, validation_status: valid, requires_review: false, Dauer ~38,6 s;
  extrahiert u. a. Vertragsnummer WM-2024-0001, Lieferant Siemens Healthineers,
  Vertragstyp maintenance, 2 GerÃ¤te (CT SOMATOM go.Top + MRT MAGNETOM Vida),
  Laufzeit 2024-07-01 bis 2027-06-30 (36 Monate), 6-Monats-KÃ¼ndigungsfrist,
  automatische VerlÃ¤ngerung (12 Monate), Jahreskosten 24.500 EUR, Monatskosten
  2.041,67 EUR, Gesamtwert 294.000 EUR, Zahlung/Leistungen/SLA (4h, 24/7);
  Quelle Seite 1, Confidence 1.0

Bekannte Probleme:
- Keine echten VertrÃ¤ge im Repository (nur .gitkeep); der Smoke-Test lief mit
  einem synthetischen PDF-Fixture. Formale Benchmark folgt in Schritt 8.
- Ermittelt im Smoke-Test: qwen3:8b bricht bei 1024 Tokens ab
  (done_reason: length, JSON mitten im String) â†’ AI_EXTRACTION_MAX_TOKENS=2048
  (done_reason: stop). Wert fÃ¼r qwen3:8b kalibriert, formal in Schritt 8 gebenchmarkt.
- Der Prompt erlaubt zusÃ¤tzliche, nicht im Schema vorhandene JSON-SchlÃ¼ssel;
  Pydantic ignoriert diese (kein hartes Ausgabeschema erzwungen) â€“ ggf. in
  Schritt 8 prÃ¼fen.
- source_text-Begrenzung (â‰¤ ~120 Zeichen) ist eine weiche Prompt-Anweisung;
  das Modell schreibt sie gelegentlich ausfÃ¼hrlicher.
- OCR weiterhin nur optional (Tesseract nicht installiert, Graceful Degradation)

NÃ¤chster Schritt:
- Schritt 8 â€“ Benchmark mit echten VertrÃ¤gen (20â€“30 TestfÃ¤lle, manuell
  vergleichen, Prompt/Schema iterativ verbessern, Halluzinationsrate messen)

## Schritt 8 â€“ Benchmark mit echten VertrÃ¤gen
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Testkategorien:
- Beginn/Ende
- KÃ¼ndigungsfrist
- automatische VerlÃ¤ngerung
- Kosten
- Dienstleister
- Reaktionszeiten
- Leistungsumfang
- Halluzinationsrate

Ziel:
- 20â€“30 reale VertrÃ¤ge als Testset
- Ergebnisse manuell vergleichen
- Prompt/Schema iterativ verbessern

Implementiertes:
- Reale, reprÃ¤sentative VertrÃ¤ge als Benchmark-Grundlage: aus der vom Nutzer
  bereitgestellten ZIP `Ø§Ù„Ø¹Ù‚ÙˆØ¯.zip` (33 echte DOCX-VertrÃ¤ge) nach
  `data/benchmark/input/Ø§Ù„Ø¹Ù‚ÙˆØ¯/` entpackt (nicht eingecheckt)
- Manuell geprÃ¼fte Ground-Truth fÃ¼r 6 Sample-VertrÃ¤ge in
  `data/benchmark/ground_truth.json` (Vision RFD 3D, Siemens MRT Vida 3T,
  Abiomed Full-Service, Apoplex SRAclinic, GE MACLAB, Truebeam STX; 64 Felder)
- Benchmark-Runner `scripts/benchmark_extraction.py` (nutzt die vorhandene
  Pipeline Schritt 5 + Schritt 7): typisierte Matcher (contains, enum_in, bool,
  null/not_null, money_amount+tol, duration, time_value, device_contains,
  serial_contains, int_ge), Fehlerklassifikation (fehlend/falsch/erfunden),
  JSON-Report nach `data/benchmark/report_latest.json`; Option `--runs N`
  (best-of-N gegen Modell-Nichtdeterminismus)
- Ergebnis-Dokumentation in `docs/AI_EVALUATION.md`

DurchgefÃ¼hrte, begrÃ¼ndete Ã„nderungen (aus Benchmark-Fehlern abgeleitet):
- `config.py`: `ai_extraction_max_tokens` 2048 â†’ 8192 (behebt abgeschnittenes
  JSON / Truncation bei komplexen VertrÃ¤gen, done_reason=length)
- `prompts/contract_extraction_v1.py`: Abschnitt â€žSCHEMA-TREUE (PRIORITÃ„T 1)â€œ
  ergÃ¤nzt (exakte Feldnamen/Struktur, equipment=Liste, services=Objekt,
  contract_type-Kleinbuchstaben-Enum, keine erfundenen Abschnitte,
  vollstÃ¤ndiges JSON)
- `contract_extractor.py`: Retry greift jetzt auch bei schemawidriger, aber
  JSON-konformer Ausgabe (bisher nur bei ungÃ¼ltigem JSON);
  `_RETRY_SYSTEM_PROMPT_SUFFIX` um Schema-Hinweis erweitert

GeÃ¤nderte Dateien:
- scripts/benchmark_extraction.py (neu)
- data/benchmark/ground_truth.json (neu)
- data/benchmark/report_latest.json (generiert)
- docs/AI_EVALUATION.md (neu)
- backend/app/core/config.py (ai_extraction_max_tokens=8192)
- backend/app/ai/prompts/contract_extraction_v1.py (SCHEMA-TREUE-Abschnitt)
- backend/app/ai/contract_extractor.py (Retry auch bei Schema-Abweichung)

Tests/Ergebnis:
- Backend: `pytest` â†’ 96 Tests bestanden (~1,2 s, unverÃ¤ndert)
- Benchmark (6 echte VertrÃ¤ge, 64 Felder):
  - Baseline (vor Ã„nderungen, 1 Lauf): 16/64 = 25,0 %; 39 fehlend, 9 falsch,
    0 erfunden; nur 1/6 validiert
  - Nach Ã„nderungen (best-of-3): 8/64 = 12,5 %; 39 fehlend, 17 falsch,
    0 erfunden; nur 1/6 validiert (Siemens); Ã˜ ~130 s/Vertrag
- Konstante Schwachstellen: contract_type/billing_interval (Enum) immer falsch,
  termination.*, Dauer/Daten und GeldbetrÃ¤ge fehlen zuverlÃ¤ssig
- Halluzinationsrate: 0 (Anti-Halluzination wird eingehalten)
- Schlussfolgerung: qwen3:8b (Q4) mit reinem Prompt-Ansatz erfÃ¼llt die
  â€žzuverlÃ¤ssige Extraktionâ€œ des MVP nicht; AnsÃ¤tze dafÃ¼r in STEP 9-Abschnitt
  von docs/AI_EVALUATION.md (z. B. strukturierte Modell-Ausgabe erzwingen)

Bekannte Probleme:
- qwen3:8b weicht trotz verstÃ¤rktem Prompt vom Schema ab (u. a. contract_type
  als GroÃŸbuchstabenwert) und liefert nur ~12,5 % Feldgenauigkeit
- Modell-Nichtdeterminismus: Lauf-zu-Lauf-Varianz; nach den Ã„nderungen stabil,
  aber auf niedrigem Niveau
- Realer Datenbestand (33 VertrÃ¤ge) wird nicht eingecheckt (data/ ist gitignored)
- FÃ¼r langsame OCR-CPU-Bewehrung: Truebeam/komplexe VertrÃ¤ge bis ~3â€“4 min

Hinweis â€” STEP 8B (interne HÃ¤rtung, zÃ¤hlt NICHT als neuer Schritt):
- Nach dem abgeschlossenen STEP 8 erfolgte eine nicht gezÃ¤hlte HÃ¤rtungsphase
  Â«STEP 8B â€“ Extraction Reliability HardeningÂ» (Details:
  docs/STEP_8B_CHECKPOINT.md und STEP-8B-Abschnitt in docs/AI_EVALUATION.md).
- Kern: native strukturierte Ausgabe Ã¼ber Ollama (`format`=JSON-Schema aus dem
  Pydantic-Modell), `repeat_penalty=1.3` (behebt Wiederholungsschleifen),
  `ai_request_timeout_seconds=300`, `extra="forbid"` auf Contract.
- Ergebnis (6 echte VertrÃ¤ge Ã— 3 LÃ¤ufe, gleiche Ground Truth): best-of-3
  Feldgenauigkeit 31/64 = 48,4 %; Validierung 6/6 (17/18 EinzellÃ¤ufe valid);
  0 erfunden, 0 Timeouts, 0 Truncation, Ã˜ ~32 s. Schema-KonformitÃ¤t/Enums behoben;
  semantische Feldabdeckung noch nicht MVP-reliabel (Kosten, Fristen, seltene
  Felder). Fortschritt bleibt 8/18 = 44,4 %.

Hinweis â€” STEP 8B-Semantik (Feldgruppen-Extraktion, weitere interne Phase):
- Matcher-Fix vervollstÃ¤ndigt (scripts/benchmark_extraction.py `_norm_str`:
  `getattr(v, "value", v)`; der frÃ¼here `isinstance(str)`-Guard war bei
  str-Enums wirkungslos und wertete ALLE Enum-Felder falsch). Korrigierte
  STEP-8B-Baseline: 38/64 = 59,4 % (31 + 7 Enum-Korrekturen; die frÃ¼her
  genannte 39/64 enthielt 1 DoppelzÃ¤hl-Artefakt bei Vision `equipment`).
- Neue Pipeline: `GroupPipeline` (Feldgruppen je Chunk, deterministischer
  Merge, Evidence-First-Verifikation gegen Original-DOCX, semantischer Verifier).
  Neuer Runner `scripts/benchmark_groups.py`; neuer Report
  `data/benchmark/report_groups.json` (historischer `report_latest.json`
  bleibt unverÃ¤ndert).
- Ergebnis (6 VertrÃ¤ge, 1 Lauf je Vertrag, korrigierter Matcher): Feldgenauigkeit
  **43/64 = 67,2 %** (Vision 12, Siemens 6, Abiomed 8, Apoplex 5, GE 5,
  Truebeam 7; Baseline korr. 38/64); 0 erfunden, 0 Timeouts, 0 Retries,
  0 Truncation, Ã˜ ~62 s (Truebeam ~156 s, 11 Chunks/44 Gruppen).
- Ehrlicher Zusatzbefund: Validierung fÃ¤llt auf 0/6 `invalid` + requires_review â€“
  konservative Verifier-/Review-Logik (unsupported sensible Felder), nicht
  fehlende Extraktion; Security gut, Automation noch nicht selbstvalid.
  Fortschritt bleibt **8/18 = 44,4 %**.

Hinweis â€” Dokument-Ingestion / QualitÃ¤ts-Check Benchmark v2 (Diagnose, kein Schritt):
- Neues PDF-Korpus aus `Desktop\Ø§Ù„Ø¹Ù‚ÙˆØ¯ Ø§Ù„Ø¬Ø¯ÙŠØ¯Ø©.zip` nach
  `data/benchmark_v2/input/` extrahiert (Original-Archiv und Legacy-`data/benchmark/`
  unangetastet; kein neues Ground Truth).
- Ergebnis der Textschicht-Diagnose (36 PDFs, 355 Seiten): **34Ã— scanned_image,
  2Ã— partial_text (nur Kopf-/Metadaten-Layer: BD Service â€žDocusign Envelope IDâ€¦",
  1-seitiges CCE-Konditionsblatt), 0Ã— native_text, 0Ã— unreadable**. Gesamt nur
  3.095 native Zeichen (Ã˜ 8,7/Seite) â†’ der neue PDF-Korpus ist praktisch
  vollstÃ¤ndig ein OCR-Korpus; qwen3:8b-Benchmarks dort sind erst nach OCR sinnvoll.
- Neue, testbare Klassifikationslogik: `backend/app/documents/quality.py`
  (+ `scripts/document_quality_inspection.py`, Report
  `data/benchmark_v2/document_quality.json`, Doku
  `docs/DOCUMENT_QUALITY_EVALUATION.md`; fokussierte Tests 9 passed).
- OCR-Ist-Zustand: Abstraktion vorhanden und lokal (`OCRProvider`,
  `extract_pdf_units` rastet textarme Seiten mit 300 dpi, Seiten-Evidence bleibt
  Ã¼ber `ExtractionUnit`/Page-Index erhalten, `ocr_lang="deu"` konfiguriert) â€“
  aber **Tesseract-Binary ist auf dieser Maschine NICHT installiert**
  (pytesseract/Pillow/fitz vorhanden; kein choco/scoop/PATH) â‡’
  `is_available()=False`. Es wurde NICHTS installiert; lokale Optionen geprÃ¼ft.
- Fortschritt bleibt **8/18 = 44,4 %**.

Hinweis â€” Quell-Navigation in extrahierten Einheiten/Nachweisen (interne Phase):
- Vorarbeiten fÃ¼r STEP 14 â€žQuelle anzeigen Ã¶ffnet passende PDF-Seiteâ€œ: Die Schritt-5-
  Textextraktion trÃ¤gt jetzt deterministisch Koordinaten-Metadaten mit, damit die
  Quellenanzeige ohne erneute Extraktion/Re-OCR auskommt.
- `app/documents/geometry.py` (neu): `ocr_pixels_to_pdf_rect` rechnet OCR-Bildpixel
  deterministisch in PDF-Punkte um (72/inch, Ursprung oben links, y nach unten;
  Seitenrechteck-basiert, robust gegen Clips/Skalierung).
- `app/documents/extraction/pdf.py`: native Wort-Boxen je Seite (`page_words`,
  PyMuPDF) sowie OCR-Wort-Boxen je gerasteter Seite (300 dpi) werden als
  `SourceBox(page, x0,y0,x1,y1,text,confidence)` an jeder `ExtractionUnit`
  mitgefÃ¼hrt (`bbox`=EinhÃ¼llende, `boxes`=Wort-Boxen, `ocr_confidence`=Mittelwert
  gÃ¼ltiger Konfidenzen; negative/nicht vorhandene Konfidenzen => None).
- `app/documents/extraction/schemas.py`: `ExtractionUnit` um optionale `bbox`/
  `boxes`/`ocr_confidence` erweitert (default wertefrei â‡’ alle bestehenden
  Aufrufer unverÃ¤ndert gÃ¼ltig).
- `app/models/evidence.py`: `SourceEvidence` um `document_id`, `bounding_box`
  (PDF-Punkte) und `ocr_confidence` erweitert (alles optional, rÃ¼ckwÃ¤rts-
  kompatibel).
- `app/ai/groups/evidence.py`: `verify_evidence` fÃ¼llt den `bounding_box` eines
  PDF-Nachweises aus den echten Wort-Boxen der belegten Seite (nur Boxen, deren
  Text im Quelltext vorkommt; sonst die Einheiten-Region) und Ã¼bernimmt die
  Einheiten-OCR-Konfidenz â€“ Mathematik statt Raterei, niemals erfundene
  Koordinaten.
- Sicherheit/Ist: Es werden KEINE Bild- oder Seitenrender-Koordinaten gespeichert;
  die Workspace-Logik â€žKI extrahiert Fakten, Code berechnet/zeigtâ€œ bleibt
  unangetastet. Kein neues Rendering fÃ¼r die Anzeige nÃ¶tig.

GeÃ¤nderte Dateien (interne Phase):
- backend/app/documents/geometry.py (neu)
- backend/app/documents/extraction/schemas.py (SourceBox, ExtractionUnit+Boxen)
- backend/app/documents/extraction/pdf.py (Wort-Boxen native+OCR, Konfidenz-Mittel)
- backend/app/models/evidence.py (document_id, bounding_box, ocr_confidence)
- backend/app/ai/groups/evidence.py (deterministische Bounding-Box-Anreicherung)
- backend/tests/test_source_navigation.py (neu)

Tests/Ergebnis:
- Backend: `pytest` â†’ **132 Tests bestanden** in ~2 s
  (neu: 14 Quell-Navigations-/Geometrie-/KompatibilitÃ¤tstests; alle 118
  Bestands-Tests weiterhin grÃ¼n).
- Frontend: keine Frontend-Ã„nderungen nÃ¶tig.
- Bekannte EinschrÃ¤nkung: OCR-Koordinaten fallen erst an, wenn Tesseract
  installiert ist (native PDF-Seiten bringen auch ohne OCR Boxen mit).

Hinweis â€” STEP 8B/DI (Lokale Dokument-Intelligence-Schicht, interne Phase):
- Ziel: Aufbau einer minimalen, provider-neutralen Document-Intelligence (DI)-
  Schicht in `backend/app/documents/intelligence/` und Messung der OCR-QualitÃ¤t
  auf 3 reprÃ¤sentativen Original-PDFs, BEVOR STEP 9 die Qwen-Extraktion auf den
  Bestand anwendet. Fortschritt bleibt **8/18 = 44,4 %**.
- Kanonisches Modell `canonical.py` (Medflux-eigen, keine Provider-AbhÃ¤ngigkeit):
  `ElementType`, `BoundingRegion`, `TextSpan(offset,length)`, `Method`
  (NATIVE/OCR/LAYOUT/STRUCTURE/UNKNOWN), `Element` (text, page, region, spans,
  reading_order, method, confidence, table, children, metadata), `Cell`,
  `TableStructure` (num_rows/num_cols, cells, headers, `cell()`, `row_texts()`,
  `linearized_text()` Label->Wert-erhaltend), `Page`, `ProcessingProvenance`,
  `DocumentIntelligenceResult` (`page()`, `all_tables()`, `find_text()`,
  `canonical_text` mit `\f`-Seitentrenner).
- Provider-Abstraktion `provider.py`: `DocumentIntelligenceSettings`
  (do_ocr, do_table_structure, table_mode accurate/fast, ocr_lang ["de","en"],
  device cpu, num_threads, max_pages, ocr_backend rapidocr),
  `DocumentIntelligenceProvider` (ABC), Registry `get_provider()`/
  `available_providers()` (docling, native_pdf; paddle/tesseract folgen).
- `docling_provider.py` (Docling 2.123.1, MIT; offizielle Modelle Apache-2.0 +
  CDLA-Permissive-2.0): Layout+TableFormer(ACCURATE, do_cell_matching)+
  **RapidOCR (ONNX, CPU, Apache-2.0, 3.9.2)** statt fehlendem Tesseract;
  `HF_HUB_DISABLE_SYMLINKS=1` (Windows), Converter-Cache je Pipeline-Hash,
  Mappingâ†’kanonisch inkl. BOTTOMLEFTâ†’PDF-Punkte-Umrechnung, OCR-Konfidenz,
  Warnungen aus `result.errors`. `native_provider.py` nutzt die Schritt-5-
  Extraktion (Method.NATIVE).
- Wichtige Fehlerbehebungen wÃ¤hrend der Diagnose: (1) `_assign_page_text`
  zÃ¤hlte bei leeren Elementen (Bilder) den Trenner nicht â†’ Span-Offsets nach
  einem Bild verschoben â†’ Quell-Navigation schlug fehl; (2) Docling lieferte
  Items doppelt (Body+Floats) â†’ Dedup je Seite/Box/TextlÃ¤nge; beide als
  Regressionstests abgesichert.
- Ergebnisse der 3-PDF-Diagnose (`scripts/document_intelligence_diagnosis.py`,
  JSON-Reports unter `data/benchmark_v2/di_reports/`, Hervorhebungs-Render im
  Original-PDF-Kontext als PNG, Token-Scans, GT-Abgleich, PDF-vs-DOCX,
  Lesereihenfolge-HF-Check):
  - **Vision RFD 3D** (5 S., 36,6 s): 66 Elemente, 4 Tabellen; Geld
    `13.115,00`â†’Seite 4 = GT 13115,00 (match 1/1 DOCX); Datum 13.06.2017â†’S.1;
    GT 6/7 (einziger Miss: Seriennummer liegt im Scan als â€ž21115" vor, im
    Legacy-DOCX-Brief ebenfalls â€ž21115", GerÃ¤tetabelle nennt 24445 â†’
    dokumentierte DisparitÃ¤t, fÃ¼r STEP 14/9 mit Konfidenz statt Annahme).
  - **GE MACLAB** (6 S., 33,5 s): GT 2/2 (CA-15120, MacLab); Geld im deutschen
    `-,`-Format erkannt, DOCX-Vergleich **3/3 match**; Datum 16. April 2025;
    Prozentwerte 2,5â€“25 %, negative Abdunkler (5 % Eigenleistung) korrekt.
  - **Truebeam STX** (14 S., 94,2 s): GT 4/6 â€“ fehlende 2 sind reine
    Datumsformat-Differenz (GT ISO 2018-01-27 vs. Scan â€ž27. Januar 2018",
    beide Werte sind IM OCR-Text vorhanden); Gesamtwert **792.000,00** und
    inkl. MwSt. **942.480,00** (19 %), GerÃ¤te-Seriennummer H192469, Klausel
    â€žKÃ¼ndigungsfrist"â†’Seite 11; DOCX-Geldabgleich 4/6 (2 Abweichungen sind
    Nur-Noise â€ž000,00"/â€ž480,00" aus einem OCR-Tippfehler 150,480,00).
  - Lesereihenfolge/HeaderFooter-Sharing: HF-Anteil 0,0 fÃ¼r alle (Docling
    klassifiziert bei Scans keine PAGE_HEADER/FOOTER-Elemente) â†’ Check
    trivially grÃ¼n; verbleibender Hinweis fÃ¼r STEP 9-Prompting.
  - Negation/Deutsch/Englisch: Negationsbegriffe PDFâ‰ˆDOCX (7â‰ˆ7, 20â‰ˆ20,
    123â‰ˆ127), deutsche ZeichenÃ¤hnlichkeit hoch (77/89, 177/193, 726/743).
- Sicherheit/Datenlebenszyklus-Entscheidungen (RECORD, keine Umsetzung):
  - DI-Schicht speichert NUR extrahierte Texte/Struktur/Koordinaten in
    `data/benchmark_v2/di_reports/` (gitignored); Original-PDFs werden beim
    Rendern NIE modifiziert (fitz `new_shape()` in-memory).
  - Kein neues Ground Truth, kein Produktions-Cache, keine Konfidenz-Mischung:
    OCR-/Layout-Konfidenz verbleibt in der DI-Schicht; KI-semantische
    Konfidenz (STEP 7/8B-Semantik) bleibt getrennt.
  - Cache-/Reprozess-Vertrag fÃ¼r STEP 9: canonical-json je Quelle + SHA-256 +
    Pipeline-Hash + Verarbeitungszeit in Provenance; `--refresh` zur
    Reproduktion; keine zusÃ¤tzlichen Artefakte nÃ¶tig.
- **Entscheidung Sicherungspunkt (Gate B)**: Docling+RapidOCR als KERN-OCR/
  Layout/Tables-Schicht fÃ¼r STEP 9 geeignet, MIT Pflicht-Vorgaben:
  1) OCR-Zeichen-Konfidenz je Element in die SourceEvidence-Auswertung
     Ã¼bernehmen (String-Hypothese > 0,999 Ã¼ber vollstÃ¤ndigem Wort-Box-Abgleich);
  2) Serien-/Werte-DisparitÃ¤t (Vision â€ž21115"vsâ€ž24445") nur Ã¼ber
     Dokumenten-Konsistenz + Konfidenz auflÃ¶sen, nie erraten;
  3) komplexe Kostentabellen (Truebeam: 2 vs. 14 DOCX-Tabellen) via
     Lese-Reihenfolge-Fallback (Werte sind im Text vorhanden);
  4) German-Month-Datumsform (â€ž27. Januar 2018") beim Parsing mitnehmen.
- GeÃ¤nderte Dateien:
  - backend/app/documents/intelligence/{canonical,provider,native_provider,
    docling_provider,__init__}.py (neu)
  - backend/tests/test_document_intelligence.py (13 fokussierte Tests)
  - scripts/document_intelligence_diagnosis.py (neu)
  - data/benchmark_v2/di_reports/* (generiert, gitignored)
  - docs/PROJECT_PROGRESS.md (dieser Hinweis)
- Tests/Ergebnis: `pytest` â†’ **145 Tests bestanden** (132 Baseline + 13 DI;
  inkl. Regressionen fÃ¼r Span-Offsets bei leeren Elementen und Item-Dedup).
- Ressourcen: Vision 36,6 s / GE 33,5 s / Truebeam 94,2 s auf CPU; Modelle
  nach erstem Lauf im HF-Cache, seither offline verwertbar
  (`offline_after_setup=True`).

Hinweis â€” STEP 8B/DI korrektive HÃ¤rtung (interne Phase, Fortschritt bleibt 8/18 = 44,4 %):
- Anlass: Gate B war erteilt, vier dokumentierte Pflichtvorgaben wurden in einer
  internen 10-Phasen-HÃ¤rtung geschlossen; anschliessend Gate-Entscheidung Aâ€“E.
- Phase 1 â€“ Legacy-Review (`C:\Users\JAMAL\Desktop\Medflux_Legacy`, READ-ONLY):
  Konzepte statt Kopie. Ãœbernommene Konzepte: char-gewichtete Sprachanteile,
  Kopf-/Fuss-Band-Heuristik (~12 %), mittlerer positiver OCR-Konfidenzwert,
  Bild-Abdeckungsstatistik, deutsche Text-Nachbereitung. Abgelehnt (dokumentiert):
  LightTableDetector (cv2/Tesseract-Gitterlinien), Tesseract-Leser-Pipeline,
  Legacy-Schemas/Provenance-/Offsets-Services (skaffold, schema-gebunden);
  Legacy-Tests nicht portabel â†’ Ã¼bernommene Tests: 0.
- Phase 3A â€“ Evidenz-BrÃ¼cke `intelligence/evidence.py`: `evidence_from_element/`
  `evidence_from_cell` â†’ SourceEvidence mit `ocr_confidence` (Recognition) STRENG
  getrennt von `confidence=None` (semantisch, erst spÃ¤tere KI-Stufe) und
  `extraction_method=PROGRAMMATIC`; BoundingBox nur bei vorhandener Region.
- Phase 3B â€“ DisparitÃ¤t `intelligence/disparity.py`: `ValueCandidate`+
  `classify_values()` â†’ CONSISTENT/SINGLE/CONFLICT/UNDETERMINED, NIE Raten;
  Original-Wortlaut bleibt erhalten. Erkannte RealitÃ¤t: Vision Seriennr.
  â€ž21115" (Scan+Brief) vs. â€ž24445" (GerÃ¤tetabelle) â†’ CONFLICT, review_required.
- Phase 3C â€“ Deutsche Daten `intelligence/dates.py`: Monatsnamen + Ã¼bliche
  AbkÃ¼rzungen (Jan./Feb./MÃ¤rzÂ§/Apr./Jun./Jul./Sep./Okt./Nov./Dez.),
  numerisch DD.MM.YYYY; â€ž27. Januar 2018"â†’2018-01-27; ungÃ¼ltig/ereignisbasiert
  (â€žab Ãœbergabedatum", â€ž32. Januar") â†’ None (kein Erfinden).
- Phase 3D â€“ Kostentabellen `intelligence/table_normalize.py` (Verifikation
  auf Truebeam): table_p5_12 ist Zell-strukturiert (Zeile â€žTrueBeam STx -
  H192469 - Essentials" mit 8Ã— â‚¬99.000,00; â€žâ‚¬99,000,00"-Zellen â†’ review);
  die kritischen BetrÃ¤ge ausserhalb der Tabelle (792.000,00 / 942.480,00 auf
  S.2/4/5) sind DETERMINISTISCH Ã¼ber â€žein Label links in derselben y-Bande"
  belegbar (`trust=geometry`, BetrÃ¤ge 792000.00/942480.00); â€ž150,480,00" unter
  Label â€žMwSt. 19.0 %" bleibt `review_required` (suspicious_ocr_token) â€“ als
  MwSt-Ausweis (942.480,00âˆ’792.000,00) fÃ¼r den Menschen prÃ¼fbar. Keine
  supplier-spezifischen Regeln (z. B. â€žÃ—9" wird nie interpretiert).
- Phase 4 â€“ Strukturrollen `intelligence/structure.py`: deterministischer
  Nachbereitungs-Pass `apply_structural_roles()` (y-Banden oben/unten â‰¤8 %,
  Wiederholung auf â‰¥2 Seiten, Seitenzahl-Muster) setzt NUR
  `metadata["structural_role"]` = header/footer/page_number; Text wird nie
  gelÃ¶scht (schÃ¼tzt z. B. vor Docusign-Envelope-ID-Dominanz). In
  `docling_provider` aktiviert (`settings.structural_roles=True`) und in der
  Provenance als `preprocessing="structural_roles_v1"` festgehalten.
  Diagnose-Ergebnis auf den 3 Scans: 0 markierte (echte Negativprobe â€“ die
  Scans enthalten KEINE wiederkehrenden Band-Zeilen/Seitenzahlen); der Pass
  lief auf allen Seiten und meldet sich per Warning; Funktionseinheit ist per
  Unit-Test belegt.
- Phase 5 â€“ Token-Sicherheit `intelligence/token_safety.py`: nur UNAMBIVALENTE
  Muster normalisiert (`792.000,00`â†’Decimal(792000.00), `1.234,-`â†’1234.00);
  verdÃ¤chtige OCR-Muster (`150,480,00`, `5.916.67`, `792,000,00`) â†’ 
  `suspicious`/â€žmanueller Review erforderlich", Prozent-/Datum-/Serien-Tokens
  separat klassifiziert.
- Phase 6 â€“ Quell-Navigation `scripts/source_navigation_diagnostics.py`
  (nur Cache, kein Docling): 6/6 Ziele programmatisch gefunden + hervorgehobene
  Render-PNGs + Manifest `source_navigation_diagnostics.json` â€“ Vision: Datum
  13.06.2017 (S.1) + 13.115,00 (S.4); GE: Datum 16. April 2025 (S.1) + 3.429,-
  (S.5); Truebeam: 942.480,00 (S.2) + Phrase â€žKÃ¼ndigungsfrist" (S.11).
  **VISUAL HUMAN VERIFICATION PENDING** â€“ das Modell kann keine Bilder sehen;
  die programmatische Verifikation (Seite/Element/Span/Region/Render) ist von
  einem Menschen im Original-PDF zu bestÃ¤tigen, getrennt berichtet.
- Phase 8 â€“ Manifest `scripts/manifest_verification.py`: alle 3 kanonischen
  Ergebnisse `all_ok=True` (source_sha256, provider+Version, RapidOCR+Version,
  ocr_lang, dpi=None dokumentiert, preprocessing, CANONICAL_SCHEMA_VERSION
  â€ž1.1.0", created_at, warnings). Keine duplizierten Metadaten.
- GeÃ¤nderte/neue Dateien:
  - backend/app/documents/intelligence/{canonical,provider,docling_provider}.py
    â€“ Provenance erweitert (dpi/preprocessing/canonical_schema_version),
    Strukturrollen-Pass eingebunden
  - backend/app/documents/intelligence/{evidence,disparity,dates,token_safety,
    structure,table_normalize}.py (neu)
  - backend/tests/test_di_hardening.py (neu: 33 fokussierte Tests)
  - scripts/{truebeam_table_diagnosis,source_navigation_diagnostics,
    manifest_verification}.py (neu)
  - data/benchmark_v2/di_reports/{truebeam_table_diagnosis,
    source_navigation_diagnostics,manifest_verification}.json (generiert)
- Tests/Ergebnis: `pytest` (backend) â†’ **178 bestanden** (145 + 33 neue
  HÃ¤rtungs-Tests; 0 Fehler). Einmaliger `--refresh` der 3 Canonicals nach dem
  Strukturrollen-Einbau (kein breites Reprocessing); Timing danach
  Vision 47,2 s / GE 39,0 s / Truebeam 101,2 s, Diagnoseergebnisse gegenÃ¼ber
  Baseline unverÃ¤ndert korrekt.
- **Gate-Entscheidung: GATE A** â€“ OCR-Token-Sicherheit, Quell-Navigation
  (programmatisch 6/6), Konfliktbehandlung und finanzielle
  Label->Wert-Beziehungen sind deterministisch belegt und getestet;
  verdÃ¤chtige Werte werden nie erraten, sondern als Review markiert.
  Verbleibender, NICHT-Code-blockierender Follow-up: visuelle BestÃ¤tigung der
  Hervorhebungs-Render durch einen Menschen. STEP 9 beginnt ausschliesslich
  nach expliziter Freigabe.
- **Korrektur nach Abschluss (Quell-Navigation â€“ EXAKTE Wort-/Segment-Geometrie;
  korrektiv, KEIN neuer Hauptschritt, Fortschritt bleibt 8/18 = 44,4 %)**.
  TemporÃ¤res Gate: **GATE D â€“ SOURCE MAPPING INSUFFICIENT**. Die bisherige
  Quell-Navigation hob ELEMENT-/Absatz-Boxen hervor (grossflÃ¤chig, OPAK
  dunkelrot) und rechnete im kanonischen View-Raum ohne die Original-PDF-
  Rotation (Vision/GE: rotation=270, Landscape-MediaBox). Die alten Renders
  galten damit NICHT als â€žvisuell bestÃ¤tigt"; GATE A wird bis zur menschlichen
  BestÃ¤tigung der korrigierten Renders als vorlÃ¤ufig ausgesetzt gefÃ¼hrt (Gate D).
  Korrektur (4 Ursachen):
  1) Koordinatensystem: `page_view_to_mediabox()` wandelt kanonische View-
     Koordinaten deterministisch in den Original-MediaBox-Raum (Rotation
     0/90/180/270, TopLeft, mit Kreislauf-PrÃ¼fung gegen `medibox_to_view`);
     MedienabstÃ¤nde/rotation kommen pro Seite aus dem Original-PDF
     (`Page.original_width_pt/original_height_pt/pdf_rotation`).
  2) Opake Farbe: fitz' `fill=(r,g,b,a)` wird NICHT als Alpha interpretiert â†’
     jetzt `fill_opacityâ‰ˆ0.22` + dÃ¼nne Umrisslinie, keine destruktive Farbe;
     Original-PDFs bleiben byte-identisch (per SHA geprÃ¼ft).
  3) Box-GranularitÃ¤t: neue `WordRegion`-Boxen an `Element.word_regions`
     (granularity word|segment|line|element) aus docling ProvenanceItem
     (charspan+bbox) im `docling_provider`; Element-Box NUR als explizit
     markierter letzter Ausweg (guard: coarse_element_box/oversized â†’
     â€žEXACT_GEOMETRY_UNAVAILABLE").
  4) TemporÃ¤r nÃ¶tiger `--refresh` (fachlich erforderlich fÃ¼r word_regions +
     Original-Seiten-Metrien; KEIN breites Reprocessing; Diagnose danach
     unverÃ¤ndert korrekt).
  Ergebnis: neues Modul `intelligence/highlight.py`, neuer Render-Modul `scripts/
  source_navigation_diagnostics.py` (EXAKT-Modus), `di_reports/highlights_exact/`,
  Manifest `source_navigation_exact.json`. **6/6** Ziele gefunden; **5/6**
  programmatisch exakte Box-Geometrie (Vision Datum S.1; GE Datum S.1 +
  3.429,- S.5; Truebeam 942.480,00 S.2 + â€žKÃ¼ndigungsfrist" S.11). 1/6 ehrlich
  nur Element-Box: 13.115,00 (S.4) liegt AUSSCHLIESSLICH in Tabellenzellen;
  docling liefert fÃ¼r Zellwerte keine Wort-/Segment-Box â†’ coarse_element_box,
  transparent gerendert und markiert. Render-Ort aller 6 per Umriss-Abgleich
  pixel-genau gleich der Umrechnung (overlap=YES). Neue fokussierte Tests
  `tests/test_source_navigation_exact.py` (20): Rotation-Roundtrips 0/90/180/
  270 inkl. Media-Box-Erhalt, Spanâ†’Segment-AuflÃ¶sung, Phrase Ã¼ber 2 Segmente,
  Guard-Schutzregeln, transparentes Render auf synthetischem PDF (Original-SHA
  byte-identisch, halbtransparentes fill_opacity, kein opaker RGBA-Trick).
  Gesamt: **198 Tests bestanden** (178 + 20), 0 Fehler.
  **Gate bleibt D (temporÃ¤r), bis ein MENSCH die Renders visuell am Original-
  PDF bestÃ¤tigt hat** (VISUAL HUMAN VERIFICATION PENDING â€“ das Modell kann
  keine Bilder sehen). Danach Ãœbergang in â€žGate A â€“ bestÃ¤tigt" OHNE
  automatische Freigabe. STEP 9 beginnt NICHT vor expliziter Freigabe.

NÃ¤chster Schritt:
- STEP 9 â€“ Date & Cost Engine (Berechnungen). Beginnt NICHT automatisch; erst nach
  expliziter Freigabe und â€“ wie in docs/STEP_8B_CHECKPOINT.md empfohlen â€“ nach
  spezialisierter Feldgruppen-Extraktion + Evidence-Verifikation.
  Vorbedingung: menschliche BestÃ¤tigung der `highlights_exact/`-Renders
  (Aufhebung Gate D), danach Gate-A-Ãœbergang ohne automatische Freigabe.

### Korrektur-Analyse (Diagnose; Gate D bleibt; NOCH KEIN Fix)

Menschliche VISUELLE PrÃ¼fung der 6 Renders = **1/6 PASS** (nur GE Datum S.1).
Damit ist Gate D bestÃ¤tigt und die Ursachen-KlÃ¤rung abgeschlossen:

- Transparenz/Lesbarkeit: PASS (kein opaker Ãœberzug mehr).
- Exakte Geometrie: 5 Ziele visuell falsch positioniert (Vision Datum S.1,
  Vision 13.115,00 S.4, GE 3.429,- S.5, Truebeam 942.480,00 S.2,
  KÃ¼ndigungsfrist S.11).

Diagnose-Ergebnis (nur Cache + Original-PDF-Inspektion, kein Docling-Refresh,
kein Qwen, keine Benchmark; Artefakt `di_reports/source_navigation_diagnosis.json`,
Tool `scripts/source_navigation_diagnose.py`):

1) Textâ†”BBox-Zuordnung ist NICHT auf unserer (kanonischen) Ebene gebrochen:
   IN ALLEN 5 FÃ¤llen erfÃ¼llt der dem BBox zugeordnete Segment-/Element-Text die
   Invarianz â€žText enthÃ¤lt Ziel" (INVARIANT_CANONICAL=True). Ein reiner
   Text-Containment-Check kann diesen Fehler NICHT erkennen.
2) Die Zuordnung ist im PROVIDER (Docling/RapidOCR) falsch/instabil:
   - Dokumente sind REINE SCANS (keine native Text-Schicht; get_text/search_for
     liefern nichts) â†’ einzige Geometriequelle ist Docling.
   - Auf den betroffenen Seiten ist die BBox-y-Folge NICHT monoton zur
     Element-/Text-Reihenfolge; Richtungs-Wechsel (direction_flips) 2â€“12.
     Pass-Seite GE S.1: 0 Flips (global umgekehrte, aber atomare Paarung â†’
     Highlights weiterhin korrekt). Genau die Flipp-Seiten schlagen fehl.
   - Multi-Zeilen-AbsÃ¤tze werden von Docling zu EINEM TextItem/ProvenanceItem
     mit EINER BBox kollabiert (z. B. Truebeam S.11 10.1-Paragraf, 677 Zeichen,
     eine BBox, die real die Sektoren 10.4â€“10.6 trÃ¤gt).
   - BetragsnÃ¤hen in Tabellen/Formularen erhalten oft die REIHEN-BBox (Label
     und Wert teilen den Y-Band, z. B. Truebeam S.2 label/value je y=381â€“390),
     keine Wort-Box.
   - Tabellenzellen (Vision 13.115,00, S.4): Zellen-BBoxen von Docling liegen in
     einem inkonsistenten Koordinatenraum (Y-Spiegelung relativ zur Element-
     Region; keine Ãœberschneidung) â†’ nur Gesamt-Tabellen-Box verfÃ¼gbar, die
     real den â€žServicepaket"-Beschreibungsbereich Ã¼berdeckt.
   - Vision S.1: unmittelbar aufeinanderfolgende Texte â€žAnlagen" (y151â€“165) und
     â€ž13.06.2017" (y546â€“563) liegen visuell ~400 pt auseinander â†’ Paarung der
     kurzen Zeilen beim Provider vertauscht; BBox des Datums liegt auf leerer
     FlÃ¤che (Tinte 0.0).
3) Schlussfolgerung: Der verbleibende Defekt ist die Text-Spanâ†’Geometrie-
   Assoziation DES PROVIDERS, nicht unsere Umrechnung/Span-Mathematik. Eine
   Korrektur muss die (text,bbox)-Paare atomar (pro OCR-Zeile, nicht pro
   Absatz) aus Docling nehmen (oder pro Wort) und zusÃ¤tzlich deterministisch
   verifizieren (BBox-y-Monotonie zur Text-Reihenfolge; Tinte an der BBox;
   fÃ¼r Zellen: Koordinatenraum-Abgleich mit der Tabellen-Region). KEIN breites
   Reprocessing, KEIN Koordinaten-System-Rewrite (bereits ausgeschlossen).
   Fix erfolgt NACH Freigabe dieser Diagnose als nÃ¤chster Arbeitsschritt.
   Gate D bleibt bis zur visuellen BestÃ¤tigung durch einen Menschen.

### Korrektur umgesetzt â€“ Atomische OCR-Geometrie (Gate D; BestÃ¤tigung weiterhin ausstehend)

Die Diagnose wurde akzeptiert und die Fix-Architektur umgesetzt: atomare
OCR-Geometrie (RapidOCR) als Geometrie-EIGENTÃœMER statt Paragraph-Level-Provenienz.

**Ergebnis (6/6 Ziele navigieren programmatisch EXAKT zur richtigen Seite):**

| Vertrag | Ziel | PrÃ¤zision | Seite | Quelle-OCR-Einheit | Conf. |
|---------|------|-----------|-------|--------------------|-------|
| Vision RFD 3D | 13.06.2017 | EXACT_WORD | 1 | p1_l11_w0 | 1.000 |
| Vision RFD 3D | 13.115,00 | EXACT_WORD | 4 | p4_l41_w0 (valid. Zelle) | 1.000 |
| GE MACLAB     | 16. April 2025 | EXACT_LINE | 1 | p1_l28 | 0.989 |
| GE MACLAB     | 3.429,- | EXACT_WORD | 5 | p5_l33_w1 | 0.631 |
| Truebeam STX  | 942.480,00 | EXACT_WORD | 2 | p2_l38_w1 | 0.986 |
| Truebeam STX  | KÃ¼ndigungsfrist | EXACT_WORD | 11 | p11_l40_w5 | 1.000 |

Pixel-Umriss-Abgleich an den gerenderten Views: alle 6 Boxen liegen auf Tinte
(ink_frac 0.15â€“0.29, auch rotierte Seiten rot=270 korrekt zurÃ¼ckgedreht) â†’
Defekt ist geschlossen; Highlights sind atomar belegt.

**Implementiert (Dateien):**
- `canonical.py` â†’ Schema 1.2.0: `GeometryPrecision`-Enum (word/line/table_cell/
  coarse_element/estimated); `AtomicUnit` (unit_id, kind, text, bbox over page,
  precision, confidence, provider, parent_line_id, canonical_offset/length,
  aligned); `Page.atomic_units`; Provenienz-Felder `geometry_provider`/-version;
  RÃ¼ckwÃ¤rtskompatibilitÃ¤t erhalten (Defaults).
- `atomic_ocr.py` (neu): RapidOCR-Erfassung pro Seite (Zeilen via `to_json()`,
  WÃ¶rter via `return_word_box`/`word_results`), Skala fest aus View-Pixel vs.
  kanonischer Seitenabmessung; deterministische Alignment (globaler
  SequenceMatcher Ã¼ber Token-Folge + lokaler Anker-Fallback fÃ¼r isolierte/
  rotierte Zeilen, PrÃ¤fix-tolerante OCR-Abschneidung); Wort-Offsets via
  casefold-`find` im alignierten Zeilen-Slice (nie erfunden).
- `table_cells.py` (neu): deterministische Y-Spiegel-Reconciliation der
  Docling-Zell-BBoxes (IdentitÃ¤t vs. Y-Spiegel, entschieden Ã¼ber OCR-Wort-
  Mittelpunkt-Belegung); nur validierte `docling_cell`-Einheiten mit
  `VALIDATED_TABLE_CELL`; nie Gesamt-Tabellen-Box als exakt.
- `highlight.py`: neuer atomarer AuflÃ¶ser `resolve_target_atomic` â†’
  EXACT_WORD / VALIDATED_TABLE_CELL / EXACT_LINE / COARSE_FALLBACK /
  TARGET_NOT_FOUND, Containment-Invariante (normalisierter Zieltext âˆˆ
  Einheitstext); `render_transparent_boxes` (Box-basiert).
- `scripts/atomic_geometry_augment.py` (neu): fokussierter Refresh (NUR die
  3 Diagnose-PDFs, ~85 s, 11.551 atomare Einheiten; Text/Layout des Caches
  unverÃ¤ndert). KEIN Docling-Refresh, KEIN Qwen, KEIN Benchmark.
- `scripts/source_navigation_diagnostics.py` â†’ atomarer Modus, Report
  `source_navigation_atomic.json` (je Ziel: page, target, source OCR unit,
  precision, boxes View+MediaBox, confidence, alignment method,
  Anomalie-Signale, render), Renders in `di_reports/highlights_atomic/`.

**Tests:** `tests/test_atomic_geometry.py` (21, davon 4 neue: Modell-Roundtrip,
Zeilen-/Wort-Alignment, lokaler Anker-Fallback inkl. rotierter Euro-Zeile,
PrÃ¤fix-Toleranz, AuflÃ¶ser-Klassifikationen, Tabellenzell-Y-Spiegel/-IdentitÃ¤t).
Vollsuite: **219 passed, 0 Fehler**.

**Gate bleibt D (temporÃ¤r):** Die programmatische Geometrie ist verifiziert,
die Renders mÃ¼ssen aber weiterhin von einem MENSCHEN am Original-PDF bestÃ¤tigt
werden (`VISUAL HUMAN VERIFICATION PENDING`). Kein automatischer Gate-A-Ãœbergang.


Status: OFFEN

Wichtig:
Die KI extrahiert Fakten.
Der Code berechnet:
- spÃ¤testen KÃ¼ndigungstermin
- Tage bis Frist
- Tage bis Vertragsende
- Jahreskosten aus Monatskosten
- Monatskosten aus Jahreskosten
- aggregierte Gesamtkosten
- Warnstufen

## Schritt 9 â€“ Date & Cost Engine
Status: ABGESCHLOSSEN
Datum: 30.08.2026

Ziel (aus STEP-9-Vorgabe):
- Deterministische, erklÃ¤rbare Date & Cost Engine, **getrennt** vom
  extrahierten/source-of-truth `Contract`-Modell.
- Pure Funktionen `(contract, as_of_date) -> ContractCalculationResult`.
- Kein Qwen, kein neuer OCR/Docling-Lauf, keine STEP-8B-Benchmark-Ã„nderung,
  keine externen Werte â€“ bei fehlenden/kollidierenden Eingaben:
  `NOT_CALCULABLE` / `REVIEW_REQUIRED` / `CONFLICT`, niemals fabriziert.

Implementiertes (neues Paket `backend/app/contracts/calculation/`):
- `models.py`: Berechnete Resultat-Modelle, strikt getrennt vom Extrakt.
  - `CalculationStatus` (str-Enum): CALCULATED / EXPLICIT / NOT_CALCULABLE /
    REVIEW_REQUIRED / CONFLICT.
  - `DateTimeResult`, `DifferenceResult`, `MoneyFieldResult`: jedes Feld =
    Wert + Status + ErklÃ¤rung + Eingabe-Provenienz (`inputs`) + `review_required`.
  - `CalcDuration`, `RenewalBoundary`, `DateCalculationKind`, `TaxBasis`
    (UNKNOWN/NET/GROSS), `CalculatedDateField`, `ContractStatusDerivation`,
    `RecurringCostNormalized`, `CostCategory`, `CalculateContractCosts`,
    `ContractCalculationResult` (calculation_version="step9-1.0").
- `calendar_.py`: Kalenderbewusste Arithmetik. Monate mit dokumentierter
  End-of-Monat-Regel (31.01.+1 Monat â†’ 28.02., Schaltjahr â†’ 29.02.; Tag wird
  auf letztes gÃ¼ltiges Datum geklemmt). Kein â€žMonat=30 Tage", kein â€žJahr=365 Tage".
- `dates.py`: Date Engine. `calculate_contract_end_date` (A explizit / B
  start+duration kalenderbewusst / C ereignisbasiertâ†’NOT_CALCULABLE / D
  Konflikt explizit-vs-abgeleitetâ†’CONFLICT), `calculate_latest_cancellation_date`
  (nur bei klarer Relation â€žzum Vertragsende"; freie Formulierung/Quartal â†’
  REVIEW_REQUIRED, nie still gerechnet), `calculate_renewal_boundaries`
  (automatische VerlÃ¤ngerung nur mit `automatic_renewal=True` + `renewal_period`
  + bekannter Grenze), `compute_days_until` (negative Tage = vergangen, NICHT
  auf 0 geklemmt), `derive_contract_status` (ACTIVE/EXPIRED/UNKNOWN;
  TERMINATED nur bei expliziter Markierung).
- `money.py`: Decimal-Grenze. Geld nur als `Decimal`; `float` wird an der
  Berechnungsgrenze **stringbasiert** konvertiert (0.1+0.2==0.3). Bestehender
  `Money.amount` (float) bleibt unverÃ¤ndert (RÃ¼ckwÃ¤rtskompatibilitÃ¤t).
  `scaling_factor` nur fÃ¼r explizit wiederkehrende Perioden
  (monthlyÃ—12, quarterlyÃ—4, semi_annualÃ—2, annualÃ—1); ONCE/HOURLY/UNKNOWN
  werden NICHT annualisiert.
- `costs.py`: Cost Engine. `normalized_recurring` aus EINER wiederkehrenden
  Quelle; bei zugleich vorhandenem annual+monthly wird Ã¼bereinstimmend
  (exakt/toleriert â‰¤0,5 %) korroboriert, sonst CONFLICT. `total_contract_value`
  wird NICHT automatisch addiert. Kategorien (Stundensatz/Reise/Material/
  Ersatzteile/cond. Zusatzkosten) nie blind addiert. Mehrere WÃ¤hrungen â†’
  `currency_conflict`, kein FX. `tax_basis` bleibt UNKNOWN (keine 19 %-Annahme).
- `engine.py`: `calculate_contract(contract, as_of_date)` orchestriert die
  Date/Cost Engine und aggregiert `overall_review_required` + `review_reasons`.

GeÃ¤nderte Dateien:
- neu: `backend/app/contracts/calculation/__init__.py`
- neu: `backend/app/contracts/calculation/models.py`
- neu: `backend/app/contracts/calculation/calendar_.py`
- neu: `backend/app/contracts/calculation/money.py`
- neu: `backend/app/contracts/calculation/dates.py`
- neu: `backend/app/contracts/calculation/costs.py`
- neu: `backend/app/contracts/calculation/engine.py`
- neu: `backend/tests/test_calculation_engine.py`
- unverÃ¤ndert: `app/models/*` (source of truth), Document-Intelligence-/Quell-Navigation.

Tests/Ergebnis:
- Neu: 72 fokussierte Tests in `tests/test_calculation_engine.py`
  (Kalender- und Datumslogik, KÃ¼ndigungs-Relation streng ohne Default-Annahme,
  as_of-abhÃ¤ngige wiederholte VerlÃ¤ngerungen mit expliziter Boundary-Konvention,
  Konflikt-Propagation, TERMINATED-Verhalten, Sicherheits-Invarianten;
  Geld: monthlyâ†’annual, quarterlyâ†’annual, semiannualâ†’annual, annual, einmalig
  ausgeschlossen, 0.1+0.2==0.3, annual+monthly korroborierend/konflikt,
  unbekannte Periode/fehlender Betrag/WÃ¤hrungsmismatch, Stundensatz/Reise/
  Material nicht blind-addiert, Steuerbasis unbekannt, zero vs None,
  scaling_factor, WÃ¤hrungsrundung, kein verstecktes Datum).
- **STEP-9-Korrektheits-HÃ¤rtung** nach finaler Review: strenge KÃ¼ndigungs-
  Relation (keine Default-Annahme), wiederholte automatische VerlÃ¤ngerungen
  relativ zu `as_of_date` (bounded-arithmetisch), Konflikt-Propagation in
  abhÃ¤ngige Datumsberechnungen. Details: `docs/STEP_9_CHECKPOINT.md` Â§9â€“Â§12.
- Volle Backend-Suite: **291 passed** (219 Bestand + 72 STEP-9, keine
  Regressionen).

Bekannte Probleme / bewusst NICHT unterstÃ¼tzt (STEP-9-Grenzen):
- `EXPIRING_SOON` (Warnstufe) folgt in Schritt 11.
- Keine Mehrwertsteuer-/Netto-/Brutto-Ableitung (nur future-safe `tax_basis`).
- Kein FX/MehrwÃ¤hrung-Rechnen; KÃ¼ndigungsfrist nur bei klarer Relation
  â€žzum Vertragsende".
- Keine Persistenz/API-Anbindung (folgt Schritt 10).

NÃ¤chster Schritt:
- Schritt 10 â€“ Datenbank (SQLite-Persistenz der Extraktions- und der
  STEP-9-Berechnungsergebnisse). **STOP â€“ kein STEP 10-Start in dieser Sitzung.**

## Schritt 10 â€“ Datenbank-Persistenz (PostgreSQL + SQLAlchemy + Alembic)
Status: ABGESCHLOSSEN
Datum: 31.08.2026

Umfang (STEP 10A Design-Gate â†’ STEP 10B Implementierung):
- **Design-Gate (10A)** genehmigt: `docs/STEP_10_DATABASE_DESIGN.md`
  (Architektur, Â§6-Spaltenentwurf, Evidence-Ownership Â§10, JSONB/Artifact Â§7,
  LÃ¶sch-Lifecycle Â§13, UUID-Policy Â§2A, Entscheidungen Â§20).
- **Infrastruktur-Entscheidung:** nach instabilem WSL2-Netzwerk **PostgreSQL 18.6
  nativ auf Windows** (EDB-Installer, Service `postgresql-x64-18`, Port 5432,
  127.0.0.1). Rolle `medflux` (LOGIN, CREATEDB) + DB `medflux`. WSL-PG-Cluster
  gestoppt (Port 5432 frei), keine RÃ¼ckkehr zu WSL-PG.
- **UUID-Policy:** datenbank-seitige **UUIDv7** (`uuidv7()` aus PG 18), im ORM
  als `server_default=text("uuidv7()")`, Abruf per RETURNING (`eager_defaults=True`).
  Python 3.10.11 ohne Stdlib-`uuid7`/Drittbibliothek. Bestehende app-erzeugte
  IDs bleiben unverÃ¤ndert (kein Konvertierungs-Migration); kompatibel via
  `document_file.external_id`.
- **ORM (15 EntitÃ¤ten)** unter `backend/app/database/models/`, an Â§6 angeglichen:
  organization (Foundation), document_file, document_version, document_artifact,
  document_processing_result + processing_summary, contract_extraction +
  extraction_evidence, calculation_run + calculation_result +
  calculation_review_flag, contract + contract_document (n:m, Rollen) +
  contract_equipment, review_action.
- **Persistenz-Services** `backend/app/database/services.py`: einziger Schreibrteil
  mit korrekten Transaktionsgrenzen (run/status â†’ commit â†’ teure Verarbeitung
  auÃŸerhalb â†’ kurze Ergebnis-Transaktion), SHA-256-Idempotenz (kein Duplikat-
  History bei Retry), atomare Extraktion (Run + Snapshot + Evidence mit
  `field_ref`-Bindung), atomare Berechnung (Run + Result + Flags), Contract-
  Projektion/Akzeptanz (TERMINATED nur explizit, Â§11), n:m-VerknÃ¼pfung und
  Quell-Navigation (STEP-8B-Kette Contractâ†’Evidenceâ†’Extractionâ†’Versionâ†’storage_key).
- **Alembic 1.13.3:** initiale Migration (alle Tabellen/Indizes/Constraints,
  deterministische Naming-Convention). ZirkulÃ¤rer FK
  `document_artifact.processing_run_id âŸ· document_processing_result` korrekt
  in zwei Schritten (Tabellen ohne zirkulÃ¤ren FK â†’ ALTER TABLE) angelegt.
  Ãœberlange Identifier (>63 Zeichen, PostgreSQL-Limit) auf kompakte Namen
  gekÃ¼rzt. upgrade/downgrade/re-upgrade gegen native PG 18.6 verifiziert.
- **Money/Decimal:** relationale GeldbetrÃ¤ge als NUMERIC(18,2), als `Decimal`
  zurÃ¼ckgelesen (nie BinÃ¤r-Float); WÃ¤hrung separat. GeschÃ¤ftsdaten als DATE,
  technische Timestamps TIMESTAMPTZ (UTC). `calculation_run.as_of_date` explizit
  persistent (heutiges Datum wird nie in gespeicherter Berechnung substituiert).
- **`storage_key` relativ** (nie absolute Pfade); Artifact-Storage-Policy Â§7/Â§13.
- **Sicherheit:** Credentials nur in gitignored `backend/.env` (DATABASE_URL);
  kein Commit von Secrets; temporÃ¤re Setup-Skripte gelÃ¶scht.

GeÃ¤nderte Dateien (STEP 10B):
- neu: `backend/app/database/{base,columns,session,__init__}.py`
- neu: `backend/app/database/models/{organization,document,artifact,processing,
  extraction,calculation,contract,review,__init__}.py`
- neu: `backend/app/database/services.py`
- neu: `backend/alembic/ini`, `backend/alembic/env.py`, `backend/alembic/
  script.py.mako`, `backend/alembic/versions/20260831_4d930fb1d75e_initial_schema.py`
- neu: `backend/tests/test_database_persistence.py` (25 fokussierte PG-Tests)
- geÃ¤ndert: `backend/app/core/config.py` (database_url default PostgreSQL),
  `backend/requirements.txt` (sqlalchemy 2.0.*, psycopg[binary] 3.2.*,
  alembic 1.13.*), `.env.example` (DATABASE_URL PostgreSQL), `.gitignore`
  (`models/` â†’ `/models/` root-only, damit DB-Modelle git-sichtbar).

Tests/Ergebnis:
- **25/25 fokussierte PostgreSQL-Persistenz-Tests bestanden** (UUIDv7-PK,
  Org-Idempotenz, SHA-256-Dedup Dokument/Version, Relative-storage_key,
  Status-Constraints, Artifact-Lifecycle, Processing-Run/Summary, atomare
  Extraktion+Snapshot+Evidence, Integrity-Schnelltest, Calculation-Run+Result
  +Flags, Decimal-Betrag (nicht Float), as_of_date, Contract-Projektion,
  TERMINATED-Regel, Akzeptanz-Zeiger, n:m-Idempotenz, Rolle-Constraint,
  Equipment, Quell-Navigation-Kette, JSONB-Snapshot-Roundtrip, Evidence-Cascade).
- **Volle Backend-Suite: 316 passed** (291 Bestand + 25 STEP-10, 0 Regressionen).
- Migration gegen native PG 18.6: upgrade â†’ downgrade â†’ re-upgrade grÃ¼n;
  alle 16 Tabellen (15 Domain + alembic_version) + zirkulÃ¤rer FK vorhanden.

Bekannte Probleme / bewusst NICHT unterstÃ¼tzt (STEP-10-Grenzen):
- Kein Autoh/RBAC/RLS (nur Ownership-Foundation + RLS-AnknÃ¼pfungspunkte,
  Â§15). Kein STEP-16-Audit, kein STEP-17-Backup/Export.
- KEIN Blankett-JSONB; groÃŸe Payloads/Original-PDFs â†’ Artifact-Storage
  (Verbindung zu bestehender `DocumentStorage`-Logik in spÃ¤teren Schritten).
- Berechnungs-Orchestrator, Import-/Extraktions-Wiring auf DB und API-Anbindung
  folgen in spÃ¤teren Schritten (STEP 10 legt nur Persistenz-Fundament).

NÃ¤chster Schritt:
- Schritt 11 â€“ Warnsystem (EXPIRING_SOON, Warnstufen, Handlungsbedarf).
  **STOP â€“ kein STEP-11-Start in dieser Sitzung.**

## Schritt 11 â€“ Warnsystem (Production-Grade Warning & Action-Readiness)
Status: ABGESCHLOSSEN
Datum: 31.08.2026

Drei klar getrennte Schichten:
- A) **Deterministische Warn-Bewertung** (reine Funktion, `app/contracts/warnings/`).
- B) **Durable Warn-Zustand/Historie** (Persistenz `warning_evaluation_run` +
  `contract_warning`).
- C) **Future Action/Ownership-Integration** (dokumentierter Erweiterungspunkt).

Implementiertes:
- **Reine Engine** `evaluate_contract_warnings(contract, calculation, policy)`:
  kein DB/Netz/KI/verstecktes Datum; `as_of_date` kommt NUR aus dem
  STEP-9-Berechnungslauf; konsumiert STEP-9-Felder, rechnet KEINE Termine neu.
- **Versionierte Policy** (`step11-default-1`, Schwellen 180/90/60/30/14/7,
  Kalendertage) mit exakter Bucket-Semantik (smallest-passing-threshold) und
  Schweregrad-Mapping; Policy-Version wird je Evaluation aufgezeichnet.
- **12 Warn-Typen** (Ende-AnnÃ¤herung/abgelaufen, KÃ¼ndigung annÃ¤hernd/heute/
  verstrichen, Auto-VerlÃ¤ngerung, unklar/Konflikt/manueller Review, fehlende
  Kosten/Kostenkonflikt/WÃ¤hrungskonflikt) â€“ maschinenlesbar strukturiert.
- **KÃ¼ndigungsfrist = primÃ¤rer Handlungstermin**; kein erfundenes Datum bei
  NOT_CALCULABLE/REVIEW_REQUIRED/CONFLICT; TERMINATED-Invariante nie Ã¼berschrieben.
- **Dedup/Alert-Fatigue:** `logical_fingerprint` (stabile semantische IdentitÃ¤t),
  nur dringlichster Bucket, konsolidierte Review-Warnung, deterministische Sortierung.
- **Lebenszyklus getrennt:** `active` (Evaluations-Zustand) vs. `action_state`
  (open/acknowledged/resolved/dismissed, menschlich) â€“ Clearing setzt `active=False`
  ohne History-/action_state-Verlust.
- **Current-Projektion (Â§18):** TERMINATED â†’ STEP9-EXPIRED â†’ EXPIRING_SOON â†’
  ACTIVE/UNKNOWN; `risk_level` aus hÃ¶chster aktiver Warn-Severity (â†’ RiskLevel).
- **Persistenz:** `warning_evaluation_run` + `contract_warning` (org-owned,
  UUIDv7, FKs+ondelete, Filter-Indexe fÃ¼r STEP 12/13); `run_warning_evaluation()`
  idempotent je Berechnungslauf; Organisation-Isolation.
- **Sicher/Datenminimal:** Referenzen statt Vertragstext; keine Fake-User, keine
  Notification-Delivery, keine externen APIs; Owner/Escalation als saubere spÃ¤tere
  FK-Migration (Schicht C) dokumentiert.

GeÃ¤nderte Dateien:
- neu: `backend/app/contracts/warnings/__init__.py`
- neu: `backend/app/contracts/warnings/models.py`
- neu: `backend/app/contracts/warnings/policy.py`
- neu: `backend/app/contracts/warnings/engine.py`
- neu: `backend/app/database/models/warning.py` (WarningEvaluationRun, ContractWarning)
- geÃ¤ndert: `backend/app/database/models/__init__.py` (Registrierung)
- geÃ¤ndert: `backend/app/database/services.py` (Warn-Services + Current-Projektion)
- neu: `backend/alembic/versions/20260831_81aa19e5d946_step11_warning_evaluation_and_contract_.py`
- neu: `backend/tests/test_warning_engine.py` (50 pure Tests)
- neu: `backend/tests/test_warning_persistence.py` (9 PG-Tests)

Tests/Ergebnis:
- Pure Engine: **50 Tests** (exakte Grenzen KÃ¼ndigung+Ende 181..-1, nur
  dringlichster Bucket, KÃ¼ndigungs-PrioritÃ¤t, Auto-Renewal-FÃ¤lle, Review/CONFLICT/
  NOT_CALCULABLE, Kosten, tax_basis UNKNOWN nicht schwer, Determinismus,
  Fingerprint stabil, keine erfundenen Werte).
- Persistenz: **9 PG-Tests** (UUIDv7, Roundtrip+Projektion, Dedup, Severity-
  Eskalation gleiche Zeile, Clearing ohne History-Verlust + action_state erhalten,
  Organisations-Isolation, Contract-Delete-Cascade, TERMINATED/EXPIRED-Projektion).
- **Migration auf nativer PG 18.6:** upgrade â†’ downgrade â†’ re-upgrade grÃ¼n.
- **Volle Backend-Suite: 375 passed** (316 Bestand + 59 neu, 0 Regressionen).

Bekannte Probleme / Grenzen:
- KEIN Dashboard/UI, KEINE Email/Slack/externe Notification, KEIN RBAC/Auth,
  KEINE Fake-User (gehÃ¶ren zu STEP 12/16).
- `action_state`-ÃœbergÃ¤nge sind persistiert; benutzergetriebene Transitions + Owner/
  Escalation/Notification folgen in spÃ¤teren Schritten.
- Kein volles Event-Sourcing (genÃ¼gend Historie fÃ¼r Audit/Reproduzierbarkeit).

NÃ¤chster Schritt:
- Schritt 12 â€“ Dashboard. **STOP â€“ kein STEP-12-Start in dieser Sitzung.**

## Schritt 12 â€“ Dashboard (Production-Grade Procurement Dashboard)
Status: ABGESCHLOSSEN
Datum: 31.08.2026

Ziel:
- Ernsthaftes, krankenhaus-taugliches Operations-Dashboard (â€žÃœbersicht") fÃ¼r
  Einkauf/Finanzen/Vertragsmanagement, das die Kernbeschaffungsfragen beantwortet:
  Welche WartungsvertrÃ¤ge haben wir, was kosten sie, wo besteht jetzt
  Handlungsbedarf, welche KÃ¼ndigungs-/VerlÃ¤ngerungsentscheidung steht als
  NÃ¤chstes an, wie zuverlÃ¤ssig sind die Daten.
- Read-Model-Architektur: Dashboard liest ausschlieÃŸlich akzeptierte/aktuelle
  Runs + aktive `contract_warning`-Zeilen (materialisierte STEP-11-Projektion)
  + `contract.status`/`risk_level`. KEINE SQL-Frontend-/Browser-Warnlogik, kein
  zweiter Warn-Engine, kein Schreiben bei GET.

Kern-KPIs (Backend autoritativ):
- aktive VertrÃ¤ge (Portfolio; TERMINATED/EXPIRED ausgeschlossen, Subcounts aktiv/bald auslaufend)
- bald auslaufende VertrÃ¤ge (distinkt mit aktiver CONTRACT_END_APPROACHING-Warnung)
- kritische KÃ¼ndigungsfristen (aktive cancellation_deadline today/passed/approaching kritisch)
- jÃ¤hrliche Gesamtkosten (nur verlÃ¤sslich, pro WÃ¤hrung, nie gemischt; 0 â‰  fehlend)
- Gesamtvertragswert (nur bei CALCULATED + Money aus akzeptierter Extraktion)

Bereiche:
- Handlungsbedarf (primÃ¤re, priorisierte Queue, top 12 via ACTION_QUEUE_LIMIT)
- FristenÃ¼bersicht (semantische Balkenliste, KÃ¼ndigung vs. Vertragsende getrennt)
- KostenÃ¼bersicht (Jahreskosten + Gesamtvertragswert, MehrwÃ¤hrung als Flag)
- DatenqualitÃ¤t / manuelle PrÃ¼fungen (ZÃ¤hler aus aktiven Warnungen)
- Daten-Frische (requested/current vs. warning_evaluation_as_of; stale explizit)

Implementiertes:
- Backend-Read-Model `backend/app/dashboard/` (models.py: getrennte DTOs;
  service.py: `build_dashboard_overview(session, organization_id, as_of_date)`,
  deterministisch, org-gebunden, READ-ONLY, keine KI, keine Warn-Neuberechnung).
- API `backend/app/api/routes/dashboard.py`: `GET /api/dashboard/overview?
  organization_slug&as_of_date`; `as_of_date` wird NUR an der API-Grenze
  aufgelÃ¶st und abwÃ¤rts gereicht; 404 bei fehlender Org; generischer 500.
  Router in `app/main.py` registriert.
- Performance: 4 gebundene Queries (Contracts, aktive Warnings IN-ids,
  akzeptierte CalculationRuns IN-ids, akzeptierte ExtractSnapshots IN-ids +
  max Warn-eval-Stichtag) statt N+1; kein unbeschrÃ¤nktes Payload; Ergebnis bounded.
- Handlungsbedarf-PrioritÃ¤t nach (Severity-Rang, Warn-Typ-PrioritÃ¤t, Ziel-Datum,
  Fingerprint); keine Duplikat-logical-Warnungen; `total_action_items` =
  alle aktiven requires_action/requires_review; geliefert â‰¤ 12.
- Finanz-Regeln: Jahreskosten nur aus `normalized_recurring.annual` wenn
  value+currency und Status CALCULATED|EXPLICIT, KEIN recurring/currency_conflict;
  Gesamtvertragswert nur bei `total_contract_value_status == CALCULATED` UND
  Betrag aus akzeptierter Extraktion; ausgeschlossene VertrÃ¤ge werden explizit
  gezÃ¤hlt, unknown â‰  0.
- Frontend: `app/page.tsx` (Ãœbersicht, Client, fetch via apiGet) + Komponenten
  `components/dashboard/{KpiCard,ActionList,DeadlineDistribution,
  FinancialOverview,DataQuality}.tsx`; `app/layout.tsx` (Nav: Ãœbersicht aktiv,
  Import Link, VertrÃ¤ge/Einstellungen disabled â€“ keine kaputten Links);
  `app/globals.css` (Design-Tokens, Severity-Farben, Fokus, reduced-motion,
  .visually-hidden, responsive); `lib/dashboard-types.ts` + `lib/format.ts`
  (deutsche Format-Helfer DD.MM.YYYY, Intl de-DE, â€žin X Tagen"/â€žÃ¼berfÃ¤llig").
- Library-Entscheidungen: KEIN Chart (keine ECharts â€“ kleine Balkenliste als
  semantisches HTML), KEIN TanStack Query (ein Read-only-Fetch), KEIN TanStack
  Table in STEP 12 (fÃ¼r STEP 13 evaluiert), kein externes Asset/CDN/Font.
- Sicherheit/Privacy: keine externen Assets, kein dangerouslySetInnerHTML, keine
  Vertragstexte/DB-IDs in DTOs, generische deutsche Fehlermeldung, kein
  Console-Logging von Vertragsdaten; Sicherheits-Header per `next.config.js`
  (nosniff, referrer-policy, X-Frame-Options DENY, permissions-policy,
  CSP frame-ancestors 'none'); volles CSP erst mit Auth/STEP 16 (Inline-Styles
  der Import-Seite + Cross-Origin-Dashboard-Fetch). KEIN Fake-RBAC/keine
  Fake-User (STEP 16). Org-Isolation Ã¼ber `organization_slug` (server-seitig
  aufgelÃ¶st); `NEXT_PUBLIC_ORG_SLUG ?? "krankenhaus"`.
- ZugÃ¤nglichkeit WCAG 2.2 AA ausgerichtet: lang="de", semantisches HTML,
  korrekte Ãœberschriften-Hierarchie, sichtbarer Fokus, Severity immer Text+Farbe
  (nie Farbe allein), prefers-reduced-motion, keinerlei Zertifizierungs-Claim.
- Test-Stack Frontend neu: Vitest 2.1.9 + RTL 14 + jest-axe 9 + jsdom 24
  (Pins gegen Vite-7-Konflikt); `eslint`+`eslint-config-next@14.2.15`+
  `.eslintrc.json`; `test/` + `vitest.config.ts` aus Next-Build-Typcheck
  ausgenommen (Standard-Pattern).

GeÃ¤nderte Dateien:
- Backend:
  - neu: `backend/app/dashboard/{__init__,models,service}.py`
  - neu: `backend/app/api/routes/dashboard.py`
  - geÃ¤ndert: `backend/app/main.py` (dashboard.router registriert)
  - neu: `backend/tests/test_dashboard.py` (24 PG-Tests)
- Frontend:
  - neu: `frontend/app/page.tsx` (Ãœbersicht-Dashboard)
  - neu: `frontend/components/dashboard/{KpiCard,ActionList,DeadlineDistribution,
    FinancialOverview,DataQuality}.tsx`
  - neu: `frontend/lib/dashboard-types.ts`, `frontend/lib/format.ts`
  - geÃ¤ndert: `frontend/app/layout.tsx` (Nav), `frontend/app/globals.css`,
    `frontend/next.config.js` (Sicherheits-Header), `frontend/package.json`
    (test-Script, eslint+test-Deps), `frontend/tsconfig.json` (test-exclude),
    `frontend/.eslintrc.json`
  - neu: `frontend/test/dashboard.test.tsx` (11 Tests), `frontend/test/setup.ts`,
    `frontend/vitest.config.ts`
- Docs:
  - neu: `docs/STEP_12_CHECKPOINT.md`
  - geÃ¤ndert: `docs/PROJECT_PROGRESS.md` (dieser Eintrag)

Tests/Ergebnis:
- Frontend: `npm run test` â†’ **11 passed**; `npx tsc --noEmit` grÃ¼n;
  `npm run lint` â†’ No warnings/errors; `npm run build` â†’ produktiver Next-Build
  kompiliert (Routen `/` und `/import` statisch, Sicherheits-Header-Konfiguration
  kompiliert). Test-Abdeckung: Laden, Fehler, leer, normal, deutsche
  WÃ¤hrungs-/Datums-Formatierung, Ã¼berfÃ¤llig, kritischer Handlungspunkt,
  unzuverlÃ¤ssige Kosten, MehrwÃ¤hrung, automatischer a11y-Check (jest-axe,
  `toHaveNoViolations`).
- Backend: `tests/test_dashboard.py` **24 passed** (PG-Transaktion-pro-Test):
  aktives Portfolio inkl. expiring_soon, TERMINATED/EXPIRED ausgeschlossen,
  kritische KÃ¼ndigungsfristen, verstrichene Frist ohne Terminierung-Inferenz,
  Jahreskosten-Aggregation, MehrwÃ¤hrungs-Trennung, fehlende Kosten â‰  0,
  Kostenkonflikt ausgeschlossen, Gesamtvertragswert-Semantik, nur akzeptierter/
  superseded-ausgeschlossen, Org-Isolation, Handlungsbedarf-Reihenfolge, Queue-
  Limit (â‰¤12), kein Duplikat, kein Handlungsbedarf, Determinismus, stale/fresh,
  bounded payload, partielle Daten, Review-ZÃ¤hler, Fristen-Buckets, Zustand ohne
  Warn-Projektion.
- **Volle Backend-Suite: 399 passed** (375 Bestand + 24 Dashboard, 0 Regressionen;
  5 benigne PyMuPDF-SWIG-Warnungen). Keine neue Alembic-Revision, keine
  DB-Schema-Ã„nderung (Read-Model Ã¼ber bestehende Tabellen), keine alte Migration
  geÃ¤ndert.

Bekannte Probleme / Grenzen (bewusst NICHT in STEP 12):
- Keine volle STEP-13-Vertragsliste/Suche/Filter â€“ Handlungsbedarf top 12,
  `total_action_items` als Gesamtzahl.
- Kein STEP-14-Detail-/Quellen-Drill-Down (keine kaputten Links).
- `action_state`-Transitionen, Owner/Escalation, Notification, volles RBAC = STEP 16.
- Kein vollumfÃ¤ngliches CSP bis Auth/STEP 16 (nur frame-ancestors).
- KEIN Fake-RBAC / keine Fake-User; `organization_slug` reiner aktueller
  Scoping-SchlÃ¼ssel, echte Auth-Schicht in STEP 16.

NÃ¤chster Schritt:
- Schritt 13 â€“ Vertragsliste & Suche (inzwischen ABGESCHLOSSEN, siehe unten).
  **STOP â€“ kein STEP-14-Start in dieser Sitzung.**

## Schritt 13 â€“ Vertragsliste & Suche (Production-Grade Contract Portfolio / Search / Filter)
Status: ABGESCHLOSSEN
Datum: 31.08.2026

Ziel:
- VollstÃ¤ndige, durchsuch- und filterbare Vertrags-Portfolio-Liste (â€žVertrÃ¤ge"),
  das operative GegenstÃ¼ck zum STEP-12-Dashboard (dort Handlungsbedarf/KPIs top-12,
  hier die vollstÃ¤ndige Liste). Grundlage fÃ¼r STEP-14-Detailnavigation.
- Design-Prinzip: **PostgreSQL ist die Suchplattform** (kein separater Such-Dienst,
  keine Volltext-Suche Ã¼ber OCR-Bodies, kein zweiter Volltext-Kopie kompletter
  VertrÃ¤ge). Gesucht wird ausschlieÃŸlich Vertrags-Metadaten, org-gebunden,
  deterministisch.

Implementiertes:
- Backend-Suchpaket `backend/app/contracts/search/` (models.py: getrennte DTOs
  ContractListResponse/ContractListItem/ContractFinance/ContractWarningSummary/
  ContractFacets/SearchFreshness; service.py: `build_contract_search(session,
  params, organization_id, request_as_of)` â€“ READ-ONLY, org-bound, Filter/Ranking/
  Sortierung on DB, ein Aggregate-Facet-Query, max. 6 Queries/Seite, keine Joins
  (EXISTS/scalar-Subqueries) -> keine Duplikate, kein N+1).
- API `backend/app/api/routes/contracts.py`: `GET /api/contracts` mit typisierten,
  allowlist-validierten Query-Params (q, status, risk, warning_type,
  requires_action/review, critical_cancellation, automatic_renewal, supplier,
  currency, annual_cost_min/max, start/end/cancellation-Datumsbereiche, sort,
  direction, page, page_sizeâˆˆ{25,50,100}); 422 fÃ¼r ungÃ¼ltige Werte, 404 bei
  fehlender Org, generischer deutscher 500. In `app/main.py` registriert.
- Ranking (dreistufig deterministisch): exakte Nr. â†’ PrÃ¤fix Nr. â†’ exakter Titel â†’
  exakter Lieferant â†’ Titel enthÃ¤lt â†’ Lieferant-PrÃ¤fix â†’ GerÃ¤te â†’ FTS
  (`search_vector @@ plainto_tsquery('german', q)`) â†’ fuzzy (pg_trgm, min. 3
  Zeichen). Identifikatoren ohne Stemmung (`simple`-TS-Config).
- Filter-Semantik: Kategorien-AND, innerhalb Multi-Select OR; Warn-Filter via
  EXISTS (keine Duplikate); Finanz nur verlÃ¤ssliche Jahreskosten (value+currency,
  Status calculated|explicit, kein currency_conflict; nie Mix/FX, missing â‰  0,
  valide via jsonb_extract_path_text); Datumsbereiche/Sortierung aus AKZEPTIERTEN
  Lauf-Feldern; Org-Isolation auf Query-Ebene.
- Migration `a3f9c1127305` (down `81aa19e5d946`): `CREATE EXTENSION pg_trgm`
  (DB-Owner ohne Superuser verifiziert), generierte `search_vector`-tsvector
  (STORED, Weights A-simple/B-german/C-simple), 8 Indexe (org-Lifecycle/-Status/
  -Ende, search_vector-GIN, supplier-/number-Trgm-GIN, equipment_trgm, warning_
  org_active). upgradeâ†’downgradeâ†’re-upgrade auf PG 18.6 verifiziert; Head =
  a3f9c1127305. ORM: `search_vector`-Computed-Column in
  `app/database/models/contract.py`.
- Frontend: `app/contracts/page.tsx` (Client, URL-Query-State via useSearchParams
  + Suspense, Debounce 300 ms, Race-Handling via Request-ID, Quick-/Advanced-
  Filter, Sortierung, Pagination, ZustÃ¤nde Laden/Fehler/leer/keine-Treffer);
  `components/contracts/ContractTable.tsx` (semantische Tabelle); `components/
  ClientNav.tsx` (aktive Navigation via usePathname, â€žVertrÃ¤ge" aktiv â†’
  `/contracts`); `lib/contract-types.ts`; `lib/format.ts` erweitert
  (formatAnnualCost, Status-/Risiko-Labels); `globs.css` (Search-/Table-/Chip-/
  Filter-/Pagination-Styles). Kein dangerouslySetInnerHTML, keine lokale
  Speicher-Persistenz, keine OCR-Snippets in URLs.
- Sicherheit/DoS: Query max. 200 Zeichen, page_size-/Offset-Bounds, Multi-Select-
  Bounds, LIKE-Escaping, kein Fuzzy fÃ¼r kurze Terme, parametrisierte Queries,
  Allowlist-Enums â†’ 422, generischer deutscher Fehlertext, kein SQL-Leak; CSP/
  Header aus STEP 12 nicht geschwÃ¤cht; DTO bounded (kein OCR/Body/Pfade/SchÃ¼ssel).
  `organization_slug` bleibt reiner Scoping-SchlÃ¼ssel (Auth in STEP 16).
- ZugÃ¤nglichkeit WCAG 2.2 AA ausgerichtet: lang="de", semantische Suche/Filter,
  keyboard-fÃ¤hig, Tabellen-Header mit scope, sichtbarer Fokus, kein color-only
  (Text+Farbe), zugÃ¤ngliche Pagination, aussagekrÃ¤ftige ZustÃ¤nde, reduced-motion.
  Automatischer jest-axe-Check. Kein Zertifizierungs-Claim.
- Library-Entscheidung: TanStack Table v9 erneut evaluiert, fÃ¼r server-seitig
  sortierte Liste (â‰¤100 Zeilen/Seite ohne Virtualisierung) bewusst NICHT
  hinzugefÃ¼gt (semantisches HTML simpler/zugÃ¤nglicher, keine Zusatz-AbhÃ¤ngigkeit).
- NICHT enthalten (bewusst, gemÃ¤ÃŸ STEP-13-Scope): kein OCR-Body-Fulltext,
  kein Elasticsearch/Meilisearch/Typesense/Redis/Vector-DB/Embeddings/RAG/LLM-
  Ranking/Cloud-Search, keine externen Analytics/Telemetrie, keine STEP-9-/11-/12-
  Semantik-Neuimplementierung, kein STEP-14-Viewer, kein Fake-RBAC.

GeÃ¤nderte Dateien:
- Backend:
  - neu: `backend/app/contracts/search/{__init__,models,service}.py`
  - neu: `backend/app/api/routes/contracts.py`
  - geÃ¤ndert: `backend/app/main.py` (contracts.router registriert)
  - geÃ¤ndert: `backend/app/database/models/contract.py` (search_vector Computed)
  - neu (Alembic): `backend/alembic/versions/20260831_a3f9c1127305_contract_search.py`
  - neu: `backend/tests/test_contract_search.py` (36 PG-Tests)
- Frontend:
  - neu: `frontend/app/contracts/page.tsx`
  - neu: `frontend/components/contracts/ContractTable.tsx`
  - neu: `frontend/components/ClientNav.tsx`
  - neu: `frontend/lib/contract-types.ts`
  - geÃ¤ndert: `frontend/lib/format.ts`, `frontend/app/layout.tsx`,
    `frontend/app/globals.css`
  - neu: `frontend/test/contracts.test.tsx` (11 Tests)
- Docs:
  - neu: `docs/STEP_13_CHECKPOINT.md`
  - geÃ¤ndert: `docs/PROJECT_PROGRESS.md` (dieser Eintrag)

Tests/Ergebnis:
- Backend: `tests/test_contract_search.py` **36 passed** (PG-Transaktion-pro-Test,
  autoskip ohne DB): leerer Bestand, exakte Nr./Titel, exakte-Kennung-rangiert,
  Lieferant/PrÃ¤fix/case-insensitive, GerÃ¤te, FTS, fuzzy, exakt-vor-fuzzy, leere/
  Whitespace-/sehr kurze Anfrage, SQL-Injection-artig, Status/Multi-OR, Warn/
  critical/requires_action/requires_review, automatic_renewal, supplier-Filter,
  Start/Ende/KÃ¼ndigungs-Datumsbereiche, Jahreskosten min/max, WÃ¤hrungs-Isolation,
  fehlende-Kosten-â‰ 0, Konflikt-ausgeschlossen, AND-Semantik, Sortierung,
  deterministischer Tie-Breaker, page_size-Bounds, Pagination-StabilitÃ¤t,
  keine-Duplikate, reliable-cost, Org-Isolation (incl. cross-org-Angriffe),
  bounded DTO, Route 422/404 (TestClient).
- **Volle Backend-Suite: 435 passed** (399 Baseline + 36 neue, 0 Regressionen;
  5 benigne PyMuPDF-SWIG-Warnungen). Migration upgradeâ†’downgradeâ†’re-upgrade grÃ¼n.
- Frontend: `npm run test` â†’ **11 passed**; `npx tsc --noEmit` grÃ¼n;
  `npm run lint` â†’ No warnings/errors; `npm run build` â†’ produktiver Next-Build
  kompiliert (statische Route `/contracts`). Test-Abdeckung: Laden, Fehler,
  leeres Kontingent, keine-Treffer, normal, deutsche WÃ¤hrungs-/Datums-Formatierung,
  fehlende-Kosten-â€žNicht eindeutig"-statt-0 â‚¬, MehrwÃ¤hrung, Warn-Severity textuell,
  veraltete Warn-Bewertung, Quick-Filterâ†’URLâ†’Refetch, automatischer a11y-Check.

Bekannte Probleme / Grenzen (bewusst NICHT in STEP 13):
- Kein OCR-Body-Fulltext-Such; Suche auf Vertrags-Metadaten begrenzt.
- Kein STEP-14-Detail-/Quellen-Viewer (keine kaputten Links; `contract_id` als
  stabiler, opaque NavigationsschlÃ¼ssel vorbereitet).
- Keine externe Such-Infrastruktur (bewusst PostgreSQL-only).
- Keine STEP-9-/11-/12-Semantik-Neuimplementierung; Definitionen bleiben autoritativ.
- KEIN Fake-RBAC/Fake-User; `organization_slug` reiner Scoping-SchlÃ¼ssel,
  echte Auth/RLS in STEP 16.

NÃ¤chster Schritt:
- Schritt 14 â€“ Vertragsdetailansicht & Quellenanzeige. **STOP â€“ kein STEP-14-Start
  in dieser Sitzung.**

## Schritt 14 â€“ Vertragsdetailansicht
Status: ABGESCHLOSSEN
Datum: 01.09.2026

Bereiche:
- Ãœbersicht
- Kosten
- Laufzeit
- KÃ¼ndigung
- Leistungen
- Risiken
- Originaldokument
- Quellen

Spezialfunktion:
- "Quelle anzeigen" Ã¶ffnet passende PDF-Seite (lokaler pdf.js-Viewer)

Implementiertes (Kern: Storage-/Provenance-Grenze + sicheres Detail-Read-Model +
sicherer Dokument-Bytes-Endpoint + lokale Quellen-/PDF-Ansicht):
- **Storage-/Provenance-Grenze (User-Entscheidung, zuerst gelÃ¶st):** Ein einziger
  Produktions-Schreib-/Lesepfad `app/documents/persistence.py` â€“
  `DocumentPersistenceService.store_original` koordiniert: SHA-256-
  IdentitÃ¤t/Dedup (global nach Bytes), DocumentFile-Flush mit
  kanonischer `storage_key` (`<UUID.hex>/original.<ext>`), Bytes via
  `DocumentStorage.write_reference`, dann DocumentVersion; bei DB-Fehler nach
  File-Write explizite Kompensation (`delete_reference`), Storage-Fehler lÃ¤sst
  keine akzeptierte DB-Beziehung zurÃ¼ck. `storage_key` ist die einzig
  legitime kanonische Referenz; `DocumentStorage.validate_reference`/
  `safe_path`/`read_reference`/`exists_reference`/`delete_reference` sind der
  Einzige Referenzâ†’Pfad-Ãœbersetzer (nur relativ, erwartete Struktur, kein
  `..`, kein Absolut-/Drive-/UNC-Escape, Containment Ã¼ber `resolve()`/
  `relative_to`). Browser/API erfÃ¤hrt NIE storage_key/Pfade. Legacy-/
  deterministische `resolve_bytes_for_version` meldet unbekannt â†’ generische 404.
- **Detail-Read-Model** `app/contracts/detail/`: `build_contract_detail`
  (org-gebunden, active-Lifecycle, generische 404, kein N+1, KEINE Warn-
  Neuberechnung im GET). Liefert akzeptierte Extraktion(identity/scope/sla +
  Evidence-Provenienz), akzeptierte STEP-9-Berechnung (Dates/Costs/Status),
  STEP-11-aktive Warnungen, Equipment, sichere Dokumentliste.
  Evidence-/Geometrie-Policy: nur element-/seitengebunden â†’ feinste ehrliche
  `precision` = "coarse" (mit bbox) / "none" (ohne); `geometry_normalized`
  (alle bbox-Koordinaten in [0,1]) ist der EINZIGE Fall in dem das Frontend
  pixelgenau hervorheben darf (`supports_exact_navigation`); numerisch
  validierte bbox (finite/geordnet/nicht-negativ), invalid â†’ Seiten-/Snippet-
  Fallback.
- **Sicherer Dokument-Bytes-Endpoint** `GET /api/contracts/{contract_id}/
  documents/{document_version_id}/content`: org+vertrag+version gebunden via
  `DocumentPersistenceService.resolve_bytes_for_version`; MIME-Allowlist
  (PDF/DOCX, sonst 415); HTTP-Range (206/416, bounded); `X-Content-Type-Options:
  nosniff`; `Cache-Control: private, no-store`; RFC-5987/Base-name-sanitierte
  `Content-Disposition` (inline fÃ¼r PDF, attachment fÃ¼r DOCX); generische 404;
  keine storage_keys/Pfade im Response.
- **Detail-Route** `GET /api/contracts/{contract_id}` â†’ `ContractDetailResponse`.
- **Frontend:** `app/contracts/[contract-id]/page.tsx` (Client, Breadcrumb,
  Loading/Fehler-Erneut-zustÃ¤nde via opaque `contract_id`),
  `components/contracts/detail/ContractDetail.tsx` (Abschnitte Ãœbersicht/Kosten/
  Laufzeit/KÃ¼ndigung/Leistungen/SLA/GerÃ¤te/Warnungen + Quellen-Seitenleiste),
  `EvidencePane.tsx` (Quellenangaben, ehrliche PrÃ¤zision coarse/none, Navigation),
  `PdfViewer.tsx` (pdf.js lokal, kein CDN, Worker aus `public/pdfjs/`, bbox-
  Overlay nur bei `supports_exact_navigation`, Seiten-/Zoom-Steuerung,
  Seite-Sprung bei Navigation), `PageControls.tsx`, `SourceLink.tsx`,
  `lib/contract-detail-types.ts`. `pdfjs-dist@3.11.174` gepinnt (lokale
  `public/pdfjs/*.min.js`). Kein iframe als primÃ¤rer Viewer, kein
  DOCX-Fake-Reconvert, keine Document-Content im localStorage.
- **A11y (WCAG 2.2 AA ausgerichtet):** ZugÃ¤ngliche Quellen-Buttons/Evidence,
  `aria-live` fÃ¼r Seiten-/Navigations-Info, Text-Labels fÃ¼r PrÃ¤zisions/Severity-
  Pillen (kein color-only), jest-axe-Check.

GeÃ¤nderte Dateien (neu):
- backend/app/documents/persistence.py (DocumentPersistenceService,
  canonical_storage_key, StoredDocument, link_to_contract)
- backend/app/documents/storage.py (validate_reference, safe_path,
  write_reference, exists_reference, read_reference, delete_reference, _REF_RE)
- backend/app/contracts/detail/__init__.py, models.py, service.py
- backend/app/api/routes/contracts.py (Detail- + Content-Endpoint, Imports)
- backend/tests/test_storage_boundary.py, backend/tests/test_contract_detail.py
- frontend/app/contracts/[contract-id]/page.tsx
- frontend/components/contracts/detail/{ContractDetail,EvidencePane,PdfViewer,PageControls,SourceLink}.tsx
- frontend/lib/contract-detail-types.ts, frontend/lib/api.ts (contentUrl)
- frontend/test/contracts-detail.test.tsx, frontend/package.json, frontend/app/globals.css

Tests/Ergebnis:
- Backend fokussiert: `test_storage_boundary.py` (12) + `test_contract_detail.py`
  (12 Detail+Content) â†’ 24 passed. Volle Backend-Suite: **459 passed** (435
  Baseline + 24 neue, 0 Regressionen).
- Frontend: `npm run test` â†’ **28 passed** (6 neue Detail-/Quellen-Tests, jest-axe
  inklusive); `npx tsc --noEmit` grÃ¼n; `npm run lint` â†’ No warnings/errors;
  `npm run build` â†’ produktiver Next-Build kompiliert (Route
  `/contracts/[contract-id]`, `Æ’ Dynamic`).

Bekannte Probleme / Grenzen:
- DOCX-Quellen werden ehrlich als â€žnicht als PDF-Vorschau" ausgewiesen (kein
  stiller DOCX-Reconvert in STEP 14; `viewer_supported` nur fÃ¼r `.pdf`).
- `store_original` dedupliziert global nach Bytes; eine Duplikat-Version zeigt
  auf die zuerst importierende Org â€“ Content-Zugriff bleibt org-gebunden
  (korrektes Sicherheitsverhalten). Wird in STEP 16 (Upgrade-Pfad: Duplikat-
  Verlinkung pro Org) adressiert.
- Kein Voll-CSP fÃ¼r den pdf.js-Worker: aktuelle CSP minimiert
  (`frame-ancestors 'none'` etc.); vollumfÃ¤ngliches CSP + Auth folgt STEP 16.
- `organization_slug` bleibt reiner Scoping-SchlÃ¼ssel (Auth/RBAC/RLS STEP 16).

NÃ¤chster Schritt:
- Schritt 15 â€“ BenutzeroberflÃ¤che & Design.

## Schritt 15 â€“ BenutzeroberflÃ¤che & Design
Status: ABGESCHLOSSEN
Datum: 01.09.2026
Fortschritt: **15 / 18 = 83,3 %**

Ziel:
- moderne deutsche Krankenhaus-/Procurement-Enterprise-Optik (Design System)
- klar, wenig Navigation, konsistent
- responsive (Desktop/Tablet/Mobile-Spalte, Reflow/200-%-Zoom)
- keine autoritative Business-Ã„nderung: STEP-12/13/14-Semantik exakt erhalten
- ZugÃ¤nglichkeit: WCAG 2.2 AA ausgerichtet (Status nie als Farbe allein)

Implementiertes (Frontend-only; kein Stack-Wechsel, kein groÃŸes UI-Framework):
- **Design-Token-Foundation** in `frontend/app/globals.css` `:root`:
  - Typografie-Skala (`--fs-xsâ€¦3xl`, `--fw-*`, `--lh-*`), `--font-sans`
  - Spacing (`--space-1â€¦12`), Radii (`--radius-sm/md/lg/pill`), Border/Fokus-
    Ring (`--focus-width/ring/offset`), Surface-Hierarchie (`--surface-2/muted`),
    Elevation (`--shadow-sm/md`), Content-Breiten (`--content-max/narrow`),
    Tabellen-Dichte, semantische Statusfarben (`--status-neutral/info/success/
    warning/critical/review/stale/unknown` + `-bg`)
  - AbwÃ¤rtskompatibel: alte Namen (`--sev-*`, `--bg`, `--surface`, `--border`,
    `--text`, `--accent`) bleiben; `body` nutzt `--font-sans`; `:focus-visible`
    nutzt Fokus-Tokens (auch fÃ¼r input/select/textarea/button/`a`)
- **Shared-Primitives** `frontend/components/ui/` (nur real genutzte Wiederholungen):
  `PageHeader` (einziger H1, setzt `document.title`), `SectionCard`, `InlineAlert`
  (neutral/info/success/warning/critical + Rolle), `EmptyState`, `LoadingState`,
  `Button` (ghost/primary/danger, md/sm), `StatusBadge` (immer Textlabel + Punkt,
  nie Farbe allein), `Field`, `DefinitionList` (dl/dt/dd)
- **App-Shell:** `layout.tsx` + `ClientNav.tsx` â†’ Skip-Link â€žZum Hauptinhalt
  springen" (#main-content, focusable), `<nav aria-label="Hauptnavigation">`,
  Brand, korrekte `aria-current=page`-Active-States; â€žEinstellungen" ist jetzt
  ein echter Eintrag (Route neu), `aria-disabled`-Stub entfernt.
- **Seiten Ã¼berfÃ¼hrt:**
  - Dashboard (`app/page.tsx`): PageHeader + Stale-Indikator (aktuell/veraltet/
    noch keine Warn-Bewertung) als semantischer Status; KPI-/Handlungsbedarf-/
    DatenqualitÃ¤ts-Semantik exakt wie STEP 12
  - Vertragsliste (`app/contracts/page.tsx`): PageHeader (Treffer + Filtercount +
    stale), ZustÃ¤nde (keine Filtertreffer vs. leer), Suche/Debounce,
    Quick-Filter, erweiterte Filter, Sortierung/Seitenwechsel wie STEP 13
  - Detail (`app/contracts/[contract-id]/page.tsx`): nur Loading-/Error-UI
    vereinheitlicht; STEP-14-Provenance-/Quellen-Semantik unverÃ¤ndert
  - Import (`app/import/page.tsx`): Inline-Styles entfernt, Design-System,
    Keyboard-zugÃ¤ngliche Dropzone, Auswahlstatus, Fortschrittsanzeige,
    deterministisches Ergebnis (Importiert/Duplikat/Fehlgeschlagen) inkl.
    â€žZu den VertrÃ¤gen"-Link; nur Anzeigename, kein Pfad/Key
- **Einstellungen (neu) `app/settings/page.tsx`:** ehrlicher KI-Status Ã¼ber
  `GET /api/ai/status` (provider/available/model/model_available/message) â€“
  keine erfundenen Produktions-Suitability-ZustÃ¤nde; Diagnose-Button Ã¼ber
  `POST /api/ai/test`; Abschnitte â€žLokale KI & Runtime", â€žDiagnose",
  â€žUmgebung & Speicher", â€žSicherheit & Benutzerverwaltung" (zukÃ¼nftiges
  Admin-/RBAC-Target, KEINE breite Env-/Hardware-Exposition, kein STEP-16-RBAC).
- **Accessibility/UX-HÃ¤rtung:** Semantische Status-Pillen mit Text+Icon,
  deutliche Fokus-Indikatoren, Heading-Hierarchie, `aria-live` fÃ¼r
  Lade-/ErgebniszustÃ¤nde, formular-assoziierte Labels, Skip-Link, reduced-motion-
  freundlich; React-Aria-Entscheidung: NICHT benÃ¶tigt (alle interaktiven Muster
  nativ, keine Dialoge/Popover/Menus) â€“ dokumentiert.

GeÃ¤nderte Dateien:
- frontend/app/globals.css (Token-Foundation + Primitive-/Shell-/Import-/
  Settings-Styles)
- frontend/app/layout.tsx (Skip-Link, App-Shell, tabIndex-Ziel)
- frontend/components/ClientNav.tsx (Einstellungen aktiv, aria-current)
- frontend/app/page.tsx (Dashboard, Seite)
- frontend/app/contracts/page.tsx (Vertragsliste, Seite)
- frontend/app/import/page.tsx (Import, neu strukturiert)
- frontend/app/settings/page.tsx (NEU)
- frontend/components/ui/{PageHeader,SectionCard,InlineAlert,EmptyState,
  LoadingState,Button,StatusBadge,Field,DefinitionList}.tsx (NEW)
- frontend/lib/ai-types.ts (NEU), frontend/lib/api.ts (apiPost)
- frontend/test/{shell,settings,import}.test.tsx (NEU)

Tests/Ergebnis:
- Frontend: `npx vitest run` â†’ **43 passed** (28 STEP-12/13/14 + 15 neue
  Shell/Settings/Import-Tests inkl. jest-axe); `npx tsc --noEmit` grÃ¼n;
  `npx next lint --no-cache` â†’ No warnings/errors; `npm run build` â†’
  produktiver Next-Build kompiliert.
- Backend: NICHT verÃ¤ndert in STEP 15 (frontend-only) â†’ keine erneute volle
  Suite nÃ¶tig; Baseline-Bestand unangetastet (459 passed, Stand STEP 14).

Bekannte Probleme / Grenzen:
- Playwright/browserbasierte E2E nicht vorhanden; Entscheidung in
  `docs/STEP_15_CHECKPOINT.md` dokumentiert (Kosten/Nutzen; agency-testing
  + keyboard/manual bleibt empfohlen).
- Kein Voll-CSP-Durchbruch in STEP 15 (minimierte Header bleiben; volles CSP
  + Auth folgt STEP 16, laut next.config.js-Kommentar).
- Settings zeigen nur gemeldete ZustÃ¤nde (available/model_available/message);
  detaillierte Hardware-/Env-Info bleibt bewusst zurÃ¼ckhaltend bis Admin.

NÃ¤chster Schritt:
- Schritt 16 â€“ Benutzer/Login & Audit Minimalversion (+ Voll-CSP, RBAC/RLS,
  Duplikat-Verlinkung pro Org). Beginnt NICHT automatisch; erst auf Anweisung.

## Schritt 16 â€“ Benutzer/Login & Audit Minimalversion
Status: OFFEN

- lokaler Login
- Benutzername/Rolle
- Analyse erstellt von
- Vertrag geÃ¤ndert von
- Zeitpunkt protokollieren

## Schritt 17 â€“ Export & Backup
Status: OFFEN

- CSV/Excel Export
- lokale Datenbanksicherung
- Dokument-Backup
- Restore-Konzept

## Schritt 18 â€“ Release Candidate & Krankenhaus-Pilot
Status: OFFEN

- Security Review
- Datenschutz-Dokumentation
- Installationsanleitung
- Offline-Betrieb testen
- Performance testen
- Pilot-Demo mit echten VertrÃ¤gen
- Liste offener Punkte fÃ¼r Krankenhaus-Deployment

---

# Aktueller Fortschritt

Gesamtschritte: 18

Abgeschlossen: 15
In Arbeit: 0
Offen: 3

Fortschritt: 15 / 18 = 83,3 %

Aktuell abgeschlossen:
- Schritt 1 â€“ Projektdefinition & Architektur
- Schritt 2 â€“ Repository & OpenCode-Grundstruktur
- Schritt 3 â€“ Vertrags-Datenmodell definieren
- Schritt 4 â€“ Dokument-Import (PDF/DOCX)
- Schritt 5 â€“ Text-Extraktion (PDF/DOCX)
- Schritt 6 â€“ Local-AI-Anbindung (Ollama)
- Schritt 7 â€“ Strukturierte KI-Extraktion
- Schritt 8 â€“ Benchmark mit echten VertrÃ¤gen
- Schritt 9 â€“ Date & Cost Engine
- Schritt 10 â€“ Datenbank-Persistenz (PostgreSQL + SQLAlchemy + Alembic)
- Schritt 11 â€“ Warnsystem (Production-Grade Warning & Action-Readiness)
- Schritt 12 â€“ Dashboard (Production-Grade Procurement Dashboard)
- Schritt 13 â€“ Vertragsliste & Suche (Production-Grade Contract Portfolio / Search / Filter)
- Schritt 14 â€“ Vertragsdetailansicht (Production-Grade Contract Detail & Quellenanzeige / Document-Viewer)
- Schritt 15 â€“ BenutzeroberflÃ¤che & Design (Design System, Shell/UX, Einstellungen, WCAG 2.2 AA)

NÃ¤chster Schritt:
- Schritt 16 â€“ Benutzer/Login & Audit Minimalversion

---

# Wo haben wir angefangen?
Wir haben mit der Produktidee begonnen:
Lokale KI zur Analyse deutscher WartungsvertrÃ¤ge fÃ¼r KrankenhÃ¤user.

Danach wurde der Umfang bewusst reduziert:
kein groÃŸes ERP, sondern ein fokussiertes lokales Contract-Intelligence-System.

# Wo stehen wir jetzt?
Die Produktidee und Architektur sind definiert.
Projekt-Setup (Schritt 2), Vertragsdatenmodell (Schritt 3), Dokument-Import
(Schritt 4), Text-Extraktion (Schritt 5), Local-AI-Anbindung (Schritt 6),
die strukturierte KI-Extraktion (Schritt 7) und der Benchmark mit echten
VertrÃ¤gen (Schritt 8) sind abgeschlossen: sicherer PDF/DOCX-Import,
seitenbasierte Textextraktion, eine lokale Ollama-Anbindung mit
austauschbarer Provider-Abstraktion sowie eine strukturierte, lokale
Extraktion von Vertragsfakten (JSON-Schema, deutsche Prompts,
Quelle+Seite/Confidence, Anti-Halluzination, Multi-Chunk-Merging).
Backend: 96 Tests laufen; Frontend baut erfolgreich. Der Schritt-8-Benchmark
gegen 6 reale VertrÃ¤ge zeigt: 0 erfundene Werte (Anti-Halluzination hÃ¤lt),
aber nur ~12,5 % Feldgenauigkeit und 1/6 validierten Vertrag â€“ qwen3:8b (Q4)
mit reinem Prompt-Ansatz erreicht die geforderte ZuverlÃ¤ssigkeit noch nicht
(AnsÃ¤tze im STEP-9-Abschnitt von docs/AI_EVALUATION.md). Inzwischen ergÃ¤nzt:
DB-Persistenz (Schritt 10, PostgreSQL) und die Berechnungsengine (Schritt 9).

# Wo haben wir aufgehÃ¶rt?
Nach Abschluss von STEP 9 (deterministische Date & Cost Engine), STEP 10
(Datenbank-Persistenz: PostgreSQL 18.6 + SQLAlchemy 2.x + Alembic, Persistenz-
Services fÃ¼r Import/Verarbeitung/Extraktion/Berechnung/Contract), STEP 11
(Production-Grade Warning & Action-Readiness System: reine Deterministische
Warn-Engine + durable Warn-Persistenz warning_evaluation_run/contract_warning +
Current/risk-Projektion, 375 Tests grÃ¼n) sowie STEP 12 (Production-Grade
Procurement Dashboard: Backend-Read-Model over akzeptierte Runs + aktive
Warnungen + Contract-Projektion, GET /api/dashboard/overview, Frontend
â€žÃœbersicht"-Dashboard mit Handlungsbedarf/Fristen/Kosten/DatenqualitÃ¤t/
Daten-Frische, 11 Frontend-Tests + 24 Backend-Dashboard-Tests, 399 Backend-Suite
grÃ¼n). STEP 13 (Production-Grade Contract Portfolio / Search / Filter: PostgreSQL-
authoritative Vertragsliste/Suche/Filter mit FTS (generierter search_vector) +
pg_trgm-fuzzy + strukturierte Filter + deterministischer Ranking-Tiers + Facets/
Pagination, GET /api/contracts, Frontend â€žVertrÃ¤ge", Migration a3f9c1127305,
36 Backend-Search-Tests + 11 Frontend-Tests, 435 Backend-Suite grÃ¼n). STEP 14
(Production-Grade Contract Detail & Quellenanzeige / Document-Viewer: Storage-/
Provenance-Grenze Ã¼ber DocumentPersistenceService + kanonische storage_key-
Referenz + Kompensation, org-gebundenes Detail-Read-Model aus akzeptierten Runs,
sicherer Dokument-Bytes-Endpoint mit Range/MIME-Allowlist/Headers, Frontend
`/contracts/[contract-id]` mit Abschnitten + EvidencePane + lokalem pdf.js-
Viewer mit bbox-Overlay, 24 neue Backend-Tests + 6 Frontend-Tests, 459 Backend-
Suite grÃ¼n, 28 Frontend-Tests grÃ¼n).
Offen ab hier:
BenutzeroberflÃ¤che & Design (Schritt 15).

# Was machen wir als NÃ¤chstes?
1. Schritt 15 â€“ BenutzeroberflÃ¤che & Design
2. Schritt 16 â€“ Benutzer/Login & Audit Minimalversion
3. Schritt 17 â€“ Export & Backup

---

# Integrations-Reparatur (Produktions-Import-Pipeline) â€“ korrektive HÃ¤rtung
Hinweis: interne korrektive Arbeit an der ZusammenfÃ¼hrung der bereits
abgeschlossenen Schritte (Production-Pipeline: Import â†’ Persistenz/Version â†’
Text/OCR â†’ Deterministische KI-Extraktion â†’ Berechnung â†’ Warn-Bewertung â†’
akzeptierter Vertrag â†’ `/api/contracts` + Dashboard). **Kein neuer Hauptschritt â€“
Fortschritt bleibt 15/18 = 83,3 %.**

Datum: 02.09.2026

Umgesetzt:
- `backend/app/documents/processing.py` (1400 Zeilen): Einziger Produktions-
  Orchesterpfad `DocumentProcessingService.process`; explizite `organization_id`-
  Durchreichung; `_persist_document`/`_persist_pipeline`/`process` konsolidiert.
- `backend/app/api/routes/documents.py`: Import-Route lÃ¤uft Ã¼ber
  `DocumentProcessingService.process` in `run_in_threadpool`; `organization_slug`
  Pflicht-Query-Param; sichere Meldungen; `processed.error` â†’ `message`.
- `backend/app/documents/extraction/service.py`: `_extract_pdf`/`_extract_docx`
  wiederhergestellt; `extract()` delegiert an `extract_from_path`.
- `backend/app/contracts/detail/service.py`: `_sla_section`/`_sla_value_str`
  formatieren TimeValue-Snapshots deterministisch (behebt 500 im Detail-Endpoint).
- `backend/app/documents/schemas.py`: `ImportStatus` + `ImportFileResult` um
  `analysis_failed`/`analysis_status`/`requires_review`/`contract_id` erweitert.
- Frontend: `types.ts`/`api.ts`/`import/page.tsx`/`globals.css` â€“ Import-Flow inkl.
  Ergebnis-Link `/contracts/{contract_id}`.

Verifiziert (End-to-End):
- Import `vertrag_smoke.pdf` â†’ `imported` + `contract_id`; `analysis_status: success`.
- DB (org krankenhaus): contract (Siemens Healthineers, WM-2024-0001, active,
  medium), Extraction/Calculation accepted, 3 aktive contract_warnings.
- `GET /api/contracts/{id}` â†’ 200 mit formatierten SLA-Strings; `GET /api/contracts`
  â†’ 1 Track (facets requires_action=1/requires_review=1); `GET /api/dashboard/overview`
  â†’ active_contracts=1.

Tests: **444 passed, 0 failed** (Vollsuite). Korrekturen in
`tests/test_contract_extraction.py` (Test-Signatur/Status-Erwartungen an die
dokumentierte STEP-8B-Semantik), `tests/test_text_extraction.py` (entfernte,
veraltete `/extract`-Endpunkt-Tests), `tests/test_warning_persistence.py`
(org-/contract-scoped Queries), `tests/test_atomic_geometry.py` (Schema 1.3.0).
Frontend: `tsc --noEmit` und `eslint` grÃ¼n.

Bekannte Punkte:
- Alle `data/contracts`-Korpusdateien auÃŸer `vertrag_smoke.pdf` sind reine Scans
  (OCR-abhÃ¤ngig); OCR ist standardmÃ¤ÃŸig deaktiviert â†’ vollstÃ¤ndiger AI-Lauf ohne
  OCR nur fÃ¼r `vertrag_smoke.pdf` mÃ¶glich.
- Konfig. kann das Schema 1.3.0 weiterhin sperrig gegenÃ¼ber Ã¤lteren Persistenz-
  Erwartungen erscheinen; bewusst, kein RÃ¼ckschritt.

---

# PR-1 â€“ Real Contract Ingestion Reliability (korrektive HÃ¤rtung)

Hinweis: internes korrektives Vorhaben. Ziel: Die **5 realen Benchmark-VertrÃ¤ge**
(3 gescannte PDFs) zuverlÃ¤ssig durch die Produktions-Pipeline
(`DocumentProcessingService.process`) zu bringen, statt in opaken
â€žprocessing failed"-ZustÃ¤nden zu enden. Untersuchung zuerst, gezielte Fixes,
evidenzbasierte Verifikation gegen echte LÃ¤ufe und eigene Selbst-Sabotage.
**Kein neuer Hauptschritt â€“ Fortschritt bleibt 15/18 = 83,3 %.**

Datum: 02.09.2026

## Root-Cause-Analyse (vor Fixes: alle 5 Benchmark-VertrÃ¤ge schlugen fehl)

- **Root-Cause #1 (OCR-Lang-Code):** `Settings.ocr_lang="deu"` (Tesseract/ISO-639-3)
  wurde unverÃ¤ndert an `RapidOcrOptions(lang=["deu"])` durchgereicht â†’ `ValueError:
  ... does not support language 'deu'`. Da `ocr_enabled=True` (Standard), schlug
  **jeder** PDF-Import deterministisch fehl. Gegenprobe mit `["de","en"]` lief durch.
- **Root-Cause #2 (Verifier-Crash):** `_collect_sensitive_values` in
  `app/ai/groups/verifier.py` nutzte 5Ã— den buggy Inline-Ausdruck
  `x.evidence.source_text[:120] if x.evidence else None`. Pydantic-Modelle sind
  immer truthy â†’ `source_text=None` â†’ `TypeError: 'NoneType' object is not
  subscriptable`. ViorstoÃŸ gegen den Verifier-Kontrakt â€ždarf Pipeline nie abbrechen".
- **Persistenz-LÃ¼cke:** `ProcessingRun` hatte **keine** Fehlerspalte â†’ FehlgrÃ¼nde
  wurden nur geloggt und in der transienten API-Antwort, nie in der DB.
- **Stale-Run-Blockade:** Von Tool-Timeouts hinterlassene `running`-Runs
  short-circuiteten `process()` als â€žbereits in Verarbeitung" und blockierten
  Reprocessing (Crash-Recovery-Problem).

## Umgesetzte Fixes

- **OCR-Sprachcode-Normierung** (`app/documents/intelligence/docling_provider.py`):
  `_RAPIDOCR_LANG_MAP` + `_rapidocr_lang_code()` mappen `deuâ†’de, gerâ†’de, engâ†’en,
  fraâ†’fr, araâ†’arabic, ...`; Unbekanntes geht unverÃ¤ndert durch (kein stilles
  Verwerfen). Angewandt in `_get_converter` als `RapidOcrOptions(lang=[...])`.
- **Verifier-Fix** (`app/ai/groups/verifier.py`): alle 5 Inline-Nutzungen auf das
  vorhandene sichere Helper `_ev(section)` umgestellt.
- **Sichere Fehlerpersistenz:** `ProcessingRun` + `message`/`error` (`nullable
  Text`) via Alembic `20260902_7f2c9a1e4b80`; `create_processing_run`/
  `finish_processing_run` + `_finalize_run`/`_finish_run_in_session`/
  `_persist_failed_analysis` reichen sie durch; Exception-Handler persistiert
  `message=_SAFE_PROCESSING_FAILURE` und `error=_sanitized_error(str(exc))`.
- **HÃ¤rtung `_sanitized_error`** (`app/documents/processing.py`): von Tracebacks
  nur die letzte Fehlerzeile (Spalte 0) behalten â†’ Frame-/Quellzeilen (absolut UND
  relativ, inkl. Zeilennummern) werden verworfen; zusÃ¤tzlich Maskierung absoluter
  Windows-/POSIX-Pfade (`<path>`) und mutmaÃŸlicher Secrets (`AKIA...`,
  `password=`, `api_key`, `Authorization: Bearer <token>` â†’ `<secret>`);
  einzeilig, max. 500 Zeichen. `error` bleibt geschÃ¼tzter Diagnosezustand (nie von
  einer API gerendert), `message` ist das browser-sichere Feld.

## Dateien

- `backend/app/documents/intelligence/docling_provider.py` (OCR-Sprachcode-Fix)
- `backend/app/ai/groups/verifier.py` (Crash-Fix)
- `backend/app/documents/processing.py` (`_sanitized_error`, Fehler-Weiterleitung)
- `backend/app/database/models/processing.py`, `backend/app/database/services.py`
  (ProcessingRun `message`/`error`)
- `backend/alembic/versions/20260902_7f2c9a1e4b80_processing_run_error_message.py`
- `backend/tests/test_document_intelligence.py`, `backend/tests/test_ai_verifier_safety.py`
  (Regressionstests)

## Verifikation (evidenzbasiert, reale ProduktionslÃ¤ufe via `svc.process`)

| Benchmark | SeitengrÃ¶ÃŸe/Typ | Wandzeit | Status | Ergebnis |
|-----------|-----------------|----------|--------|----------|
| CCE (Cook) | 1 S., nativ | 17,4 s | imported | Manual Review, persisted, `/api/contracts` sichtbar |
| CT Revolution EVO | 6 S., Scan | 91,1 s | imported | Manual Review, GE Healthcare, 3 Evidenzen |
| BD Service Vertrag | 16 S., teilw. nativ | 276,9 s | imported | **expired / high risk** erkannt, 4 Evidenzen |
| AXIOM Q Biplane | 16 S., Scan | 210,2 s | imported | contract_no â€ž100494M1", Siemens, 4 Evidenzen |
| HOLMIUM (Arabisch) | 2 S., Scan | 43,4 s | imported | Manual Review, Cook Deutschland, 3 Evidenzen |

Alle 5 VertrÃ¤ge: `ProcessingRun.status=succeeded`, kanonisches Artifact persistiert,
Extraction `partial`/`validation=invalid`/`requires_review=True` mit **echten
GrÃ¼nden** (Vertragsdaten nicht eindeutig / keine verlÃ¤ssliche Jahreskostenangabe /
vertrag ausgelaufen), Evidenz-Objekte vorhanden, Contract verknÃ¼pft, Ã¼ber
`GET /api/contracts?organization_slug=krankenhaus` und
`GET /api/contracts/{id}` sichtbar (200). GegenÃ¼ber dem Ausgangszustand (alle 5
opak fehlgeschlagen) ist das die akzeptierte ZuverlÃ¤ssigkeits-HÃ¼rde: sauberer
Verarbeitungserfolg + nachvollziehbarer Manual-Review-Bedarf statt Fehlerzustand.

Sicherheits-Check `_sanitized_error` (eigene Sabotage, live verifiziert): Windows-
u. POSIX-Pfade â†’ `<path>`; voller Traceback â†’ nur letzte Zeile (`ValueError: boom`);
`password=`, `Bearer <JWT>`, `AKIA...` â†’ `<secret>`; leere Eingabe â†’ None; LÃ¤nge â‰¤ 500.

## Tests

`pytest -q` Vollsuite: **454 passed, 0 failed** (Baseline 445 + 9 neue
Regressionstests). Korrektur-spezifische Tests:
- `test_rapidocr_lang_code_maps_tesseract_to_rapidocr`
- `test_sanitized_error_strips_paths_and_newlines` / `_empty_is_none` /
  `_caps_length` / `_drops_traceback_frames` / `_redacts_secrets`
- `tests/test_ai_verifier_safety.py` (3 Tests: Verifier bricht Pipeline nicht ab,
  `_collect_sensitive_values` bei fehlender Evidenz sicher)

## Bekannte Punkte

- RapidOCR meldet bei reinen/gescannten Seiten gelegentlich â€žempty result"
  (OCR-Freitext-Seiten ohne erkannte Zeichen); die Pipeline lÃ¤uft dennoch sauber
  durch (kein Fehlerzustand). Kein Fixbedarf fÃ¼r diese PR, aber zu beobachten.
- Stale-`running`-Runs (z. B. nach Prozess-Abbruch) blockieren Reprocessing bis
  `document_processing_stale_minutes`; Crash-Recovery-Verbesserung optional spÃ¤ter.

## NÃ¤chster Schritt

Nicht vor anweisung: STEP 16 ist ausdrÃ¼cklich NICHT Teil dieser PR. Nach Abschluss
von PR-1 stoppen und auf weitere Anweisung warten.

---

# PR-2 â€“ Contract 360 + Evidence Viewer

Ziel: **Evidence-first-Arbeitsbereich** fÃ¼r einen aufgerufenen Vertrag. Jeder
**belegte** kritische Fakt ist klickbar und Ã¶ffnet die exakte Quellenstelle im
Original-PDF (Evidence-Interaktion Faktâ†’Quelle). Voraussetzung wÃ¶rtlich:
â€žNOT COMPLETE unless a user can click a real extracted contract fact and reach
the correct source location in the original PDF." Kein neuer Hauptschritt â€“
**Fortschritt bleibt 15/18 = 83,3 %.** STEP 16 ist NICHT Teil von PR-2.
Kein Commit.

Datum: 03.09.2026

## Diagnose (vor Fix: Quellen waren faktisch unbelegt)

Empirisch aus der echten DB fÃ¼r alle 5 PR-1-Benchmarks bestÃ¤tigt:
- **Echte Evidence-Bboxen liegen in PDF-Punkten** der Original-Seite (Werte > 1,
  z. B. AXIOM `termination.evidence` `x0=59.3 y0=531.7 x1=166.7 y1=543.7`; CCE
  `termination.evidence` `x0=87.7 y0=442.1 x1=512.1 y1=464.0`). Das alte
  `supports_exact_navigation` war nur bei normalisierten `[0,1]`-Bboxen wahr â†’
  **alle echten Evidenzen lieferten `False`** â†’ Hervorhebung erschien auf echten
  Daten nie.
- `SourceBox` dokumentiert explizit: PDF-Punkte der Original-Seite, Ursprung oben
  links, y nach unten, 72/inch (`app/documents/extraction/schemas.py`). Kurzschluss
  `bbox&&page â†’ supports_exact_navigation` (PR-1) war semantisch falsch, weil
  Koordinatenraum nie kommuniziert wurde.
- `field_ref` real **gruppen-wertig** (`identity.evidence`,
  `termination.evidence`, `payment.evidence`, `sla.evidence`) â€“ Faktâ†”Evidence-Zuordnung
  muss gruppen-basiert laufen.

## Umgesetzte Fixes (Backend)

- `app/contracts/detail/models.py`: `EvidenceRef` erhÃ¤lt
  `bbox_space: Literal["pdf_points","normalized"] = "pdf_points"`; Modul-/Klassen-
  Docstrings auf PR-2-Semantik (bbox+page â†’ `supports_exact_navigation`;
  `precision` â€žcoarse"/â€žnone" ehrlich).
- `app/contracts/detail/service.py` `_evidence_ref`:
  `supports_exact_navigation = bool(bbox_obj is not None and e.page is not None)`
  (echter Nachweis, kein normalisierungs-Gate mehr);
  `bbox_space="pdf_points"`, `precision="coarse" if bbox_obj else "none"`,
  `geometry_normalized` rein informativ, Bbox unverÃ¤ndert als PDF-Punkte.
- Kein zweiter Evidence-/Dokument-Pipeline: DocumentPersistenceService,
  kanonische Artifacts, Provenienz/Geometrie, Evidence-Modelle, PDF.js und
  Contract-Detail-API werden wiederverwendet.

## Umgesetzte Fixes (Frontend)

- `lib/source-geometry.ts` (neu): reine Funktion `resolveEvidenceRect(bbox,
  bbox_space, scale, dims)` â€“ `pdf_points` â†’ `pt*scale` (scale = BASE_SCALE*zoom
  des Viewers), `normalized` â†’ `[0,1]*dims`; invalide/invertierte Bboxes â†’ `null`
  (keine erfundene Position).
- `PdfViewer.tsx`: Overlay nutzt `resolveEvidenceRect`, zoom-nachfÃ¼hrend;
  Hervorhebung nur wenn `supports_exact_navigation && bbox`; Seiten-Mismatch â†’
  keine Zeichnung; Nav-Info ehrlich (â€žSeitenbereich"/â€žohne exakte Position").
- `ContractDetail.tsx` â†’ **Contract 360**: Kopf (Lieferant, Nr., Status/Risiko/
  Review-Badges), Kennzahlen-Strip, Sektionen Laufzeit & KÃ¼ndigung / Finanzielle
  Konditionen / Leistungsumfang / SLA / GerÃ¤te / Warnungen & Handlungsbedarf /
  IdentitÃ¤t, Quell-/Evidence-Panel, PDF-Viewer. **Evidence-first**: jeder belegte
  Fakt wird klickbarer Button (`fact-value-btn`), der den Viewer zur Quelle
  navigiert (bzw. die Quelle im Panel markiert, wenn `page==null` â€“ **kein
  Seiten-Sprung, keine erfundene Hervorhebung**). RÃ¼ckkehr zum Fakt ohne
  Kontextverlust (keine Navigation weg vom Workspace).
- `EvidencePane.tsx`: navigiert Ã¼ber `EvidenceRef` (trÃ¤gt `bbox_space`),
  ehrliche PrÃ¤zisions-Labels (â€žPositionsbestimmt"/â€žSeite, ohne Position"/
  â€žOhne Positionsangabe"), Gruppen-Sektions-Label, Review-Hinweise.
- `lib/contract-detail-types.ts`: `bbox_space` in `EvidenceRef` und
  `SourceNavigationTarget`; `EVIDENCE_GROUP_TO_SECTION` + `evidenceGroup*`-
  Helfer.
- `app/globals.css`: Contract-360-Stile (`kpi-strip`, `fact-*`, `review-badge`,
  `notice.warning`, `detail-tags`, scoped Margins/Sticky).

## Dateien

- Backend: `app/contracts/detail/models.py`, `app/contracts/detail/service.py`
- Frontend: `components/contracts/detail/ContractDetail.tsx`,
  `components/contracts/detail/EvidencePane.tsx`,
  `components/contracts/detail/PdfViewer.tsx`, `lib/source-geometry.ts` (neu),
  `lib/contract-detail-types.ts`, `app/globals.css`
- Tests: `backend/tests/test_contract_detail.py`,
  `frontend/test/contracts-detail.test.tsx`, `frontend/test/source-geometry.test.ts` (neu)

## Verifikation (evidenzbasiert, reale Benchmarks)

`pr2_verify_detail` (Service Ã¼ber echte DB, aktive akzeptierte VertrÃ¤ge) â€“ alle 5
PR-1-Benchmarks liefern jetzt `supports_exact_navigation=True`, `bbox_space="pdf_points"`:

| Benchmark | evidence | navigable | Quellen (Seite) |
|-----------|----------|-----------|-----------------|
| AXIOM (Siemens) | 4 | 2 | termination p7, sla p5 |
| CCE (Cook) | 2 | 2 | termination p1, sla p1 |
| CT (GE) | 3 | 2 | termination p3, payment p3 |
| BD (BD Tech, expired/high) | 4 | 4 | identity p2, termination p2, payment p15, sla p3 |
| HOLMIUM (Arabisch) | 3 | 3 | termination/payment/sla p1 |

Nicht-navigierbare Evidenzen (page=None + requires_review) bleiben bewusst
nicht-navigierbar (kein Fake-Highlight).

**Quellen-/Byte-Abnahme** (`pr2_acceptance` gegen gespeicherte PDFs via
`resolve_bytes_for_version`, PyMuPDF): fÃ¼r alle 5 VertrÃ¤ge werden die PDF-Bytes
org-/vertragsscope-aufgelÃ¶st, Seiten in-bounds, und die Hervorhebungsregion
Ã¼berlappt **reale Inhalte**:
- Native-VertrÃ¤ge (CCE, Siemens Healthineers): Region enthÃ¤lt echten Text (`TEXT`).
- Scans (AXIOM, GE, HOLMIUM, BD): Seite hat keinen Text-Layer; die Region
  Ã¼berlappt das gerenderte Scan-Bild (`bbox overlaps placed image`) â†’ ehrliche
  OCR-Fakt-Region auf echter Quelle, kein Leerraum.

**Performance (lokal):** Detail-Aufbau 4â€“35 ms/Vertrag, Quellen-Bytes 2â€“21 ms,
je ein Request (Detail + Viewer-Content), keine redundanten NeuladevorgÃ¤nge.

**Cross-Org:** bereits abgedeckt durch `test_detail_missing_and_cross_org_404`
(Detail â†’ generische 404) und `test_content_cross_org_fails` (Quell-Bytes â†’ 404).
Evidence wird nur innerhalb der org-scoped Detailantwort geliefert; es gibt keinen
eigenstÃ¤ndigen Evidence-Endpoint.

## Tests

- Backend: **456 passed** (PR-1: 454 + 2 netto neue Detail-Evidence-Tests:
  `test_detail_pdf_points_bbox_is_exactly_navigable`,
  `test_detail_bbox_without_page_is_not_exact`; `â€¦_falls_back_to_none_precision`
  blieb bestehen).
- Frontend: `test/contracts-detail.test.tsx` (9 Tests, inkl. PR-2: Fakt-Button
  Ã¶ffnet Quelle; Fakt ohne Seitenangabe springt Viewer NICHT; RÃ¼ckkehr ohne
  Kontextverlust) + `test/source-geometry.test.ts` (4 Tests: PDF-Punktâ†”Pixel exakt,
  Zoom-Tracking, `[0,1]` nur bei normalized, invalide Bbox â†’ null).
- Frontend `tsc --noEmit`, `next lint --file â€¦`, `next build` : grÃ¼n.
- Volle Frontend-Suite: 49/50 grÃ¼n â€“ einziger Fehlschlag ist **vorbestehend**
  (STEP 15 `test/import.test.tsx`: erwartet â€ž1 von 2 Dateien erfolgreich importiert."
  in `app/import/page.tsx`, dort nicht gerendert; auÃŸerhalb PR-2-Scope, dokumentiert,
  nicht angefasst).

## Bekannte Punkte

- Scans haben keinen Text-Layer; Positionsbestimmung dort bedeutet
  Seitenbereich auf dem Scan-Bild (NÃ¤herungscharakter ehrlich als â€žSeitenbereich"
  ausgewiesen), nicht pixelgenaue Textzeile des Scans.
- Rotations-/Crop-SonderfÃ¤lle (PDF-Rotation â‰  0) werden im Viewer nicht
  umgerechnet (Benchmarks haben Rotation 0); als Debt dokumentiert.
- Vorbestehender STEP-15-Import-Testfehler (oben) unberÃ¼hrt gelassen.

## NÃ¤chster Schritt

Nicht vor anweisung: STEP 16 ist ausdrÃ¼cklich NICHT Teil von PR-2. Nach Abschluss
von PR-2 stoppen und auf weitere Anweisung warten.

---

# PR-3 â€“ Financial + Deadline Intelligence (Berechnungsgrundlage)

Ziel: Die in STEP 9/11 bereits vorhandenen, deterministischen Fakten (Ende,
KÃ¼ndigungsfrist, Kostenaggregation, Warnstufen) in eine **erklÃ¤rbare, nachvollziehbare
Financial- & Deadline-Intelligence** Ã¼berfÃ¼hren â€“ ohne einen zweiten
Berechnungs-/Warn-Engine. Reuse der STEP-9-Engine (calculate) und der STEP-11-
Warn-Engine; Contract 360 zeigt Finanz-/Fristen-Snapshots mit â€žBerechnungsgrundlage"
und Click-to-Source. Verifikation gegen alle 5 PR-1-Benchmarks. **Fortschritt bleibt
15/18 = 83,3 %.** STEP 16 ist NICHT Teil von PR-3. Kein Commit.

Datum: 03.09.2026

## Architektur-Beweis (keine duplizierte Logik)

Produktions-Pipeline ist EIN Pfad: `documents/processing.py:519` â†’
`calculate_contract` â†’ persistiert als `CalculationRun.result_snapshot`
(`ContractCalculationResult` JSON); `contract.accepted_calculation_run_id` zeigt
darauf. Alle Consumer revalidieren denselben Snapshot (`model_validate`):
Detail (`detail/service.py`), Dashboard (`dashboard/service.py`), Liste
(`search/service.py`, `_extract_annual`). Warnungen persistiert als
`ContractWarning` (kein Recompute). **Kein duplicated money/date code in Consumers**
â†’ Anforderung D bereits architektonisch erfÃ¼llt (kein Codewechsel nÃ¶tig).
Erweiterte optionale Felder am `ContractCalculationResult` sind mit alten
DB-Snapshots rÃ¼ckwÃ¤rtskompatibel (Defaults in `model_validate`).

## B. Financial intelligence (Backend)

- `app/models/contract.py` `Costs` erweitert: `quarterly_cost`,
  `semi_annual_cost`, `setup_installation_cost`, `tax_basis: Optional[str]`
  (nur `net`|`gross`), `tax_rate_percent: Optional[float]` (0â€“100).
- `app/contracts/calculation/costs.py` neu strukturiert:
  - `_collect_recurring_sources`: primÃ¤re wiederkehrende Quellen
    (monthly/quarterly/semi_annual/annual + defensiv weekly via getattr).
  - Ein-Quellen-Annualisierung Ã¼ber zentralen `scaling_factor` (kein hartes `x12`
    an getrennten Stellen); `round_currency` fÃ¼r monthly = annual/12.
  - Mehr-Quellen-Korrobation Ã¼ber `_coherence` (Toleranz 0,005) â†’ `CALCULATED`.
  - `maintenance_fee` bleibt **eigene Charge**, wird NIE in den primÃ¤ren
    Korroborationssatz gemischt; annualisiert NUR als einzige wiederkehrende
    Quelle UND nur bei annualisierbarer Periode; ohne Periode â†’ `NOT_CALCULABLE`
    (Review). Verschiedene `monthly_cost`/`maintenance_fee`-Werte
    **konfliktieren nicht** (getrennte Chargen).
  - `tax_basis` streng aus Extraktion (`net`/`gross`), Unbekanntes nie erfunden;
    `tax_rate_percent` nur bei expliziter Angabe.
  - Pro-Quelle `category_totals`, WÃ¤hrungs-Konflikterkennung.
- `app/contracts/calculation/models.py`: `CalculateContractCosts.tax_rate_percent`.
- `app/documents/processing.py`: `CALC_VERSION = "step9-1.1"`.
- `app/ai/groups/schema.py` `COSTS_PAYMENT_PROMPT`: Feldgruppen-Guidance fÃ¼r
  quarterly/semi_annual/setup/tax_basis (`net`/`gross` nur wenn explizit; keine
  19 %-Annahme) ergÃ¤nzt.

## A. Deadline-/KÃ¼ndigungs-Intelligence (Backend-DTO)

- `app/contracts/detail/models.py`: `CalcBasis` (explanation + inputs),
  `RenewalBoundaryDto`, `CostCategoryDto`; `ContractDatesSection` erweitert um
  `calculated_end_basis`, `latest_cancellation_basis`, `next_renewal_basis`,
  `days_until_end`, `days_until_latest_cancellation`, `renewal_boundaries`;
  `ContractCostsSection` um `annual_recurring_basis`, `source_period`,
  `tax_rate_percent`, `category_totals`, `notes`.
- `app/contracts/detail/service.py`: `_dates_section`/`_costs_section` mappen
  Basis/Tage/Grenzen/Kategorien aus dem revalidierten Snapshot (autoritativ).

## C. Contract 360 Frontend

- `lib/contract-detail-types.ts` + `components/contracts/detail/ContractDetail.tsx`:
  Laufzeit-Karte mit Restlaufzeit-/Fristablauf-`DaysBadge`, VerlÃ¤ngerungsperioden,
  **â€žBerechnungsgrundlage"**; Finanzen-Karte mit Bezugsperiode (`sourcePeriodLabel`
  normalisiert alte Feld-Keys und neue Periodenwerte), Steuerbasis (+%),
  WÃ¤hrungskonflikt, Positionen (`category_totals`), notes. Defensive Zugriffe bei
  fehlenden neuen Feldern (Ã¤ltere Fixtures). Bereits vorhandene Click-to-Source
  (PR-2) bleibt unverÃ¤ndert.
- `app/globals.css`: neue Stile (`fact-basis-*`, `detail-basis`, `days-badge`
  +`-past`/`-today`, `renewal-boundaries/*`, `cost-categories/*`, `cost-notes`).

## D. Konsistenz / Verifikation (reale Benchmarks)

`bench_all.py` (as-of 2026-09-02) Ã¼ber die echte DB â€“ alle 5 korrekt/honest:

| Benchmark | Status | Annual | Grundlage |
|-----------|--------|--------|-----------|
| CCE | unknown (ereignisbasiert) | NOT_CALCULABLE | keine |
| CT | unknown (ereignisbasiert) | NOT_CALCULABLE | keine |
| BD (expired/high) | **expired** 2026-01-31 | NOT_CALCULABLE | Wartungsp. ohne Periode |
| AXIOM | unknown | **71000.04** CALCULATED | monatlich 5916.67 |
| HOLMIUM | unknown | NOT_CALCULABLE | keine |

`detail_verify.py` (Detail-Service Ã¼ber echte DB) bestÃ¤tigt â€žBerechnungsgrundlage"
End-to-End: BD `calculated_end_basis`+`latest_cancellation_basis` belegt,
`days_until_end=-214` (ablaufend); AXIOM `annual_recurring_basis` belegt,
`category_totals` gefÃ¼llt. Persistierte Snapshots sind PR-2-`step9-1.0`; die neuen
Basis-Felder werden aus vorhandenen `explanation`/`inputs` der Date-/Cost-Ergebnisse
belegt (kein Re-Import/Re-OCR nÃ¶tig) und fÃ¼r neu importierte VertrÃ¤ge via
`CALC_VERSION=step9-1.1` vollstÃ¤ndig.

## Tests

- Backend: `test_calculation_engine.py` 82/82 (72 + 10 neue PR-3-Finanz-Tests:
  quarterly/semi_annual via Costs, maintenance_fee-Perioden-Sole-Source
  annualisiert, mf ohne Periode NOT_CALCULABLE, mf nicht vermischt/konfliktfrei,
  tax_basis net/gross/unknown, setup-Kategorie, monthly-Rounding 8.33);
  `test_contract_detail.py` 17/17 (2 neue PR-3-DTO-Tests: Basis & Deadlines,
  Renewal-Boundaries-exposed). **Vollsuite Backend: 468 passed.**
- Frontend: `test/contracts-detail.test.tsx` 9/9; `tsc --noEmit` exit 0,
  `next lint` sauber, `next build` grÃ¼n.

## Bekannte Punkte

- Persistierte Snapshots der 5 Benchmarks sind `step9-1.0`; neue Finanz-Felder
  (quarterly/semi_annual/setup/tax) werden erst bei Neu-Import (step9-1.1) befÃ¼llt â€“
  Basis-/Deadline-Anzeige funktioniert jedoch bereits aus bestehenden Snapshots.
- `source_period` in alten Snapshots ist der Feld-Key (z. B. `monthly_cost`);
  die UI normalisiert ihn nach deutscher Bezeichnung (Alte+neue Werte abgedeckt).
- Vorbestehender STEP-15-Import-Testfehler (Frontend) unberÃ¼hrt gelassen.

## NÃ¤chster Schritt

STEP 16 ist ausdrÃ¼cklich NICHT Teil von PR-3. Nach Abschluss von PR-3 stoppen und
auf weitere Anweisung warten. Kein Commit.

---

# PR-4 â€“ Equipment & Work Queue (Production-Grade Equipment Intelligence + Operational Work Queue)

Ziel: Kanonische GerÃ¤te-IdentitÃ¤t (Equipment Master), vertragsÃ¼bergreifende
Equipmentâ†”Contract-Beziehungen (n:m), deterministische IdentitÃ¤tsbewertung
(exact/partial/generic/ambiguous), deterministische Arbeitslisten-Ableitung
(Work Items aus Warnungen + Equipment-Review-Flags), idempotente
Reconciliation, Equipment-/Arbeitslisten-APIs, Frontend Equipment-Liste/
Detail, Arbeitslisten-Frontend, Contract 360 Equipment-/WorkItem-Integration.
**Fortschritt bleibt 15/18 = 83,3 %.** STEP 16 ist NICHT Teil von PR-4.
Kein Commit.

Datum: 04.09.2026

## Architektur-Prinzip (PR-4-konsistent mit STEP 9/11)

- KI extrahiert Fakten (Felder: device_name, serial_number, manufacturer â€¦).
- **Code leitet ab**: identification_quality, relationship_quality,
  requires_review, review_reasons, canonical Equipment Master-Zuordnung.
- **Code leitet ab**: Work Items aus STEP-11-Warnungen + Equipment-Review-Flags.
  KEIN zweiter Warn-Engine.
- Deterministische Fingerprints (logical_fingerprint) fÃ¼r Idempotenz:
  ContractEquipment Ã¼ber Kombination der IdentitÃ¤tsfelder, WorkItems Ã¼ber
  Quell-Warn-Fingerprint oder Equipment-Fingerprint.
- Lebenszyklus getrennt: Deterministisches `active` (objektiv) vs. menschliches
  `status` (open/acknowledged/resolved) â€“ paralleles Muster zu STEP 11.

## Backend-Implementierung

### Canonical Equipment Master + ContractEquipment n:m

- `app/database/models/equipment.py`: ORM `Equipment` â€“ kanonische,
  org-gebundene GerÃ¤te-IdentitÃ¤t (device_name, manufacturer, model,
  serial_number, inventory_number, equipment_type, equipment_category,
  location, department, identification_quality). Serial-/Inventarnummern
  sind bewusst KEIN Unique (Duplikate = reale FÃ¤lle, geprÃ¼ft statt abgelehnt);
  Org-Scoping verhindert Cross-Org-Kollision.
- `app/database/models/contract.py`: `contract_equipment` um `equipment_id`
  (FK â†’ Equipment, SET NULL on delete), `logical_fingerprint` (String 64,
  dedupliziert), `identification_quality`, `relationship_quality`,
  `requires_review`, `review_reasons` (JSONB), `evidence_field_ref` erweitert.
- `app/database/services.py`: `resolve_equipment_master()` â€“ deterministische
  Master-Zuordnung: serial_number â†’ erstes match innerhalb der Org; inventory_number
  Fallback; keine Erfindung. `add_equipment()` â€“ idempotent, setzt
  `identification_quality` Ã¼ber `identity.identification_quality()`.

### Deterministische IdentitÃ¤tsbewertung

- `app/equipment/identity.py` (reine Funktionen, keine DB):
  - `identification_quality()` â†’ EXACT (Serien-/Inventarnummer), PARTIAL
    (Name/Modell/Hersteller), GENERIC (nur Kategorie), UNKNOWN (nichts).
  - `relationship_quality()` â†’ EXACT (eindeutige Kennung + Beleg), PARTIAL
    (eindeutige Kennung ohne Beleg oder partielle IdentitÃ¤t), GENERIC,
    AMBIGUOUS.
  - `requires_manual_review()` â†’ partiel/generic/ambiguous = Review.
  - `identity_fingerprint()` â†’ stabile SchlÃ¼ssel fÃ¼r Master-Zuordnung.

### Deterministische Arbeitslisten-Ableitung

- `app/work_queue/derive.py` (reine Funktionen, keine DB, kein `date.today()`):
  - `derive_from_warning(warning)` â†’ WorkItem aus STEP-11-`ContractWarning`:
    12 Warn-Typen â†’ 10 WorkItem-Typen (contract_expiry, contract_expired,
    cancellation_deadline, automatic_renewal, manual_review, missing_cost,
    sla_issue), nur bei `requires_action` oder `requires_review`.
  - `derive_from_equipment(row)` â†’ WorkItem aus `contract_equipment`
    mit `requires_review`: EQUIPMENT_COVERAGE_REVIEW (partial/generic) oder
    EQUIPMENT_RELATIONSHIP_AMBIGUOUS (ambiguous).
  - `compute_fingerprint()` â†’ stabiler SHA-256-Fingerprint fÃ¼r Idempotenz.
  - `derive_work_items()` â†’ vollstÃ¤ndige Work-Item-Liste eines Vertrags.

### Work-Item-Reconciliation

- `app/work_queue/service.py`:
  - `reconcile_work_items()` â€“ idempotenter Upsert per logical_fingerprint:
    neu â†’ INSERT, vorhanden â†’ UPDATE (Felder/Fingerprint), nicht mehr
    abgeleitet â†’ `active=False` (kein LÃ¶schen, Zeile/Historie erhalten).
    Quelle wieder aktiv â†’ gleicher Fingerprint reaktiviert.
  - `set_work_item_status()` â€“ menschlicher Lebenszyklus (open/acknowledged/
    resolved); resolved â†’ `active=False`.
  - `list_work_items()` / `list_work_items_dto()` / `get_work_item_dto()` â€“
    READ-Services mit Contract-Enrichment.

### Equipment-Lese-Services

- `app/equipment/service.py`:
  - `list_equipment()` â€“ kanonische GerÃ¤te einer Org mit konfigurierbarem
    Suchfilter (device_name, model, manufacturer, serial/inventory) und
    verknÃ¼pfter Vertrags-Anzahl via korrelierter Subquery (1 SQL).
  - `get_equipment_detail()` â€“ ein GerÃ¤t mit allen verknÃ¼pften VertrÃ¤gen
    (n:m, Ã¼ber ContractEquipment + Contract Join, 2 SQL).

### Equipment-/Arbeitslisten-APIs

- `app/api/routes/equipment.py`:
  - `GET /api/equipment?organization_slug&q&limit` â†’ `list[EquipmentSummary]`
  - `GET /api/equipment/{equipment_id}?organization_slug` â†’ `EquipmentDetail`
- `app/api/routes/work_queue.py`:
  - `GET /api/work-queue?organization_slug&active&status&severity&item_type&limit`
    â†’ `WorkItemList` (Allowlist-Validierung fÃ¼r Filter, 422 bei
    ungÃ¼ltigen Werten)
  - `PATCH /api/work-queue/{work_item_id}?organization_slug`
    â†’ `WorkItemStatusUpdate` â†’ `WorkItemSummary` (Commit bei Erfolg,
    Rollback bei Fehler)

### Contract 360 Equipment-/WorkItem-Integration

- `app/contracts/detail/service.py`: Equipment-Sektion in Contract Detail
  (equipment items mit identification_quality, relationship_quality,
  requires_review; Work Items eines Vertrags als eigene Sektion).
- `app/contracts/detail/models.py`: `ContractEquipmentItem` (PR-4 erweitert)
  + `WorkItemDto` fÃ¼r die Detailansicht.

### Enums (in `app/models/enums.py`)

- `IdentificationQuality`: EXACT / PARTIAL / GENERIC / UNKNOWN
- `RelationshipQuality`: EXACT / PARTIAL / GENERIC / AMBIGUOUS
- `WorkItemType`: CANCELLATION_DEADLINE / CONTRACT_EXPIRY / CONTRACT_EXPIRED /
  AUTOMATIC_RENEWAL / MANUAL_REVIEW / MISSING_COST /
  EQUIPMENT_COVERAGE_REVIEW / EQUIPMENT_RELATIONSHIP_AMBIGUOUS / SLA_ISSUE
- `WorkItemStatus`: OPEN / ACKNOWLEDGED / RESOLVED

### Alembic-Migrationen

- `20260903_c91e4f02a3b7_pr4_equipment_master_work_item.py`: `equipment`
  (Tabelle), `work_item` (Tabelle mit Constraints/Indizes), Erweiterung
  `contract_equipment` um `equipment_id`/`logical_fingerprint`/
  `identification_quality`/`relationship_quality`/`requires_review`/
  `review_reasons`/`evidence_field_ref`.
- `20260903_d2b3a5c0f4e1_add_contract_equipment_logical_finger.py`: index
  fÃ¼r `logical_fingerprint` auf `contract_equipment`.
- Head: **d2b3a5c0f4e1** (verifiziert).

## Frontend-Implementierung

### Equipment-Liste + Detail

- `app/equipment/page.tsx`: vollstÃ¤ndige Equipment-Liste (GET
  `/api/equipment`), search-Filter (debounced), Lade-/Fehler/leer-ZustÃ¤nde,
  Link zu Detail (`/equipment/[id]`).
- `app/equipment/[equipment-id]/page.tsx`: Equipment-Detail mit Vertrags-
  Links (n:m), identification_quality-Labels.
- `lib/pr4-types.ts`: TypeScript-Typen `EquipmentSummary`, `EquipmentDetail`,
  `EquipmentContractLink`, `WorkItemSummary`, `WorkItemList`,
  `identificationQualityLabel`, `relationshipQualityLabel`,
  `severityLabel`, `workItemStatusLabel`, `workItemTypeLabel`.

### Arbeitslisten-Frontend

- `app/work-queue/page.tsx`: vollstÃ¤ndige Arbeitsliste (GET `/api/work-queue`),
  Lade-/Fehler/leer-ZustÃ¤nde, Status-Transitionen (PATCH
  `/api/work-queue/{id}`) fÃ¼r acknowledged/resolved, BestÃ¤tigungs-Feedback,
  Severity-FÃ¤rbung (critical/high = critical, medium = warning), Link zum
  zugehÃ¶rigen Vertrag.

### Navigation

- `components/ClientNav.tsx`: â€žArbeitsliste" (/work-queue) und â€žGerÃ¤te"
  (/equipment) als neue Navigationspunkte; beide `available: true`.

### Contract 360 Frontend

- `components/contracts/detail/ContractDetail.tsx`: Equipment-Sektion
  (GerÃ¤teliste mit identification_quality-Labels, requires_review-Badge)
  + Work-Items-Sektion (aktive Arbeitselemente des Vertrags, Link zur
  Arbeitsliste).

### Test-Dateien

- `frontend/test/equipment.test.tsx` (Equipment-Liste/Detail)
- `frontend/test/work-queue.test.tsx` (Arbeitsliste inkl. Status-Transition)

## Verifikation (evidenzbasiert, reale Benchmarks â€“ 5 Benchmark-VertrÃ¤ge)

### Benchmark-Ergebnisse (krankenhaus-Organisation)

| Metrik | Wert |
|--------|------|
| contract_equipment (gesamt) | 17 |
| equipment masters (gesamt) | 17 |
| work_items (gesamt) | 25 |
| equipment duplicate serial masters | 0 |
| work-item duplicate fingerprints | 0 |

### EinzelvertrÃ¤ge (alle 5 PR-1-Benchmarks)

| Vertrag | equipment | work_items | Besonderheit |
|---------|-----------|------------|--------------|
| CCE | 1 | 1 | Manual Review, Cook |
| CT Revolution EVO | 3 | 3 | GE Healthcare, 3 Evidenzen |
| BD | 7 | 9 | expired/high, 3 Legacy-Zeilen (PR-1 artifact) |
| AXIOM | 4 | 8 | Siemens, 71000.04 CALCULATED |
| HOLMIUM | 2 | 4 | Cook, Arabisch |

### Hinweis zu BD Legacy-Equipment

BD hat 3 Legacy-Zeilen (pre-PR-4) mit leerer IdentitÃ¤t, die den gleichen
`logical_fingerprint` durante der deterministischen Backfill-Runde erhalten
haben. Dies ist ein LEGACY-BACKFILL-ARTIFAKT, kein aktueller PR-4-Pipeline-
Defekt. Die Betreffenden werden nicht manipuliert.

## Idempotenz

- `reconcile_work_items()` ist vollstÃ¤ndig idempotent: gleicher Aufruf mit
  denselben Eingaben erzeugt keine Duplikate; bestehende Zeilen werden
  aktualisiert, nicht mehr abgeleitete werden `active=False` gesetzt.
- `resolve_equipment_master()` ist idempotent: gleiche Eingabe â†’ gleiches
  Ergebnis.
- Fingerprint-Dedup: Equipment-Logical-Fingerprint und Work-Item-Fingerprint
  sind UniqueConstraints (org + contract + fingerprint); Re-Import erzeugt
  keine Duplikate.

## Organisation-Isolation (bereits verifiziert)

- Fremde Equipment-Liste â†’ leer.
- Fremdes Equipment-Detail â†’ denied/not found.
- Fremde Arbeitsliste â†’ leer.
- Cross-Org PATCH â†’ denied.
- Same-Org PATCH â†’ positiv (Kontrolltest).

## Performance (bereits verifiziert)

- Equipment List: 1 SQL-Query, 6.6 ms.
- Equipment Detail: 2 SQL-Queries, 8.4 ms.
- Work Queue List: 2 SQL-Queries, 7.9 ms.
- Kein N+1 oder redundanter Query.

## Tests

### Backend

- `tests/test_pr4_equipment_work_item.py` (fokussierte PR-4-Tests):
  IdentitÃ¤ts-Ableitung (identification_quality EXACT/PARTIAL/GENERIC/UNKNOWN),
  relationship_quality, requires_manual_review, kanonische Master-Zuordnung
  (1 GerÃ¤t â†” n VertrÃ¤ge, n GerÃ¤te â†” 1 Vertrag), Duplikat-Handling,
  Beziehungs-Dedup, deterministische Arbeitslisten-Ableitung (warnungâ†’item,
  equipmentâ†’item, 12 Warn-Typen), Reconcile-Idempotenz (zweimal gleiche
  Eingabe â†’ keine Duplikate), staleâ†’inactive, warnâ†’inactive bei Resolution,
  Lebenszyklus (openâ†’acknowledgedâ†’resolved), Org-Isolation (fremde Org
  sieht nichts, Cross-Org-PATCH abgelehnt), API-Routen (GET equipment,
  GET equipment/{id}, GET work-queue, PATCH work-queue/{id}), Re-Import
  ohne Duplikate.

### Frontend

- `frontend/test/equipment.test.tsx`: Equipment-Liste (Laden, Fehler, leer,
  Detail-Links), Equipment-Detail (Laden, Fehler, Vertrags-Links).
- `frontend/test/work-queue.test.tsx`: Arbeitsliste (Laden, Fehler, leer,
  Status-Transition acknowledged/resolved, Fehlerbehandlung, Severity-FÃ¤rbung,
  Contract-Links).
- `npx tsc --noEmit`: grÃ¼n.
- `npx next lint --no-cache`: No warnings/errors.
- `npm run build`: produktiver Next-Build kompiliert.

## Bekannte Punkte / Debt

- **Test Data Debt**: Isolierte `pr4-*`-Test-Organisationen mit SN-API/CT-API-
  Fixture-Daten. NICHT in der krankenhaus-Benchmark-Organisation. Keine
  LÃ¶schung ohne sichere unabhÃ¤ngige BestÃ¤tigung; als Cleanup-Debt dokumentiert.
- **BD Legacy-Equipment**: 3 pre-PR-4-Zeilen mit leerer IdentitÃ¤t, gleicher
  Fingerprint wÃ¤hrend Backfill. Artefakt, kein Pipeline-Defekt (s. o.).
- **DOCX-Quellen**: ehrlich als â€žnicht als PDF-Vorschau" ausgewiesen (PR-2-
  Bekanntes, nicht PR-4-spezifisch).
- **Kein Voll-CSP**: minimierte Header bleiben; Auth/volles CSP = STEP 16.

## NÃ¤chster Schritt

STEP 16 ist ausdrÃ¼cklich NICHT Teil von PR-4. Nach Abschluss von PR-4 stoppen und
auf weitere Anweisung warten. Kein Commit.

---

# OpenCode-Arbeitsregel

Nach JEDEM abgeschlossenen Schritt muss OpenCode diese Datei aktualisieren:

1. Status des Schritts auf ABGESCHLOSSEN setzen
2. Datum eintragen
3. kurz dokumentieren, was implementiert wurde
4. geÃ¤nderte Dateien auflisten
5. Tests/Ergebnis notieren
6. bekannte Probleme notieren
7. nÃ¤chsten Schritt festlegen
8. Fortschritt (x/18 und Prozent) aktualisieren

Kein neuer Hauptschritt beginnt, bevor PROJECT_PROGRESS.md aktualisiert wurde.

---

# Repository-Struktur (Medflux)

```text
Medflux/
â”œâ”€ frontend/
â”‚  â”œâ”€ app/
â”‚  â”œâ”€ components/
â”‚  â””â”€ lib/
â”œâ”€ backend/
â”‚  â”œâ”€ app/
â”‚  â”‚  â”œâ”€ api/
â”‚  â”‚  â”œâ”€ ai/
â”‚  â”‚  â”œâ”€ contracts/
â”‚  â”‚  â”œâ”€ documents/
â”‚  â”‚  â”œâ”€ alerts/
â”‚  â”‚  â”œâ”€ database/
â”‚  â”‚  â””â”€ models/
â”‚  â””â”€ tests/
â”œâ”€ data/
â”‚  â”œâ”€ contracts/
â”‚  â”œâ”€ database/
â”‚  â””â”€ backups/
â”œâ”€ docs/
â”‚  â”œâ”€ PROJECT_PROGRESS.md
â”‚  â”œâ”€ ARCHITECTURE.md
â”‚  â”œâ”€ CONTRACT_SCHEMA.md
â”‚  â””â”€ AI_EVALUATION.md
â”œâ”€ scripts/
â”œâ”€ .env.example
â”œâ”€ README.md
â”œâ”€ AGENTS.md
â””â”€ docker-compose.yml
```

---

# Definition of Done fÃ¼r MVP

Das MVP ist fertig, wenn:

1. mehrere PDF/DOCX-VertrÃ¤ge importiert werden kÃ¶nnen
2. Qwen lokal analysiert
3. Kerninformationen zuverlÃ¤ssig extrahiert werden
4. Ergebnisse gespeichert werden
5. KÃ¼ndigungsfristen programmatisch berechnet werden
6. Warnungen erscheinen
7. jÃ¤hrliche Kosten aggregiert werden
8. Dashboard funktioniert
9. Vertragsliste funktioniert
10. Vertragsdetail + Quellenanzeige funktioniert
11. keine externe KI-API notwendig ist
12. ein lokales Backup mÃ¶glich ist

---

Letzte Aktualisierung: 04.09.2026
Projektphase: PR-4 Equipment & Work Queue abgeschlossen (Fortschritt bleibt
15/18 = 83,3 %). Kanonische Equipment-Master (n:m), deterministische
IdentitÃ¤tsbewertung (exact/partial/generic/ambiguous), deterministische
Arbeitslisten-Ableitung (Work Items aus STEP-11-Warnungen + Equipment-Review-
Flags), idempotente Reconciliation, Equipment-/Arbeitslisten-APIs, Frontend
Equipment-Liste/Detail + Arbeitsliste, Contract 360 Equipment-/WorkItem-
Integration. 17 equipment masters, 25 work items, 0 duplicate fingerprints,
0 duplicate serial masters (krankenhaus Benchmark). 5 realen Benchmark-VertrÃ¤ge
verifiziert. Backend + Frontend Tests grÃ¼n, tsc/lint/build grÃ¼n. STEP 15 ist
nach wie vor der letzte abgeschlossene Hauptschritt. STEP 16 ist NICHT Teil
von PR-4. STEP 16 und PR-5 sind NICHT begonnen. Backend-Suite unverÃ¤ndert.
Alembic-Head d2b3a5c0f4e1 (unverÃ¤ndert).

---

# Genehmigte Intelligenz-Verbesserungen (post-UAT, kein Roadmap-Fortschritt)

Fortschritt bleibt **15/18 = 83,3 %**. Diese Punkte sind genehmigt als
APPROVED DESIGN â€” NOT IMPLEMENTED. Roadmap-Status unverÃ¤ndert.

Datum: 04.09.2026

## A2 â€” Independent Extraction + Evidence Bundles + Targeted Cross-Clause
Adjudication (genehmigt, nicht implementiert)

Design-Prinzipien:

1. Erste Extraktion bleibt Chunk-unabhÃ¤ngig. Keine propagated Vorab-Ergebnisse
   in spÃ¤tere Chunks â†’ kein Fehlerpropagations- oder Confirmations-Bias.

2. Erster Durchgang: Kandidaten-Fakten unabhÃ¤ngig extrahieren, exakte
   Evidence/Provenance fÃ¼r jeden Kandidaten erhalten.

3. Evidence Bundles: Nach der Extraktion deterministisch verwandte Kandidaten
   und Evidence nach Reasoning-DomÃ¤ne bÃ¼ndeln:
   - Kosten: monatlich/jÃ¤hrlich/gesamt, Zahlungsintervall, MwSt., Setup
   - Daten: Beginn/Ende/Dauer/KÃ¼ndigungsfrist/VerlÃ¤ngerung
   - GerÃ¤te: Name/Modell/Serien-/Inventarnummer/Service/Coverage
   - SLA/Leistungen: Leistungspflichten, Reaktionszeiten, AusschlÃ¼sse

4. Targeted Cross-Clause Adjudication: Semantische Reasoning-Modelle nur
   fÃ¼r Evidence Bundles einsetzen, die Vergleich erfordern â€“ insbesondere
   bei Konflikten, Mehrdeutigkeit oder querschnittlichen Beziehungen Ã¼ber
   Chunks/Seiten. Das Modell darf VorschlÃ¤ge machen und vergleichen, muss
   aber die bereitgestellte Evidence zitieren. Es darf deterministische
   Fakten oder unbelegte Evidence NICHT still Ã¼berschreiben.

5. Deterministischer Code bleibt autoritativ fÃ¼r: Berechnungen,
   Normalisierung, Evidence-Validierung, Equipment-IdentitÃ¤t, Warnungen,
   Work-Item-Ableitung, Sicherheitsgrenzen, Reproduzierbarkeit.

6. Unerledigte/WidersprÃ¼chliche FÃ¤lle â†’ manuelle PrÃ¼fung.

## B â€” Kontrollierte Korrekturerfassung (genehmigt, nicht implementiert)

**LÃ¼cke:** Kein Mechanismus, um manuelle Korrekturen zu erfassen. Gleiche
Fehler wiederholen sich bei zukÃ¼nftigen VertrÃ¤gen.

**Genehmigte LÃ¶sung:** `review_action`-Service + API-Endpoint:
- Speichert `{contract_id, field_path, original_value, corrected_value,
  evidence/context, reason, relevant version metadata, timestamp}`
- Kein automatisches Modell-/Prompt-/Regel-Update
- Korrekturen NIE direkt in Produktion
- `corrections_report`-Endpoint zeigt Muster (z. B. â€žcontract_type wurde
  12Ã— korrigiert: 8Ã— maintenanceâ†’service")
- Mensch entscheidet auf Basis des Reports Ã¼ber manuelle Ã„nderungen

## C â€” Versioned Regression/Evaluation Registry (genehmigt, nicht implementiert)

**LÃ¼cke:** Bei Prompt-/Schema-/Regel-Ã„nderungen gibt es kein systematisches
Verfahren, um die Korrektheit bestehender VertrÃ¤ge zu prÃ¼fen.

**Genehmigte LÃ¶sung:**
- BestÃ¤tigte Korrekturen werden zu Regression-/Evaluations-FÃ¤llen
- `scripts/regression_check.py`: Extraktion erneut auf Benchmark-VertrÃ¤gen,
  Vergleich gegen `ground_truth.json`, Meldung von Regressionen
- Prompt-/Regel-/Modell-Ã„nderungen mÃ¼ssen vor Annahme gegen etablierte
  FÃ¤lle ausgewertet werden
- Muss manuell vor dem Merge von Ã„nderungen ausgefÃ¼hrt werden

**Risiko:** Null Laufzeit-Risiko. Nur Entwicklungswerkzeug.

## D â€” Selective Model Routing (genehmigt, nicht implementiert)

- Kein teures Reasoning-Modell fÃ¼r jedes Chunk
- Effizientes lokales Extraktions-Modell fÃ¼r ersten Durchgang
- StÃ¤rkeres Reasoning-Modell nur fÃ¼r Evidence Bundles, die tatsÃ¤chlich
  Cross-Clause Adjudication erfordern, SOFERN Benchmark-Evidenz spÃ¤ter
  zeigt, dass das stÃ¤rkere Modell die Genauigkeit materiell verbessert
- Kein Modell-Upgrade vorausgesetzt; Modellwahl muss benchmarkgesteuert
  erfolgen

## Sicherheitsgrenze (verbindlich)

- KEIN autonomies Selbstlernen
- KEIN automatisches Lernen direkt in Produktion
- KEINE automatischen Prompt-/Regel-/Modell-Ã„nderungen aus
  Benutzerkorrekturen
- Alle Verbesserungen erfolgen Ã¼ber manuelle Ã„nderungen an Prompts,
  Schemas, Normalisierungsregeln oder Code, geprÃ¼ft Ã¼ber
  Regression-Tests


---

# UAT Defect Batch A â€“ Finanz-/Datums-Provenienz + manuelle Verifikation (25.09.2026)

Status: **UMGESETZT** (Ã„nderungen im Working Tree, KEIN Commit, kein Reset/Revert).
Kein neuer Hauptschritt â€“ wiederverwendet die PR-2/PR-3/PR-4-Architektur
(Berechnung = Code, Evidence-Provenienz, Contract-360, Persistenz). **Fortschritt
bleibt 15/18 = 83,3 %.** STEP 16 (Authentication/RBAC) ist NICHT implementiert.

> **Nachtrag (04.09.2026):** Die ursprÃ¼ngliche Batch-A-Auslieferung wurde in der
> manuellen UAT **abgelehnt** (7 Defekte, siehe unten â†’ Abschnitt â€žUAT-Ablehnung
> Batch A â€“ Remediation"). Die Remediation ist im Working Tree **umgesetzt und
> verifiziert**; **die Abnahme ist NICHT erteilt** â€“ erneute manuelle Freigabe
> steht aus.

## Fix-Bedarf (User)

1. Finanzwerte ohne Transparenz: Netto/Brutto fehlt; kein expliziter
   Steuer-Basis/Satz/Rechenweg.
2. Preisentwicklung unbelegt: â€žFestpreis Ã¼ber 8 Jahre." ohne Quellen-Nachweis.
3. Vertragsbeginn â€žÃœbergabedatum" (ereignisbasiert) hat keinen erfassbaren Termin.
4. Keine manuelle BestÃ¤tigung/Ãœbersteuerung materialer Fakten; kein Audit-Trail.
5. Provenienz/Zugang zu Quellen in der Detail-Ansicht lÃ¼ckenhaft.

## Umgesetzt (alle in bisheriger Architektur, KEINE Parallelsysteme)

### Netto/Brutto + expliziter Rechenweg (Code, determiniert)
- `backend/app/contracts/calculation/models.py`: `CostTaxBreakdown` (computed,
  base_tax_basis, rate_percent, currency, monthly_net/gross, annual_net/gross,
  explanation) + `PriceDevelopmentItem`.
- `backend/app/contracts/calculation/costs.py`: `derive_tax_breakdown(...)` â€“
  Decimal-exakt; NETâ†’gross=netÃ—(1+Satz), GROSSâ†’net=gross/(1+Satz); KEINE
  Annahme einer Basis oder 19 %; `computed=False` ohne verlÃ¤ssliche Basis/Satz.
  Fehlender Monatswert wird aus Jahreswert/12 abgeleitet (ehrlich gekennzeichnet).
  `collect_price_development(c)` aus `price_adjustment_clause`/`price_indexation`.
- Beide in `calculate_contract_costs` verdrahtet.

### Preisfixierung mit Quellen-Provenienz
- Detail-Service `_price_development_items(...)`: ergÃ¤nzt aus terminiertem
  Beleg automatisch einen `price_fixed`-Fakt (Marker festpreis/preisfixiert/
  fixpreis/indexierung/preisindex), evidence_field_ref â†’ `termination.evidence`.

### Ereignisbasierter Vertragsbeginn + manueller Termin
- Detail-Service `_dates_section`: `start_condition` (aus Extraktion),
  `start_date_status` (explicit/event_based/overridden),
  `overridden_start_date` (aus `date.event_start`-Override).

### Manueller Override/Confirm + append-only Audit (RBAC-bereit)
- `backend/app/database/models/override.py`: `ContractOverride`
  (contract_id, organization_id, key(120), action set/void/confirm CHECK, value
  JSONB, fact_ref, note, actor_id/actor_type NULL, is_development, created_at;
  Index contract+key, contract+created_at).
  **STEP 16 nicht da:** actor NULL, `is_development=True`; NIE Mitarbeiter-IdentitÃ¤t.
- `backend/app/contracts/overrides/keys.py` + `service.py`: `record_override`
  (append-only), `effective_overrides` (jÃ¼ngste set je key; void=Tombstone),
  `audit_history` (neu zuerst, kein Secret), `confirmed_fact_refs`.
- `backend/app/api/routes/contracts.py`: `POST /api/contracts/{id}/overrides`
  (key, action, value, fact_ref, note) â†’ frisches `ContractDetailResponse`.

### Detail-DTO/Service + API
- `backend/app/contracts/detail/models.py`: `TaxBreakdownDto`,
  `PriceDevelopmentDto`, `OverrideDto`, `AuditEntryDto`; `ContractCostsSection`
  + `tax_breakdown`/`price_development`; `ContractDatesSection` +
  `start_condition`/`overridden_start_date`; Antwort + `overrides`/`audit_log`.
- `backend/app/contracts/detail/service.py`: AuflÃ¶sung Steuerbasis/Satz aus
  Override (fÃ¤llt auf Extraktion zurÃ¼ck; nur net/gross = verlÃ¤sslich),
  `derive_tax_breakdown`, price_development, Override-/Audit-Liste.

### Frontend Contract 360
- `frontend/lib/contract-detail-types.ts`: neue DTO-Typen + Felder.
- `frontend/app/contracts/[contract-id]/page.tsx`: `onReload` â†’ Detail nach
  Override neu laden.
- `frontend/components/contracts/detail/ContractDetail.tsx`: Netto/Brutto-Block
  (Basis+Satz+Rechenweg), Preisfixierung mit Quellenbutton (evidenceFor +
  handleFocusEvidence), â€žBeginn-Bedingung"-Regel, Override-Panel am Ende.
- `frontend/components/contracts/detail/OverridePanel.tsx` (neu): Steuerbasis
  net/gross + Satz, Ereignisdatum setzen, Fakt bestÃ¤tigen (fact_ref+note),
  Override voiden, effective Overrides-Liste, append-only Audit-Historie.
- `frontend/app/globals.css`: Stile fÃ¼r netto-brutto-grid, override, audit.

## Migration
- `backend/alembic/versions/20260904_e3a4b5c6d7e8_add_contract_override.py`
  (neue Tabelle; **anfÃ¤nglich ohne `uuidv7()`-Default auf `id`** â†’ Insert-Crash).
- `backend/alembic/versions/20260904_f1a2b3c4d5e6_fix_contract_override_id_default.py`
  (korrigierendes `SET DEFAULT uuidv7()`, entspricht `uuid_pk()`-Muster).
- Beide angewendet: `alembic upgrade head` â†’ Head `f1a2b3c4d5e6`.

## Korrigierte Defekte im Working Tree
- `detail/service.py` fehlte `MAX_SNIPPET_CHARS` (NameError in `_evidence_ref` â†’
  Detail-View auf Beleg-VertrÃ¤gen brach) â†’ Konstante ergÃ¤nzt.
- Override-Liste im Read-Model: `key` fehlte + `created_at` als datetime
  (Pydantic-Veto) â†’ Mapping auf `OverrideDto` (charf: key + isoformat).
- `tax_basis`-Anzeige: bei fehlender Basis â€žunknown" statt `None` (PR-3-Test).

## Tests (fokussiert, Batch A)
- `backend/tests/test_uat_defect_batch_a.py` (12):
  Pure `derive_tax_breakdown` (net/gross, unknown-Basis, Satz-missing inkl.
  evidence-getragener Basiswerte, Satz 0, Monat-aus-Jahr, SteuerbetrÃ¤ge,
  `_resolve_monthly`-Read-Model), `collect_price_development`, Integration Ã¼ber
  TestClient: Evidence-first ohne Overrides (Basis=net aus â€žzzgl. USt.",
  monthly_net=5916.67, Brutto offen, monthly explicit, Preisfixierung 8 Jahre);
  Override net+19 â†’ `computed=True`, monthly_net 5916.67 / monthly_gross
  7040.84 / annual_net 71000.04 / annual_gross 84490.05; event_start â†’
  overridden_start_date + status; confirm â†’ Audit; Void entfernt wirksam, bleibt
  append-only.
- Regression-Check gegen betroffene BestÃ¤nde (keine volle Suite):
  `test_calculation_engine.py` + `test_contract_detail.py` â€“ **99 passed**;
  inkl. Batch A = **111 passed**. `tsc --noEmit` + `next lint` sauber.

## UAT-Ablehnung Batch A â€“ Remediation (04.09.2026, NICHT abgenommen)
Manueller UAT-Fehlschlag mit 7 materialen Defekten â†’ umgesetzte Korrekturen:

1. **Monats-Provenienz:** Monatswert war falsch als â€žJahreswert/12" (calculated)
   statt als belegter Fakt ausgewiesen.
   â†’ `costs.py` `normalize_recurring_costs`: Monats-Slot aus monatlichem Fakt
   (status=explicit, inputs=Quelle) statt Ableitung; Jahres/12 nur als Fallback.
   â†’ Read-Model `_resolve_monthly(...)`: stellt bei gespeicherten LÃ¤ufen den
   Monatswert aus den belegten Jahres-Eingaben wieder her (Decimal-Import-Fix).
2. **Netto/Brutto-Basis offenlegen:** Brutto/VAT wurde versteckt; 19 % wurde
   geraten.
   â†’ `derive_tax_breakdown(...)` liefert Basiswerte (netto bei Basis=net) IMMER,
   Gegen-Basis + `monthly_tax`/`annual_tax` NUR mit belegtem Satz; sonst
   â€žOppositions-Basis offen".
3. **Steuer-Basis-Inferenz:** Basis wird deterministisch aus Evidenz-Text
   (Snapshot + persistierte Evidence) abgeleitet (â€žzzgl. ... USt." â†’ net,
   â€žinkl. ... USt." â†’ brutto; AbkÃ¼rzungen nur mit USt.-Keyword; NIE SÃ¤tze raten).
4. **KPI/Summary:** â€žJÃ¤hrliche Kosten" zeigt Basis-Suffix (Netto/Brutto); das
   Netto/Brutto-Grid (Monat/Jahr Ã— netto/brutto) wird IMMER gerendert; fehlende
   Gegen-Basis = â€žNeeds Review"; USt.-Zeile (Satz, monatlich, jÃ¤hrlich) nur bei
   berechenbarem Satz.
5. **Preisfixierung first-class:** â€žPreisfixierung: 8 Jahre" (`period_years`,
   deterministisch aus â€žFestpreis Ã¼ber N Jahre") mit Quellen-Navigation.
6. **Confirm/Override/Void real nutzbar:** getrennte Buttons fÃ¼r Basis- und
   Satz-Setzen, Void fÃ¼r Basis und Satz, Audit mit `old_value` (alter â†’ neuer
   Wert) + â€žEntwicklung/unverifiziert"-Kennzeichnung; keine erfundene
   Mitarbeiter-IdentitÃ¤t.
7. **Ereignisbeginn ehrlich:** Demo-Overrides VOIDED (append-only erhalten):
   `date.event_start=2025-03-01`, `cost.tax_basis=net`, `cost.tax_rate_percent=19`.
   Effektiv: Beginn = ereignisbasiert, tatsÃ¤chliches Datum NICHT dokumentiert
   (nur Mensch trÃ¤gt es ein); Basis=net aus Evidenz; Satz offen â†’ Brutto â€žNeeds
   Review" (NIEMALS 19 %).

## API-Verifikation (AXIOM 100494M1, running Backend via --reload)
- Detail: `dates.start_condition=ereignisbasiert`, `start_date_status=event_based`
  (vor Override); `costs.tax_basis=unknown`, `tax_breakdown.computed=False`
  (keine erfundene Basis/Satz); `price_development=[price_fixed â€žFestpreis Ã¼ber
  8 Jahre." ref=termination.evidence]`; `overrides=[]`, `audit_log=[]`.
- Nach Override (siehe unten): computed=True, net=net, Satz=19.

## 3-Cent-Rundungsdifferenz (bekannt, dokumentiert)
- Defect-Fakt: Jahres-Brutto 84.490,08 (= 12 Ã— 7.040,84 Monats-brutto).
- Engine leitet Jahres-brutto aus Jahres-netto Ã— 1,19 ab:
  71.000,04 Ã— 1,19 = **84.490,05** (0,03 Differenz zur 12Ã—-Summe).
- Deterministisch und im `explanation` als Rechenweg ausgewiesen; kein
  Fehler der Extraktion, keine erfundene Annahme.
- Nach Remediation: Brutto/Gegen-Basis erscheint NUR mehr, wenn ein Steuersatz
  dokumentiert/bestÃ¤tigt ist; ohne Satz â†’ â€žNeeds Review" (keine 19 %-Annahme).

## AXIOM-Demo-Zustand nach Remediation (Test-Overrides VOIDED, append-only)
Die frÃ¼heren API-Verifikations-Overrides auf dem ECHTEN Benchmark-Vertrag
(100494M1) wurden im Zuge der UAT-Remediation per Override-Mechanismus
**VOIDED** (nichts gelÃ¶scht/umschrieben â€“ Historie append-only erhalten):
- `cost.tax_basis = net` (set 2026-09-04T17:01:47 â†’ **void** 21:26:13)
- `cost.tax_rate_percent = 19` (set 2026-09-04T17:01:47 â†’ **void** 21:26:15)
- `date.event_start = 2025-03-01` (set 17:02:34/17:03:11 â†’ **void** 21:26:11)
- 2Ã— `fact.confirm` â†’ `costs.monthly_cost` (bestÃ¤tigen bleibt wirksam)
Alle Zeilen `is_development=True`, `actor_type=None` (RBAC-bereit, ehrlich).

**Effektiver AXIOM-Zustand (evidence-first):** Beginn ereignisbasiert, kein
tatsÃ¤chliches Datum dokumentiert; Basis=net (aus â€žzzgl. USt." der Zahlungs-
Evidenz abgeleitet); Steuersatz offen â†’ Brutto â€žNeeds Review"; Monatswert
5916.67 als belegter Fakt (explicit); Preisfixierung 8 Jahre mit Quelle.

## Probleme / bekannte Grenzen
- 3-Cent-Rundungsdifferenz (Jahres-brutto, erst bei gesetztem Satz sichtbar,
  s. o.) â€“ akzeptiert, dokumentiert.
- STEP 16 fehlt: Overrides futsch ohne echte Nutzer-IdentitÃ¤t; `actor` null.
- Kein separates UI fÃ¼r â€žPreisfixierung" auÃŸerhalb des Detail-Blocks (reicht MVP).
- Brutto/Gegen-Basis ist ohne belegten Steuersatz â€žNeeds Review" (gewollt:
  keine erfundene 19-%-Annahme).

## NÃ¤chster Schritt / Hinweis
- **Erneute manuelle UAT der Remediation** lt. Anleitung unten (evidence-
  first-Anzeige ohne Overrides + voller Override/Confirm/Void-Flow).
- STEP 16 (Authentication/RBAC) und PR-5 folgen erst nach UAT-Freigabe; kein
  neuer Hauptschritt begonnen. **Batch A ist NICHT abgenommen.**
- **Nachtrag (05.09.2026):** Durch die zweite Remediation (UAT Re-Test 2,
  deterministische Fakten-Wiederherstellung aus dem persistierten Beleg) sind
  die alten UAT-Schritte 3 (â€žNeeds Review") und 5 (Override fÃ¼r 19 %)
  **Ã¼berholt** â€“ siehe untenstehenden neuen Abschnitt + angepasste Anleitung.

## Manuelle UAT-Schritte (exakt, RE-UAT der Remediation)
1. Backend http://localhost:8000 (--reload, laufend) + Frontend
   http://localhost:3000 (next dev, laufend) â€“ beide geprÃ¼ft (200/ok).
2. Vertragsliste â†’ AXIOM (100494M1) â†’ Contract 360.
3. AXIOM ohne Overrides (Demo-Overrides wurden VOIDED): KPI zeigt â€žJÃ¤hrliche
   Kosten (Netto)"; Kosten-Sektion zeigt im IMMER sichtbaren Netto/Brutto-Grid:
   Monatlich netto 5.916,67 â‚¬, JÃ¤hrlich netto 71.000,04 â‚¬, Monatlich brutto und
   JÃ¤hrlich brutto = â€žNeeds Review" (Basis=net aus â€žzzgl. USt.", Satz fehlt).
   KEINE 19 %-Annahme. Monatlich wiederkehrend = 5.916,67 â‚¬ (status explicit).
4. â€žPreisfixierung: 8 Jahre" als Fakt mit â€žQuellenangabe"-Button â†’ Viewer
   springt zur Beleg-Stelle (Seite 7). Beginn-Bedingung zeigt â€žEreignisbasiert:
   Ãœbergabedatum â€“ tatsÃ¤chliches Datum nach dem Ereignis eintragen".
5. Panel â€žBestÃ¤tigen & Ãœberschreiben": Steuerbasis `net` (eigener Button
   â€žBasis speichern") und Steuersatz `19` (â€žSatz speichern") â†’ Netto/Brutto-
   Grid fÃ¼llt sich (mon. brutto 7.040,84, jÃ¤hrl. brutto 84.490,05) + USt.-Zeile
   monatlich 1.124,17 / jÃ¤hrlich 13.490,01.
6. Ereignisdatum (z. B. 01.03.2025) im Panel setzen â†’ Status â€žoverridden",
   Datum erscheint; per â€žZurÃ¼cksetzen" VOIDEN â†’ Status wieder â€žereignisbasiert",
   Datum verschwindet (Audit bleibt).
7. Fakt â€žMonatspreis" bestÃ¤tigen (fact_ref `costs.monthly_cost`, Note) â†’
   Audit-Historie zeigt Aktion, Feld, alter â†’ neuer Wert (old_value), Notiz,
   Zeitstempel, â€žEntwicklung/unverifiziert"; kein erfundener `actor`.
8. Optional: Basis/Satz per Void zurÃ¼cknehmen (Audit bleibt), Grid wieder
    â€žNeeds Review".

---

# UAT Re-Test 2 â€“ Deterministische Fakten-Wiederherstellung aus dem Beleg (05.09.2026)

Status: **UMGESETZT + API-/Read-Model-verifiziert** (Working Tree, KEIN Commit,
kein Reset/Revert, keine erneute OCR/LLM-Ingestion). Fortschritt bleibt
**15/18 = 83,3 %**. Kein neuer Hauptschritt, keine Schema-Migration.

## Ausgangslage
- AXIOM (100494M1) ist ein Scan; der persistierte kanonische Beleg
  (`canonical.json`, docling 1.3.0, `do_ocr=True`) enthÃ¤lt die Fakten mit
  Positionsangaben (PDF-Punkte), aber die Snapshot-Extraktion hatte
  Netto/MwSt./Brutto sowie Zahlungsbeginn/Mindestvertragslaufzeit nicht belegt
  bzw. falsch geparst (`dates.minimum_duration=3` â€“ das â€ž3 Monate" der
  Zahlungsbeginn-Klausel, korrekt sind 96).
- Grundsatz: Die KI extrahiert **Fakten**. Hier wurden die Fakten
  **deterministisch aus dem bereits persistierten Belegtext** wiederhergestellt â€“
  keine erneute KI, keine erfundenen Werte, keine 19-%-Annahme.

## Neu: Recovery-Modul `backend/app/contracts/detail/recovery.py`
- `load_canonical_pages(session, ...)`: lÃ¤dt den aktiven kanonischen Artifact
  (neuester aktiver Run, outer-join ProcessingRun) speichersicher aus
  `settings.contracts_dir` â†’ Seiten mit `text`/`elements`/`tables`; bei Fehler
  `[]` (neutrale RÃ¼ckfallebene).
- `fix_text`: Mozibake-Normalisierung der OCR-Texte (Ã¼/Ã¤/Ã¶/Ã©/â‚¬).
- Reine, getestete Parser:
  - `_parse_german_amount` (deutsche Dezimal-/Tausender-Trennungen),
  - `_find_price_table`: zuerst Tabellenzellen (â€žGesamtdienstleistungspreis
    netto pro Monat" / â€žzzgl. X % MwSt." / â€žbrutto pro Monat" mit Wert in
    Nachbarzelle), sonst Seiten-Text-Regex,
  - `_find_start_event` (â€žVertragsbeginn: <Ereignis>", ohne Zahlungsbeginn/
    Mindest-/Ãœbergabe-Teilklauseln) â†’ â€žÃœbergabedatum",
  - `_find_payment_start` â†’ â€ž3 Monate nach Ablauf der GewÃ¤hrleistung",
  - `_find_minimum_duration` â†’ 96 Monate (Element-Match; Fallback: letztes
    numerisches â€žN Monate"-Token nach Label â€“ bleibt korrekt trotz der im OCR
    verbundenen p4-Klausel â€žÃœbergabedatum 3 Monate â€¦ 96 Monate").

## Recovered-Fakten (deterministisch belegt, AXIOM)
- monatlich: netto **5.916,67 â‚¬** Â· MwSt.-Satz **19 %** Â· MwSt. **1.124,17 â‚¬** Â·
  brutto **7.040,84 â‚¬**; Basis **netto**.
- jÃ¤hrlich (aus belegten MonatsbetrÃ¤gen Ã— 12, Vertrags-Rundung erhalten):
  netto **71.000,04 â‚¬** Â· MwSt. **13.490,04 â‚¬** Â· brutto **84.490,08 â‚¬**.
  LÃ¶st die dokumentierte 3-Cent-Differenz auf (kein 71.000,04 Ã— 1,19 mehr).
- Zahlungsbeginn **â€ž3 Monate nach Ablauf der GewÃ¤hrleistung"** (condition_based);
  Mindestvertragslaufzeit **96 Monate**; Beginn-Bedingung â€žÃœbergabedatum"
  (ereignisbasiert).

## Rechenmodell, DTO & Service
- `derive_tax_breakdown` (`costs.py`): neue Kwargs `recovered_vat_rate`,
  `recovered_monthly_vat`, `recovered_monthly_gross`, `recovered_monthly_net`;
  belegte Werte fÃ¼llen fehlende Extraktion und bewahren die Vertrags-Rundung;
  `explanation` kennzeichnet â€žZahlen direkt aus dem Vertragstext belegt â€¦
  nicht durch die KI errechnet". Bisheriger Berechnungspfad unverÃ¤ndert.
- `TaxBreakdownDto` + `source` + `evidence_field_refs` (je Betrag â†’ field_ref);
  `ContractDatesSection` + `payment_start_rule/status/evidence`,
  `minimum_duration_months/evidence`.
- `detail/service.py`: lÃ¤dt Recovery (neutral bei Fehlen), reicht in Datums-/
  Kosten-Sektion, baut 5 weitere EvidenceRefs.

## Evidence-Provenienz
- Je wiederhergestelltem Wert ein EvidenceRef `recovered:costs.tax_table.{net|vat|
  gross}` (Zellen der Preistabelle) bzw. `recovered:payment.payment_start`,
  `recovered:dates.minimum_duration`, jeweils mit snippet + bbox (PDF-Punkte) â†’
  `supports_exact_navigation=True`, precision â€žcoarse". 9 Evidence insgesamt
  (4 Extraktion + 5 Recovery).

## Frontend (Restitution)
- `contract-detail-types.ts`: neue Typfelder (s. o.).
- `ContractDetail.tsx`: Netto/MwSt./Brutto-Grid mit 6 Zellen (Monat/Jahr Ã—
  netto/MwSt./brutto); belegte Zellen klickbar â€žQuellenangabe" â†’ Viewer springt
  zur Fundstelle; fehlende Werte ehrlich **â€žZu prÃ¼fen"** (ersetzt â€žNeeds
  Review"); Herkunft-Zeile + â€žÃ— 12"-Hinweis bei belegter Quelle; Regeln
  â€žZahlungsbeginn" und â€žMindestvertragslaufzeit" mit Quellen-Navigation.
- `OverridePanel.tsx`: Hinweis, dass Netto/MwSt./Brutto aktuell belegt sind
  (Override nur bei Korrekturbedarf).

## Verifikation
- `tests/test_uat_defect_batch_a.py` (+6): Recovery aus kanonischen Seiten,
  Mindestlaufzeit-Letzt-Token-Regel, leere Seiten neutral, belegtes Brutto
  erhÃ¤lt Rundung (84.490,08), Gross-Basis mit belegtem Netto, belegter Satz
  fÃ¼llt fehlende Extraktion. â†’ **18 passed** (12 + 6), nur swig-Deprecation-
  Warnings.
- Backend :8000 + Frontend :3000 laufen; `GET /api/contracts/{id}` Ã¼ber HTTP:
  `computed=True`, `base_tax_basis=net`, `rate_percent=19`, mon. netto 5916.67 /
  MwSt 1124.17 / brutto 7040.84, jÃ¤hrl. netto 71000.04 / MwSt 13490.04 / brutto
  84490.08, `source` â€žâ€¦Ã¼bernommen (Seite 7).", `payment_start_rule` â€ž3 Monate
  nach Ablauf der GewÃ¤hrleistung" [condition_based], `minimum_duration_months`
  96, 9 Evidence (5 recovered mit exakter Navigation).
- `tsc --noEmit` grÃ¼n, `next lint` 0 warnings/errors.

## Probleme / bekannte Grenzen
- **Die Abnahme steht weiterhin aus** â€“ wie bei allen PR-Phasen entscheidet die
  manuelle UAT; **Batch A ist NICHT abgenommen.**
- STEP 16 fehlt weiterhin (`actor` null, Entwicklungs-Kontext ehrlich sichtbar).
- Die WertÃ¼bernahme nutzt den persistierten kanonischen Beleg; VertrÃ¤ge ohne
  OCR-Textebene oder Zahlen-Tabelle behalten die ehrliche â€žZu prÃ¼fen"-Darstellung.

## NÃ¤chster Schritt / Hinweis
- Erneute manuelle UAT der remediierten Darstellung lt. angepasster Anleitung
  unten (jetzt mit wiederhergestellten Werten inkl. Quellen-Navigation).
- STEP 16 / PR-5 erst nach UAT-Freigabe; kein neuer Hauptschritt begonnen.

## Manuelle UAT-Schritte (exakt, RE-UAT 2 â€“ Fakten aus dem Beleg, keine Overrides nÃ¶tig)
1. Backend :8000 (--reload) + Frontend :3000 (next dev) laufen â€“ geprÃ¼ft.
2. Vertragsliste â†’ AXIOM (100494M1) â†’ Contract 360.
3. Kosten-Sektion â€žNetto / MwSt. / Brutto": Basis **Netto (zzgl. USt.) Â· 19 %
   MwSt.**; Monatlich netto 5.916,67 â‚¬ Â· MwSt. 1.124,17 â‚¬ Â· brutto 7.040,84 â‚¬;
   JÃ¤hrlich netto 71.000,04 â‚¬ Â· MwSt. 13.490,04 â‚¬ Â· brutto 84.490,08 â‚¬.
   Herkunft-Zeile â€žâ€¦direkt aus der Vertragszusammenfassung Ã¼bernommen
   (Seite 7)â€¦ (Ã— 12)". Ohne manuelle Overrides; KPI â€žJÃ¤hrliche Kosten (Netto)".
4. Jede Netto/MwSt./Brutto-Zelle: â€žQuellenangabe"-Button â†’ Viewer springt zur
   markierten Fundstelle (Seite 7, exakte Position).
5. Laufzeit: â€žBeginn-Bedingung: Ereignisbasiert: Ãœbergabedatum â€“ tatsÃ¤chliches
   Datum nach dem Ereignis eintragen"; â€žZahlungsbeginn: 3 Monate nach Ablauf der
   GewÃ¤hrleistung" (Quellenangabe â†’ Fundstelle); â€žMindestvertragslaufzeit:
   96 Monate" (Quellenangabe â†’ Fundstelle).
6. Preisfixierung â€ž8 Jahre" weiterhin mit Quelle (Seite 7).
7. Panel â€žBestÃ¤tigen & Ãœberschreiben": Hinweis â€žNetto/MwSt./Brutto sind direkt
   aus dem Vertrag belegt"; Overrides nur bei Korrekturbedarf nÃ¶tig.
8. Audit-Historie weiterhin append-only (alter â†’ neuer Wert, Entwicklungs-
   Kontext, kein erfundener actor).

---

# Customer-Demo-Readiness (vollstÃ¤ndig lokal, UAT-/Demo-Bereitschaft)

Status: ABGESCHLOSSEN (Backend + Frontend + fokussierte Tests)
Datum: 06.09.2026

## Ziel / Abgrenzung
- Volle Kunden-/UAT-Demobereitschaft MIT vollstÃ¤ndig lokaler Analyse, ohne
  externe KI-API und unabhÃ¤ngig von OCR/Prompt-Version.
- Rein Vorbereitung fÃ¼r Demo/UAT: **keine Abnahme erklÃ¤rt**, kein PR-5, kein
  STEP 16 (authentifizierte Benutzerverwaltung), keine Modell-/
  Prompt-Sonderbehandlung (auch nicht fÃ¼r AXIOM).

## Implementiert (Backend)
- **Failure-safer Import:** fehlgeschlagene Analyse erzeugt einen sichtbaren
  Platzhalter-Vertrag (`lifecycle_state=active`, `status=draft`, kein
  accepted_extraction); das Dokument bleibt sichtbar, `can_retry` +
  `POST /api/documents/{document_version_id}/retry` â†’ `resume_document`
  (erneuter Lauf aus den Original-Bytes). Bei spÃ¤terem Erfolg wird der alte
  Platzhalter deterministisch als `orphan` markiert.
- **Ehrlicher Importzustand** `app/documents/status.py` (`uploaded` /
  `processing` / `analysis_ok` / `analysis_failed`), Fehlermeldungen nur als
  sichere deutsche Kurztexte; bekannte KI-Fehler (â€žnicht verfÃ¼gbarâ€œ) werden
  verstÃ¤ndlich abgebildet (`safe_failure_message`), nie interne Payloads.
- **Demo-/UAT-Workspace** `app/demo/workspace.py` + Router `/api/demo`:
  `GET /workspace`, `POST /workspace/enable`, `POST /workspace/disable`.
  Aktiv â‡’ Vertragsliste, Dashboard und Detail zeigen nur wÃ¤hrend der Demo
  hochgeladene VertrÃ¤ge (optionaler `workspace_contract_ids`-Predicate);
  deaktivieren stellt das Portfolio unverÃ¤ndert wieder her.
- **Faktgenaue menschliche PrÃ¼fung:** 20 materiale Fakten
  (`app/contracts/review/material.py`, Muster: identity, dates, payment,
  termination, costs, equipment, services). Service
  `app/contracts/review/service.py`: append-only `fact_review`/`contract_review`
  (BestÃ¤tigen Ã¤ndert nie, Korrigieren setzt wirksamen Wert, Reopen,
  Abschluss mit Quittung ungeprÃ¼fter Angaben + Notiz, `changed_after_review`
  bei Ã„nderung nach Abschluss). Werte bleiben `manual_unverified`,
  `authenticated_actor_id=None`.
- **Detail-Anreicherung:** `ContractDetailResponse` um `import_state`,
  `fact_review_states`, `fact_reviews`, `contract_review` erweitert; Routen
  `POST /{contract_id}/fact-reviews`, `/review/start`, `/review/complete`.
- **Migrations:** `0010`/`0011`-Ã„quivalente fÃ¼r `fact_review`,
  `contract_review`, `demo_workspace`, `demo_workspace_entry` (kein
  `organization_id` auf Review-Tabellen, `uuidv7()`-Server-Default); Schema
  entspricht den Modellen, `alembic current` = head.

## Implementiert (Frontend)
- `contract-detail-types.ts`: DTOs fÃ¼r `ImportStateDto`, `FactReviewDto`,
  `FactReviewStateDto`, `ContractReviewDto` + Request-Typen.
- `ContractDetail.tsx`: Importzustands-Banner (bei Fehlschlag mit
  â€žErneut verarbeitenâ€œ, sonst neutral) + eingebettetes `FactReviewPanel`.
- `FactReviewPanel.tsx`: PrÃ¼fer-Kontext, Vertragsreview (bestÃ¤tigt/open +
  Abschluss mit Quittungs-Checkbox + Notiz, Reopen), je Fakt Status
  â€žNicht geprÃ¼ft/BestÃ¤tigt/Korrigiertâ€¦", Original vs. wirksam, BestÃ¤tigen/
  Korrigieren (Wert-Eingabe)/Erneut Ã¶ffnen, append-only Historie.
- `settings/page.tsx`: Sektion â€žDemo-Modus" â€“ aktiv/inaktiv, Vertragsanzahl,
  Aktivieren/Deaktivieren.

## Verifikation / Tests
- `backend/tests/test_customer_demo_readiness.py`: **12 passed** (Material-
  Registry, Review-Summary, Complete-Flow inkl. Quittungs-Pflicht,
  Korrektur-nach-Abschluss, Reopen-Historie, Workspace-Isolation,
  Failure-safer Import + Retry + Orphan, Import-State). Nur
  swig-Deprecation-Warnings.
- Live Ã¼ber :8000 (PID nach Neustart aktual, ohne `--reload`): Demo-
  Workspace togglen (Liste 6â†’0â†’6), Detail-Anreicherung (20 Fakten,
  `contract_review.relevant=6`), Review-Lebenszyklus inkl. 422-Grenzen,
  `/api/ai/status` healthy (ollama, qwen3:8b).
- Frontend: `tsc --noEmit` grÃ¼n, `next lint` 0 warnings/errors,
  `next build` erfolgreich; :3000 lÃ¤uft.

## Probleme / bekannte Grenzen
- **Abnahme weiterhin ausstehend** â€“ Batch A wurde genauso wenig abgenommen
  wie die Demo-Bereitschaft; die manuelle UAT entscheidet.
- STEP 16 (Benutzerverwaltung) / PR-5 weiterhin offen â€“ PrÃ¼fer-Checks bis
  dahin `manual_unverified`.
- AXIOM wurde NICHT erneut mit dem LLM bewertet (kein LLM-/OCR-Rerun); auf
  einer gespiegelten Datenkopie lÃ¤sst sich die Extraktion demonstrativ
  wiederholen.
- Smoke-Test-Review-Zeilen auf dem Siemens-Vertrag
  `01a05cb6-60fe-7c41-bf32-be250bbb4b96` (krankenhaus) verbleiben append-
  only in der DB (bewusste, nicht gelÃ¶schte Testdaten).

## NÃ¤chster Schritt / Hinweis
- Manuelle UAT gemÃ¤ÃŸ der Anleitung unten (Demo-Modus standardmÃ¤ÃŸig **aus**;
  vor der Demo Ã¼ber Einstellungen â†’ Demo-Modus â†’ â€žAktivierenâ€œ einschalten,
  danach wieder deaktivieren).
- Kein neuer Hauptschritt begonnen, bis die Fortschrittsdatei/Demo-Phase
  abgestimmt ist.

## Manuelle UAT-Schritte (exakt, Kunden-Demo)
1. Ollama lÃ¤uft, `qwen3:8b` installiert; Backend :8000 + Frontend :3000
   aktiv; `/api/ai/status` meldet â€žLokale KI verfÃ¼gbar.â€œ.
2. Einstellungen â†’ Demo-Modus â†’ **Aktivieren** (bzw. nach der Demo
   **Deaktivieren**); Vertragsliste zeigt anschlieÃŸend nur demo-hochgeladene
   VertrÃ¤ge.
3. Vertrag â†’ Contract 360: Importzustand; wenn ein Lauf fehlschlug, Banner
   â€žAnalyse fehlgeschlagenâ€œ mit â€žErneut verarbeitenâ€œ â†’ nach Erfolg
   Platzhalter verwaist und echter Vertrag sichtbar.
4. â€žFaktprÃ¼fungâ€œ: Angaben mit â€žBestÃ¤tigenâ€œ Ã¼bernehmen (Wert bleibt) oder
   â€žKorrigierenâ€œ (neuer wirksamer Wert); PrÃ¼fer-Name hinterlassen.
   AnschlieÃŸend â€žReview abschlieÃŸenâ€œ (bei ungeprÃ¼ften Angaben Quittung +
   Notiz nÃ¶tig). Nach einer Korrektur nach Abschluss erscheint
   â€žÃ„nderung nach PrÃ¼fungâ€œ; â€žHistorieâ€œ zeigt die append-only Schritte.
5. Vertragsliste/Dashboard Ã¤ndern sich wÃ¤hrend der Demo entsprechend;
   `GET /api/demo/workspace` meldet `enabled` + `contract_count`.

---

# UAT Re-Test (generische Defekt-Umsetzung, Defektbereiche Aâ€“F)

Status: ABGESCHLOSSEN (Umsetzung + Backend- und Frontend-Tests grÃ¼n)
Datum: 06.09.2026
Fortschritt: unverÃ¤ndert **15 / 18 = 83,3 %** (korrektive Umsetzung, kein neuer
Hauptschritt; PR-5/STEP 16 weiterhin offen)

## Ziel / Abgrenzung
- Blind-UAT-Re-Test am ABIOMED-Vertrag (`40015645`, Contract
  `01a0743a-01d9-7248-8728-0df3b7c14bbd`) gegen die Defektbereiche Aâ€“F Ã¼ber
  **generische** Fixes (kein Einzelsonderfall).
- Keine Abnahme, kein PR-5, kein STEP 16 (Reviewer bleibt `manual_unverified`,
  `authenticated_actor_id=None`), kein Commit/Reset, keine LÃ¶schung von
  Benchmark-/History-Daten, kein voller Regressionenlauf, kein LLM/OCR-Rerun;
  bei einem GerÃ¤ten ohne Passend-Name-Detail bleibt der Eintrag ehrlich leer.

## Defektbereich A â€“ Vertragsnummer & Titel (Recovery statt KI-Annahme)
- `backend/app/documents/recovery.py`:
  - `_AUTO_RENEW` aufgerÃ¤umt (klare Wieder-Suche, keine falschen Sync-Original-
    Werte); `_find_contract_number` (Muster `Vertr.-Nr.:`), `_find_title`
    (Region-Erkennung, drittes Textformat), `_find_absolute_dates`
    (assozierte Absolutdaten **p5** 2025-04-01/2029-03-31), `_find_cost_lines`
    (Num + Betrag, Zeilen mit â€ž1./2./3. Jahrâ€œ), Neu-Suche nach â€žLaufzeit von
    4 Jahren".
  - `recover_financial_facts` â†’ `recover_identity_like`, `recover_laufzeit`,
    `recover_cost_lines` verdrahtet (Identity: Nr. 40015645 p1/Snippet,
    Titel â€žFull-Service-Vertrag ABIOMEDâ€œ p1/Region, Lieferant; Laufzeit:
    absolute_start/end, duration_years=4, auto_renewal=False, Zahlungs-
    Intervalle; `cost_lines` als `RecoveredCostLine`-Dataclasses mit Label,
    Betrag (0,00 / 8.000,00 EUR Ã—3), Seite 8, MwSt-Angabe).
- `backend/app/contracts/detail/service.py`: `_identity_section` nutzt
  wiederhergestellte `contract_number`/`contract_title`; `_resolve_evidence_page`
  (belegte Seite statt Optional-Page-Erfindung); `_build_page_index` inkl.
  Tabellenzellen-Inhalte; `_match_text` ersetzt â€ž-â€œ durch â€žâ€œ fÃ¼r robustes
  Finden; `_region_from`; `_find_supplier_ref`.
- Verifikation: `contract.contract_number='40015645'` backfill (DB), FTS-Treffer
  per `to_tsquery('simple','40015645')`, Detail-Response liefert
  `number=40015645`, `title='Full-Service-Vertrag ABIOMED'` (belegt p1, exakt).

## Defektbereich B â€“ Widerspruch Vertragsbeginn (ehrliche Status)
- `_dates_section`: dokumentierte und berechnete Beginn-/Endwerte aus der
  redundanzbasierten Wahrheit; Status jeweils `documented`/`event_based`/
  `needs_review`/`overridden` statt verstecktem Widerspruch; `documented_end_date`
  und `duration_years` (4) in der Response; `automatic_renewal` aus Recovery
  (False, belegt p5). Frontend: Beginn-Rule zeigt bei status != `explicit` einen
  deutschen Hinweis (StartStatus-Label-Map), â€žLaufzeit â€¦ Jahreâ€œ + dokumentiertes
  Ende als eigene Rules.
- ABIOMED: â€žBeginn 01.04.2025 (Im Vertrag dokumentiert)â€œ, Ende 31.03.2029
  (explizit), Laufzeit 4 Jahre, automatische VerlÃ¤ngerung â€žNeinâ€œ.

## Defektbereich C â€“ Kosten-ErklÃ¤rung statt fehlendem Jahresbetrag
- `_costs_section` + `_cost_availability`: wenn kein verlÃ¤sslicher Jahresbetrag
  existiert (annual/monatlich `None`), erscheint `availability.status=
  manual_input_required` mit `summary_de`, `found_facts` (4 Preiszeilen p8
  inkl. Steuerhinweis + Zahlungsweise), `missing_inputs` und
  `manual_input_required=true`. Frontend â€žFinanzielle Konditionenâ€œ: Kosten-
  VerfÃ¼gbarkeits-Block listet Fundstellen (Seite 8, klickbar) + fehlende
  Eingaben + â€žmanuell festlegenâ€œ deutlich.
- Explizit gebaut fÃ¼r Divergenzen: korrekte Mathematik ist kein Modus fÃ¼r
  die KI (Fakten = KI, Berechnung = Code).

## Defektbereich D â€“ Evidence-Seiten-Metadaten (keine Seitenerfindung)
- `_build_page_index` inkl. Dokumenttext + Tabellen/Zelltexte; Evidence einer
  wiederhergestellten Angabe (z. B. `identity.contract_number`) erhÃ¤lt eine
  echte Seite (Nr.: p1; Titel: p1 exakt; Datum/Ende/Laufzeit/Auto-Renew: p5;
  Kostenzeilen: p8 exakt). Ohne Pos. bleibt `page=None` und â€žohne exakte
  Positionâ€œ im UI â€“ kein Sprung/Overlay bei fehlender Seite.

## Defektbereich E â€“ Verdoppelte GerÃ¤te-Zeilen (kein Patchwork)
- `_equipment_item(p, resolved_page)`: GerÃ¤te werden nur noch bei ernsthaft
  verschiedener IdentitÃ¤t/Eigenschaften angehÃ¤ngt; gelÃ¶schte Leer-Zeilen und
  doppelte Pflegezeilen verschwinden nicht (hier: ABIOMED = 1 Zeile, Impella
  Controller, Page 8). Kein erfundenes â€žUmlage/Aufschlag"-GerÃ¤t.

## Defektbereich F â€“ Review & Faktâ†”Evidenceâ†”Quelle
- `app/contracts/review/material.py`: Equipment-Identity/Serial-Leser liefern
  Wert-Strings (Fix NameError durch Vorziehen der Helper vor `MATERIAL_FACTS`);
  `date.end_date` nutzt `documented_end_date` Fallback; `CRITICAL_FACTS` +
  `fact_is_critical` (7 materiale Fakten).
- `app/contracts/review/service.py`: `_FACT_EVIDENCE_PREFIXES` verbindet
  gruppenbezogene Evidence (equipment.identity/serial â†’ `identity_equipment.*`;
  services.coverage â†’ sla.*/scope.*); `needs_review` nur noch, wenn Fakt
  vorhanden UND keine Evidence oder `requires_review`; `linked_evidence`,
  `needs_evidence`, `is_critical`; `fact_label_de` in Historie. `contract_review`
  um `critical_count`/`critical_reviewed_count`/`critical_unreviewed_count`.
- Frontend `FactReviewPanel`: kritischer Fakt-Badge, â€žkritisch ungeprÃ¼ft"-ZÃ¤hler,
  je Fakt Quellen-Beleg-Buttons (Seite N â†’ Viewer-Navigation), â€žKein Beleg
  verlinkt"-Hinweis, deutsche Fakt-Labels in Historie; `OverridePanel`-Placeholder
  zeigt `dates.start_date` als Beispiel; Panel h3 statt h4 (heading-order).
- ABIOMED: 7 relevante Fakten, alle mit evidence_count=1 und kritisch, alle
  â€žNicht geprÃ¼ftâ€œ, `critical_unreviewed_count=7`; kein Fakt mehr fÃ¤lschlich als
  `needs_review` markiert, weil belegt.

## Defensive Frontend-HÃ¤rtung (Teildaten)
- `ContractDetail`/`OverridePanel`/`FactReviewPanel`/`ImportStateBanner`: fehlende
  Teildaten (`tax_breakdown`, `price_development`, `overrides`, `audit_log`,
  `contract_review`, `import_state`) crashen nicht mehr (Optionals, leerer
  Tax-Fallback, â€žkeine PrÃ¼f-Ãœbersichtâ€œ); `scrollIntoView`-Guard (jsdom-extern
  fixiert), damit auch in Tests keine Not-implemented-Fehler.

## Dateien (Kern)
- `backend/app/documents/recovery.py`, `backend/app/contracts/detail/service.py`,
  `backend/app/contracts/detail/models.py`, `backend/app/contracts/review/
  material.py`, `backend/app/contracts/review/service.py`
- `frontend/lib/contract-detail-types.ts`, `frontend/components/contracts/detail/
  ContractDetail.tsx`, `FactReviewPanel.tsx`, `OverridePanel.tsx`,
  `ImportStateBanner.tsx`, `frontend/test/import.test.tsx` (erwarteter UI-Text)
- DB-Backfill: `contract.contract_number='40015645'` (ABIOMED)

## Tests / Ergebnis
- Backend: `backend/tests/test_uat_retest.py` (**33 passed**) fÃ¼r German-Date-
  Parsing, Nummern-/Titel-/Datums-/Kosten-Recovery, Event-Rule-Filter,
  Titel-Bau, Evidence-Seiten-AuflÃ¶sung, VerfÃ¼gbarkeit, Material-Leser,
  Review-Summary-ZÃ¤hler; `test_customer_demo_readiness.py` umgezogen
  (Reopen-Assert â€žunreviewed|needs_review"); gesamte direkt betroffene
  Backend-Suite grÃ¼n (80 Tests).
- Frontend: `npx tsc --noEmit` grÃ¼n, `next lint` 0 Warnings,
  `vitest run` **66 passed / 9 Dateien** (inkl. contracts-detail inkl. A11y).
- Live Ã¼ber :8000 (Backend-Neustart ohne `--reload`): Detail-Response fÃ¼r
  ABIOMED liefert Identity (p1), Datum (p5), Kosten-Beleg (p8),
  VerfÃ¼gbarkeit `manual_input_required`, 18 Evidence-EintrÃ¤ge mit korrekten
  Seiten, Fakt-Review-States mit Kritikal- und Evidence-ZÃ¤hlern; :3000 lÃ¤uft.

## Probleme / bekannte Grenzen
- AXIOM nicht erneut mit LLM bewertet (durchgÃ¤ngiges Vorhaben: kein
  LLM-/OCR-Rerun); Wiederholung nur demonstrativ auf gespiegelter Kopie.
- `contract_title` lautet â€žFull-Service-Vertrag ABIOMEDâ€œ (im Dokument wÃ¶rtlich
  so vorhanden); die Betreff-Zeile â€žâ€¦fÃ¼r das Impella AIC Systemâ€œ wird mangels
  passender Element-Struktur nicht angehÃ¤ngt (akzeptierter Verbatim-Zustand).
- Bei GerÃ¤t ohne Bezeichnung bleibt der Eintrag ehrlich leer (kein gefÃ¼llter
  Zeilenname erfunden).
- Smoke-Review-Zeilen des Siemens-Vertrags bleiben append-only bestehen.

## NÃ¤chster Schritt
- Manuelle UAT Abnahme abwarten. Danach (in Abstimmung): Schritt 16 â€“
  Benutzer/Login & Audit Minimalversion; kein neuer Hauptschritt vor
  Fortschrittsdatei-Abstimmung.

---

# UAT Re-Test & Nachrevision (Defect 1â€“4) â€“ kanonische Quellen, Scope-Drei-Zustand, System-IdentitÃ¤t, deutsche Labels (07.09.2026)

Status: KORRIGIERT (Backend + Frontend + fokussierte Regressionstests grÃ¼n;
manuelle UAT Abnahme steht aus â€“ keine Abnahme durch Code, kein PR-5/STEP 16)
Datum: 07.09.2026
Fortschritt: unverÃ¤ndert **15 / 18 = 83,3 %** (korrektive Nachrevision, kein
neuer Hauptschritt; PR-5/STEP 16 weiterhin offen)

## Ziel / Abgrenzung
- Re-Test der vier UAT-Defekte am ABIOMED-Vertrag (`40015645`, Contract
  `01a0743a-01d9-7248-8728-0df3b7c14bbd`, Org `krankenhaus`) Ã¼ber **generische**
  Fixes; kein PR-5, kein STEP 16, kein UI-Redesign, kein LLM-/OCR-/Ingestion-
  Rerun, kein voller Regressionenlauf, kein Commit/Reset. Keine hartcodierten
  ABIOMED-/Seiten-5-SonderfÃ¤lle; Seiten nie erfunden (genaue Geometrie nur,
  wenn vorhanden â€“ sonst ehrliche Seiten-Navigation).

## Defect 1 â€“ Kanonische Quell-Seite je Fakt (p3 vs. p5)
- Wurzel: `ContractDetail.evidenceFor` nahm per `find` den ersten Treffer in
  Evidence-Reihenfolge â€“ die dekorative Extrak-Ref `termination.evidence` (p3)
  gewann vor der wiederhergestellten `dates.start_date` (p5); keine Dedupe.
- Backend: `_settle_canonical_evidence` in
  `backend/app/contracts/detail/service.py` (Reihenfolge-stabil; `recovered:*`
  ersetzt fÃ¼r denselben `field_ref` die AI-Extraktions-Ref). `_dates_section`
  setzt je Laufzeitdaten-Fakt die eigene Evidence-Referenz
  `start_date_evidence`, `documented_end_evidence`, `duration_evidence`,
  `auto_renewal_evidence`; automatische VerlÃ¤ngerung: dokumentierter Wert
  schlÃ¤gt Extraktion und die Evidence wird gesetzt, sobald Recovery einen Wert
  liefert (nicht nur im Konfliktfall). Pydantic-Modelle in
  `backend/app/contracts/detail/models.py` um die vier Felder erweitert.
- Frontend `ContractDetail.tsx`: `evidenceFor` priorisiert `recovered:*`-Refs
  und exakte Feld-Treffer (exact > PrÃ¤fix, recovered > extrahiert); Laufzeit-
  Rules verlinken ihre eigene Evidence (Beginn â†’ `dates.start_date` p5,
  Ende â†’ `dates.end_date` p5, Laufzeit â†’ `dates.duration` p5, Automatische
  VerlÃ¤ngerung â†’ `termination.auto_renewal` p5).
- ABIOMED live: `dates.start_date` evidence =
  `recovered:dates.start_date`, Seite 5; Beginn/Ende/Laufzeit/Auto-Renew alle p5.

## Defect 2 â€“ Leistungsumfang: Drei-Zustand-Semantik
- Wurzel: Boolescher Ja/Nein-Vergleich ohne Beleg; â€žErwÃ¤hntâ€œ wurde nicht von
  â€žausdrÃ¼cklich im/ausgenommen" unterschieden; teilweise Falsch-Ausschluss von
  Verbrauchsmaterial (falsches Brillstein des Leistungsblocks).
- Backend: deterministische Analyse des persistierten kanonischen Texts in
  `_scope_text_analysis`/`_scope_concept_verdict`/`_scope_section`
  (`backend/app/contracts/detail/service.py`): Stufen 1a Inklusiv-Listen-Treffer
  â†’ 1b Anker-Seiten-Chunk (auÃŸer starker Ausschluss im selben StÃ¼ck) â†’ 2a KI-
  Ausschluss-Liste â†’ 2b ausdrÃ¼cklicher Ausschluss-Satz auf Gegen-Seiten
  (Teilmengen- und Anker-Seite geschÃ¼tzt) â†’ 3 nur erwÃ¤hnt â†’ 4 nicht belegt.
  `scope_status` (Status/Seite/Snippet/Evidence-Ref je Leistungsart) +
  `note_de` (Zusammenfassung); Snippets nutzen lesbaren Roh-Text. Neues Modell
  `ScopeStatusItem`; `ContractScopeSection.scope_status`/`note_de`.
- Frontend: Contract 360 Leistungsumfang rendert die Drei-ZustÃ¤nde
  â€žJa â€“ Inklusive Leistungâ€œ / â€žAusgeschlossenâ€œ / â€žErwÃ¤hnt â€“ zu prÃ¼fenâ€œ inkl.
  Evidence-Button zur Quell-Seite (CSS `.scope-status` `scope-ok/no/review`),
  `note_de` als Basis-Notiz; Fallback auf den bisherigen Booleschen-Block, wenn
  kein `scope_status` vorliegt.

## Defect 3 â€“ GerÃ¤te-IdentitÃ¤t (System â€žImpella AIC Systemâ€œ primÃ¤r)
- Wurzel: `_equipment_identity_value` zeigte nur Komponenten (â€žImpella
  Controllerâ€œ); die Betreff-Zeile â€žfÃ¼r das ImpellaÂ® AIC Systemâ€œ wurde nicht
  wiederhergestellt (Regex scheiterte: Capture-Klasse ohne Leerzeichen).
- Backend: `_find_system_identity` (+ toleranter `_SYSTEM_IDENTITY_RE` in
  `backend/app/contracts/detail/recovery.py`, OCR-Umlaut-tolerant) â†’
  `RecoveredIdentity.system_identity/_page/_region/_snippet`; `_identity_section`
  stellt `system_identity` (p1) bereit, `_recovered_evidence_refs` liefert die
  Evidence-Ref `identity.system_identity` p1; `_build_contract_title` fÃ¤llt auf
  das System zurÃ¼ck. `material._equipment_identity_value` fÃ¼hrt das System
  zuerst aus (â€žImpella AIC System | Impella Controllerâ€œ).
- Frontend: GerÃ¤te-Karte zeigt â€žSystem (aus Vertrag): Impella AIC Systemâ€œ +
  Seiten-Link; IdentitÃ¤ts-Karte fÃ¼hrt `system_identity` gedeutscht.

## Defect 4 â€“ Review-/Domain-Labels (deutsche Bezeichnungen)
- Backend: `OverrideDto`/`AuditEntryDto` s erhalten `label_de`
  (`_OVERRIDE_KEY_LABELS` + materiale `fact_label`-Fallback in
  `backend/app/contracts/detail/service.py`, `models.py`); `_fact_label_de`.
- Frontend: `OverridePanel` zeigt `label_de` (Fallback lokale Karte/Key),
  Audit-Historie ebenso; Platzhalter deutsch. `review/service.py` sortiert
  `evidence_list` mit `recovered:*`-Refs zuerst (Review zeigt belegte Seiten).

## Dateien (Kern)
- `backend/app/contracts/detail/recovery.py`, `service.py`, `models.py`
- `backend/app/contracts/review/material.py`, `service.py`
- `frontend/lib/contract-detail-types.ts`,
  `frontend/components/contracts/detail/ContractDetail.tsx`,
  `OverridePanel.tsx`, `frontend/app/globals.css`
- `backend/tests/test_uat_retest_defects.py` (neu, 22 Tests)

## Tests / Ergebnis
- Backend fokussiert: `test_uat_retest_defects.py` + `test_uat_retest.py`
  **51 passed**; direkt betroffene Unit-Suites (`test_contract_detail`,
  `test_uat_defect_batch_a`, `test_pr4_equipment_work_item`,
  `test_customer_demo_readiness`, `test_contract_models`) **75 passed**.
- Frontend: `npx tsc --noEmit` grÃ¼n; `npx vitest run test/contracts-detail.test.tsx`
  **9 passed** (inkl. bestehender â€žBeginnâ€œ-Fixture-Erwartung).
- Live (Backend :8000, Frontend :3000 laufen): API-Detail ABIOMED liefert
  `identity.system_identity` p1, `scope_status` korrekt (maintenance/
  inspection/repair/software_updates/spare_parts_included/consumables_included =
  included p7; calibration/remote_support/technical_support = not_established;
  emergency_service = excluded p3; `note_de`), Laufzeitdaten-Belege alle p5,
  `equipment.identity` = â€žImpella AIC System | Impella Controllerâ€œ;
  `/contracts/[contract-id]` kompiliert, HTTP 200, 18 Evidence-EintrÃ¤ge.

## Probleme / bekannte Grenzen
- Textuelle GUI-PrÃ¼fung (Rendering der Zwei-/Drei-ZustÃ¤nde, Klick-Navigation)
  erfolgt manuell im laufenden Frontend; Contenter final bestÃ¤tigt der manuelle UAT.
- AXIOM nicht erneut mit LLM bewertet (kein LLM-Rerun â€“ gewollt).
- `scope_status`-Snippets entstammen dem Roh-Text (OCR-Striche wie â€žwerdengesondertâ€œ)
  â€“ ehrlicher Verbatum-Zustand, keine GlÃ¤ttung.
- Smoke-Review-Zeilen des Siemens-Vertrags bleiben append-only bestehen.

## NÃ¤chster Schritt
- Manuelle UAT Abnahme anhand der 4 Re-Test-Defekte im laufenden :3000/:8000.
  Danach (in Abstimmung): Schritt 16 â€“ Benutzer/Login & Audit Minimalversion.

---

# PR-5 â€“ Visuelles Design-Migration + Backend-Archiv (07.09.2026)

Status: ABGESCHLOSSEN (Migration technisch fertig; visuelle Abnahme steht beim
manuellen UAT aus â€“ kein Commit, kein STEP 16)
Datum: 07.09.2026
Fortschritt: unverÃ¤ndert **15 / 18 = 83,3 %** (kein neuer Hauptschritt; das
Archiv ist Funktions-Support fÃ¼r den AufrÃ¤um-Workflow des letzten Designs)

## Ziel / Abgrenzung
- Frontend-Migration aller Seiten auf das freigegebene dunkle Enterprise-
  Design (`design-reference/medflux_final_design_system/`): Shell (Sidebar/
  Topbar), Ãœbersicht, VertrÃ¤ge, Contract 360, PrÃ¼fungen, Nachweise, Audit,
  Archiv, GerÃ¤te, Arbeitsliste, Import, Einstellungen. Nur echte Daten, keine
  Fixtures, kein `href="#"`, deutsche UI-Labels.
- Backend: nicht-destruktives, reversibles Archivieren von VertrÃ¤gen (neue
  Felder `is_archived`/`archived_at`), um Archiv-Navigation real zu verdrahten.
- Kein LLM-/OCR-/Ingestion-Rerun, keine neuen Hauptschritte, kein voller
  Backend-Regressionenlauf (nur fokussierte Archiv-Tests + Live-Check).

## Implementiertes

### Backend â€“ Archiv (reversibel, nicht-destruktiv)
- `backend/app/api/routes/contracts.py`: Query `archived` auf `contract_list`
  (Filter-Semantik: `archived=false` â†’ nur nicht archiviert; `archived=true` â†’
  nur Archiv; default weiterhin Nicht-Archiv); POST `/{contract_id}/archive`
  und `/{contract_id}/unarchive` (org-scoped, `lifecycle_state=="active"`,
  UTC-`archived_at`, RÃ¼ckgabe `ContractDetailResponse` inkl. `is_archived`);
  Helper `_set_archived`.
- Migration `backend/alembic/versions/20260907_a4b7c9d2e0f1_add_contract_archive.py`
  (Down-Revision `fb2e6c8d1a54`): `is_archived` Boolean NOT NULL server_default
  false, `archived_at` timestamptz nullable, Index `ix_contract_org_is_archived`;
  angewendet auf Head, Spalten live verifiziert.
- `dashboard/service.py`, `equipment/service.py` (Liste + Detail-Links),
  `work_queue/service.py` (offene Punkte) schlieÃŸen archivierte VertrÃ¤ge
  kategorisch aus; Detail-Service/`ContractDetailResponse` fÃ¼hren
  `is_archived`/`archived_at` mit.

### Frontend â€“ Design-System (Token + Shell)
- `globals.css`: `:root` auf die dunkle Palette umgestellt (inkl. `--accent-soft`,
  Status-/Severity-Farben, `--radius:18px`, `--shadow`) + umfangreicher
  PR-5-Block: `.app`-Grid (240px Sidebar), `.sidebar`/`.brand`/`.side-nav`/
  `.nav-item` (SVG-Icons), `.side-bottom`/`.side-ai`/`.org-card`, `.topbar`,
  `.search`, `.import-btn`, `.page`/`.content` (max 1700px), `.panel`/`.panel-head`,
  `.card`/`.detail-card` (Radius 18), `.kpi-card`-Akzentkante, dunkle `.btn`-
  Varianten, `.state-box`, `.tag`, `.intel-strip`/`.intel`, `.dash-grid`,
  `.queue-item`/`.queue-bar`, `.risk-card`, `.lower-grid`, `.freshness-pill`,
  `.audit-grid`, `.breadcrumb`, `.badge-archived` + Override-Dunkel fÃ¼r alte
  Light-Hartcodes.
- `layout.tsx` + neues `components/ClientNav.tsx` (App-Shell): Sidebar mit
  drei Gruppen (Arbeitsbereich: Ãœbersicht/VertrÃ¤ge/Arbeitsliste/GerÃ¤te/Import;
  Kontrolle: PrÃ¼fungen/Nachweise/Audit/Archiv; System: Einstellungen),
  `aria-current="page"`, `Hauptnavigation`-Landmarke, Liveness-Punkt via
  `/api/health`, Organisations-Karte; Topbar mit Seitentitel, globaler Suche
  (â†’ `/contracts?q=`), â€žVertrag importierenâ€œ; Skip-Link â†’ `#main-content`.

### Frontend â€“ Seiten
- Ãœbersicht (`app/page.tsx`): Intel-Strip-KPIs, Dash-Grid (Handlungsbedarf /
  FristenÃ¼bersicht), Lower-Grid (KostenÃ¼bersicht / Manuelle PrÃ¼fung &
  DatenqualitÃ¤t), Datenstands-Zeile mit Freshness-Pill, `.state-box`-Leerzustand.
- VertrÃ¤ge-Liste: in `.panel` gefasst, `.state-box`-LeerzustÃ¤nde (Texte
  unverÃ¤ndert â€žNoch keine VertrÃ¤ge vorhanden.â€œ / â€žKeine VertrÃ¤ge fÃ¼r die
  gewÃ¤hlten Filter gefunden.â€œ).
- New: `app/review/page.tsx` (requires_review=true + â€žPrÃ¼fenâ€œ-Link),
  `app/nachweise/page.tsx` (Vertrags-Selektor â†’ Quellenliste + PdfViewer +
  EvidencePane), `app/audit/page.tsx` (Vertrags-Selektor â†’ contract_review-
  Zusammenfassung + audit_log + fact_reviews), `app/archiv/page.tsx`
  (archived=true-Liste + Un-Archivieren-Aktion mit Reload).
- Contract 360: Breadcrumb (â€žVertrÃ¤ge / Nr.â€œ), Archiv-Badge + Archivieren/
  Wiederherstellen-Button (POST archive|unarchive + `onReload`); Headline-
  Zeile zeigt Archivdatum.
- GerÃ¤te-/Arbeitslisten-/Import-/Einstellungs-Seiten: `.panel`-Rahmen,
  `.state-box`-LeerzustÃ¤nde, `<main>`-Wrapper auf `.page`-Divs normiert (kein
  verschachteltes `<main>` in der Shell).
- `ContractTable`: optionale Extraspalte (colSpan 10) fÃ¼r PrÃ¼fungen/Archiv.

## Dateien (Kern)
- Backend: `backend/app/api/routes/contracts.py`, `backend/app/contracts/search/
  service.py`+`models.py`, `backend/app/contracts/detail/service.py`+`models.py`,
  `backend/app/dashboard/service.py`, `backend/app/equipment/service.py`,
  `backend/app/work_queue/service.py`,
  `backend/alembic/versions/20260907_a4b7c9d2e0f1_add_contract_archive.py`,
  `backend/tests/test_contract_archive.py`
- Frontend: `frontend/app/globals.css`, `frontend/app/layout.tsx`,
  `frontend/components/ClientNav.tsx`, `frontend/app/page.tsx`,
  `frontend/app/contracts/page.tsx`, `frontend/app/contracts/[contract-id]/page.tsx`,
  `components/contracts/detail/ContractDetail.tsx`,
  `components/contracts/ContractTable.tsx`, neue Seiten `app/{review,nachweise,
  audit,archiv}/page.tsx`, Umbauten `app/{equipment,work-queue,import,settings}/`
  sowie `app/equipment/[equipment-id]/page.tsx`,
  `frontend/lib/contract-types.ts`, `frontend/lib/contract-detail-types.ts`

## Tests / Ergebnis
- Backend fokussiert: `test_contract_archive.py` (8 Tests) +
  `test_contract_search.py` **43 passed**; `test_dashboard.py` +
  `test_pr4_equipment_work_item.py` **39 passed**; Live-`archive`â†’
  `is_archived=true`, Live-`unarchive`â†’`is_archived=false` Ã¼ber :8000.
- Frontend: `npx tsc --noEmit` grÃ¼n; `next lint` 0 Warnings;
  `npx vitest run` **66 passed / 9 Dateien**; `npm run build` erfolgreich
  (alle 13 Routen, statisch/dynamisch korrekt).
- Live :3000: alle 12 Routen HTTP 200 nach Backend-Neustart (OpenAPI enthÃ¤lt
  die Archiv-Routen); ABIOMED-Detail (BASIS) rendert inkl. Archiv-Aktion.

## Probleme / bekannte Grenzen
- Laufende Server vor dem Neustart hatten den Archiv-Stand nicht (Docker des
  Uvicorn-`--reload`); nach sauberem Neustart sind Archiv-Routen live.
- `/` lieferte einmalig 500 nach dem `next build` (`.next`-Ãœberschreibung im
  laufenden Dev-Server); erneuter Request und alle Routen danach 200.
- Audit/Nachweise sind vertragsbezogen real verdrahtet (Navigationsziel
  Referenz-â€žAudit" ist kein Fake-Destinations-Dummy).
- Visuelle Endabnahme (Kontrast, AbstÃ¤nde, Icon-Passung) erfolgt durch den
  manuellen UAT; der schriftliche Fortschritt bleibt 15/18.

## NÃ¤chster Schritt
- Manuelle UAT-Abnahme der Design-Migration + des Archiv-Workflows im laufenden
  Frontend (:3000) / Backend (:8000). Danach (in Abstimmung): Schritt 16 â€“
  Benutzer/Login & Audit Minimalversion (kein neuer Hauptschritt vor
  Fortschrittsdatei-Abstimmung).

---

# UAT-Befund 1 â€“ VollstÃ¤ndiges Interaktions-Audit (PR-5 Defect Batch 1)

**Status:** ABGESCHLOSSEN (Befunde behoben; Fortschritt bleibt 15/18 â€“ die
Endabnahme erfolgt nach der manuellen UAT-RÃ¼ckschau des Kunden)

**Datum:** 08.09.2026

## Ausgangslage (gemeldete Defekte)
1. Dashboard blieb im â€žDashboard wird geladenâ€¦â€œ-Zustand hÃ¤ngen.
2. Topbar â€žVertrag importierenâ€œ navigierte nicht.
3. Einstellungen â€žKI-Verbindung testenâ€œ fÃ¼hrte keine Aktion aus.
4. Einige Settings-Async-LadezustÃ¤nde lÃ¶sten sich nicht auf.

## Ursachenanalyse
- **Gemeinsame Wurzel (A): Der API-Layer hatte gar keine Timeouts.**
  `frontend/lib/api.ts` (apiGet/apiPost/apiPatch) und der interne
  Content-Fetch von `PdfViewer.tsx` hingen bei einem blockierten Backend
  unbegrenzt â†’ Ladezustand â€žunendlichâ€œ. Live-Antworten des Backends waren im
  Audit-Zeitraum gesund (Dashboard ~2 s, ai/status + ai/test ~4 s, demo ~2 s);
  die Symptome traten bei einem gehÃ¤ngten/alten Serverzustand auf.
- **Befund (B): `ClientNav` prÃ¼fte /api/health â€“ der Backend-Endpunkt heiÃŸt
  `/health`.** Damit meldete die Shell bei gesundem Backend dauerhaft
  â€žOfflineâ€œ (roter Status-Dot). Dies ist der einzige echte
  Verbindungs-Layout-Defekt im Befund.
- **Befund (C): Detail-Laden in Nachweise/Audit teilte den Fehlerzustand mit
  der Vertragsliste.** Schlug das Vertragsdetail fehl, verschwand die gesamte
  Sektion samt Auswahlbox â†’ Sackgasse ohne Retry. ZusÃ¤tzlich luden beide
  Seiten die Liste bei jedem `contractId`-Wechsel neu (Flackern/Race).
- **Befund (D): FehlerzustÃ¤nde ohne Wiederhol-Aktion** (VertrÃ¤ge, Dashboard,
  GerÃ¤te-Liste/-Detail, Arbeitsliste, PrÃ¼fung, Archiv, Einstellungen
  Demo-Bereich) boten keinen â€žErneut ladenâ€œ-Button.

## Implementiertes
- `frontend/lib/api.ts`: `fetchWithTimeout` (AbortController) mit
  Standard-Timeout 20 s fÃ¼r apiGet/apiPost/apiPatch, pro Aufruf Ã¼bersteuerbar
  (0 = ohne). `apiUpload` bleibt bewusst ohne Standard-Timeout (Import-Analyse
  lÃ¤uft ggf. minutenlang). Kein Ladezustand kann mehr endlos hÃ¤ngen.
- `PdfViewer.tsx`: Content-Fetch mit 30-s-Timeout und Abort beim Unmount;
  Fehlerzustand bekommt â€žErneut ladenâ€œ.
- `ClientNav.tsx`: Health-Check zeigt jetzt auf den echten Endpunkt `/health`.
- `nachweise/page.tsx` + `audit/page.tsx`: eigener `detailError`-Zustand,
  Retry-Button im Detail-Fehler, Liste wird nicht mehr pro Vertrag neu
  geladen (Auto-Select einmalig per funktionalem setState).
- â€žErneut ladenâ€œ in allen Fehlerpfaden: Overview, VertrÃ¤ge, GerÃ¤te (+Detail),
  Arbeitsliste, PrÃ¼fung, Archiv, Nachweise (Liste + Detail), Audit (Liste +
  Detail), Einstellungen (Demo-Bereich).

## Verifikation
- Frontend-Tests: `npx vitest run` **77 passed / 11 Dateien** (2 neue Dateien:
  `api-timeout.test.ts` â€“ garantierte Terminierung des API-Layers;
  `interaction-audit.test.tsx` â€“ Import-CTA-Link, Topbar-Suche, Health-Pfad,
  Dashboard-Retry, Settings-Test (erfolgreich + ehrlicher Fehler), Nachweise
  Detailfehler/Retry).
- `npx tsc --noEmit` grÃ¼n; `next lint` 0 Warnings; `npm run build` erfolgreich
  (13 Routen).
- Live :3000: alle 11 Routen HTTP 200 nach sauberem Dev-Neustart.
- Live :8000 (frischer Uvicorn): `/health` ok; `/api/ai/status`
  `available=false` (Ollama lÃ¤uft nicht) und `/api/ai/test` ehrlicher
  Fehlertext â€“ beide ZustÃ¤nde werden in den Einstellungen korrekt angezeigt,
  kein erfundener Erfolg. Archiv-Roundtrip (archive â†’ archived 0â†’1 â†’
  unarchive â†’ 0) live verifiziert.

## Bekannte Grenzen / Hinweise fÃ¼r UAT
- Beide Server mussten nach dem `next build` als vollstÃ¤ndig gelÃ¶ste
  Prozesse (Win32_Process) neu gestartet werden; laufende Prozesse dÃ¼rfen
  ihren Build-Ordner nicht mit `npm run build` teilen.
- Demo-Arbeitsbereich ist **aktuell aktiv** (8 VertrÃ¤ge, Liste zeigt 1
  sichtbaren Vertrag: 40015645 ABIOMED). Sichtbarkeit ist dadurch
  arbeitsbereichsbezogen; wird im UAT zentral geprÃ¼ft.
- Kein neuer Hauptschritt, kein Commit.

## NÃ¤chster Schritt
- Manuelle UAT-RÃ¼ckschau des Kunden auf Basis dieses Befunds; danach (in
  Abstimmung) Schritt 16 â€“ Benutzer/Login & Audit Minimalversion.

---

# UAT-Befund 2 â€“ Defekt-Batch Aâ€“H (PR-5)

**Status:** ABGESCHLOSSEN (Befunde behoben und verifiziert; Fortschritt bleibt 15/18 â€“ kein neuer Hauptschritt)

**Datum:** 08.09.2026

## Ausgangslage (gemeldete Defekte)
1. Daten-Isolation: Backend-Tests griffen auf die Produkt-DB zu (fehlende Session/Transaction-Isolation; Alembic nicht idempotent auf sauberem Schema).
2. Arbeitsliste (Work Queue): GET /api/work-queue lieferte bei aktiver Produkt-DB eine 500 (pydantic ValidationError).
3. Contract 360: Scroll-Position verlor sich bei jeder Detail-Aktualisierung.
4. Nachweise/Evidenz: Bounding-Boxen wurden als exakte Markierungen gezeichnet, obwohl MEDTRON-Coordinaten fast die ganze Seite umfassen (Unehrlichkeit).
5. E: Aktionen ohne Benutzer-Feedback (kein Toast-System).
6. F: Import zeigte vorgetÃ¤uschte Fortschritts-Prozente; kein Retry fÃ¼r fehlgeschlagene Analysen.
7. G: â€žLight-Enterprise-Design-Tokensâ€œ â€“ Konsistenz abseits der freigegebenen Palette.
8. H: Deutsche LeerzustÃ¤nde an allen fÃ¼r leere Daten relevanten Stellen.

## Ursachenanalyse
- A: `backend/conftest.py` nutzte das produktschema (SQLite same-file); Sessions/Commits liefen auf der echten `data/`-DB; die Alembic-Migration erzeugte ohne Vorzustand einen zweiten unique index (nicht idempotent).
- B: `_collapse_sibling_duplicates` in `work_queue/service.py` merge clean `references` (eine Dict-Spalte) zu einer Liste â†’ `WorkItemSummary.references` (dict|null) warf zur Laufzeit.
- C: `app/contracts/[contract-id]/page.tsx` bedingte das gesamte ContractDetail auf `!loading` â†’ jeder Reload unmountete die Seite und setzte den Scroll zurÃ¼ck.
- D: Es fehlte eine ehrliche Klassifikation der Bounding-Box-GrÃ¶ÃŸe (exakt = lokalisierte WÃ¶rter; grob = Seitenbereich).
- E/G: Kein Toast-System; im Zuge der visuellen Konsistenz lagen vereinzelte Farb-Hartcodes auÃŸerhalb der Token-Palette.
- F: Der Import-Shirin zeigte fake-% (Fortschritt â€žglattâ€œ gemessen); ein Retry-Weg fehlte.
- H: LeerzustÃ¤nde waren weitgehend vorhanden, aber nicht fÃ¼r alle Zielseiten geprÃ¼ft/abgesichert.

## Implementiertes

### A â€“ Test-Schema-Isolation (Backend)
- `backend/conftest.py`: In-Memory-SQLite via `SQLITE_MEMORY`-Env vor Imports; jede Test-Session mit Migration(skopf) erzeugt, Produkt-DB unberÃ¼hrt; DB-Layer auf Nightly-Head angewendet.
- Alembic-Downchain gefixt: Headpfad idempotent von leer (kein doppelter `ix_contract_org_is_archived`); Schritt-Dokumentation in `docs/`.
- Produkt-Cleanup: 1 Organisations-, 1 Vertrag-, MEDTRON-Bestand (GerÃ¤te, Docs, Evidence, Facts, Work-Items); Backups unter `data/backups/pre-cleanup-20260908-*.json`, Restore-Skript `scripts/restore_from_backup.py`.

### B â€“ Work-Queue (Backend + Daten)
- `work_queue/service.py`: `_collapse_sibling_duplicates` merzt nur noch `source_field_refs` (keep `references` des Keepers unangetastet); Transitionen openâ†’acknowledged/resolved, acknowledgedâ†’resolved (resolved terminal), Fehler â†’ 422 (PersistenceError), SQL-Seitige Filterung nach `active`.
- Datenfix: 5 Produkt-Rows mit `references=[]` â†’ NULL; Reconcile-Skript `scripts/reconcile_medtron_queue.py` ergab 4 aktive Items (keine Duplikate).

### C â€“ Scroll-Position bei Reload (Frontend)
- `app/contracts/[contract-id]/page.tsx`: Stale-while-revalidate â€“ altes ContractDetail bleibt bei Reload gemountet, Ladezeile nur ohne Daten; bei Fehler mit vorhandenen Daten dezente, non-blocking Meldung â€žAktualisierung fehlgeschlagen â€“ die Anzeige zeigt den zuletzt geladenen Stand.â€œ

### D â€“ Ehrliche Evidenz-Geometrie (Frontend, keine Datenmutation)
- `lib/source-geometry.ts`: `A4_POINTS` (595.28Ã—841.89), `bboxPageFraction`, `evidencePrecision()` â†’ `exact`/`coarse`/`none` (coarse bei FlÃ¤chenanteil â‰¥ 30 %; negative Koordinaten â†’ `none`/null); `resolveEvidenceRect` lehnt negative BBoxen ab.
- `PdfViewer.tsx`: grobe Markierungen gestrichelt/weich mit Label â€žungefÃ¤hre Lage (Seitenbereich)â€œ; Infozeile unterscheidet â€žQuelle (Seitenbereich) hervorgehobenâ€œ, â€žungefÃ¤hre Lage auf Seite N (keine exakte Position)â€œ, â€žohne exakte Positionâ€œ.
- `ContractDetail.tsx`/`EvidencePane.tsx`: Pill â€žUngefÃ¤hre Lageâ€œ statt â€žPositionsbestimmtâ€œ; Hinweistext bei grober Lage.

### E â€“ Toast-System (Frontend)
- `components/ui/Toast.tsx`: `ToastProvider` + `useToast` (success/error/info, `TOAST_DURATION_MS=5000`, Viewport unten rechts, `aria-live="polite"`, role status/alert, Stapel max. 5 via `slice(-4)`).
- `app/layout.tsx`: Provider um die App; `app/work-queue/page.tsx`: Success-Toasts bei status-Transitions. Bestehende Inline-Meldungen (FactReviewPanel, Archiv) unverÃ¤ndert.
- `globals.css`: `.toast-viewport`, `.toast`, Varianten; Toast-Styles strikt Ã¼ber Tokens (`--surface-3`, `--text`, `--border`, `--shadow`, `--success/--danger/--info`, `--radius-sm`).

### F â€“ Ehrlicher Import-Fortschritt + Such-/Filter-Verifikation
- `backend/app/documents/schemas.py`: `ImportFileResult` + `document_version_id` (nullable); `backend/app/api/routes/documents.py` befÃ¼llt das Feld aus `processed.document_version_id`.
- `frontend/app/import/page.tsx`: ehrlicher Ladezustand ohne Fake-Prozente (Phasenliste Uploadâ†’Lesenâ†’OCR nur bei gescannten Seitenâ†’Extraktionâ†’PrÃ¼fungâ†’Berechnungâ†’fertig/fehlgeschlagen), â€žErneut verarbeitenâ€œ-Button fÃ¼r `analysis_failed`/`failed` mit `document_version_id` (POST `/api/documents/{dv}/retry`, Toast-Feedback, `retryingId`).
- F2 (Suche/Filter): Backend `STATUS_ALLOWLIST`/`RISK_ALLOWLIST` matchen die Frontend-Labels â€“ keine Fake-Dimensionen gefunden, kein Echange nÃ¶tig.

### G â€“ Design-Token-Konsistenz (Frontend)
- Referenz (`design-reference/medflux_final_design_system`) ist das dunkle Enterprise-System; `globals.css` implementiert die Palette bereits token-for-token (â”€â”€bgâ”€â”€ etc.). Abgleich: verbliebene ad-hoc Hartcodes entfernt, Toast-Komponente (E) auf Token-Werte umgestellt; keine Palette erfunden, kein â€žLightâ€œ hinzugefÃ¼gt (Referenz definiert dunkel).

### H â€“ Deutsche LeerzustÃ¤nde (Frontend)
- Verifiziert/abgesichert: VertrÃ¤ge â€žNoch keine VertrÃ¤ge vorhandenâ€œ, Arbeitsliste â€žKeine offenen Arbeitspunkteâ€œ, Nachweise â€žKeine VertrÃ¤ge verfÃ¼gbarâ€œ, Ãœbersicht â€žKeine Arbeitsdaten verfÃ¼gbarâ€œ, Audit â€žKeine VertrÃ¤ge verfÃ¼gbarâ€œ, Archiv â€žKeine archivierten VertrÃ¤geâ€œ, PrÃ¼fungen â€žKeine offenen PrÃ¼fungenâ€œ, GerÃ¤te â€žKeine GerÃ¤te vorhandenâ€œ, Import â€žNoch keine Dateien ausgewÃ¤hlt.â€œ, Kosten â€žKeine verlÃ¤sslichen Kosten verfÃ¼gbar.â€œ
- Neuer Test `frontend/test/empty-states.test.tsx` pinned die zuvor ungetesteten Pfade.

## Dateien (Kern)
- Backend: `backend/conftest.py`, `backend/app/database/base.py`/`session.py`, `backend/alembic/versions/20260903_d2b3a5c0f4e1_add_contract_equipment_logical_finger.py`, `backend/app/work_queue/service.py`, `backend/app/documents/schemas.py`, `backend/app/api/routes/documents.py`
- Skripte: `scripts/cleanup_product_db.py`, `scripts/restore_from_backup.py`, `scripts/reconcile_medtron_queue.py`
- Frontend: `app/contracts/[contract-id]/page.tsx`, `lib/source-geometry.ts`, `components/contracts/detail/{PdfViewer,ContractDetail,EvidencePane}.tsx`, `components/ui/Toast.tsx`, `app/layout.tsx`, `app/work-queue/page.tsx`, `app/import/page.tsx`, `lib/types.ts`, `app/globals.css`
- Tests (neu): `frontend/test/{contract-detail-reload-scroll,source-geometry,evidence-pane-geometry,toast,empty-states}.test.tsx`; angepasst: `frontend/test/contracts-detail.test.tsx` (useRouter-Mock), `frontend/test/import.test.tsx` (apiPost-Mock); Backend: `backend/tests/test_work_queue_state_machine.py`, `test_pr4_equipment_work_item.py`

## Tests / Ergebnis
- Backend fokussiert: `test_work_queue_state_machine.py` + `test_pr4_equipment_work_item.py` + `test_document_import.py` â†’ **35 passed**.
- Frontend fokussiert (14 Dateien): toast, work-queue, import, source-geometry, evidence-pane-geometry, contracts-detail, empty-states, contract-detail-reload-scroll, contracts, dashboard, fact-confirm-display, fact-confirm-reviewer, review-chip-nav, archive-confirm, shell â†’ **70 passed**.
- `npm run lint`: 0 Warnings/Errors (inkl. fixes fÃ¼r useCallback-Dependency `toast`).
- Live: Backend-Sauberneustart (eine Instanz, 127.0.0.1:8000); OpenAPI enthÃ¤lt `ImportFileResult.document_version_id`; GET /api/work-queue?active=true â†’ 3 aktive Items (kein Duplikat; ein Item wurde wÃ¤hrend der B-Verifikation per PATCH bewusst als â€žerledigtâ€œ markiert und verschwindet dadurch aus der aktiven Liste â€“ legitime, persistente Benutzer-Aktion).

## Probleme / bekannte Grenzen
- Vor dem Sauberneustart liefen zwei uvicorn-Instanzen (Repo-venv + System-Python310) um Port 8000; gestoppt, eine frische Instanz gestartet.
- Audit/Nachweise/empty-states nur fokussiert geprÃ¼ft; kein voller 16/18-Suite-Lauf (abgestimmt).
- G: Die UI ist bewusst das dunkle Enterprise-Design der freigegebenen Referenz; â€žLightâ€œ wurde nicht erfunden.

## NÃ¤chster Schritt
- Manuelle UAT-RÃ¼ckschau zu Batch Aâ€“H im laufenden Frontend (:3000) / Backend (:8000). Danach (in Abstimmung) Schritt 16 â€“ Benutzer/Login & Audit Minimalversion (kein neuer Hauptschritt vor Fortschrittsdatei-Abstimmung).

---

# UAT-Befund 3 – Provider-unabhängige lokale KI + unabhängige Scroll-Bereiche (PR-5 Re-Test)

**Status:** ABGESCHLOSSEN (Fortschritt bleibt 15/18 – kein neuer Hauptschritt)

**Datum:** 09.09.2026

## Ausgangslage / Anforderungen
- Anforderung: Die KI-Schicht darf sich nicht auf Ollama/LM Studio/llama.cpp/Qwen allein festnageln. Provider sollen sicher erkennbar, Capabilities ehrlich normalisiert und die aktive Auswahl dauerhaft gepersistet sein. Gespeicherte Auswahl gilt, sobald gesetzt (Bootstrap-Werte aus der Umgebung als Fallback); kein stiller Fallback auf einen anderen Provider.
- Defekt I: Evidence-Liste und PDF-Ansicht teilten sich den Seiten-Scroll, statt unabhängig zu scrollen.
- Randbedingungen: Discovery läuft ausschließlich lokal (localhost), endlich (ai_discovery_timeout_seconds=2.0), ohne Vertragsinhalte und ohne Inferenz; die neue Abstraktion trägt strukturierte Ausgaben, max_tokens und Capability-Abfragen (Harness v2 nicht angefasst).

## Implementiertes (Backend)
- `app/core/config.py`: `lmstudio_base_url` (http://127.0.0.1:1234), `llama_cpp_base_url`, `generic_openai_base_url`, `ai_discovery_timeout_seconds` (2.0).
- `app/ai/schemas.py`: `ModelCapabilities` (text/vision/embedding: bool|None), `ModelDescriptor`, `ProviderInfo`, `SelectionInfo`, `AISnapshot`, `SelectionUpdate`; `ModelInfo/AIStatus/AITestRequest/AITestResponse` unverändert.
- `app/ai/base.py`: `AIProvider` ABC mit provider_id/display_name/kind/supports_structured_output, Modell-Resolver, `default_model -> settings.ollama_model`; abstraktes `discover_models()`.
- Provider: `providers/ollama.py` (Discovery GET /api/tags + POST /api/show enrichment; Vision autoritativ über `model_info`-Keys `.vision.*` bzw. Vision-Familien; Text-Fähigkeit über Embedding-Ausschlussfamilien; Kontext über `{arch}.context_length` – live verifiziert: qwen3-vl 262144, qwen3:8b/14b 40960, aya-expanse 8192), `providers/openai_compat.py` (Basis `/v1`-Chat, ids-only-Fallback mit ehrlichem `None` für unbekannte Fähigkeiten), `providers/lmstudio.py` (native v1-/v0-Signatur mit loaded/context/quant/architecture; Erkennung nur bei nativer Signatur), `providers/llamacpp.py` (Erkennung über `/props` bzw. `/health`; Kontext über `default_generation_settings.n_ctx`; leere Konfig ist ehrlich "nicht konfiguriert"), `providers/generic.py` (generic-openai mit Endpunkt-Override).
- `app/ai/providers/registry.py`: ProviderSpec-Registry, `build_provider` (Endpunkt-Override nur für generic-openai), `endpoint_for`, `UnknownProviderError`.
- `app/ai/providers/discovery.py`: `discover_providers` (spezifische Reachability-Sonden je Provider, Generic-Fallback nur für identifizierte `/v1/models`-Endpunkte, Anreicherung der Modellliste mit importeigenen Meldungen, keine Inferenz), `probe_provider_reachable`.
- Auswahl/Persistenz: `app/database/models/application_setting.py` (neue Migration `20260909_a4b8c9d2e0f2_add_application_setting.py`, auf Live-DB angewendet `a4b7c9d2e0f1 -> a4b8c9d2e0f2`), `app/database/ai_selection.py` (Schlüssel `ai_provider`, `ai_model`, `ai_provider_endpoint`; DELETE bei None), `app/ai/settings_service.py` (DB vor Environment), `app/ai/selection.py` (`build_selection` – unbekannter/nicht erreichbarer Provider oder fehlendes Modell => `unavailable` mit deutscher Meldung, Ziel-IDs bleiben erhalten, kein stiller Fallback).
- `app/ai/service.py`: AIService löst Auswahl über settings_service (active_provider_id/active_model_id pro Request), `_ensure_provider` baut den Adapter bei Provider-Wechsel neu; alte Status-Meldungen (C) von test_ai.py bleiben kompatibel.
- `app/api/routes/ai.py`: `GET /api/ai/status`, `GET /api/ai/snapshot` (Discovery/Selection), `POST /api/ai/test`, `PUT /api/ai/selection` (Validierung: unterstützter Provider, lokaler Endpunkt für generic-openai, Erreichbarkeits-Probe, Modell in discover_models(); speichert; liefert frischen Snapshot; deutsche 400-Details). `app/main.py`: CORS-PUT erlaubt. `.env.example` um neue Provider-Variablen ergänzt.

## Implementiertes (Frontend)
- `lib/api.ts`: `apiPut` (Fehler-Body-Detail wird ehrlich übernommen); `lib/ai-types.ts`: Capabilities/Provider/Selection/Snapshot-Typen.
- `app/settings/page.tsx`: neu gegliederte Einstellungen-IA (Allgemein, Lokale KI, Dokumentenverarbeitung, Speicher & Daten, Benutzer & Sicherheit, System & Diagnose), snapshot-getrieben, Provider→Modell-Interaktion, Capability-Chips (Text/Vision/Bild/Embedding), aktive Auswahl mit Zustands-Badges (Bereit / Nicht verfügbar / Nicht erreichbar), Speichern via PUT mit Toast "KI-Auswahl gespeichert." und ehrlichen Inline-Fehlern, Erweiterte Einstellungen (Auswahl-Quelle, Bootstrap, Endpunkte), Diagnose "KI-Verbindung testen".
- `components/ui/Toast.tsx`: Toast-Viewport bekommt `role="region"` (axe: aria-label auf div erforderte erlaubte Rolle); `globals.css`: Styles für `.form-field/.select/.capability-chips/.advanced-details` und Formulare in den Einstellungen.

## Defekt I – Unabhängige Scroll-Bereiche (Evidence/PDF)
- `globals.css`: `.detail-main` und `.detail-aside` als eigene Scroll-Container (`overflow-y: auto; max-height: min(calc(100dvh - 300px), 1200px)`); `.detail-viewer` als eigenständiger Bereich (`height: calc(100dvh - 150px); min-height: 480px`), `.pdf-viewer`/`.pdf-stage` flexibel (`flex: 1; min-height: 0; overflow: auto`) – die PDF-Seite scrollt jetzt im eigenen Bereich, ohne die Evidence-Liste abzurollen.
- Responsive (≤900px): zurück zu natürlichem Fluss (Spalten ohne fixe Höhe, `.pdf-stage` max. 72dvh) – mobile Geräte folgen weiterhin dem Seitenfluss.
- Neuer Struktur-Test `frontend/test/detail-scroll-layout.test.tsx` verankert drei getrennte Regionen (Faktenspalte, Quellenangaben, Quelle anzeigen) und die Vollständigkeit der Evidence-Liste in der Seitenleiste.

## Dateien (Kern)
- Backend: `app/ai/{base,service,schemas,selection,settings_service}.py`, `app/ai/providers/{ollama,openai_compat,lmstudio,llamacpp,generic,registry,discovery}.py`, `app/core/config.py`, `app/database/{ai_selection.py, models/application_setting.py}`, `app/api/routes/ai.py`, `app/main.py`, `alembic/versions/20260909_a4b8c9d2e0f2_add_application_setting.py`, `.env.example`.
- Backend-Tests: `tests/test_ai_provider_discovery.py` (10), `tests/test_ai_selection.py` (16); kompatibel: `tests/test_ai.py` (24).
- Frontend: `app/settings/page.tsx`, `lib/api.ts`, `lib/ai-types.ts`, `components/ui/Toast.tsx`, `app/globals.css`.
- Frontend-Tests: neu `test/settings.test.tsx` (8), `test/detail-scroll-layout.test.tsx` (3); angepasst `test/interaction-audit.test.tsx` (7).

## Tests / Ergebnis
- Backend fokussiert: **50 passed** (test_ai_provider_discovery + test_ai_selection + test_ai) in 1.86 s; Discovery-Tests belegen u. a. "keine Inferenz während Discovery/Selection" und ehrliche Capability-Normalisierung (vision nur bei autoritativen Belegen, z. B. `smol-vl`-Name wird nicht als Vision gewertet).
- Frontend: fokussiert 18 passed (settings 8, interaction-audit 7, detail-scroll-layout 3); Gesamtlauf **117 passed / 21 Dateien**.
- `npx tsc --noEmit` grün; `next lint` 0 Warnings/Errors.
- Live: `GET /api/ai/snapshot` 200 mit `selection.state=ready`, `message_de="Bereit: 'Ollama' mit Modell 'qwen3:8b'."`, Ollama native erkannt, Modelle mit korrekten Capabilities und Kontextlängen; `GET /api/ai/status` 200; `/health` ok; Frontend :3000 200. Migration auf Live-DB angewendet.

## Probleme / bekannte Grenzen
- Der Backend-Prozess läuft nach dem früheren Aufräumen ohne `--reload` weiter; der Listener auf 8000 ist aus dieser Session nicht sauber aufzulösen (netstat meldet PID 14564, tasklist kennt den Prozess nicht – Session-/Proxy-Kontext) und wurde deshalb bewusst NICHT neu gestartet, um die laufenden Dienste nicht zu riskieren. Dienste antworten mit aktuellem Code.
- Kein voller 18/18-Gesamtlauf (abgestimmt, fokussierte Tests); keine Datenmutationen, keine neuen Imports/OCR/Modelländerungen in dieser Runde.
- generic-openai erlaubt nur lokale Endpunkte; die Auswahl erfolgt über den persistenten Endpunkt-Abgleich.

## Nächster Schritt
- Manuelle UAT-Rückschau der Einstellungen (Anbieterauswahl, Speichern/Neustart-Überleben, Diagnose) und der unabhängigen Scroll-Bereiche im laufenden Frontend (:3000) / Backend (:8000). Danach (in Abstimmung) Schritt 16 – Benutzer/Login & Audit Minimalversion (kein neuer Hauptschritt vor Fortschrittsdatei-Abstimmung).

---

# UAT-Befund 4 – Referenznahes helles Krankenhaus-Design (PR-5 Re-Test)

**Status:** ABGESCHLOSSEN (visuelle Frontend-Anpassung umgesetzt und verifiziert; Fortschritt bleibt 15/18 – kein neuer Hauptschritt)

**Datum:** 10.09.2026

## Ausgangslage / Anforderung
- Die Oberfläche sollte optisch näher an die bereitgestellte helle Referenz rücken: weißer horizontaler Header, Krankenhaus-/Vertragsverwaltungs-Wording, Blau-/Türkis-/Grün-Palette, Hero-Bereich und saubere weiße Karten.
- Die Änderung sollte bestehende Funktionalität und Tests nicht brechen.

## Implementiertes
- `frontend/components/ClientNav.tsx`: Branding angepasst auf „Krankenhaus Wartungsverträge" und „Verwaltungssystem für Wartungsverträge"; Navigation bleibt testkompatibel, insbesondere `/import` weiterhin mit Label „Import".
- `frontend/app/page.tsx`: Dashboard um einen neuen Welcome-Hero mit CTA „Neuen Vertrag hinzufügen" ergänzt, Ziel `/import`.
- `frontend/app/globals.css`: helle Referenz-Theming-Schicht ergänzt: horizontale Top-Navigation, weiße Flächen, blau/türkis/grüne Design-Tokens, überarbeitete Cards/KPIs, Hero-Gradient, responsive Header-/Hero-Regeln und Inter-orientierte Typografie.

## Dateien
- `frontend/components/ClientNav.tsx`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `docs/PROJECT_PROGRESS.md`

## Tests / Ergebnis
- `npx vitest run` → **119 passed / 22 Dateien**.
- `npx tsc --noEmit` → grün.
- `npx next lint --no-cache` → 0 Warnings/Errors.
- `npm run build` → erfolgreicher Next-Production-Build, 13 Routen erzeugt.
- Bekannte nicht-blockierende Testumgebungs-Hinweise bleiben unverändert: jsdom kann `HTMLCanvasElement.prototype.getContext` ohne Canvas-Package nicht implementieren; einzelne React-`act(...)`-Warnings in bestehenden Tests. Beide verhindern den erfolgreichen Testlauf nicht.

## Bekannte Grenzen / Hinweise
- Keine Backend-, Datenbank-, KI- oder OCR-Änderungen.
- Keine neue Navigation oder Feature-Logik; der Import-Link bleibt funktional und testkompatibel.
- `C:\Users\almba\Medflux` ist aktuell kein Git-Repository, daher kein Git-Status/Commit in dieser Sitzung.

## Nächster Schritt
- Manuelle visuelle UAT-Rückschau im Browser. Falls das helle Referenzdesign akzeptiert ist, danach in Abstimmung Schritt 16 – Benutzer/Login & Audit Minimalversion.


---

# Rollenbasierte Dashboards – Admin & Developer

**Status:** IMPLEMENTIERT

**Datum:** 13.09.2026

## Ziel
- Organisationsadministration und technische Systemverwaltung klar trennen.
- Admins sehen operative Organisationsdaten; Developer sehen systemweite Technik und Organisationen.
- Nach Login erfolgt eine rollenabhängige Weiterleitung.

## Implementiert
- Admin Dashboard: offene Aufgaben, Prüfbedarf, aktive Benutzer, Arbeitsbereich, Schnellzugriffe, letzte Aktivitäten und Benutzerübersicht.
- Developer Dashboard: echter API-/PostgreSQL-/Authentifizierungsstatus, lokaler KI-Status, Organisationsverwaltung und technische Werkzeuge.
- Neuer geschützter Endpoint `GET /api/system/organizations/status` nur für Developer.
- Developer sieht keinen Link zum Admin Dashboard mehr.
- Rollenrouting nach Login: Developer → `/developer`, Admin → `/admin`, andere Rollen → `/`.
- Responsive CSS-Module für beide Dashboards.

## Dateien
- `backend/app/api/routes/system_organizations.py`
- `frontend/app/admin/page.tsx`
- `frontend/app/admin/admin.module.css`
- `frontend/app/developer/page.tsx`
- `frontend/app/developer/developer.module.css`
- `frontend/app/login/page.tsx`
- `frontend/components/ClientNav.tsx`

## Verifikation
- Rollen- und Endpoint-Logik statisch geprüft.
- Vollständiger lokaler Testlauf ist nach `git pull origin Ahmad` auf der Windows-Installation auszuführen.


## Korrektur – Developer-Zugriff auf Admin Dashboard
- Developer bleibt standardmäßig im Developer Dashboard.
- Nach Auswahl einer Organisation darf der Developer deren Admin Dashboard öffnen.
- Dadurch kann er organisationsbezogene Ansichten entwickeln, prüfen und Fehler beheben.
- Ohne ausgewählte Organisation bleibt der Zugriff auf das Admin Dashboard gesperrt.


---

# Multi-Hospital-Struktur & systemweiter Developer-Zugriff

**Status:** IMPLEMENTIERT

**Datum:** 13.09.2026

## Implementiert
- Eine Organisation kann mehrere Krankenhäuser enthalten; jedes Krankenhaus besitzt eigene Abteilungen und Kostenstellen.
- Organisations-Admins und Developer können Krankenhäuser, Abteilungen und Kostenstellen anlegen, bearbeiten, aktivieren und deaktivieren.
- Der Scope-Picker unterstützt Organisation → Krankenhaus → Abteilung sowie die Gesamtansicht über alle Krankenhäuser.
- Benutzer können auf Krankenhaus und optional Abteilung eingeschränkt werden; Admin und Developer dürfen organisationsweit arbeiten.
- Developer erhalten systemweiten Zugriff auf alle aktiven Organisationen und darin die effektive Admin-Rolle, ohne einzelne Memberships pflegen zu müssen.
- Strukturänderungen werden mit Benutzer, effektiver Rolle, Organisation, Krankenhaus/Abteilung und Kontext im Activity Log protokolliert; Developer erscheinen ausdrücklich als `developer`.

## Dateien
- `backend/app/api/routes/organization_structure.py`
- `backend/tests/test_developer_authorization.py`
- vorhandene Multi-Hospital-Basis: Models, Migrationen, Scope-Middleware und Organisationsstruktur-UI

## Verifikation
- Autorisierungsregeln durch fokussierte Unit-Tests abgesichert: Developer-Bypass und unveränderte Einschränkung normaler Rollen.
- Vollständiger lokaler Backend-/Frontend-Testlauf ist nach `git pull origin Ahmad` auf der Windows-Installation auszuführen.

## Bekannte Grenzen
- Keine harte Löschung von Krankenhäusern/Abteilungen in der Oberfläche; Deaktivierung bewahrt Vertrags- und Audit-Historie.

---

## Frontend development roadmap — 2026-09-13

- Status: Planning complete; frontend implementation has not started.
- Dedicated tracker: `docs/FRONTEND_PROJECT_PROGRESS.md` (English).
- Implemented: Ten ordered frontend development steps with task checklists, acceptance criteria, verification, backend dependencies, and completion records.
- Files: `docs/FRONTEND_PROJECT_PROGRESS.md`, `docs/PROJECT_PROGRESS.md`.
- Verification: Documentation structure and initial step status checked; no application tests required for this documentation-only update.
- Known issues: Full visual audit and baseline tests remain pending in FE-01.
- Next step: Execute FE-01 — current-state audit and acceptance baseline.
- Frontend progress: 0/10 (0%). Original MVP progress x/18 and percentage remain unchanged; no MVP implementation step was completed by this planning update.


---

## Visual identity v1.0 integration — 2026-09-13

**Status:** IMPLEMENTED

### Scope
- Applied the approved MedFlux identity from `docs/VISUAL_IDENTITY.md` to the product shell and authentication entry points.
- Added a reusable, accessible logo component with full and compact variants.
- Added an SVG application icon/favicon.
- Added a final global identity layer that maps the approved palette to existing semantic tokens without changing business-state meanings.
- Updated visible product naming from `Medflux` to `MedFlux` in the shell, login, organization selector, page metadata, and fallback title.
- Branded the dashboard hero, navigation selection, primary actions, cards, and login surface.
- Kept Poppins as the approved font with the existing local/system stack as fallback until self-hosted Poppins files are added.

### Files
- `frontend/components/brand/MedFluxLogo.tsx`
- `frontend/app/brand-identity.css`
- `frontend/app/icon.svg`
- `frontend/components/shell/AppSidebar.tsx`
- `frontend/components/shell/AppTopbar.tsx`
- `frontend/components/ClientNav.tsx`
- `frontend/app/login/page.tsx`
- `frontend/app/select-organization/page.tsx`
- `frontend/app/layout.tsx`
- `frontend/test/visual-identity.test.tsx`
- `docs/VISUAL_IDENTITY.md`

### Verification
- Static repository verification completed for imports, asset paths, metadata, approved naming, and token values.
- Added focused component tests for full and compact logo variants.
- Full `npm run verify` must be run after pulling branch `Ahmad` to the local Windows installation.

### Known limit
- Poppins is declared as the approved font but is not fetched remotely. The application intentionally falls back to its local/system font stack until licensed font files are self-hosted in the repository.


### Correction — canonical Main Logo 01 only

- Replaced the reconstructed SVG/wordmark implementation with the exact cropped `01 — Main Logo` artwork from the approved identity board.
- The single canonical application asset is `frontend/public/brand/medflux-main-logo.png`.
- Sidebar, login, and organization selection use that same asset; no horizontal, icon-only, or code-drawn alternative is rendered.
- Removed `frontend/app/icon.svg`; `frontend/app/icon.png` is derived from Main Logo 01 for the required square browser icon.
- Updated `frontend/test/visual-identity.test.tsx` to require the canonical PNG and reject inline SVG logo rendering.


### Logo refinement — clean MedFlux-only HD asset

- Updated the canonical logo to contain only the flowing M and the `MedFlux` wordmark.
- Removed `Healthcare Intelligence Platform`, the divider, and `Connect · Analyze · Improve` from the production logo.
- Replaced the application asset with an enhanced 860 × 536 px PNG and regenerated the favicon from the same clean artwork.
- Removed the separate login tagline so no text is rendered beneath the logo.


### Logo refinement — transparent integration

- Removed the raster logo's white background and preserved alpha transparency.
- Removed the login logo container's white background, border, padding, and shadow.
- The MedFlux logo now renders directly on its surrounding surface without a visible frame.


### Login contrast correction — primary logo on light identity background

- Replaced the dark login background with a light `#E6F4F8`-based brand gradient so the canonical teal/dark-blue logo remains fully legible.
- Kept the logo transparent and unframed.
- Reduced the login card shadow and border contrast for a calmer, integrated healthcare presentation.


---

## Profile editing database fix — 2026-09-13

**Status:** IMPLEMENTED

### Problem
- The `Mein Profil` UI and `/api/profile` endpoint already supported editable profile data, but local setup and container startup did not execute Alembic migrations.
- Existing installations could therefore run application code against a database that did not yet contain the profile columns, causing profile loading or saving to fail.

### Resolution
- `scripts/setup.ps1` now runs `python -m alembic upgrade head` after installing backend dependencies.
- The backend container now copies Alembic configuration/migrations and upgrades the database before starting Uvicorn.
- Backend setup documentation now explicitly requires the migration after pulls.

### Verification
- Confirmed that the profile model, API route, frontend form, and migration `f9a3b4c5d6e7` agree on the editable fields.
- Static verification completed for the Windows and Docker startup commands.
- Local runtime verification requires the configured database service.


### Profile authentication correction — 2026-09-13

- Runtime logs showed `GET /api/me` returning 200 while `GET /api/profile` returned 401 for the same browser session.
- The profile route now resolves the authenticated account directly from the configured login-session cookie, matching the proven `/api/me` behavior.
- Added a regression test preventing the profile route from returning to fragile `request.state.account_id` authentication.


---

## Contract-analysis architecture repair — 2026-09-15

**Status:** IMPLEMENTED

### Problem
- Production import used the canonical Harness path while older diagnostics/docs still described the legacy chunked StructuredContractExtractor path.
- Empty-text guarding depended on an injected legacy analyzer, so the production Harness path could continue with a non-analyzable document.
- PDF/DOCX classification incorrectly inferred DOCX from the presence of logical units.
- Canonical analyzability incorrectly depended on `canonical_text` instead of the actual units consumed by analyzers.
- Harness evidence persistence was coupled to the exact version string `"v2"`; Harness `v2.1` evidence could therefore be silently skipped.
- Contract-detail recovery logic also compared the Harness version literally to `"v2"`, causing version drift for `v2.1`/`v3`.
- Legacy-only `chunk_count=0` diagnostics were persisted for Harness runs and could be misread as a chunking failure.

### Resolution
- Made the no-text/no-units gate engine-independent before either analysis path is selected.
- Made source file type derive from the original filename extension rather than canonical structure.
- Made analyzability and character count derive from actual extraction units.
- Made Harness evidence persistence version-neutral by consuming the Harness evidence payload whenever present.
- Made Contract 360/read-model Harness detection version-neutral.
- Persist `chunk_count`/`truncated_chunks` as NULL for Harness/not-started analyses so legacy chunk metrics cannot masquerade as Harness failures.
- Updated structured-extraction and document-import documentation to describe the actual synchronous production Harness pipeline and placeholder semantics.

### Files
- `backend/app/documents/processing.py`
- `backend/app/contracts/detail/service.py`
- `backend/tests/test_document_processing.py`
- `backend/tests/test_contract_detail.py`
- `docs/STRUCTURED_AI_EXTRACTION.md`
- `docs/DOCUMENT_IMPORT.md`
- `docs/PROJECT_PROGRESS.md`

### Verification
- Added regression coverage for structured PDF source typing, unit-derived analyzability, Harness v2.1 evidence projection, Harness diagnostics without fake chunk counts, and version-neutral Contract Detail Harness detection.
- GitHub Integration Check was triggered for the updated branch; final workflow result still queued at the time of this progress entry.
- Real-contract local E2E retest remains required after pulling the branch because the GitHub runner cannot access the user's local PostgreSQL/Ollama/document bytes.

### Known follow-up
- Re-run the same real contract locally and verify: canonical units > 0, Harness AI calls > 0, model/provider populated, accepted extraction created, evidence rows persisted, and Contract 360 fields populated.
- A placeholder draft without `accepted_extraction_id` must continue to be treated as failed analysis, not accepted contract truth.

### Progress
- No new MVP main step was added; this is a corrective hardening pass across the existing import/AI/detail pipeline.


## Reliability hardening – 2026-09-15 (scan/Vision production path)

**Status:** Implemented; automated CI and real-contract UAT are the release gate.

A repository/runtime audit after real scanned-PDF testing found that image-only PDFs were rejected by a text-only analyzability gate before local AI could run. The production default also still selected Harness V2 and a text-only Qwen model although V3/Vision code existed.

Implemented:
- Harness V3 + `qwen3-vl:8b-instruct` are production defaults.
- stale private `HARNESS_ENGINE=v2` values safely route to V3; legacy V2 requires `v2-compat`.
- image-only PDFs with real pages reach V3 instead of failing before AI.
- textless visual blocks keep direct bounded transcription even with page batches.
- exact `visible_text` can ground facts; descriptions/inference cannot.
- vision-only evidence is explicitly review-required and included in semantic grounding.
- failed analysis is no longer styled as successful in the import UI.
- synchronous local AI import/retry windows raised to 30 minutes.
- Windows startup tries existing local PostgreSQL safely before Docker and checks `/ready`.
- PDF processing falls back locally from a failed Docling/OCR-layout pass to PyMuPDF page discovery so V3 Vision can still analyze the protected original.
- regression coverage expanded for truly textless scanned documents.
- full findings/UAT criteria: `docs/RELIABILITY_AUDIT_2026-09-15.md`.

No external AI service, destructive data migration, fixture contract truth or automatic acceptance of visual uncertainty was introduced.


## Explicit AI model selection – 2026-09-15

Medflux besitzt kein aktives Standardmodell mehr. Ein Modell wird ausschließlich
über die Einstellungsoberfläche bewusst ausgewählt und in der Datenbank gespeichert.
Ohne vollständige Provider-/Modell-Auswahl bleibt der KI-Zustand `unselected` und
Import/Analyse darf keine Inferenz starten. Environment- oder Bootstrap-Werte
dürfen weder bei fehlender Auswahl noch bei DB-Fehlern still als aktives Modell
übernommen werden. Ein Provider-Wechsel in der UI wählt ebenfalls nicht automatisch
das erste gefundene Modell; der Benutzer muss das Modell explizit auswählen.


## Clean product start – 2026-09-15

The runtime no longer exposes or applies the historical Demo/UAT workspace to
contract lists, dashboard visibility, document imports, or contract detail
authorization. Fresh installations are required to contain zero contract,
document, equipment, work-item, evidence, review, warning, calculation and
Demo/UAT workspace rows. Automated regression tests remain isolated from the
product database; they are not product data and must never seed the live
installation.

Existing local development databases are intentionally **not** auto-erased on
startup. A one-time explicit cleanup is required before UAT so a normal restart
can never destroy real hospital contracts.


## Persistent local admin bootstrap – 2026-09-15

Local development/test setup now idempotently ensures the account
`admin@medflux.local` exists after migrations. Existing credentials are never
rewritten during normal setup, so the current password remains valid across
restarts, pulls and product-data cleanup. The contract-data reset explicitly
preserves accounts, memberships, organizations and the stored password digest.

For a completely fresh database, the password is supplied once via an
interactive hidden prompt (or the one-process `MEDFLUX_LOCAL_ADMIN_PASSWORD`
environment variable). No plaintext/default password is committed to GitHub.
Pilot/production bootstrap is intentionally not automatic.


## Harness V3 direct-analysis reliability & extraction-quality fix — 2026-09-17

**Status:** IMPLEMENTED (code + automated tests); real-model run and official UAT pending.

### Symptom (root cause of the failed UAT re-analysis)
- Production re-analysis of `Abiomed Impella.pdf` aborted with
  `HarnessFailure purpose=direct category=RuntimeError` (`output_truncated`,
  `ai_call_count=3`, `groups_processed=0`).
- Root cause: the retry budget used the over-estimated prompt token count
  (`_estimate_tokens`, ~6968) instead of the real `prompt_eval_count` (~5255),
  so `8192 - 6968 - 512 = 712 < 1928` made a retry impossible; the commercial
  pack output (~5618 chars ≈ 1499 eval tokens vs the 1800 cap) proved
  truncation is nondeterministic.

### Defects found during measurement (`scripts/measure_tokens.py`,
`scripts/run_harness_real.py`, `scripts/dump_full_diag.py`)
1. Model returns dates as `{"year": Y, "month": M, "day": D}` -> normalizer gave
   `{}` -> `start_date` accepted with date=None.
2. Model returns durations as `{"years": N}` -> mapped to `{}` -> rejected.
3. Model quotes start with leading `...` -> exact quote matching failed
   (`evidence_not_located`).
4. Money signal matcher was a digit-substring test (`"0"` matched any amount
   containing a 0), so `monthly_cost=2226` was not uniquely bound.
5. Junk acceptance: `applicability="unknown"` facts with empty quotes were
   retroactively saved via the loose literal fallback
   (e.g. `costs.price_adjustment_clause="nicht automatisch verlängert."`).
6. The commercial pack saw all pages and no money-mapping guidance, so Qwen
   missed `annual_cost=8000` and sprayed `24365796.0` over cost fields.
7. The date/duration signal matchers shared the same substring disease: the
   `4 Jahren` duration signal also matched `2025-04-01` because it contains a 4.

### Resolution (backend/app/ai/harness/v3.py)
- PACKS restructured to 4 packs `(name, field selectors, retrieval topics)`:
  core / commercial / payment / operations, with `_PACK_GUIDANCE` MONEY MAPPING
  for the commercial pack (annual_cost / scheduled_prices / variable_charges).
- New `_pack_pages()` selects per-pack source pages deterministically from
  signal kind + `RETRIEVAL_TERMS` keyword hits (identity page always included;
  fallback to all pages). `_pack_source()` renders exactly those pages + vision.
- `call()` captures `provider.last_usage["prompt_tokens"]`; the single bounded
  retry now uses the measured prompt tokens so `8112-…`-margin fits
  (`8192-5334-512=2346 >= 1800+128` -> retry fires).
- Normalizers: `_normalize_date_payload` handles `{year,month,day}` (top-level
  and nested), durations handle bare unit keys (`{years:4}` etc.), money handles
  bare numbers.
- `_clean_quote()` strips leading/trailing `...`/`…`; exact date/duration signal
  matching compares value AND unit (no more digit substring collisions);
  money signal matching is exact amount equality.
- Literal fallback binding requires `applicability == "applicable"`.

### Tests (backend/tests/test_harness_v3.py)
- `stage_call_counts["semantic"]` expectation moved 3 -> 4 (per-pack calls).
- New: date/duration dict-shape normalization; retry uses actual prompt tokens
  (commercial truncation -> retry at 2680 output tokens -> success);
  money matcher binds 8000 to `8.000,00 EUR` despite a `0 EUR` signal on the same
  page; unknown-applicability junk with empty quote is rejected.
- `pytest tests/test_harness_v3.py`: **12 passed**.
- No-regression run of `test_harness_v3`, `test_harness_v2`, `test_ai_structured`,
  `test_document_processing`, `test_document_intelligence`,
  `test_contract_extraction`, `test_ai`, `test_contract_models`: 111 passed.
  The 6 failures are pre-existing auth/route tests (HTTP 401, reproduced on a
  clean `git stash` baseline) and are unrelated to the harness.

### Known follow-up
- Real-model validation via `scripts/run_harness_real.py`: all eight UAT facts
  (ABIOMED Europe GmbH, 40015645, 01.04.2025, 31.03.2029, 4 years,
  automatic_renewal=false, annual_cost 8.000 EUR, per_call 2.226 EUR) must reach
  the Contract360 UI with evidence.
- Official UAT re-analysis of `Abiomed Impella.pdf` via
  `/api/documents/{document_version}/reanalyze`, UI screenshots, report A-T.

### Progress
- No new MVP main step; corrective reliability/quality pass on the V3 direct
  analysis pipeline (stage: fix implementation complete, validation ongoing).

---

### Deterministic source-grounded money layer (2026-09-17 addendum)

**Status:** IMPLEMENTED, tested, validated on real Qwen run — all 8 UAT facts land.

#### Problem
Qwen transcribed `8.000,00` as `8.0` and marked `scheduled_prices` as `alternative`
(amounts collapsed to 2 entries with `8.0`), so `annual_cost` was never proposed.
The model also emitted `variable_charges` with `value_str`/`currency_code` dict
shapes that the normalizer couldn't parse → amounts dropped to `{}`.

#### Deterministic German contract-language readers (generic, not per-contract)
New helpers in v3.py:
- `_STAGED_YEAR_RE`: matches `im N.Jahr <label> | <amount> EUR` patterns
- `_PER_CALL_RE`: matches `per call: <amount> EUR`
- `_staged_price_rows(text)` → list of `(row_dict, quote)`
- `_per_call_rows(text)` → list of `(row_dict, quote)`
- `_steady_annual_amount(rows)` → `float | None`: derives steady yearly amount
  when rows are constant from year 2 onward (requires ≥3 rows if year 1 present)
- Wire-in: after proposal normalization, for `scheduled_prices`/`variable_charges`
  proposals with a valid page, parse the page text → override fact value deterministically
- Post-loop: if `scheduled_prices` accepted and `annual_cost` is None, derive
  `Money(steady, EUR, "annual")` from `_steady_annual_amount` and append evidence

#### Bug fix found during test authoring
`_normalize_money_payload` dict branch lost nested `currency` when amount was a
sub-dict like `{"cents": 800000, "currency": "EUR"}` — currency was read only from
the outer dict. Fixed to fall back to `nested.get("currency")`.

#### Real Qwen run results (qwen3-vl:8b-instruct, v3, 42.2s)
- status=partial validation=valid, ai_call_count=4, supported=12, evidence=12
- **All 8 UAT facts:**
  - `identity.supplier` = `ABIOMED Europe GmbH` (clean, no address)
  - `identity.contract_number` = `40015645`
  - `dates.start_date` = 2025-04-01
  - `dates.end_date` = 2029-03-31
  - `dates.duration` = 4 years
  - `termination.automatic_renewal` = false
  - **`costs.annual_cost` = 8000.0 EUR (annual)** — derived deterministically
  - **`costs.variable_charges`** = per call 2226.0 EUR
- `costs.scheduled_prices` = [(1, 0.0), (2, 8000.0), (3, 8000.0), (4, 8000.0)]
  — exact source-grounded re-read; model's `8.0` transcription overridden
- Junk (discounts/sla/deadline_days as `unknown` with no quote) correctly rejected
- `customer` includes address (lower priority, not blocking)

#### Tests
- `pytest tests/test_harness_v3.py`: **17 passed** (8 original + 9 new)
- Regression tests: dict-date/duration normalization, retry-with-actual-tokens,
  money-fact-literal-signal-bind, unknown-applicability-junk-rejection
- Unit tests: `_staged_price_rows`, `_per_call_rows`, `_steady_annual_amount`,
  `_retry_output_plan`, nested `currency` preservation in `_normalize_money_payload`
- Related suites: 39 passed across `test_harness_v3` + `test_ai_source_grounding` +
  `test_ai_verifier_fail_closed`

### Identity extraction restabilized on real canonical (2026-09-17, official UAT)

**Status:** IMPLEMENTED, tested, validated on production `/reanalyze` path.

#### Problem during official UAT
The official `/reanalyze` (production cache + `region_image` loader) persisted a
contract with `identity.supplier = null` although the isolated harness run had
extracted `ABIOMED Europe GmbH`. The page-1 canonical text is split into 12
layout elements (e.g. `zwischen` and `ABIOMED Europe GmbH ...` are separate
elements), so `locate()`'s per-element `_find_quote` never found the model's
cross-element quote; the literal fallback then failed the unique-match guard
because `ABIOMED Europe GmbH` also occurs in the page-6 Rechnungsanschrift.

#### Fix in `locate()` (v3.py)
When per-element quote search yields no match but the fact carries a page, resolve
the quote against the authoritative linearized page text (`page.text`), exactly
what the model saw via `_pack_source`. This keeps evidence verbatim (no fuzzy
matching) while bridging element boundaries. Garbled model quotes (e.g.
`contract_title` with OCR noise `ein den` instead of `für das`) still fail
closed → no invented values.

#### Verification
- `pytest tests/test_harness_v3.py`: **18 passed** (17 + new regression test
  `test_quote_that_spans_layout_elements_binds_to_page_text`)
- Related suites: 40 passed across `test_harness_v3` + `test_ai_source_grounding` +
  `test_ai_verifier_fail_closed`
- Real cached-canonical probe: 5/5 runs extracted supplier via production path
- Production `/reanalyze` (66.8 s) persisted snapshot now contains all 8 UAT facts:
  `supplier=ABIOMED Europe GmbH`, `title=Full-Service-Vertrag für das Impella®AIC
  System`, `40015645`, start 2025-04-01, end 2029-03-31, 4 Jahre,
  `automatic_renewal=false`, `annual_cost=8000.0 EUR (annual)`,
  `scheduled_prices` 0/8000/8000/8000, `per_call=2226.0 EUR`

---

## Runde 2 – Critical Fixes, Evidence-Linkage, Preispraesentation, UAT-Abschluss

**Status:** IMPLEMENTIERT + offiziell im Produktionspfad verifiziert (kein Commit vor Freigabe) |
**Datum:** 2026-09-18 | **Fortschritt:** 18/18 (MVP-Core), Runde-2-UAT abgeschlossen, A–R-Bericht/Stopp vor Commit

#### Implementiertes
- **CRITICAL #1 – Falsch-Positiv direkter Konflikte durch Tag-1-Differenz:**
  `calculate_contract_end_date` (`backend/app/contracts/calculation/dates.py`)
  behandelt reine Jahr/Monat-Dauern jetzt inklusiv: entspricht das explizite
  Ende exakt `abgeleitet − 1 Tag`, gilt es als **EXPLICIT ohne Review**
  (`overall_review_required=false`, kein „weichen ab…“ in `review_reasons`,
  `days_until_end` deterministisch berechnet, Status `ACTIVE`). Tage/Wochen-
  Dauern bleiben strikt; ein echter Konflikt (explizit 2025-01-01 vs. 365 Tage
  ab 2024-01-01 => abgeleitet 2024-12-31) bleibt CONFLICT mit `review_required=true`.
- **CRITICAL #2 – Equipment-Persistenz:** `backend/app/ai/harness/v3.py`
  normalisiert `equipment` deterministisch ueber `_normalize_equipment_payload`
  (akzeptiert str/list[str]/list[dict]; unbekannte Keys wie `evidence` werden
  **nicht** persistiert; Seriennummer wird nie erfunden; Geraeate-Identitaet
  „Impella AIC System“ vor Komponenten). Operations-Pack-Guidance ergaenzt.
- **CRITICAL #3 – Servicezeiten / 24-7:** `_normalize_timevalue_payload` fuer
  `sla.response_time/resolution_time/service_hours/emergency_availability`
  (str/int/dict; `original_text` wird aus start/end/days synthetisiert, z. B.
  „Mo, Di, Mi, Do, Fr 09:00-17:00“); `availability_24_7=false` bleibt bei
  explizitem Zeitfenster erhalten. Evidence haengt am Gruppen-Halter
  (`contract.sla.evidence`), nicht am TimeValue.
- **CRITICAL #4 – Enthaltene/ausgeschlossene Leistungen:** Harness-Normalisierung
  + Operations-Pack-Guidance; Read-Model-Projektion `_scope_section` liest die
  Snapshot-Listen `included_services`/`excluded_services` aus.
- **HIGH – Evidence-Linkage im Review-Prueffluss:** `_link_fact_evidence`
  (`backend/app/contracts/review/service.py`) bindet materiale Fakten
  deterministisch an Belege: exakt, Harness-Zeile (`fact_key.evidence`),
  Alias (z. B. `costs.annual_cost`, `costs.tax_table.net/vat/gross`,
  `termination.automatic_renewal`, `services.included/excluded_services`) und
  Praefixe (`equipment.*`/`identity.system_identity`, `scope.`/`sla.` fuer
  `services.coverage`). Gruppenzeile (`{group}.evidence`) nur als Fallback,
  leer bei vorhandenem spezifischen Beleg.
- **HIGH – Interne KI-Fehler verbergen + Analysehistorie mit sicheren deutschen
  Labels:** `_serialize` in `backend/app/api/routes/processing_jobs.py` gibt nie
  rohe `row.error`-Strings zurueck; stattdessen `status_label_de`
  (`_STATUS_LABELS_DE`) und `result_label_de` (`_result_label_de` +
  `_KNOWN_KI_ERRORS`-Map ueber `AIUnavailableError`/`RuntimeError`/
  `HarnessFailure`/`Timeout`, Fallback `app.documents.status.safe_failure_message`).
  Frontend rendert die sicheren Labels
  (`frontend/lib/domain-api/processingJobs.ts`,
  `frontend/components/contracts/detail/ContractBackendAnalysisPanel.tsx`).
- **HIGH – Kosten-Praesentation (2.226 € per call / 8.000 €-Staffel):**
  `ContractCostsSection` (+ DTOs `ScheduledPriceDto`/`VariableChargeDto` in
  `backend/app/contracts/detail/models.py`) projiziert jetzt
  `scheduled_prices` (Staffeljahre, nie annualisiert) und `variable_charges`
  (label/amount/unit/condition + ehrlicher `note_de`: nie zum Fixwert addiert)
  aus dem Snapshot (`_price_schedule_items`/`_variable_charge_items` in
  `backend/app/contracts/detail/service.py`). Frontend-Finanzbereich
  (`frontend/components/contracts/detail/ContractWorkspace.tsx`) zeigt beide
  Bereiche getrennt vom wiederkehrenden Jahresbetrag; Typen in
  `frontend/lib/contract-detail-types.ts`.

#### Dateien
- `backend/app/contracts/calculation/dates.py`
- `backend/app/ai/harness/v3.py`
- `backend/app/contracts/review/service.py`
- `backend/app/contracts/detail/models.py`
- `backend/app/contracts/detail/service.py`
- `backend/app/api/routes/processing_jobs.py`
- `frontend/components/contracts/detail/ContractWorkspace.tsx`
- `frontend/components/contracts/detail/ContractBackendAnalysisPanel.tsx`
- `frontend/lib/contract-detail-types.ts`
- `frontend/lib/domain-api/processingJobs.ts`
- Tests: `backend/tests/test_calculation_engine.py`, `test_warning_engine.py`,
  `test_harness_v3.py`, `test_uat_retest_defects.py`

#### Tests / Ergebnis
- `test_calculation_engine.py` + `test_warning_engine.py`: **140 passed**
  (inkl. `test_inclusive_year_term_no_conflict_uat` und
  `test_days_based_duration_no_inclusive_tolerance`)
- `test_harness_v3.py`: **19 passed**
- `test_uat_retest_defects.py`: **38 passed** (inkl. `TestFactEvidenceLinking`
  mit 8 Faellen, `TestPriceScheduleAndVariableCharges` mit 6 Faellen und
  `TestAnalysisHistorySafeLabels` mit 6 Faellen)
- Gesamt-Backend (DB laeuft, plain pytest): **851 passed, 37 failed** – die 37
  sind **vorbestehende Route-Test-Fehlschlaege** (alle `401 Anmeldung
  erforderlich.` wegen `auth_enabled=True` in `backend/.env` im Dev-Betrieb;
  `LocalAuthMiddleware` erlaubt nur `/api/health` + `/api/auth/login`). Gegenprobe
  per `git stash`: identische Fehler auf HEAD ohne Aenderungen – **kein** neuer
  Regression-Beitrag aus Runde 2. (Ein 38. Fehlschlag in einem Zwischenlauf war
  flaky und bestand beim Wiederholen nicht; Fehlerliste identisch zur
  vorbestehenden 37er-Liste.)
- Frontend: `npm run lint` sauber (nur vorbestehende Warnungen),
  `npx tsc --noEmit` ohne Fehler.

#### Produktions-UAT Runde 2 (offiziell, Stack oben)
- Stack: PostgreSQL (PID 20276, :5432), Ollama `qwen3-vl:8b-instruct` (PID 8452,
  :11434), uvicorn (PID 9680, :8000, ohne `--reload`), Frontend `next dev`
  (PID 20652, :3000). `set_ai_selection('ollama','qwen3-vl:8b-instruct')` gesetzt.
- Login `admin@medflux.local`/Sessions-Cookie; Health `GET /health` = 200.
- Offizielles `/reanalyze` auf `01a0aa26-dcd1-7617-baaf-e89432e5f854`
  (org `krankenhaus`): **85,6 s**, `status: reanalyzed`, atomar akzeptierter
  Snapshot (alter akzeptierter Snapshot trug den alten Konflikt bis zur
  Re-Analyse). Danach 9 offene Fact-Reviews (normaler Workflow, kein Konflikt).
- **Verifiziert live (Detail `01a0aa27-f57b-7b4f-9659-5aadfed6f6c9`):**
  - CRITICAL #1: `calculated_end 2029-03-31 | status explicit`,
    `requires_manual_review false`, keine Warnungen, Vertrag `ACTIVE`.
  - CRITICAL #2/#3/#4: `equipment` = Impella®AIC System (`identification_quality
    exact`, Seriennr. „I laut Lieferschein“ aus dem Dokument, nie erfunden);
    `sla.service_hours` = „Montag bis Freitag von 09:00 Uhr bis 17:00 Uhr“;
    `scope.excluded` persistiert (Sturzschaeden/Hoehere Gewalt; `included` in
    diesem Lauf leer = Modellstreuung, Normalisierung funktioniert).
  - Finanzen: `scheduled_prices` = 0/8000/8000/8000 EUR (Staffeljahre 1–4,
    Labels „(zuzueglich der jeweils geltenden gesetzlichen MwSt“-Variante);
    `variable_charges` = „per call: 2.226,00 EUR“ / `unit_label_de` „pro
    Einsatz“ / ehrlicher Hinweis (nie zum Fixwert addiert). Preisplan wird
    nicht annualisiert.
  - Evidence-Linkage im Review-Fluss: Fakten tragen „Quellen-Beleg“-Buttons,
    z. B. Vertragsnummer → Seite 1, Jaehrliche Gesamtkosten (8.000,0) →
    Seite 8 (Staffel-Tabelle).
  - Nachweise-Liste (23 Belege) mit ehrlicher Praezision: „Positionsbestimmt“
    vs. „Seite, ohne Position“ + Hinweis „…, aber ohne exakte Position (keine
    Wort-Hervorhebung)“ (bbox-Honesty); `supports_exact_navigation` korrekt.
  - Analysehistorie: nur deutsche Labels („Erfolgreich“, „Teilweise (prüfen)“,
    „5 erfolgreich / 7 fehlgeschlagen“ …), keine rohen Harness-Fehlerstrings.
- Screenshots (UAT Runde 2): `.playwright-mcp\uat-round2\01-dashboard-overview.png`
  bis `09-evidence-list.png` (Dashboard, Vertragsliste, Detail Finanzen/
  Leistungen/Geräte/Analysehistorie/Faktprüfung/Nachweise).

#### Bekannte Probleme / offen
- 37 vorbestehende Auth-Route-Tests (401): dokumentiert, kein Code-Fix (Auth
  nicht abschwaechen). Fuer die UAT werden die Fehlerberichte als
  „erwartet bis Auth-Testseite“ ausgewiesen.
- Offene kosmetische UX-Punkte (separate Checkliste, bewusst offen):
  RTL/LTR + Terminologie, Uebersetzung rechtlicher Entitaetsnamen +
  Service-Kontakt (p9), Evidence-Dedupe in der UI-Darstellung (Backend
  canonical-Settle existiert; UI praesentiert die gepaarten Belege bereits
  faktenbezogen). Die zwei urspruenglich offenen Punkte „interne KI-Fehler
  verbergen“ und „Analysehistorie-Statuslogik“ sind in dieser Runde
  umgesetzt und live verifiziert.

#### Naechster Schritt
- A–R-Bericht Runde 2 fertigstellen und `git diff/status`-Stopp vor Commit –
  kein Commit/Push ohne Freigabe. Danach optional die drei kosmetischen
  UX-Punkte (RTL/LTR, Entitaetsnamen/p9-Kontakt, Evidence-Dedupe-UI).

## Runde 3 – Included-Services deterministisch, Rechtsnamen/p9-Kontakt, Evidence-Dedupe

**Status:** CODE + TESTS ABGESCHLOSSEN; offizielles /reanalyze + Live-DB/API-Verifikation noch ausstehend (Produktions-DB voruebergehend nicht startbar, siehe „Bekannte Probleme“)
**Datum:** 2026-09-21 | **Fortschritt:** 18/18 (MVP-Core; Runde-3-Fix-Round, kein neuer Hauptschritt)

#### Implementiertes
- **Fix 1 – included_services deterministisch (nicht mehr Modell-Varianz):**
  - `_normalize_scope_list` (Harness) bildet beliebige Proposal-Formen
    (list-of-dicts, einzelner String, Leereintraege) konservativ auf
    `list[str]` ab (strip, Reihenfolge-erhaltendes Dedupe; niemals erfundene Items).
  - `_merge_service_scope_facts`: evidence-gestuetzte Bool-Service-Fakten (`True`)
    werden deterministisch in `services.included_services` projiziert
    (generischer kanonischer DE-Leistungsbegriff, feste Reihenfolge, idempotent).
    `False`/`None`/nicht lokaalisierte Fakten bleiben aussen (fail-closed).
    Kein ABIOMED-Bezug in der Mapping-Logik.
  - Equipment-`included_services`/`excluded_services` nutzen dieselbe Normalisierung.
  - Zitat-Resolver (`_find_quote`): toleriert Innen-Ellipsen (`...`/`…`) des
    Modells, bridging nur Whitespace/Ellipsen-Marker, nie andere Worte
    (kein Fuzzy-Matching); Positionen bleiben original (bbox-tauglich).
  - Guidance-Text (Operations-Pack): Bool-Fakten + Liste spiegeln sich.
- **Fix 2 – Rechtsnamen wörtlich + Service-Kontakt (Seite 9):**
  - Produktionspfad normalisiert `identity.supplier/customer/contractor` nur per
    `strip()` (keine Uebersetzung/Transliteration/Qualifier-Rewrite) – jetzt
    per Tests abgesichert; Guidance ergaenzt (Rechtsform wörtlich, ohne Strasse).
  - Schema-Luecke dokumentiert und minimal generisch geschlossen:
    `identity.service_email` + `identity.service_phone` (Optional[str]) in
    `ContractIdentity` – im KI-Feldkatalog, im Snapshot (JSONB) und im
    Detail-`identity`-Block via Backend-API. Evidence-pflichtig (fail-closed);
    keine ABIOMED-spezifische Sonderlogik. Kein Frontend-Change noetig.
- **Fix 3 – Evidence-Dedupe im Read-Layer:**
  - `_dedupe_evidence` in `build_contract_detail` (nach `_settle_canonical_evidence`):
    Duplikat nur = gleicher `field_ref` + gleiche Quelle/Seite/Paragraf-/Tabellen-
    Index + gleiche normalisierte Aussage. Andere Seite/Quote/Fakt/Source bleiben
    erhalten; DB-/Audit-Zeilen werden nie veraendert.
  - Deterministisch (Sortierung nach `(key, evidence_id)`, von DB-Lieferreihenfolge
    unabhaengig); Merge aggregiert `requires_review` (ODER), bevorzugt den
    `recovered:`-Beleg, hoehere Konfidenz und vorhandene bbox.
  - Gruppen-Fallback und feldspezifische Prioritaet im Review bleiben unveraendert.
- **Tests:** 18 neue Tests in `test_harness_v3_services.py` (8),
  `test_contract_identity_contact.py` (4), `test_evidence_dedupe.py` (6).

#### Geaenderte Dateien
- `backend/app/ai/harness/pipeline.py` – `_find_quote` Ellipsen-Fallback
- `backend/app/ai/harness/v3.py` – Scope-List-Normalisierung, Merge, Guidance
- `backend/app/models/contract.py` – `service_email`/`service_phone` (ContractIdentity)
- `backend/app/contracts/detail/service.py` – `_dedupe_evidence`, Identity-Block
- `backend/tests/test_harness_v3_services.py`, `backend/tests/test_contract_identity_contact.py`,
  `backend/tests/test_evidence_dedupe.py` (neu)
- `docs/PROJECT_PROGRESS.md` (dieser Eintrag)

#### Tests/Ergebnis
- Neue Tests: 18/18 bestanden.
- Gezielte Suites (calculation_engine, warning_engine, uat_retest_defects,
  contract_detail, evidence_dedupe, harness_v3, harness_v3_services,
  contract_identity_contact, contract_models): 240 passed / 6 failed –
  die 6 sind vorbestehende Auth-401-Route-Tests (identisch per `git stash`
  auf HEAD nachgewiesen, 12 passed / 6 failed mit und ohne Aenderungen).
- Gesamt-Backend: 869 passed / 37 failed (Baseline 851/37; +18 neue Tests,
  Fehlerzahl identisch = die 37 vorbestehenden Route-/Auth-Fehlschlaege, kein Regress).
- Frontend: `npm run lint` ok (nur 2 vorbestehende Warnings), `npx tsc --noEmit` exit 0.

#### Bekannte Probleme / offen
- Produktions-PostgreSQL (`C:\Program Files\PostgreSQL\18\data`, Port 5432) kann
  aktuell nicht starten: stale Windows Shared-Memory-Block des frueher hard-
  gekillten postmaster („pre-existing shared memory block is still in use“)
  – Datenverzeichnis intakt („database system is shut down“), kein Prozess haelt
  den Block; zuverlaessig nur durch Reboot aufgeloest. Die ABIOMED-Daten liegen
  ausschliesslich dort (`data/contracts` leer; `data/backups` nur .gitkeep).
- Daraus folgt: das geforderte EINE offizielle `/reanalyze` auf ABIOMED sowie die
  Live-`DB/API`-Verifikation sind ausstehend (User hat Bericht ohne Live-Reanalyze
  gewaehlt). Nach DB-Recovery ausfuehren.
- 37 vorbestehende Auth-Route-Tests (401): weiterhin dokumentiert, kein Code-Fix.
- RTL/LTR + Terminologie: bewusst NIE umgesetzt (User-Direktive dieser Runde).

#### Naechster Schritt
- 14-Punkte-A–R-Bericht Runde 3 abliefern (`git diff --stat`, `git status`,
  Commit-Dateiliste) – Stopp vor Commit/Push bis Freigabe. Danach: Reboot,
  alte DB starten, Ollama/uvicorn, ein offizielles `/reanalyze` auf ABIOMED,
  Live-DB/API-Verifikation, PROJECT_PROGRESS-Dateigruppe nachtragen.

## Runde 4 - Frankfurt-Scan-E2E: Harness V3 Haertung (OCR-Toleranz, Geld-Locator, Context-Budget)

**Status:** CODE + TESTS + REALE E2E ABGESCHLOSSEN (kein Commit/Push; Stopp bis Freigabe)
**Datum:** 2026-09-25 | **Fortschritt:** 18/18 (E2E-Haertungsrunde, kein neuer Hauptschritt)

#### Ausgangslage (BEFORE)
- Realer E2E auf dem gescannten Frankfurt-Vertrag (RAV-00074, PDF, 9 Seiten, HybridVision:
  alle Seiten hybrid_required) hatte deutlich mehr nicht verortete Fakten als Grundgesamtheit.
  Diagnose-Punkte: (1) Context-Budget - prompt+output konnte die konfigurierte num_ctx
  (8192) nicht selbst korrigieren und lief in Output-Trim/Abbruch; (2) OCR-tolerantes
  Evidence-Matching fehlte - Pipe-Separatoren (`|`) in Tabellenzellen und einzelne OCR-Typos
  (z. B. "Komponeten", "Schanzenfeldstr.") verhinderten Quote-Bindungen; Geld wurde
  potenziell ueber reine Zahlen (falsche Nicht-Geld-Zeilen) gebunden; (3) Page-Provenance -
  block ids `p{page}:{element_id}`, canonical page == PDF page (1-basiert) waren nicht
  ausreichend gegen die reale Verteilung geprueft. Zusaetzlich: `identity.supplier` (volle
  Adresse) wird im Briefkopf auf mehreren Seiten wiederholt -> globale Literal-Eindeutigkeit
  schlaegt fehl; `payment.payment_deadline_days` (30 Tage) wurde durch die ueberbreite
  `_money_field`-Praedikatabfrage (payment.*) zu Unrecht als Geld-Feld behandelt und
  verworfen; Datum-/Dauer-Literal-Value-Shapes (`{date_type,...}` bzw.
  `{duration_type, literal_value}`) wurden zu {} geleert; zwei `variable_charges`-Zeilenfakten
  ueberschrieben sich gegenseitig im Contract.

#### Implementiertes (AFTER)
- **Context-Budget:** `_effective_context` + `_CONTEXT_RESERVE=512` - hebt die effektive
  num_ctx auf prompt+output+reserve an, gedeckelt durch die echte Modellkapazitaet
  (descriptor.context_length); ohne gemeldete Kapazitaet bleibt der angeforderte Budget
  (konservativ). Exakt EIN gebundener Retry bei `done_reason=length`, danach fail-closed.
  Diagnosefelder: requested_context, output_reserve, effective_context, truncation_count,
  retry_count, retry_decision, retried_with_output_tokens.
- **OCR-Toleranz:** Pipeline `_TOLERANT_TOKEN_SPLIT`/`_tolerant_tokens`/
  `_find_quote_tolerant` (Token-Split auf Pipes/Whitespace, Komma zwischen Ziffern bleibt
  Teil des Geldtokens, <=2 buchstabengenaue OCR-Typos, Wort-Reihenfolge bleibt wichtig,
  fehlende Woerter -> fail-closed). Geld-Literal-Regex `_MONEY_LITERAL_RE` (Praefix-/
  Suffix-Waehrung, jeweils position), `_money_amount`, `_money_amounts_from_value`.
- **Staged Money-Locator:** `_locate_money_staged` verankert den Betrag-Literal auf der
  Fact-Seite und verlangt das (OCR/pipe-tolerante) Label in der Naehe; Geld wird NIE allein
  ueber die Zahl gebunden; Ambiguitaet/falsche Seite -> `evidence_not_located` (fail-closed).
  `_money_field` (echte Geld-Felder + Zeilenfelder) ersetzt die ueberbreite startswith-
  Abfrage. Quote-Pfad fuer Nicht-Geld-Felder bleibt verfuegbar (payment_deadline_days bindet
  wieder).
- **Page-Scoped Literal-Fallback:** `_literal_evidence` sucht zunaechst nur auf der
  Fact-Seite eindeutig, erst danach global; wiederholter Briefkopf (Seite 1 + Seite 6)
  laesst den supplier (volle Adresse) auf seiner eigenen Seite binden.
- **Normalisierung:** `_normalize_row_amount` erhaelt flache Betraege in Zeilen
  ("9.500,00 EUR", "9500" + Zeilenwaehrung) statt {} zu leeren; `_normalize_duration_payload`
  unterstuetzt `{duration_type, literal_value}`; `_normalize_date_payload` unterstuetzt
  `{date_type, literal_value}` (start 04.06.2025 -> 2025-06-04, end -> 2029-06-03).
- **Projektion:** zwei gleichnamige Zeilenfakten (`costs.variable_charges`,
  `costs.scheduled_prices`) werden aneinandergehaengt statt sich zu ueberschreiben
  (180,00 + 200,00 EUR pro Call bleiben beide erhalten).

#### Geaenderte Dateien
- `backend/app/ai/harness/pipeline.py` - _TOLERANT_TOKEN_SPLIT, _tolerant_tokens,
  _word_distance, _find_quote_tolerant
- `backend/app/ai/harness/source_signals.py` - `_MONEY_RE` Praefix/Suffix
- `backend/app/ai/harness/v3.py` - _effective_context/_CONTEXT_RESERVE, call()-Retry-Schleife,
  _MONEY_LITERAL_RE/_money_amount/_money_amounts_from_value/_money_label_phrase/
  _locate_money_staged, _money_field, _literal_evidence, _normalize_row_amount,
  _normalize_duration_payload/_normalize_date_payload Literal-Value-Shapes,
  Zeilenfakten-Merge in der Projektion, locate()-Guards (money_quote_ok, staged, signal-exclude)
- `backend/tests/test_harness_v3_money_ocr.py` - Money/OCR/Budget/Provenance-Suite + Regressionen
- `backend/tests/test_harness_v3.py` - page-scoped supplier literial Regression
- `docs/PROJECT_PROGRESS.md` (dieser Eintrag)

#### Tests/Ergebnis
- Gezielte Harness-Suites (test_harness_v3, test_harness_v3_services,
  test_harness_v3_money_ocr, test_hybrid_scanned_pipeline, test_hybrid_vision_runtime): 63 passed.
- Mit Source-Navigation (test_source_navigation, test_source_navigation_exact): 97 passed.
- (test_document_processing / test_contract_extraction / test_document_intelligence haengen an
  echten Docling/PDF/Local-AI/DB-Laeufen - umgebungsbedingt, ausserhalb des gruenen Scopes.)

#### Reale E2E (AFTER, Frankfurt-Scan, qwen3-vl:8b-instruct, HARNESS_CONTEXT_TOKENS=8192, DB-frei)
- 14 AI-Calls (1 routing + 9 vision + 4 semantic), 0 Truncations, 0 Retries, 0 Failures,
  244,33 s, PARTIAL/VALID, evidence_count=15, supported_count=15, requires_review=True.
- Akzeptierte Fakten (Feld -> GT-Wert -> Extrahiert): identity.contract_number -> RAV-00074 ->
  RAV-00074 (S.1); identity.supplier -> Abbott Medical GmbH, Betriebsstaette Wetzlar,
  Schanzenfeldstrasse 2, 35578 Wetzlar -> identisch als volle Adresse (S.1, page-scoped
  literal); identity.contractor -> Krankenhaus Nordwest GmbH -> inkl. Adresse Steinbacher
  Hohl 2-26 60488 Frankfurt (S.1); identity.customer_number -> 1000051342 -> 1000051342 (S.1);
  dates.start_date -> 04.06.2025 -> 2025-06-04 (S.1); dates.end_date -> 03.06.2029 ->
  2029-06-03 (S.1); dates.duration -> 48 Monate -> 48 months (S.2); dates.minimum_duration ->
  48 Monate -> 48 months (S.2); costs.annual_cost -> 12.000,00 EUR -> 12.000,00 EUR (S.3) via
  OCR/pipe-Zitat "Anteilige Zahlung fuer Investitionsgut: | | EUR 12.000,00";
  costs.scheduled_prices -> 9.500,00 EUR -> 9.500,00 EUR (S.3); costs.variable_charges ->
  180,00/200,00 EUR/Stueck -> beide 180,00 + 200,00 EUR per_call (S.5);
  payment.payment_deadline_days -> 30 Tage -> 30 (S.6).
- Nicht uebernommen (Modell-seitig, korrekt fail-closed): equipment (applicability unknown),
  costs.*/payment.* als model_marked_ambiguous, services.included_services
  (applicability:alternative). Kein Code-Eingriff in Ground Truth - Abweichungen sind
  Modell-Proposals, kein Locator-Bug.

#### Bekannte Probleme / offen
- `equipment` (OPTIS Mobile Next Imaging System) noch nicht belegt: Modell markiert
  applicability unknown ohne Quote; kein Locator-Fix erzwingt hier eine Falschannahme.
- 12.000,00 EUR einmalig wird als annual_cost gefuehrt; Katalog-Entscheidung bleibt UNGELOEST
  (advance_payment vs. annual_cost) - Modell flaggt advance_payment als ambiguous, fail-closed.
- Die drei Document-Processing-Testdateien haengen an echten Pipeline-Laeufen (Environ), nicht
  Teil des gruenen Scopes.
- Harness arbeitet nur innerhalb der Facetten dieser Runde; keine DB-Migration, keine API-/
  Frontend-Aenderungen, AHMAD unberuehrt.

#### Naechster Schritt
- BEFORE/AFTER-Bericht abliefern (git diff --stat, git status, Feldtabelle, E2E-Kennzahlen),
  Stopp vor Commit/Push bis Freigabe. Optional danach: equipment-Lokalisierung via
  Angebots-Deckblatt-Position praezisieren und advance_payment/annual_cost-Katalogbewertung
  der 12.000,00-Euro-Einmalzahlung klaeren.

---

## STEP 3: Kontrollierte Integration (Integration-Branch, Stand 2026-09-26)

**Status:** Stufe 1-2 abgeschlossen; Aenderungsflaechen-Unit-Suite gruen; Gate 1
(Finanz-Klassifikations-Guard) benchmark-verifiziert; Gate 2 (isoliertes PostgreSQL via
WSL-PostgreSQL 18.6 auf 55432) etabliert, breite Backend-Regression erstmals GRUEN
(988 passed / 1 Environment-Artefakt); Frankfurt-Benchmark durchgefuehrt. Abschluss-
bewertung in `docs/STEP3_INTEGRATION_REVIEW.md`. KEIN Merge in JAMAL ohne finale Freigabe.

**Datum:** 2026-09-26

**Implementiertes (Integration-Branch `step3/integration-20260926`, Basis `356975d` origin/JAMAL):**

| Commit | Inhalt |
|--------|--------|
| `42a7564` | chore(dev): lokaler MedFlux-Launcher + isolierte Postgres-Hilfsskripte (Runde-4) |
| `b14bfe1` | feat(harness): Runde-4-Haertung - OCR-Toleranz, Geld-Locator, Kontextbudget |
| `db0aa30` | docs: Runde-4-Haertung + lokaler Launcher |
| `cb0431c` | merge(audit): Finance-Provenance - striktes `_steady_annual_amount(expected_years=)` + `derived_facts` (3-Way-V3-Semantik-Merge, Konflikt manuell geloest) |
| `472f917` | fix(ai): lokaler Ollama-Streaming-Provider (getrennte Timeouts connect/read/write/pool, NDJSON-`_chat`, `_payload`), `keep_alive` + Vision/Visual-First-Config-Knobs |
| `87671fc` | feat(harness): Visual-First-Seitenbild-Ablesung (12/2 pages/reviews), STEP-5-Ambiguity-Guard (multipage/other-page/unverified -> review-only, kein harter Reject nur wegen Quote auf anderer Seite), Provenance-Tests, V3-Integration (`visual_first_experiment_enabled`-Gate) |

**Dateien (Aenderungsflaechen):** `backend/app/ai/providers/ollama.py`, `backend/app/core/config.py`,
`backend/app/ai/harness/v3.py`, neu `backend/app/ai/harness/visual_first.py`,
`backend/app/ai/harness/visual_first_bridge.py`, neu `backend/tests/test_visual_first_bridge.py`,
`backend/tests/test_visual_first_isolated.py`, `docs/PROJECT_PROGRESS.md`.

**Tests/Ergebnis:**
- Unit-Suite (ohne DB, `MEDFLUX_UNIT_ONLY=1`, Test-Schema-Isolation unberuehrt):
  `test_harness_v2` + `test_harness_v3` + `test_harness_v3_money_ocr` +
  `test_harness_v3_services` + `test_visual_first_bridge` + `test_visual_first_isolated` +
  `test_finance_provenance_audit` = **98 passed**.
- Zusaetzlich gruen: `test_harness_v3_money_ocr` (28), `test_harness_v3_services` (8).

**Bekannte Probleme / offen:**
- Breite Backend-Regression BLOCKIERT: Die DB-tragenden Suiten (`test_ai.py`, Verifier,
  `test_contract_extraction.py`, API/Auth-E2E) brauchen eine erreichbare PostgreSQL. Eine
  unabhaengig provisionierte, voellig isolierte Test-Instanz (eigener Port, eigenes Data-Dir,
  eigene Zugangsdaten; 5432/MedFluxPostgres18 unangetastet) liess sich auf dieser Maschine
  NICHT stabil etablieren:
  * `postgres.exe` von PostgreSQL 18.6 verweigert den Direktstart unter einem
    Administrator-Konto ("Execution ... under a user with administrative permissions is not
    permitted").
  * pg_ctl gestartete Zweitinstanzen derselben Binaries kollidieren mit dem laufenden
    5432-Service auf Windows im Shared-Memory-Adressraum (Fehler 487
    ERROR_INVALID_ADDRESS): Backend-Spawns schlagen dauerhaft fehl; genau EIN Start gelang
    (60 s stabil), dann Degeneration.
  * GemSss Freigabe-Regel: bei nicht sicher etablierbarer Test-DB gilt "Unit-Tests weiter,
    Integrationstests als blockiert berichten". Aufraeumung abgeschlossen: alle eigenen
    Orphan-Prozesse beendet, `pgtest`-Artefakte geloescht, 5432-Service verifiziert stabil
    ("accepting connections", Prozess-PIDs vom 2026-09-25 unveraendert).
- `test_llama_archive*.py` (LlamaIndex) weiterhin Environment-Gap in den verfuegbaren venvs.

**Naechster Schritt:**
- Frankfurt-Benchmark gegen integrierten Stand (`visual_first_experiment_enabled=1`) erst
  nach GPU-/Ollama-Koordination (VRAM-Check via `ollama ps`); Vergleich gegen Phase-3-Baseline.
- Abschlussbericht: Commit-IDs, geaenderte Dateien, Tests, Benchmark-Vergleich, Restpunkte,
  Go/No-Go-Empfehlung. Merge in `JAMAL` nur nach expliziter Freigabe.

### STEP 3 - Frankfurt-Benchmark (integriert), 2026-09-26

**Status:** Durchgefuehrt (EIN kompletter instrumentierter Lauf, Exit 0). Regression danach
gruen.

**Lauf-Umgebung:** Ollama 0.34.0 (bereits laufend, nicht erneut installiert/konfiguriert),
Modell `qwen3-vl:8b-instruct` (bereits installiert, 6.2 GB, 89% GPU/11% CPU), RTX 3070
(8192 MiB), keine parallelen GPU-Workloads. Pipeline integral: Integrations-Backend
(`step3/integration-20260926`) via PYTHONPATH, venv = `Medflux-Integrated-Test\backend\.venv`,
`real_frankfurt_full_benchmark.py`, `visual_first_experiment_enabled=True`,
`max_pages=9`, `max_reviews=2`, `context=8192`, `vision_output=600`, Timeout 300s,
Gesamtbudget 1500s. Frankfurt-Original verifiziert (9 Seiten, sha256/Storage-Key-Read-only-Rückfrage,
Rollback - keine DB-Aenderung, nichts hochgeladen).

**Ergebnisse (integriert):**

| Metrik | Phase-3-Baseline | Integriert | Diff |
|---|---|---|---|
| Analyse-Laufzeit (FULL_REAL_ELAPSED_SECONDS) | 278.8 s | 320.2 s | +41.4 s (+15%) |
| AI-Calls (result.ai_call_count, identische Instrumentierung) | 36 | 57 | +21 |
| Provider-Requests (Stages summiert: warmup+vf9+review2+semantic4) | - | 16 | (Instrumentierung Detail) |
| Timeouts | 0 | 0 | 0 |
| Retries (retried_with_output_tokens) | - | 0 | 0 |
| Truncated vision reads (ohne Retry-Explosion) | - | 3 | tolerant |
| Peak VRAM (max MiB / 8192) | 7791 | 7851 | +60 |
| Visuelle Beobachtungen (Visual-First vision_count) | 21 | 21 | 0 |
| Beobachtungs-Seiten | {2,3,4,6,7,8} | {2:10,3:4,4:1,6:1,7:2,8:5} | gleich |
| Akzeptierte Felder | 7 | 7 | 0 |
| Akzeptierte Seiten-Referenzen | {1,2,3,6} | {1:4,2:1,3:1,6:1} | gleich |
| Analyse-Status / requires_review | partial / True | partial / True | gleich |
| Reject-Reasons | - | superseded 1, evidence_not_located 4, model_marked_ambiguous 5, alternative 1 | - |
| Reconciliation | - | uncertain 25, ocr_only 10, vision_only 1 | - |
| Docling (OCR/Preprocessing) | - | 60.1 s | - |

**Provenance-Guard (STEP 5) verifiziert:**
- Kein einziger harter Reject nur wegen "Quote auf anderer Seite" (`rejected_page_mismatch`
  fehlt in FULL_REAL_VISUAL_REJECTED = 0) - Ambiguity-Flaechen bleiben review-pflichtig.
- Abdeckung bleibt erhalten (21 Beobachtungen, gleiche Seiten) - der Guard kollabiert die
  NOTATION nicht (Regression gegen Phase-2/3-Fruehwert: VISION_COUNT 5 verworfen).
- Review-Trigger im Lauf: rejected_page_error 3, region_dropped 20; insgesamt
  requires_review=True.
- Deterministische Matcher/Guard-Wahrheitstabelle durch 12 Bridge-Unit-Tests abgedeckt
  (duplicate literal on other page, multipage, nicht-in-OCR) - alle gruen.

**Contested EUR 12,000:**
- Wird als `costs.annual_cost` gefuehrt, akzeptiert mit Seite 3, Quote in OCR vorhanden,
  visuell korroboriert (Seite 3: 4 Beobachtungen), `annual_cost_page_reference = 3`.
- Gesamt-Analyse bleibt `partial` + `requires_review=True`; die 12.000er-Katalog-Ambivalenz
  (advance_payment vs. annual_cost) ist weiterhin dokumentiert als offener Punkt.
- Finance-Stage ist strikt (`_steady_annual_amount(expected_years=)` + `derived_facts`);
  keine fachfremde Aggregation durch den integrierten Merge.

**Regression nach Benchmark:** `test_harness_v2` + `test_harness_v3` +
`test_harness_v3_money_ocr` + `test_harness_v3_services` + `test_visual_first_bridge` +
`test_visual_first_isolated` + `test_finance_provenance_audit` = **98 passed**
(`MEDFLUX_UNIT_ONLY=1`, Test-Schema-Isolation unberuehrt).

**Restpunkte / offen:**
- Breite Backend-Regression weiterhin BLOCKIERT (kein isoliertes PostgreSQL etablierbar;
  Details im STEP-3-Abschnitt oben). DB/Produktdaten unangetastet, 5432 unveraendert.
- `equipment`/Services/SLA weiterhin fail-closed (0/0/False); termination-Eckdaten None.
- Gearbeitete Laufzeiten: Vision-VF 211.7 s (9 Lesevorgaenge), Semantic 96.0 s (4 Packs),
  Review 10.3 s (2), Warmup 2.1 s - alle timeouts=0.

**Naechster Schritt:**
- Abschlussbericht (Commits, Dateien, Tests, Benchmark-Vergleich, Restpunkte, Go/No-Go).
- Merge in `JAMAL` nur nach expliziter Freigabe; keine Bereitstellung.

### STEP 3 - Finale Sicherheits-Gates (Gate 1 / Gate 2 / Gate 3), 2026-09-27

**Status:** Alle drei Gates abgeschlossen; keine weitere Blockade. KEIN Merge, KEINE
Bereitstellung (wie freigegeben). Der Restpunkt "kein isoliertes PostgreSQL etablierbar"
ist damit aufgeloest.

**Gate 1 - Finanz-Klassifikations-Guard (verifiziert):**
- Problem: Ambige Betraege (Katalog-Ambivalenz advance_payment vs. annual_cost, z.B.
  EUR 12.000, nur als Zahl + Quote ohne Zeitraum-Anker) durften NICHT in
  `costs.annual_cost` als akzeptierte jaehrliche Verpflichtung einfliessen.
- Implementierung: `_financial_classification_verified(fact, visual_first_rows, *,
  page_texts=None, resolved_page=None)` in `app/ai/harness/v3.py`. Akzeptanz NUR via
  Zeitraum-Anker im `fact.quote`, deterministischen Seitentext-Anker
  (`page_texts[target_page]`) oder korroborierte Beobachtung mit Anker in Label/Quote.
  Laeuft NACH der `locate()`-Seitenaufloesung (der urspruengliche Bypass entstand, weil
  der Guard vor `locate()` auf einer uneingeloesten Seitenansicht lief → leere
  Zeilenliste → True). Zurueckweisung fail-closed mit
  `financial_classification_unverified` + Issue "Financial classification requires manual
  review" + `continue`. `visual_first_rows` leer → True (Kontrollpfad ohne Visual-First).
- Regressionstests: `tests/test_financial_classification_gate.py` (3 Tests inkl.
  Praedikaten-Matrix: unverankerter Jahresbetrag abgelehnt, Anker akzeptiert,
  Korroboration mit/ohne Anker, Seitentext-Anker).
- Frankfurt-Re-Run (Modell `qwen3-vl:8b-instruct`, `real_frankfurt_full_benchmark.py`,
  Log `frankfurt-gate2.log`): `FULL_REAL_CONTESTED_AMOUNT_ASSIGNED_ANNUAL False`,
  `FULL_REAL_ANNUAL_COST_PRESENT False`, akzeptierte Felder 7→6, Rejects mit
  `financial_classification_unverified: 1`, Seite 3 ohne korroborierte Zeilen
  (uncertain 3 / vision_only 1 / ocr_only 5), `PAGE_TEXT_HAS_ANCHOR False`,
  Kosten-Domain nicht mehr vorhanden, `requires_review True`.
- Commits: `c5c9aaa` (Guard + Tests), `7696677` (Aufloesung auf Zielseite +
  Seitentext-Anker-Evidenz).

**Gate 2 - Isoliertes PostgreSQL (WSL, etabliert):**
- Fruehere Windows-Versuche (postgres.exe unter Admin verweigert, pg_ctl-Kollision im
  Shared-Memory, Fehler 487) wurden ersetzt durch WSL2 Ubuntu 26.04 mit vorinstalliertem
  `postgresql-18` (18.6).
- Eigene, voellig isolierte Cluster-Instanz: Data-Dir `/opt/medflux-test-pg/data`, Port
  `55432`, Superuser `medflux_test` (Scram-SHA-256), `listen_addresses='127.0.0.1'`;
  5432/`MedFluxPostgres18` unangetastet. Provisionierung: `provision_pg.sh` (Temp-Hilfs-
  skript), Aufruf `wsl -d Ubuntu -u root -- bash /mnt/c/.../provision_pg.sh`.
- Windows→WSL-Konnektivitaet per psycopg verifiziert:
  `postgresql+psycopg://medflux_test:***@127.0.0.1:55432/postgres`.

**Breite Backend-Regression (erstmals mit erreichbarer Test-DB, Settings unter log):
  `DATABASE_URL=WSL-PG-55432`, `AUTH_ENABLED=false` + `MEDFLUX_INSECURE_DEV=true` 
  (kein `MEDFLUX_UNIT_ONLY`):**
- **988 passed / 1 failed**. Einziger Fehlschlag
  `test_security_runtime_config.py::test_valid_production_security_posture_passes` =
  Environment-Artefakt (Leak der Unit-Dev-Variablen in den Security-Konfig-Test); unter
  canonical-artiger Env (`AUTH_ENABLED=true` + unverraeterter `APP_SECRET_KEY`) 11/11 grün.
- Unter auth-ON-Umgebung: 38 API-401-Fehler (vorbestehender Env-Mismatch — API-Tests
  erwarten auth-aus; keine Regression).
- Zusaetzlich repariert: `generate()` sendet `stream=false` (einzeiliges JSON),
  Harness-/Chat-Pfade behalten NDJSON-Streaming (`_payload(*, stream=True)` Default) —
  Commit `d27550b`; behebt `test_generation_sends_think_and_stream_opts`.
- Ergebnis fuer die Aenderungsflaechen 101 gruen (harness v2/v3/money_ocr/services +
  visual_first bridge/isolated + finance_provenance + financial_classification_gate).

**Gate 3 - Integrations-Review:**
- Vollstaendige Bewertung (Commit-Liste, semantischer Vergleich vs. canonical JAMAL,
  verbleibende Konfliktpunkte, Datei-Inventar added/replaced/obsolete, Rollback-
  Prozedur, exakte Test-Matrix) in `docs/STEP3_INTEGRATION_REVIEW.md`.
- Executable Dateien vs. canonical (SHA256): 6 added (visual_first.py,
  visual_first_bridge.py, 4 Tests), 7 modified (v3.py, ollama.py, config.py,
  test_contract_identity_contact.py, test_evidence_dedupe.py, test_harness_v3_services.py,
  test_runtime_security_posture.py). Keine obsolete/ersetzten Executables.

**Bekannte Probleme / offen:**
- `test_security_runtime_config.py` reagiert auf Unit-Dev-Env-Leaks (auth-aus +
  insecure-dev true); unter Produktions-Env-Bild gruen. Env-Abhaengigkeit dokumentiert.
- `test_llama_archive*.py` (LlamaIndex) weiterhin Environment-Gap in den verfuegbaren venvs.
- Frankfurt: `equipment`/Services/SLA weiterhin fail-closed; termination-Eckdaten None.
  Die 12.000er-Katalog-Ambivalenz ist nun explizit abgewiesen (kein annual_cost) und
  wird als Review-Punkt im Analysefeld gefuehrt.

**Naechster Schritt:**
- Abschlussbericht an den Projekteigentuemer (Gates 1-2 verifiziert, Test-Matrix, Review-
  DoKument, Go/No-Go-Vorlage). Merge in `JAMAL` nur nach expliziter Freigabe; keine
  Bereitstellung.

### STEP 3 - Issue #11 / PR #12: Financial-Provenance-Fix + Cleanup, 2026-09-27

**Status:** Abgeschlossen. PR #12 (`review/financial-evidence-cleanup-20260927`, Commits
`c4453a4`+`afc97ad`) kritisch geprueft und durch eine korrigierte Implementierung DIREKT auf
`step3/integration-20260926` ersetzt (kein Blind-Merge). Alle Issue-#11-Punkte 1-6 umgesetzt;
Tests gruen. KEIN Merge in JAMAL, KEINE Bereitstellung (wie freigegeben).

**PR-#12-Review (Befund):** Absicht korrekt (Finanz-Klassifikation an den vorgeschlagenen
Betrag binden, nicht an Seitenwoerter), aber Mängel: (1) eigene Money-Regex duplizierte die
authoritative `_MONEY_LITERAL_RE`; (2) ungenutzter `page_texts`-Param blieb; (3) kein
numerischer Wert-Handling. Daher verbessert umgesetzt statt uebernommen.

**Implementiertes (Commits auf `step3/integration-20260926`):**
- `e20126e` fix(harness): `_financial_classification_verified(fact, visual_first_rows, *,
  resolved_page=None)` — `page_texts`-Pfad ENTFERNT (Seitenwoerter sind keine Evidenz);
  `_money_amounts_from_value` versteht jetzt top-level int/float (nicht bool); Zitat-Pfad
  verlangt Zeitraum-Anker + EXAKT EIN Geld-Literal gleich dem Betrag; korroborierte-Zeilen-
  Pfad verlangt Seiten-Match + Wert-Match + Anker in Label/Quote; mehrere/keine Betraege in
  `fact.value` → False; leere `visual_first_rows` → True (Legacy). Kommentar-Neuordnung
  `_PERIOD_FIELDS`: (a) Anker+Betrag, (b) korroborierte Zeile Betrag+Anker, (c) Legacy ohne
  Visual-First; Seitenwort ist NIE Evidenz.
- `e8ef82a` fix(harness): Provenance fail-closed — nur-sichtbare Vision-Echo-Fakten erzwingen
  jetzt `requires_review=True` + Issue "Evidence requires manual review: <field>" + PARTIAL
  (vorher: zeilenseitig requires_review, analyse-seitig aggregierte nur issues → Echo konnte
  als "vertrauenswuerdig" gespeichert werden).
- `36e34d1` fix(launcher): PostgreSQL-Wire-Protocol-Identity-Probe (Startup-Message 3.0 +
  Antwort-Byte) statt Blind-TCP-Port; bare TCP-Listener wird NICHT mehr als PostgreSQL-ready
  gemeldet; Real-Check gegen WSL-PG 55432 ok.
- `e34e34c` chore(harness): tote `_SPACER_SEPARATORS` entfernt; Mojibake-Eurozeichen
  (`â‚¬` statt `€`) in `visual_first.amount()` korrigiert (echte EUR-Literale banden vorher
  nicht) inkl. Regression.
- `936a17a` ci: `audit-finance-provenance.yml` laeuft jetzt auch auf
  `step3/integration-20260926` (plus Finance+Visual-Testdateien); `integration-check.yml`
  fuehrt die Integration-Branch-Commits ebenfalls.
- `de1e011`/`5e227e3` docs(architect): Evidence-basierte Haken in `docs/ARCHITECT_TASKS.md`.
- Push: `9df85ee..5e227e3`.

**Dateien (geaendert in dieser Runde):** `backend/app/ai/harness/v3.py`,
`backend/tests/test_financial_classification_gate.py` (12 Tests), neu
`backend/tests/test_visual_evidence_fail_closed.py`, `scripts/start_local_postgres.ps1`,
`scripts/test_start_local_postgres.ps1`, `backend/app/ai/harness/visual_first.py`,
`backend/app/ai/harness/pipeline.py`, `docs/LOCAL_LAUNCHER_AR.md`, `docs/ARCHITECT_TASKS.md`,
`.github/workflows/audit-finance-provenance.yml`, `.github/workflows/integration-check.yml`,
`docs/PROJECT_PROGRESS.md`.

**Tests/Ergebnis:**
- Fokussiert (nur Finanz/Harness-V3/Visual-First): 121 passed (6 Dateien: gate + money_ocr +
  harvester/bridge/isolated/fail-closed + finance_provenance + v2 + services + evidence_dedupe
  + contract_identity in zwei Batch-Laeufen, 87 + 34).
- Volle Backend-Regression (DB = WSL-PG 55432, auth-aus): **999 passed / 1 failed** — der
  einzige Fehlschlag ist das dokumentierte Environment-Artefakt
  `test_security_runtime_config.py::test_valid_production_security_posture_passes` (Env-Leak);
  unter Produktions-Env-Bild 11/11 gruen. 999 = 997-Baseline + 1 Fail-Closed-Test + 1
  Euro-Variante, keine Regression.
- Auth-ON / Tenant-Isolation (AUTH_ENABLED=true, echtes Secret, kein insecure-dev): Auth-E2E
  + Route-Boundary + Security + Review-Provenance 20/20; Security-Config/Posture 26/26.
- Launcher-Identity: `test_start_local_postgres.ps1` 4/4 inkl. bare-Listener-Reflexion +
  Real-PG-Check 55432 exit 0.

**Bekannte Probleme / offen:**
- 2 Archive-Route-Probes (`test_archive_route_unknown_org_404`/`..._unarchive...`) erwarten
  unter auth-ON 404, erhalten aber 401 (unauthentifizierter Probe → auth fail-closed zuerst);
  Testdesign fuer auth-aus-Env, kein Code-Bug, separat gemeldet.
- `v3_perception.py` (origin/JAMAL-Bestand) hat NULL Importeure → toter Code, aber NICHT Teil
  des Changed-File-Inventars; Entfernung nur mit Eigentuemer-Freigabe dokumentiert.
- `test_security_runtime_config.py` Env-Leak (wie gehabt, dokumentiert); `test_llama_archive*`
  Environment-Gap; Frankfurt `equipment`/Services/SLA weiterhin fail-closed.

**Naechster Schritt:**
- Abschlussbericht (dieser Runde) an den Eigentuemer; Push erfolgt, PR/Branch bereit.
- Merge in `JAMAL` nur nach expliziter Freigabe; keine Bereitstellung.

### Pilot-Wiederholung: Radiosurgery + OPTIS, 2026-10-03

**Status:** Beide realen Dokumente wurden über den lokalen Import-/Reanalysepfad im
isolierten UAT erneut verarbeitet. Die Analyse endet in beiden Fällen kontrolliert als
`partial` / manuelle Prüfung; keine der unvollständigen Antworten wurde stillschweigend
freigegeben. Der MVP-Fortschritt bleibt **18/18 (100 %)**; dies ist ein Stabilitäts- und
Abnahmelauf, kein neuer MVP-Hauptschritt.

**Behobene Befunde:**
- `_primary_contract_title` nutzt nun auch kanonischen Seitentext und bindet den Titel
  weiterhin an den Quellbeleg. Ein enger OCR-Zeilenartefakt-Filter entfernt eine isolierte
  Nummer zwischen `RAV-00074` und dem OPTIS-Titel, ohne das Zitat im Beleg zu verändern.
- `_explicit_labelled_contract_dates` liest Vertragsstart/-ende aus expliziten Labels,
  berücksichtigt die durch OCR vertauschte Tabellenlesereihenfolge und ignoriert ein
  dazwischenliegendes, allgemeines Angebotsfeld `Datum`. Eindeutige Quellfelder haben
  Vorrang vor widersprechendem Modelloutput; der Widerspruch bleibt ein Review-Grund.
- Ein explizites Kalenderdatum unterdrückt die zusätzliche ereignisbasierte Startbedingung
  als parallelen Startwert.
- Ergänzte Regressionen für OPTIS-Titel/OCR-Artefakt, gleichseitiges Start-/Enddatum,
  nicht vertragsbezogenes Datum, widersprechende Quelldaten und Modellkonflikt.

**Validierung:**
- Backend-Fokus: `test_harness_v3.py`, `test_ai_schema_constraints.py`,
  `test_harness_v3_money_ocr.py` — **137 passed**, 5 bekannte PyMuPDF/SWIG-Deprecation-
  Warnings.
- Radiosurgery (18 Seiten): Titel `SERVICEVERTRAG RADIOSURGERY`, Brainlab Sales GmbH,
  EUR 52.500 wiederkehrend pro Jahr, EUR 210.000 Gesamtwert und drei quellgebundene
  Systeme/Geräte. Analyse bleibt `partial`/Review wegen fehlerhafter Modellantworten und
  fehlender eindeutiger Kalenderdaten.
- OPTIS (9 Seiten): Titel `Rahmenvertrag Nr. RAV-00074 - OPTIS™ Mobile Next Imaging
  System`, Abbott Medical GmbH, 04.06.2025–03.06.2029, aktive Laufzeit und
  `OPTIS™ Mobile Next Imaging System`. Keine feste jährliche Vertragsgebühr aus dem
  kanonischen Dokument belegt; EUR 12.000 und EUR 9.500 sind einmalig, Verbrauchsprodukte
  sind Stückkosten. Deshalb bleibt annual recurring `not_calculable` und manuelle Prüfung
  erforderlich.
- Beide Dokumente wurden über Backend 8011, Frontend 3010 und ausschließlich die
  isolierte PostgreSQL-Datenbank 55432 verarbeitet; der Closed-Barrier-Launcher bestätigte
  bei jedem Neustart Ziel-Datenbank und Server.

**Offen:**
- Beide Verträge bleiben prüfpflichtig. Radiosurgery hat weiterhin Modell-/Schemafehler
  in einzelnen Extraktionsgruppen; OPTIS hat keinen belegten wiederkehrenden Jahrespreis.
  Die UAT bestätigt die Schutzwirkung, nicht eine vollautomatische Freigabe der Dokumente.
- Kein Push oder Merge. Änderungen für diesen Pilot sind für einen neuen Commit auf dem
  bestehenden Branch vorgesehen.

### OPTIS-UAT-Wiederholung, OCR-Quellposition und Nummernbeleg

- Die gescannte OPTIS-Originaldatei wurde auf dem isolierten Stack erneut verarbeitet;
  die Quelldatei blieb unverändert und außerhalb des Repositories. Das Ergebnis wurde
  in Contract360 geprüft: `RAV-00074`, Abbott Medical GmbH, 04.06.2025–03.06.2029,
  aktiver Vertrag und `OPTIS™ Mobile Next Imaging System`.
- Die Kostenanzeige enthält einmalig EUR 12.000, Aufbau/Installation EUR 9.500 sowie
  bedingte Stückpreise EUR 180 und EUR 200. Ein wiederkehrender Jahrespreis wurde nicht
  belegt und blieb leer. Der Lauf endete erwartungsgemäß `partial` mit Review, da
  Geräteidentität/-beziehung nur teilweise belegt war.
- `/api/documents/{version}/source-region` lehnte `.pdf` fälschlich mit HTTP 415 ab,
  weil die Endung mit führendem Punkt verglichen wurde. Die Prüfung normalisiert nun
  führende Punkte/Leerraum und Groß-/Kleinschreibung. Der echte OPTIS-Aufruf lieferte
  danach HTTP 200 und Seite 1; die Position blieb ehrlich `coarse` (OCR-Atomgeometrie).
- `source_signals` erkannte `Rahmenvertrag Nr.` bisher nicht. Die Regex deckt diese
  deutsche Vertragsnummernform jetzt ab; ein eindeutiger wörtlicher Treffer wird in
  Harness V3 mit Seitenbeleg als `identity.contract_number` übernommen. Mehrdeutige
  Nummernsignale werden nicht automatisch gewählt.
- Gezielte DB-freie Regressionen: **28 passed**, 5 bekannte PyMuPDF/SWIG-Warnungen.
  Ein zunächst zu breit gewählter Integrationstest hätte per autouse fixture die
  PostgreSQL-Konfiguration des Moduls verwendet; der Lauf wurde sofort beendet, bevor
  irgendein Testergebnis entstand. Danach liefen ausschließlich DB-freie Tests.
- Die Browser-Frontend-Seite auf 3011 zeigte `Cannot find module './vendor-chunks/@swc.js'`.
  Damit wurde kein visueller UI-Retest der neuen API-Ausgabe beansprucht; Contract360-
  Daten wurden über die authentifizierte API geprüft. Verbleibende pnpm-Artefakte und
  `.playwright-mcp/`/Screenshot wurden nicht verändert oder eingecheckt.
- Die gescannten Originale werden als echte Acceptance-Eingaben verwendet. Sie sind
  keine ungeprüften Trainingslabels: eine spätere Anpassung muss pro repräsentativem
  Scan eine menschlich bestätigte Soll-Angabe mit Seite und wörtlichem Beleg erhalten;
  Dokumente und OCR-Rohdaten bleiben lokal.

## 2026-10-03 – Acceptance-Basis aus lokalem Vertragsbestand

Status: IN ARBEIT

Ergebnisse:
- Lokale Vertrags- und UI-Referenzen bleiben außerhalb des Repositorys; keine echten
  Vertragsdateien, OCR-Ausgaben oder Mitarbeiterdaten wurden in Fixtures kopiert.
- Ergänzte Regression für mehrseitige Serviceverträge: Der Eröffnungstitel
  `SERVICEVERTRAG RADIOSURGERY` bleibt Vertragsidentität, auch wenn auf der letzten
  Seite allgemeine Geschäftsbedingungen vorkommen. Der Beleg muss auf Seite 1 liegen.
- Bestehende OPTIS-Titel-/Datumstests, mehrjährige Finanzplan-Tests, quellgebundene
  Geräte-Tests, Review-/Fehlerstatus-Tests und Assistentenkontext-Tests wurden als
  vorhandene Abdeckung identifiziert.

Validierung:
- Neue Radiosurgery-Titelregression: **1 passed** (gezielter pytest-Aufruf im
  `MEDFLUX_UNIT_ONLY`-Modus; keine Datenbankverbindung).
- Breiter fokussierter Backend-Lauf erreichte 68 %, blieb anschließend ohne Ausgabe
  hängen und wurde abgebrochen; somit kein vollständiges Regressionsergebnis.

Offen:
- Als nächste Acceptance-Stufe fehlt ein gemeinsamer, mehrseitiger Szenariotest, der
  OCR-/Visionsignale, Vertragsidentität, Finanzplan, Gerätebeziehungen, Seitenbelege
  und Review-Entscheidung zusammen prüft.
- Die 36 lokalen Vertrags-PDFs sind überwiegend bildbasiert. Vor jeder Modellanpassung
  ist pro repräsentativer Stichprobe eine menschlich bestätigte Soll-Ausgabe mit
  Feldwert, Seite und Beleg nötig. Rohdateien bleiben lokal und werden nicht versioniert.

### Radiosurgery-UAT-Wiederholung und Zustandskorrektur

- Die Verarbeitung des echten 18-seitigen Vertrags wurde auf dem isolierten lokalen
  Stack (Backend 8012, PostgreSQL 55432, Ollama `qwen3.5:4b`) wiederholt. Docling/OCR
  endete erfolgreich; der KI-Lauf benötigte rund 166 Sekunden und ergab korrekt
  `partial` mit manueller Prüfung.
- Bestätigt extrahiert wurden `SERVICEVERTRAG RADIOSURGERY`, Brainlab Sales GmbH,
  wiederkehrend EUR 52.500/Jahr und EUR 210.000 Gesamtwert; drei Geräte/Systeme
  wurden erkannt und blieben wegen unvollständiger Identitätsbelege prüfpflichtig.
  Vertragsnummer und eindeutige Kalenderdaten fehlten weiterhin.
- Fehlerursache der falschen UI-Meldung: `build_import_state` wertete den Status des
  Docling-`ProcessingRun` statt den neuesten KI-`ContractExtraction` aus. Dadurch
  wurde ein OCR-Lauf `succeeded` als Analysefehler behandelt, obwohl die Analyse
  `partial` war. Statusabbildung und gezielte Regressionen wurden korrigiert; die
  API liefert nun `analysis_partial`, `analysis_status=partial` und Review-Hinweis.
- Im gespeicherten Harness-Diagnoseobjekt wurden 15 fehlgeschlagene Calls von 28
  sichtbar: 7 Vision-Seiten und 8 semantische Chunks mit Kategorie `malformed_json`;
  alle hatten `done_reason=stop`. Damit ist dies kein Request-Timeout, und die
  konkrete nächste Modell-/Schemaursache bleibt offen.
- Gezielte Tests: **12 passed**. Der frühere breite Fokuslauf blieb bei 68 % hängen;
  kein vollständiger Backend-Lauf wurde bestätigt.

## 2026-10-03 – Produktreferenz und Organisationsstruktur in der Oberfläche

Status: Phase 1 der Oberfläche umgesetzt; weitere Produktphasen offen

Ergebnisse:
- `docs/MEDFLUX_PRODUCT_BUILD_PLAN.md` bündelt die Anforderungen an Verträge,
  Organisation, Prüfung, Kosten, Fristen, Geräte, Suche und Assistent als deutsche
  Produktreferenz. Die Anforderungen sind dort ausdrücklich von bereits gelieferten
  Funktionen getrennt. Es wurden keine hebräischen UI-Texte ergänzt.
- Die Organisationsansicht zeigt Abteilungen und Einheiten als verschachtelten Baum.
  Einheiten können beim Anlegen einem Krankenhaus und optional einer übergeordneten
  Einheit zugeordnet werden. Vorhandene Einheiten lassen sich umhängen; die Auswahl
  schließt sich selbst und eigene Nachfahren aus. Die Backend-Prüfungen bleiben die
  maßgebliche Grenze für Krankenhauszugehörigkeit und Zyklen.
- Organisationspfade werden in der Baumansicht und in Kostenstellen-Auswahlen
  angezeigt. Bereichsbezogene Kostenstellen erscheinen an der Einheit, klinikweite
  Kostenstellen separat.
- Die vorhandenen Backend-Routen für Vertragsrollen (verantwortlicher und nutzende
  Bereiche) werden im Frontend noch nicht verwendet. Ihre Darstellung und Auswahl im
  Import-/Contract360-Ablauf ist der nächste UI-Schritt.

Dateien:
- `docs/MEDFLUX_PRODUCT_BUILD_PLAN.md`
- `frontend/lib/organization-tree.ts`
- `frontend/lib/domain-api/organizations.ts`
- `frontend/components/settings/OrganizationStructureManager.tsx`
- `frontend/app/organization.css`
- `frontend/test/organization-tree.test.ts`
- `frontend/test/organization-structure-manager.test.tsx`

Validierung:
- Vollständiger Frontend-Testlauf: **165 passed** in 33 Testdateien; bestehende
  React-`act(...)`-Warnungen erschienen in mehreren UI-Tests.
- TypeScript-Prüfung mit `tsc --noEmit`: erfolgreich.
- Lokale Organisationsseite auf Port 3011: HTTP 200; ein vollständiger visueller
  Browservergleich wurde in diesem Schritt nicht bestätigt.
- Keine Backend-Datenbank, kein Backend-Service und keine echten Vertragsdateien
  wurden für diese UI-Änderung verwendet.

Offen:
- Vertragszuordnung für Krankenhaus, verantwortlichen Bereich, nutzende Bereiche und
  Kostenstelle in Import und Contract360 integrieren.
- Anwenderpfad anschließend mit den vorhandenen Rollen und Berechtigungen prüfen.
- Das bestehende Arbeitsverzeichnis enthält weitere nicht zu diesem Schritt gehörende
  lokale Artefakte; sie wurden nicht verändert oder aufgenommen.

## 2026-10-03 – Vertragsrollen in Contract360

Status: Zuordnung in Contract360 umgesetzt; Laufzeitprüfung gegen Testdatenbank offen

Ergebnisse:
- Contract360 lädt und zeigt Krankenhaus, verantwortlichen Bereich, nutzende Bereiche,
  Kostenstelle und verantwortliche Person. Bereichsauswahlen enthalten den vollständigen
  Organisationspfad; historische Verknüpfungen ohne dokumentierte Rolle werden als
  ungeklärt ausgewiesen und nicht automatisch klassifiziert.
- Die Rollen werden über die vorhandenen `department-roles`-Routen verwaltet. Der
  Krankenhauswechsel ist gesperrt, solange explizite Bereichsrollen bestehen, weil die
  Rollen-API sie an das Vertragskrankenhaus bindet.
- Metadatenänderungen dürfen bereits klassifizierte Abteilungsbeziehungen nicht
  überschreiben. Der Ownership-Service erlaubt solche Änderungen nur bei unveränderter
  Abteilungsmenge und unverändertem Krankenhaus; veränderte Rollen müssen über den
  dedizierten Rollenendpunkt laufen.
- Deutsche Frontend-Regression prüft vollständige Pfade, Rollenanzeige und Speichern.
  Backend-Regressionen decken den Erhalt beziehungsweise die Ablehnung veränderter
  klassifizierter Beziehungen ab.

Dateien:
- `frontend/components/contracts/detail/ContractOwnershipPanel.tsx`
- `frontend/lib/domain-api/ownership.ts`
- `frontend/test/contract-ownership-roles.test.tsx`
- `frontend/app/ownership.css`
- `backend/app/api/routes/ownership.py`
- `backend/app/ownership/service.py`
- `backend/tests/test_contract_department_roles_a2.py`

Validierung:
- TypeScript-Prüfung: erfolgreich.
- Zugehörige Contract360-Frontendtests: **11 passed**; neuer Rollen-Paneltest darin
  enthalten. React-`act(...)`-Warnungen und eine jsdom-Canvas-Warnung aus vorhandenen
  Komponenten erschienen im Lauf.
- Backend-Pytest konnte nicht ausgeführt werden: die aktive Python-Installation enthält
  `pytest` nicht (`No module named pytest`). Es wurden keine Tests oder Services mit
  Datenbankverbindung gestartet.

Zum damaligen Abschluss offen:
- Backend-Regressionen in der vorgesehenen Projektumgebung ausführen.
- Browserablauf gegen isolierte UAT-Datenbank prüfen, einschließlich unzulässiger
  krankenhausübergreifender Zuordnung.

### UAT-Nachtrag: Contract360-Zuordnung und Testumgebung

- Backend-Regression `tests/test_contract_department_roles_a2.py`: **7 passed** im
  isolierten, temporären Testschema der freigegebenen Trial-Datenbank; der Testlauf
  beendete sich regulär, sodass das Testschema wieder entfernt wurde. Zusätzlich
  erfolgreich im `MEDFLUX_UNIT_ONLY`-Modus ohne Datenbankverbindung.
- Backend 8012 und Frontend 3011 wurden aus diesem Checkout für den UAT-Lauf gestartet.
  Der API-Login-Preflight wurde zunächst durch die lokal fehlende CORS-Freigabe für
  `127.0.0.1:3011` abgewiesen. Mit einer ausschließlich prozesslokalen CORS-Einstellung
  antwortete er erfolgreich; kein CORS-Wert wurde in Projektdateien gespeichert.
- UAT-Login und Contract360-Ansicht funktionierten. Die Vertragsliste enthielt unter
  anderem OPTIS/RAV-00074 und SERVICEVERTRAG RADIOSURGERY; der Radiosurgery-Datensatz
  zeigte EUR 52.500 jährliche Kosten.
- Ein erfolgreicher Rollen-Speichervorgang und ein echter organisationsübergreifender
  Negativtest waren nicht möglich: `/api/organization-structure` und die sichtbare
  Einstellungsseite meldeten **0 Krankenhäuser, 0 Einheiten, 0 Kostenstellen**. Ohne
  Teststruktur würde ein Save entweder unmöglich sein oder Änderungen an echten
  Vertragsdaten erfordern. Es wurden deshalb keine Vertrags- oder Organisationsdaten
  in UAT angelegt oder geändert.
- Beim ersten UAT-Versuch zeigte der Browser veraltete Next.js-Chunkfehler; nach Start
  des aktuellen Frontend-Devservers renderten Anmeldung, Vertragsliste, Radiosurgery-
  Detail und Organisationsseite. Der Login-Fehler vor der CORS-Korrektur ist behoben.

Nächster Schritt:
- Eine ausdrücklich als synthetisch markierte Krankenhaus-/Einheitenstruktur in der
  isolierten Testdatenbank über eine rücksetzbare Fixture bereitstellen und damit den
  positiven Rollen-Save sowie die Ablehnung eines Bereichs aus einem anderen
  Krankenhaus automatisiert gegen die API prüfen. Für die aktuelle UAT-Datenbank keine
  Organisationsdaten ohne bestätigten Bereinigungsweg erzeugen.

### Synthetischer API-Integrationstest für Vertragsrollen

- Ergänzt wurde `tests/test_contract_department_roles_api.py`. Der Test legt nur im
  pro Testlauf neu angelegten PostgreSQL-Testschema eine synthetische Organisation,
  zwei Krankenhäuser, drei Bereiche, eine Kostenstelle, ein Testkonto und einen Vertrag
  an.
- Über die echten FastAPI-Routen prüft er erfolgreiches Rollen-Speichern und erneutes
  Lesen, HTTP 422 für einen nutzenden Bereich aus dem zweiten Krankenhaus sowie das
  Beibehalten beider Rollen beim Ändern von Kostenstelle und verantwortlicher Person.
- Der kombinierte Backend-Lauf mit Rollen-API- und Modell-/Service-Regressionen endete
  mit **8 passed**. Der pytest-Isolator entfernt das temporäre Testschema am Sessionende;
  UAT-`public`-Daten wurden nicht geändert.
- Zugehörige Frontend-Regressionen endeten mit **11 passed**; TypeScript-Prüfung war
  erfolgreich. Vorhandene React-`act(...)`- und jsdom-Canvas-Warnungen bleiben sichtbar.
- Die manuelle UI-Speicherprüfung in der echten UAT-Organisation bleibt mangels
  Krankenhäusern/Einheiten dort offen. API-Verhalten und Frontend-Verhalten sind aber
  jetzt separat durch isolierte Integrationstests und UI-Tests abgedeckt.

Nächster Schritt:
- Eine Betreiber-Teststruktur für die manuelle Importzuordnung in der isolierten UAT
  bereitstellen; danach Upload und Contract360-Zuordnung mit mehreren Dateien prüfen.

### Vertragszuordnung direkt beim Import

Status: ABGESCHLOSSEN (Implementierung und isolierte Regressionen)
Datum: 2026-10-03

- Die Importseite bietet Administratoren und Vertragsmanagern nun Auswahlfelder für
  Krankenhaus, verantwortlichen Bereich, nutzende Bereiche und Kostenstelle.
- Die Werte werden zusammen mit den Dateien als Multipart-Felder gesendet. Der Import-
  Endpunkt validiert vor der Verarbeitung aktive und organisations-/krankenhausgleiche
  Zuordnungen sowie Rollen- und Kostenstellenkonsistenz. Vertragsmanager bleiben auf
  ihren vorhandenen Krankenhaus-/Abteilungsbereich beschränkt.
- Neue Verträge erhalten die explizite Zuordnung; Duplikate werden nicht umgehängt.
  Analysefehler nach erfolgreicher Persistierung erhalten dieselbe Zuordnung, damit
  spätere manuelle Prüfung nicht den organisatorischen Bezug verliert. Ohne explizite
  Auswahl bleibt die bestehende Zuordnung aus dem aktuellen Arbeitsbereich bestehen.
- Ergänzt wurden API-Weiterleitungs- und UI-Regressionen für den gemeinsamen Upload
  samt Organisationsauswahl.

Dateien:
- `backend/app/api/routes/documents.py`
- `backend/tests/test_document_import.py`
- `frontend/app/import/page.tsx`
- `frontend/app/globals.css`
- `frontend/lib/api.ts`
- `frontend/lib/domain-api/documents.ts`
- `frontend/test/import.test.tsx`

Validierung:
- Backend `tests/test_document_import.py`: **14 passed** im `MEDFLUX_UNIT_ONLY`-Modus;
  keine Trial-Datenbankverbindung.
- Frontend `test/import.test.tsx`: **9 passed**; bestehende React-`act(...)`-Warnungen
  aus asynchronen Seitenzustandsaktualisierungen bleiben sichtbar.
- TypeScript `tsc --noEmit`: erfolgreich.
- `git diff --check`: erfolgreich; Git meldete lediglich bestehende CRLF-Hinweise für
  andere bereits geänderte Dateien.

Grenze:
- Noch nicht manuell gegen UAT geprüft, da die dortige Organisationsstruktur leer ist.
- Die UAT-Organisation bleibt unverändert; der Integrationstest wurde ausschließlich im
  vom pytest-Setup angelegten temporären Schema der freigegebenen Trial-DB ausgeführt.

### DB-Integrationstest für Vertragszuordnung beim Import

Status: ABGESCHLOSSEN (isolierter API-/Persistenztest)
Datum: 2026-10-03

- `tests/test_document_import_assignment_api.py` richtet im pytest-Testschema eine
  synthetische Organisation mit zwei Krankenhäusern, verantwortlichem und nutzendem
  Bereich, fremdem Bereich, Kostenstelle und Vertrag ein.
- Der echte Import-Router speichert die Zuordnung: Krankenhaus, Kostenstelle,
  `scope_type=department` sowie die beiden `contract_department`-Rollen werden direkt
  aus der Datenbank zurückgelesen und geprüft.
- Ein anschließender Importversuch mit einem Bereich des zweiten Krankenhauses wird mit
  HTTP 422 abgelehnt, bevor der Processing-Stub aufgerufen wird. Der zuvor gespeicherte
  Vertrag und seine Rollen bleiben unverändert.
- Zusammen mit `tests/test_document_import.py` liefen beide Dateien gegen die
  `sr415_flow`-Trial-Verbindung, aber ausschließlich im pytest-isolierten Schema:
  **15 passed**. Der Session-Abbau entfernt dieses temporäre Schema; das UAT-`public`
  wurde durch den Test nicht adressiert.

Dateien:
- `backend/tests/test_document_import_assignment_api.py`
- `docs/PROJECT_PROGRESS.md`

Nächster Schritt:
- Keine weiteren Implementierungsarbeiten aus diesem Testschritt offen. Für UAT ist noch
  eine vom Betreiber bereitgestellte Krankenhausstruktur erforderlich. Die in
  `MEDFLUX_MASTER_HANDOVER.md` beschriebenen Storage-/Duplikatrisiken bleiben ein eigener,
  noch nicht bearbeiteter Arbeitsstrang.

### Gesamtregression nach den aktuellen technischen Änderungen

Status: BESTANDENE AUTOMATISIERTE REGRESSION; RUNTIME-UAT NICHT ERSETZT
Datum: 2026-10-03

- Backend-Gesamtsuite im vorgesehenen Testmodus (`APP_ENV=test`, unauthentifizierter
  Test-Opt-in) und gegen das vom pytest-isolator erzeugte Schema der freigegebenen
  Trial-Verbindung: **1346 passed, 3 skipped**. Die drei opt-in Drift-/Migrationstests
  wurden ohne ausdrücklich bereitgestellte disposable DB übersprungen. Das Testschema
  wird nach dem Lauf von `conftest.py` entfernt.
- Der erste Gesamtlauf machte sichtbar, dass zwei Regressionstestgruppen ihre
  Authentifizierungsannahmen aus der lokalen Prozessumgebung erbten. Deren Fixtures sind
  nun isoliert: Contract-Org-Sicherheitschecks laufen explizit ohne den unsicheren
  Entwicklungs-Bypass; Runtime-Konfigurationstests setzen ihren eigenen sicheren
  Ausgangszustand. Danach lief die komplette Backend-Suite erfolgreich.
- Frontend: `npm run lint` erfolgreich mit fünf bestehenden React-Hook-Warnungen;
  Vitest **34 Dateien / 167 Tests bestanden**; `npm run build` erfolgreich, inklusive
  Typprüfung und statischer Seitenerstellung.
- Der zusammengefasste `npm run verify` wurde zunächst im Sandbox-Modus durch verweigerten
  Zugriff von esbuild auf den pnpm-gelinkten Paketpfad unterbrochen. Die Teilkommandos
  wurden separat validiert; die Testausführung bestand nach genehmigtem Lauf außerhalb
  der Sandbox. Der Build meldete Cache-Snapshot-Warnungen, wurde aber erfolgreich beendet.
- `git diff --check` erfolgreich; nur CRLF-Hinweise zu bereits geänderten Dateien.

Dateien dieses Verifikationsschritts:
- `backend/tests/test_contract_delete_guard.py`
- `backend/tests/test_security_runtime_config.py`
- `docs/PROJECT_PROGRESS.md`

Offen:
- Diese Resultate belegen Tests und Produktionsbuild, aber keinen neuen Browser-/Pilotlauf
  mit echten Verträgen. Die bekannte fehlende UAT-Organisationsstruktur, OPTIS-Duplikat-
  und Storage-Drift-Befunde aus dem Master-Handover bleiben ungelöst.

### Wiedereinstieg nach MEDFLUX_MASTER_HANDOVER

Status: DOKUMENTATION GELESEN; KEINE WEITEREN CODEÄNDERUNGEN IN DIESEM SCHRITT
Datum: 2026-10-03

- `MEDFLUX_MASTER_HANDOVER.md` wurde vollständig gelesen (40 Abschnitte). Es beschreibt
  die Architektur, die lokale Pilot-/Datenbanktopologie, die Dokument- und Evidence-Pipeline,
  Rollen/Sicherheit, Tests sowie die konkreten Radiosurgery- und OPTIS-Befunde.
- Der dokumentierte Stand ist die Baseline `c900b07` auf
  `fix/frankfurt-contract-analysis-20261001`; dieser HEAD wurde beim Wiedereinstieg erneut
  verifiziert. Die Hand-over-Aufnahme entstand vor den hier vorhandenen späteren
  Working-Tree-Änderungen und ist daher keine vollständige Beschreibung des aktuellen Diffs.
- Zentrale Lernpunkte für die Fortsetzung: der Produktwert hängt an belegten Fakten
  (Quelle/Seite/Confidence) und deterministischer Berechnung; importiert ist nicht gleich
  erfolgreich analysiert; OCR-Fallback, Fehlerdiagnostik, Storage↔DB-Drift und Duplikate
  müssen als getrennte Fehlerklassen behandelt werden; Assistant-Berechtigungen müssen vor
  und nach dem Modellaufruf fail-closed geprüft werden.
- Die Hand-over-Prioritäten für spätere Arbeit sind Storage-/Datenbank-Abgleich und
  Duplikatlebenszyklus bei OPTIS, danach die irreführende Umgebungs-/Modellinventur und der
  npm/pnpm-Konflikt. Diese Risiken erfordern vor operativen Korrekturen eine explizite,
  isolierte Verifikations- und Rücksetzstrategie; in diesem Schritt wurde daran nichts
  ausgeführt.
- Verifizierter Wiedereinstiegszustand: HEAD `c900b07ffcdd057ff987125a4d0d5ae5e1e9e137`;
  Branch `fix/frankfurt-contract-analysis-20261001`. Die bestehenden Änderungen zu
  Organisationsstruktur/Vertragsrollen und Importzuordnung sowie ungetrackte Dateien bleiben
  unangetastet; nichts wurde gestaged oder committet.

Nächster Schritt:
- Vor weiteren Änderungen den konkreten Arbeitsauftrag anhand der Hand-over-Prioritäten
  festlegen. Für die soeben ergänzte Importzuordnung steht noch ein echter, isolierter
  DB-Integrationstest der Persistierung und Ablehnung krankenhausübergreifender IDs aus.

## 2026-10-03 – WP1: Organisationsstruktur-Vervollständigung (Einheitentyp, Kostenstellen-Pflege, Struktursuche)

Grundlage: `docs/architecture/WORKPLAN_ORGSTRUKTUR_PHASE1_20261003.md` (Anforderungsdokumente vom 26.09.2026 und „Organisationsstruktur“).

**Umgesetzt (DoD-Kette):**
- Model/Migration: `department.unit_type` (optional; `klinik|abteilung|bereich|einheit|station|funktionsbereich`, Check-Constraint `ck_department_unit_type`), Alembic `d5e7f9a01003` — additiv, keine Zeile verändert. Auf dem 55432-Trial-Cluster angewendet (`c4d6e8f00930 → d5e7f9a01003`).
- Backend API: `PATCH /api/cost-centers/{id}` (Bezeichnung, Code, Abteilung im selben Krankenhaus, aktiv/inaktiv; Activity-Log `cost_center.updated`); `GET /api/organization-structure/search?q=` (Einheiten und Kostenstellen nach Name/Code, jeder Treffer mit vollständigem Pfad `A › B › C` und Krankenhaus; Scope-Filter wie `GET /api/organization-structure`); `unit_type` in Department-Create/Update/Read, `unit_types` in der Strukturantwort.
- Frontend: Einheitentyp-Auswahl im Formular „Einheit hinzufügen“ und Anzeige im Baum; Kostenstellen-Chips mit „Bearbeiten“/„Deaktivieren|Aktivieren“; Suchfeld „Einheit oder Kostenstelle suchen“ (z. B. `471120` → `471120 – CT · Radiologie › CT · Krankenhaus Heidelberg`).
- Tests: `backend/tests/test_org_structure_search_wp1.py` (rein, 5), `backend/tests/test_cost_center_patch_and_search_api_wp1.py` (DB, 2), `frontend/test/organization-structure-wp1.test.tsx` (3). Bestehende Tests angepasst (Mock-Exporte).
- Tooling: `scripts/run_wp1_tests.bat` (Guard-Diagnose + pytest + vitest + tsc, Ergebnisse unter `local-archive/test-results/`), `scripts/migrate_trial_db.bat` (nur 55432), `START_MEDFLUX_PILOT.bat` (WSL-55432 + Backend + Frontend + Browser).

**Verifikation (2026-10-03, lokal):** Backend WP1 15 passed; Backend-Gesamtlauf 1377 passed / 3 skipped / 0 failed (Test-Env `AUTH_ENABLED=false`, `MEDFLUX_INSECURE_DEV=true`); Frontend 9/9 passed; `tsc --noEmit` sauber; laufendes Backend liefert beide neuen Routen (OpenAPI) mit 401 ohne Session.

**Entscheidungen (vorläufig, änderbar):** `unit_type` optional; Kostenverteilung in Analysen standardmäßig nach verantwortlicher Einheit (WP5); E-Mail-Versand nach In-App-Benachrichtigung (WP4).

**Offen (nächste WPs):** WP2 Finanzfelder (Zahlungsintervall, Netto/Brutto beide Varianten, Preisanpassung), WP3 Review-Provenienz, WP4 Benachrichtigungen/E-Mail, WP5 Analysen.

## 2026-10-04 – H0–H2/H6: Vertragsregister (Ablösung HYDMedia, Meilenstein M1)

Grundlage: `docs/architecture/HYDMEDIA_GAP_ANALYSIS_AND_INTEGRATION_PLAN_20261004.md` (Entscheidungen D1–D4: MedFlux ersetzt das Altsystem; Status-Set wie HYDMedia; ein Vertrag kann mehreren Gesellschaften gehören; alle Vertragstypen). Datenmigration (H10) bleibt bis zu einer Vereinbarung mit dem Krankenhaus zurückgestellt. Kein neuer Hauptschritt der 18er-Roadmap (18/18 = 100 % bleibt); Erweiterung auf Branch `feature/contract-register-core`.

**Umgesetzt:**
- H0: Ordner mit echten Vertrags-PDFs aus der Git-Verfolgung genommen und ignoriert (bleibt lokal; ältere Historie enthält die Dateien weiterhin). `CLAUDE.md` und Plan-Dokument ergänzt.
- H1.1 Register-Stammdaten am Vertrag (Kurzbeschreibung, interne Nr., Gegenstand, Rahmenvertrag, Partner, Typ/Kategorie, Lagerort, Konto, manuelle Abrechnung, Vertragsart, Beginn/Ende, Laufzeit, Mindestlaufzeit, Kündigungsfrist + „Kündigung zum“, Verlängerung, Erinnerung/Eskalation/ToDo, Kündigung am/zum, Löschfrist). Feld-Herkunft in `contract_field_provenance` (`ai`, `manual`, `ai_confirmed`, `ai_corrected`); Reanalyse überschreibt Menschwerte nie, sondern legt einen KI-Vorschlag ab. Pipeline-Anbindung in `DocumentProcessingService._persist_pipeline`, Bestandsverträge werden beim ersten Aufruf abgeglichen.
- H1.2 Vertrag ohne Dokument anlegen (`POST /api/contracts`, Seite `/contracts/new`); Abteilungsnutzer werden verantwortliche Abteilung.
- H1.3 Deterministische Fristenlogik für fünf Vertragsarten inkl. Monats-/Quartals-/Halbjahres-/Jahresende und Mindestlaufzeit (`app/register/terms.py`); HYDMedia-Beispiele als Tests.
- H1.4 Status-Workflow In Arbeit → Gültig → Gekündigt/Beendet → Gelöscht (+ Reaktivierung), rollen- und prüfgebunden.
- H1.5 Nummernkreis mit Reservierung, nebenläufigkeitssicher; Bestandsverträge je Organisation nummeriert.
- H2 Vertragspartner (Dublettenerkennung, Ähnlichkeitsvorschläge), Vertragstypen/Kategorien (n:m), Auswahllisten, bereinigter Standardkatalog; Mehrfach-Gesellschaften (`contract_hospital`) im Scope berücksichtigt.
- H6 Bemerkungs-Journal (append-only); alle Änderungen mit Feld-Diff im Activity-Log.
- UI: Tabs „Stammdaten“ und „Bemerkungen“ in Contract360, Vertragsliste/Kopf mit Vertragsnr. und Status, `/partners`, `/settings/catalogs`.

**Dateien (Auswahl):** `backend/app/register/*`, `backend/app/api/routes/{contract_register,catalogs}.py`, `backend/app/database/models/register.py`, Migration `20261004_e6f8a0b21004_contract_register_core.py`, `frontend/components/contracts/detail/{ContractRegisterPanel,ContractRemarksPanel}.tsx`, `frontend/components/catalogs/*`, `frontend/app/{contracts/new,partners,settings/catalogs}`.

**Verifikation (2026-10-04, Windows, isolierter PostgreSQL-18-Container):** Backend 1484 passed / 3 skipped / 1 failed – der Fehlschlag (`test_source_navigation.py::test_ocr_word_data_empty_when_unavailable`) tritt identisch auf dem Stand vor der Änderung auf (OCR-Umgebung). Neue Tests: `test_register_terms.py` (26), `test_register_units.py` (31), `test_contract_register_api.py` (7, inkl. Nebenläufigkeit). Migration up/down/up geprüft, Modell ↔ Migration ohne neue Abweichung, Migration + KI-Abgleich auf einer Kopie der lokalen Datenbank geprüft. Frontend `npm run verify` grün (176 Tests, Build). End-to-End über die echte Middleware (Login, Origin-Prüfung, Scope) und im Browser geprüft.
Hinweis: Die DB-Tests liefen gegen einen Wegwerf-Container (Port 55499) mit einem Plugin, das `conftest.py` spiegelt; der vorgesehene WSL-Testcluster 55432 existiert auf diesem Rechner nicht. CI führt die Tests regulär aus.

**Bekannte Punkte:** Schreibanfragen ohne `Origin`-Header werden von der bestehenden Middleware akzeptiert (unverändert, Sicherheitsreview). Warnungen/Arbeitsliste/E-Mail-Erinnerungen für reine Registerverträge folgen mit H5. KI-Werte, die Abteilungs-/Kostenstellen betreffen, werden noch nicht abgebildet.

**Nächster Schritt:** M2 – H5 (Fristen-Entität, Scheduler, E-Mail/ICS, Vertretung, Postfach), danach H3 (Dokumente/Nachträge/Rahmenverträge).

## 2026-10-04 – M2: Fristen & Erinnerungen (H5) und Dokumente/Rahmenverträge (H3)

Branch `feature/deadlines-documents` (auf `feature/contract-register-core`). Entscheidungen D5/D6 mit sicheren Standards umgesetzt: Tageslauf im Backend per Opt-in (`REMINDER_SCHEDULER_ENABLED`) oder per Aufgabenplanung (`python -m app.jobs.daily`); E-Mail per SMTP, ohne SMTP nur Postfach + Warteschlange.

**Umgesetzt:**
- H5.1 `contract_deadline`: Systemtermine aus den Register-Fristen (Kündigungsfrist, Ende fester Laufzeit, „auf Beendet setzen“ nach Kündigung), automatisch nachgeführt. Verpasste Fristen bleiben offen/überfällig und eskalieren, bis sie erledigt werden; danach folgt die nächste Periode. Manuelle Termine mit Zuständigkeit, Eskalation, ToDo, E-Mail/ICS.
- H5.2 Tageslauf (Advisory-Lock, idempotent über `dedupe_key`): Erinnerungen, Überfälligkeit, Eskalation; E-Mail-Warteschlange mit Wiederholung; ICS-Einladungen; minimale Mailinhalte (Datenschutz); `job_run`-Monitoring, manueller Lauf je Organisation.
- H5.3 Vertretungen (Zeiträume, Standardvertretung) und E-Mail-Einstellungen je Konto; Vertretung erhält Kopie im Postfach.
- H5.4 Postfach mit Gelesen-Status; Glocke zählt ungelesene Erinnerungen; Übersicht `/termine` (Wiedervorlage); Admin-Panel „Tageslauf“.
- KI-Bezug: Termine, deren Grundlage ungeprüfte KI-Werte sind, werden gekennzeichnet.
- H3.1 Mehrere typisierte Dokumente je Vertrag (Hauptdokument, gültig/ungültig, Dokumentart), Upload mehrerer Dateien; Analyse über `DocumentProcessingService.attach_to_contract` – Nachträge und Kündigungsschreiben erzeugen ausschließlich KI-Vorschläge an den Stammdaten (mit Dokumentname).
- H3.2 Rahmenverträge über `contract_relation` (`governs`); KI erkennt Verweise auf bestehende Rahmenvertragsnummern und schlägt die Verknüpfung vor, Mensch bestätigt/verwirft.
- H3.3 Import-Seite: Ziel „Neuer Vertrag“ oder „Zu bestehendem Vertrag hinzufügen“.
- Middleware: Postfach-gelesen und eigene Benachrichtigungs-Einstellungen sind für jede Rolle erlaubt (nur eigenes Konto).

**Migrationen:** `f7a9b1c31004` (Fristen/Benachrichtigungen/Vertretung/Joblauf), `g8b0c2d41004` (Dokument-Metadaten, eindeutige Relationen). Up/Down/Up und Modellabgleich geprüft; alle drei neuen Migrationen sowie der Tageslauf auf einer Kopie der lokalen Datenbank geprüft.

**Verifikation (2026-10-04, isolierter PostgreSQL-18-Container):** Backend 1510 passed / 3 skipped / 1 failed (vorbestehend, OCR-Umgebung). Neue Tests: `test_deadlines_units.py` (20), `test_deadlines_api.py` (4), `test_contract_documents.py` (2). Frontend `npm run verify` grün (38 Dateien, 184 Tests, Build). End-to-End über die echte API/Middleware: Systemfrist, Tageslauf (Erinnerung an Zuständige und Vertretung, E-Mails in Warteschlange ohne SMTP, zweiter Lauf ohne Dubletten), Postfach, Vertretung, Upload, Erledigt. Dabei gefunden und behoben: Ungelesen-Zähler berücksichtigte die Sichtbarkeit nicht. Browser-Durchklick dieses Mal nicht möglich (Login-Formular im automatisierten Browser reagierte nicht); UI durch Komponententests abgedeckt.

**Bekannte Punkte:** Kein echter SMTP-Versand getestet (Fake-Transport in Tests). Nutzer ohne Krankenhaus-Mitgliedschaft sehen organisationsweite Verträge nicht (bestehende Scope-Regel) – Erinnerungen an sie bleiben unsichtbar; Zuständige sollten passende Mitgliedschaften haben.

**Nächster Schritt:** M3 – H4 Finanzen (Finanzeinträge, Leistungskatalog, Kostenstellen-Aufteilung, Preisanpassung), danach H8 Rechte/Vertraulichkeit, H7 Listen/Export/Berichte.

## 2026-10-04 – M3/H4: Finanzdaten (Finanzeinträge, Leistungskatalog, Kostenstellen, Preisanpassung)

Branch `feature/finance` (auf `feature/deadlines-documents`).

**Umgesetzt:**
- H4.1 `contract_finance_entry`: Ausgaben/Einnahmen mit Betrag, Netto/Brutto, Steuersatz, Währung, Intervall, Gültig ab/bis, Kostenart. Deterministische Berechnung kalkulatorisch auf Basis ganzer Monate (`app/finance/calc.py`): laufendes Jahr, bisher, bis Vertragsende, Gesamtlaufzeit, jährlich aktuell – je Währung, ohne Umrechnung; ohne bekanntes Vertragsende werden „bis Vertragsende“/„Gesamtlaufzeit“ nicht geraten. CSV-Export (Ausgaben/Einnahmen).
- H4.2 `contract_service_item` (Leistungskatalog: Leistung, Betrag, Einheit, zzgl. USt., Gültigkeit).
- H4.3 `contract_cost_allocation`: Aufteilung auf Kostenstellen (Summe 100 %, gleiches Krankenhaus, Weiterbelastung); größter Anteil wird Hauptkostenstelle. Strukturierte Preisanpassung als Registerfelder (prozentual/Index/Festpreis/Verhandlung) mit Projektion bei prozentualer Anpassung und Systemtermin „Preisanpassung prüfen“ einen Monat vorher.
- KI: Vorschläge für Finanzeinträge (wiederkehrende Kosten, Preisstufen je Vertragsjahr, Einmalkosten) und Leistungen (variable Kosten, Stundensatz, Reisekosten) aus der akzeptierten Extraktion; fehlende Steuerbasis/-satz nur als gekennzeichnete Annahme; Übernehmen/Verwerfen, nie automatisch. Preisanpassungsklausel wird gelesen und als Registervorschlag abgelegt.
- Vertragsliste nutzt gepflegte Finanzeinträge für die Jahreskosten.
- UI: Tab „Finanzen“ mit Übersichtsmatrix, KI-Vorschlägen, Einträgen, Leistungskatalog, Kostenstellen-Aufteilung; Stammdaten-Abschnitt „Preisanpassung“.

**Migration:** `h9c1d3e51004` (additiv). Up/Down/Up, Modellabgleich und Kopie der lokalen Datenbank geprüft.

**Verifikation (2026-10-04):** Backend 1538+ passed / 1 failed (vorbestehend, OCR-Umgebung); neue Tests `test_finance_calc.py` (14), `test_finance_ai.py` (12), `test_finance_api.py` (2), Preisanpassungs-Termin in `test_deadlines_units.py`. Frontend `npm run verify` grün (39 Dateien, 187 Tests). Im Medflux-Browserprofil gegen eine Testinstanz geprüft: 3.500 € netto monatlich + 3 % ab 2027 + 2.000 € einmalig ⇒ Gesamtlaufzeit 131.817,80 € netto (2026–2028); Umstellung auf feste Laufzeit ersetzt die Fristen automatisch.

**Bekannte Punkte:** Sortieren/Filtern nach Jahreskosten in der Vertragsliste nutzt weiterhin die KI-Berechnung (gepflegte Finanzeinträge nur in der Anzeige). Keine Währungsumrechnung. Dashboard-Summen folgen in H7.

**Nächster Schritt:** H8 Rechte-Matrix und vertrauliche Verträge, danach H7 Listen/Export/Berichte/Analysen und H9 Aufbewahrung.

## 2026-10-04 – M3 abgeschlossen: H8 Rechte/Vertraulichkeit, H9 Aufbewahrung, H6.2 Historie, H7 Register/Export/Berichte, 13a Entscheidungsvorlagen

Branch `feature/permissions-reports` (auf `feature/finance`). Kein neuer Hauptschritt der 18er-Roadmap (18/18 = 100 % bleibt). H10 (Datenübernahme) bleibt zurückgestellt.

**Umgesetzt:**
- H8.1 Zentrale Rechte-Matrix `app/auth/permissions.py` (Rolle × Aktion, `require()` in allen neuen und umgestellten Routen); `GET /api/permissions`; Seite „Rollen & Rechte“ (`/settings/roles`).
- H8.2 Vertrauliche Verträge (Kennzeichen am Vertrag oder am Vertragstyp) mit Einzelfreigaben; zentral in `scoped_contract_ids` ausgeblendet (fail-closed). Sichtbar für Admin, Verantwortliche, Erinnerungsempfänger und Freigegebene. UI im Reiter Stammdaten.
- H9 Aufbewahrung je Vertragstyp (Standard 10 Jahre) oder je Vertrag; „Löschen ab“ = 1.1. nach Jahresende + Frist; Systemtermin „Löschprüfung“. KI erkennt Datenschutzbezug (AVV/Art. 28 DSGVO) als Vorschlag, ohne Menschwerte zu überschreiben.
- H6.2 Reiter „Historie“ am Vertrag (Aktivitäten, Fakt-Prüfungen, manuelle Werte, Dokumente, versendete E-Mails); organisationsweite Historie (`/audit`) mit Filtern Benutzer/Bereich/Vertrag/Zeitraum, Seitenweise, CSV-Export (protokolliert, Excel-sicher).
- H7.1 Vertragsregister `/register`: 32 Spalten (Register, Fristen, Personen, Organisation, Kosten, Aufbewahrung), Spaltenauswahl, Spaltenfilter (leer/nicht leer/Werteliste/Bereich/„in N Tagen“/„ich“), Gruppierung (2 Ebenen) mit Anzahl und Summen, Sortierung, Suche. Berechnung gebündelt ohne N+1.
- H7.2 Gespeicherte Ansichten (`saved_view`): persönlich oder global (nur Admin), Standardansichten „Meine Verträge“, „Meine Wiedervorlage“, „Kündigungsfrist < 90 Tage“, „In Arbeit“, „Zum Löschen vorgesehen“, „Gelöschte Verträge“.
- H7.3 Baum Gesellschaft → Abteilung mit Anzahl als Filter.
- H7.4 Excel-Export der aktuellen Ansicht (mit Gruppen- und Info-Blatt), Portfoliobericht als Excel, Deckblatt-PDF je Vertrag (lokal mit PyMuPDF). Exporte werden protokolliert.
- H7.5 `/analysen`: Kennzahlen, Handlungsbedarf (ohne Verantwortliche, ohne Kosten, ohne Ende, Löschprüfung, Lieferantenkonzentration) mit Sprung in das Register, Kosten je Gesellschaft/Abteilung/Kostenstelle/Typ/Partner, Ausgaben/Einnahmen je Jahr (inkl. Prognose), Fristen der nächsten 6 Monate, Status. Diagramme nach Dataviz-Regeln (validierte Palette, Tabellenansicht, Hover).
- 13a Entscheidungsvorlage vor Kündigungsfristen (Reiter Termine) und Übersicht `/verlaengerungen`: was ohne Handeln passiert, Kosten der Verlängerung, Preisanpassung, weitere Verträge mit dem Partner, Datenlücken – jeweils mit Begründung; Entscheidung wird nur auf Klick als Lifecycle-Entscheidung erfasst, nichts automatisch.

**Migrationen:** `i0d2e4f61004` (Vertraulichkeit, Freigaben, Aufbewahrung), `j1e3f5a71004` (gespeicherte Ansichten). Up/Down/Up und Modellabgleich geprüft; alle sechs M1–M3-Migrationen auf einer Kopie der lokalen Datenbank geprüft (Kopie danach gelöscht).

**Verifikation (2026-10-04, isolierter PostgreSQL-18-Container):** Backend 1557 passed / 3 skipped / 1 failed (vorbestehend, OCR-Umgebung). Frontend: Lint, 44 Dateien / 197 Tests und Produktions-Build grün. Im Medflux-Browserprofil gegen eine Testinstanz geprüft (Register, Analysen, Entscheidungsvorlage); dabei zwei Fehler gefunden und behoben (feste Laufzeit meldete „Frist nicht berechenbar“; Lieferantenkonzentration für Verträge ohne Partner).

**Neue Tests:** Backend `test_confidential_retention.py` (5), `test_history.py` (3), `test_register_grid.py` (5), `test_renewal_brief.py` (4). Frontend `contract-register` (Vertraulichkeit/Aufbewahrung), `permissions`, `history`, `register-grid`, `register-portfolio`, `renewal-brief`.

**Bekannte Punkte:** Die ältere KI-Vertragsliste (`/contracts`) sortiert weiterhin nach KI-Kosten; das neue Register nutzt die gepflegten Finanzdaten. Semantische Suche über Vertragsinhalte und KI-Fließtext für Entscheidungsvorlagen sind offen (§4A). Diagramme nur im hellen Design (die App hat kein dunkles Design).

**Nächster Schritt:** Abnahme mit Fachanwender:innen, danach Merge der Feature-Branches nach `main` (CI + Release-Gate). H10 erst nach Vereinbarung mit dem Krankenhaus.

## 2026-10-04 – Restpunkte des HYDMedia-Plans geschlossen

Branch `feature/register-gaps` (auf `feature/permissions-reports`). Kein neuer Hauptschritt (18/18 = 100 % bleibt).

**Umgesetzt:**
- Klassische Vertragsliste sortiert und filtert nach den gepflegten Jahreskosten (Zwischenspeicher `contract.maintained_annual_cost`, aktualisiert bei Finanz-/Stammdatenänderung und im Tageslauf), sonst wie bisher nach KI-Wert.
- Gespeicherte Ansichten der klassischen Liste liegen auf dem Server; frühere Browser-Ansichten werden einmalig übernommen.
- Register: Spalte „Kostenstellen-Aufteilung“; Portfolio-Kosten je Kostenstelle anteilig nach Aufteilung.
- Leistung: Zeilen-Zwischenspeicher je Organisation mit Daten-Fingerabdruck, Baum in derselben Antwort. Messung mit 3.000 Verträgen: ~1 s beim ersten Aufbau, ~3 ms danach; Excel-Export 0,4 s.
- Historie vollständig: KI-Übernahmen in Stammdaten, Systemtermine (angelegt/angepasst/entfernt), zugestellte Erinnerungen/Eskalationen (Akteur „System“), Dokument-Uploads, Katalogänderungen mit Vorher/Nachher.
- Inhaltssuche `/suche` über alle Vertragsdokumente (lokal): deutscher Wortstamm, Teilwörter, Fachsynonyme, Phrasen; jeder Treffer mit Dokument, Seite und Sprung in den PDF-Viewer. Optional inhaltliche Ähnlichkeit über ein lokales Embedding-Modell (`SEARCH_EMBEDDING_MODEL`, nur localhost); derzeit ist kein Embedding-Modell installiert, daher aus.
- Entscheidungsvorlage: Kurzfassung durch die lokale KI auf Knopfdruck; jede Zahl der Antwort muss in den berechneten Fakten stehen, sonst wird sie verworfen.
- E-Mail: Versand über echtes SMTP-Protokoll (Anmeldung, Empfänger, ICS) gegen einen lokalen Testserver geprüft.

**Migrationen:** `k2f4a6b81004` (Kosten-Zwischenspeicher, Indizes, Ansichtsart „contracts“), `l3a5b7c91004` (Seitentexte + Volltext-/Trigramm-Index). Up/Down/Up und Modellabgleich geprüft; alle acht Migrationen seit dem letzten Stand der lokalen Datenbank auf einer Kopie geprüft, dort 6 Dokumente indiziert und durchsucht (Kopie gelöscht).

**Verifikation:** Backend 1569 passed / 3 skipped / 1 failed (vorbestehend, OCR-Umgebung). Frontend: Lint, 45 Dateien / 199 Tests, Build grün. Im Browser geprüft: Inhaltssuche, KI-Kurzfassung mit dem lokalen Modell qwen3:8b (Zahlenprüfung bestanden).

**Bekannte Punkte:** Diagramme nur hell (die App hat kein dunkles Design). Semantische Suche erst nach Installation eines lokalen Embedding-Modells. H10 zurückgestellt.

**Nächster Schritt:** Abnahme, Merge der Feature-Branches nach `main`, danach `alembic upgrade head` auf der Produktivdatenbank.

## 2026-10-04 – Frontend-UX-Plan U0–U10 umgesetzt

Branch `feature/ui-refactor` (auf `feature/register-gaps`). Plan: `docs/architecture/FRONTEND_UX_ANALYSIS_AND_REFACTORING_PLAN_20261004.md` (Abschnitt 0 = Umsetzungsstand). Kein neuer Hauptschritt (18/18 bleibt).

**Umgesetzt:**
- U0: Playwright-Journeys mit axe, Bildvergleich, abgesicherter e2e-Seed (verweigert Port 5432 und DB `medflux`), Ausgangsbericht `docs/ux/BASELINE_20261004.md`.
- U1: Inter/JetBrains Mono lokal, 7-stufige Schriftskala, semantische Farb-Tokens mit dunklen Werten, stylelint-Regeln (69 → 7 Schriftgrößen, 263 → 0 Hex-Farben außerhalb der Tokens, 31 → 0 Kontrastfehler).
- U2: Bausteine in `components/ui` (Dialog, Drawer, Tabs, DataTable, Badge, Breadcrumbs, Skeleton, Tooltip, KpiTile, Formular-Wächter).
- U3: neuer Anwendungsrahmen mit 6 Bereichen, Strg+K-Befehlspalette, Tastenkürzel, Kontomenü mit Darstellung.
- U4: Vertragsseite mit Objektkopf und 7 Reitern, eine Vertragsliste (`/register`), Startseite „Mein Tag“, Import-Assistent.
- U5: verständliche Texte und Feldhilfen, Einrichtungs-Checkliste für Admins (`GET /api/admin/setup-status`), „Ansicht als Rolle“ (nur Darstellung), Historienfilter in der Adresse, Entwicklermodus mit API-Zeiten, `docs/FRONTEND_CONVENTIONS.md`, Bausteinreferenz `/developer/components`.
- U6: axe-Prüfung aller 25 Seiten hell, dunkel und im Windows-Kontrastmodus; Katalog-Reiter korrigiert.
- U7: PDF-Viewer und Reiter-Panels werden nachgeladen (Vertragsseite 150 → 140 kB).
- U8: Darstellung je Konto gespeichert (`GET/PUT /api/profile/preferences`).
- U9: kein waagerechtes Scrollen bei 1440/900/390 px (automatisch geprüft); Registerspalte und Telefon-Umbrüche korrigiert.
- U10: PR-Vorlage, Leistungsbudget, neue Referenzbilder; 375 ungenutzte CSS-Regeln (~43 KB) entfernt.

**Migration:** `m4b6c8d01004` (`account.ui_preferences`, JSONB, nullable). Up/Down/Up auf einer Wegwerf-DB geprüft.

**Verifikation:** Backend 1573 passed / 3 skipped / 1 failed (vorbestehend, OCR-Umgebung `test_ocr_word_data_empty_when_unavailable`). Frontend `npm run verify` grün (45 Dateien / 178 Tests, Build). Playwright 146/146 (Journeys, axe-Sweep, Layout, Bildvergleich Desktop + Telefon) gegen die Wegwerf-DB.

**Offen:** Combobox/Datums-/Betragsfeld als eigene Bausteine; Lighthouse noch manuell; Usability-Runde mit Anwendern (SUS, Aufgabenzeiten); restliche Alt-CSS-Dateien (~170 KB) weiter zusammenführen.

**Nächster Schritt:** Abnahme im Browser, Merge der Feature-Branches nach `main`, danach `alembic upgrade head` auf der Produktivdatenbank (jetzt bis `m4b6c8d01004`).

### Nachtrag 2026-10-04 – Benutzer-Massenimport

Entscheidung des Product Owners: Der Administrator vergibt jedem neuen Benutzer das Erstpasswort.

- Backend: `POST /api/users/import` (`app/auth/user_import.py`), nur `user.admin`. Erst prüfen (`dry_run`), dann alles oder nichts. Prüft je Zeile E-Mail (doppelt in der Liste / schon vorhanden), Name, Rolle (deutsche Bezeichnungen oder Codes, leer = Leser), Krankenhaus und Bereich (Kürzel oder Name, eindeutig, aktiv, in der eigenen Organisation), Erstpasswort (mindestens 10 Zeichen, nicht gleich E-Mail/Name). Einzel- und Massenanlage nutzen denselben Helfer `_create_member`. Audit: `account.created` je Benutzer und `account.bulk_imported`; Passwörter werden weder zurückgegeben noch protokolliert. Höchstens 500 Zeilen.
- Frontend: Abschnitt „Mehrere Benutzer importieren“ unter `/settings/users` (`components/users/UserImport.tsx`, `lib/user-import-csv.ts`): Vorlage, CSV aus Excel (Semikolon/Komma/Tab), Vorschau mit Fehlern je Zeile, Erstpasswort je Zeile eintragen oder „Fehlende Passwörter erzeugen“ (Zufallsgenerator des Browsers), Anlegen erst nach fehlerfreier Prüfung, danach optional „Zugangsdaten herunterladen“ mit Hinweis zum Löschen.
- Nebenbei: doppelter „Mein Profil“-Knopf im Einstellungsrahmen entfernt; Benutzerseite mit Seitenabstand und ohne waagerechtes Scrollen auf dem Telefon; Anmeldeformular mit `method="post"` (kein Absenden über die Adresse vor dem Laden); Arbeitsbereichsauswahl mit gültiger ARIA-Rolle.
- Tests: Backend `tests/test_user_import.py` (3); Frontend `test/user-import.test.tsx` (5); Playwright-Journey 9 (Liste hochladen, fehlendes Passwort erkannt, Passwörter erzeugen, anlegen, Anmeldung des neuen Benutzers mit dem Erstpasswort).
- Verifikation: Backend 1576 passed / 3 skipped / 1 failed (vorbestehend, OCR); `npm run verify` grün (46 Dateien); Playwright 147/147.
- Hinweis: Ein Zwang zum Passwortwechsel bei der ersten Anmeldung gibt es noch nicht.

## 2026-10-06 – Stammdaten an einem Ort (S1–S5)

Branch `feature/stammdaten-hub` (auf `feature/ui-refactor`). Plan und Aufbau: `docs/architecture/STAMMDATEN_20261006.md`. Kein neuer Hauptschritt (18/18 bleibt), keine Migration.

**Status:** umgesetzt.

**Umgesetzt:**
- S1: Bereich `/stammdaten` (Navigation „Verwaltung → Stammdaten“, `g d`, alle Datenarten in Strg+K) mit Bereichsnavigation und Übersicht (Bestand je Datenart, zuletzt geändert, Hinweise auf Dubletten und Partner ohne Vertrag, Suche über alle Stammdaten). Alte Seiten leiten weiter (`/partners`, `/settings/organization`, `/settings/catalogs`); Nummernkreis eigene Seite `/settings/nummernkreis`. Einrichtungs-Checkliste, Verwaltungsseite, Entwicklerseite und Befehlspalette verweisen auf die neuen Adressen.
- S2: eine Bedienung für alle Datenarten (`components/master-data/`: `EntityManager`, `EntityEditor`, `EntityForm`, Definitionen je Art). Tabelle mit Suche/Filter/Status in der Adresse, Bearbeiten in der Seitenleiste, Pflichtfeldprüfung, Strg+S, Rückfrage bei ungespeicherten Änderungen, Strukturbaum für Abteilungen. Die drei alten Verwaltungen (`PartnerManager`, `CatalogManager`, `OrganizationStructureManager`) und ihre CSS-Regeln sind entfernt.
- S3: Spalte „Verträge“ mit Link in die gefilterte Vertragsliste (`GET /api/master-data/usage`), Deaktivieren mit Rückfrage bei verwendeten Einträgen, Änderungsverlauf je Eintrag (`GET /api/history?object_type=&object_id=`), Dubletten zusammenführen (`POST /api/catalogs/partners/{id}/merge`, Vertragshistorie `contract.partner_merged`).
- S4: „Neuer Partner“/„Neuer Typ“ im Formular „Vertrag anlegen“ und „Neuer Partner“ in den Vertrags-Stammdaten mit demselben Formular (`QuickCreate`, nachgeladen); der neue Eintrag ist danach ausgewählt.
- S5: CSV-Import (Vertragspartner, Abteilungen, Kostenstellen, Auswahllisten; `POST /api/master-data/import/{kind}`, erst prüfen, alles oder nichts, Hinweise blockieren nicht) und CSV-Export der sichtbaren Zeilen. `lib/csv.ts` ist jetzt auch die Grundlage des Benutzerimports.
- Nebenbei: doppelte Kürzel bei Krankenhaus/Abteilung/Kostenstelle liefern 409 statt Serverfehler; leere Namen/Kürzel 422. `useFocusTrap` setzte bei jedem neuen `onClose` den Fokus neu (Eingaben in Seitenleisten verloren den Fokus nach dem ersten Zeichen) – behoben. Rechte für Bedienelemente kommen aus `lib/use-permissions.ts` (`/api/permissions`, berücksichtigt die Rollenvorschau). `Drawer` kann breit (`wide`).

**Dateien (Auswahl):** `backend/app/master_data/{service,imports}.py`, `backend/app/api/routes/master_data.py`, `backend/app/register/catalogs.py`, `backend/app/api/routes/{catalogs,history,organization_structure,cost_center_routes,admin_setup}.py`, `backend/app/history/service.py`; `frontend/components/master-data/**`, `frontend/app/stammdaten/**`, `frontend/app/settings/nummernkreis/page.tsx`, `frontend/lib/{master-data,use-permissions,csv,lookup-fields}.ts`, `frontend/lib/domain-api/masterData.ts`, `frontend/app/master-data.css`.

**Tests:** Backend `tests/test_master_data.py` (7: Übersicht/Verwendung mit Bereich und gelöschten Verträgen, Zusammenführen, Partner-Import alles-oder-nichts, Struktur-Import mit Elterneinheiten aus der Datei, Auswahllisten-Import, Einzelhistorie, 409 bei doppelten Kürzeln). Frontend `test/master-data.test.tsx` (13) und `test/master-data-quick-create.test.tsx` (1), jeweils mit axe. Playwright-Journey 10 (Partner anlegen, finden, deaktivieren) und die Stammdaten-Seiten im axe- und Layout-Durchlauf.

**Verifikation:** Backend 1584 passed / 3 skipped / 0 failed. Auf diesem Rechner gibt es den WSL-Testcluster nicht; gelaufen in einem Wegwerf-Container (`postgres:18` + Python 3.12, CI-Identität `127.0.0.1:5432/medflux` nur im Container-Netz). Die 8 Fehler in `test_text_extraction.py` beim ersten Lauf kamen von einer fehlenden Schrift im schlanken Container und verschwinden mit `fonts-dejavu-core`. Frontend `npm run verify` grün (46 Testdateien). Playwright 168/168 gegen eine Wegwerf-Datenbank (Docker, Port 55499), Bildvergleich-Referenzen erneuert (neue Seitenleiste mit „Stammdaten“; dazu Hell/Dunkel-Schalter und Banner aus 195f75e, deren Referenzen noch nicht erneuert waren). Im Windows-Kontrastmodus hatte das Banner auf „Mein Tag“ unlesbaren Text (aus 195f75e) – behoben. Leistungsbudget: Vertragsseite 143 kB (vorher 140), Stammdaten-Seiten ≤ 120 kB.

**Offen:** Verwendung weiterer Auswahllisten zählen; Import für Krankenhäuser/Vertragstypen; „Neu anlegen“ für Kostenstellen in der Kostenaufteilung und Abteilungen in der Zuständigkeit.

**Nächster Schritt:** Abnahme im Browser, dann Merge mit den übrigen Feature-Branches.

## 2026-10-06 – Ein Thema, eine Stelle: Fristen & Aufgaben, Vertragslisten, Verwaltung

Branch `feature/stammdaten-hub` (nach den Stammdaten S1–S5). Grundlage: UX-Analyse vom selben Tag – dieselbe Kündigungsfrist stand an fünf Stellen, davon zweimal aus verschiedenen Quellen. Kein neuer Hauptschritt, keine Migration.

**Status:** umgesetzt.

**Umgesetzt:**
- **Fristen & Aufgaben** (`/fristen`, Menü „Verträge“, `g t`): Reiter Termine, Kündigungsentscheidungen, Aufgaben; Reiter und „Nur meine“ in der Adresse. `/termine`, `/verlaengerungen`, `/work-queue` leiten weiter. Entscheidung: Fristdaten kommen **nur** aus den gepflegten Vertragsdaten (Systemtermine). Die KI-Arbeitsliste erzeugt keine Aufgaben mehr für Kündigungsfrist, Vertragsende, Verlängerung und ausgelaufene Verträge (`work_queue/derive.DEADLINE_ITEM_TYPES`); vorhandene Einträge dieser Art sind in Liste, Glocke, Berichten und Vertragsseite ausgeblendet (`task_items_only`), nicht gelöscht. „Aufgaben“ enthält nur noch Prüfbedarf, fehlende Kosten, Geräte- und Service-Level-Punkte. Das Postfach behält seine Wiedervorlage (enthält auch Termine vertretener Kolleginnen und Kollegen) und verweist auf „Fristen & Aufgaben“.
- **Vertragslisten**: Archiv (`/archiv`) und Prüfungen (`/review`) zeigen jetzt die Vertragsliste mit fester Standardansicht („Archiv“ mit „Wiederherstellen“ je Zeile, „Zu prüfen“ mit „Prüfen“ je Zeile) – gleiche Spalten, Filter, Gruppen und Excel-Export wie überall. Backend: `GridSpec.archived`, Spalte „Archiviert am“, Standardansichten `review` und `archive`, `system_key` in der Ansichtsliste, `?ansicht=<system_key>` auf `/register`. Die alte Tabelle `ContractTable` ist entfernt. Seiten mit fester Ansicht überschreiben die zuletzt genutzte Ansicht der Vertragsliste nicht.
- **Verwaltung**: alle Seiten unter `/admin` und `/settings` haben dieselbe Bereichsnavigation wie die Stammdaten (Übersicht, Benutzer, Rollen & Rechte, Stammdaten, Nummernkreis, Vertragslöschung, Einstellungen, Entwicklung; je nach Rolle). Eine gemeinsame Umsetzung `components/shell/AreaNav.tsx` für Stammdaten und Verwaltung.
- Navigation: fünf statt sechs Bereiche (Start, Verträge, Prüfung, Auswertungen, Verwaltung); „Aufgaben“ heißt überall so (vorher „To-dos“ auf der Seite).

**Hinweis zur Prüfliste:** Die frühere Prüfungsliste zählte Verträge mit prüfbedürftigen Warnungen; die Ansicht „Zu prüfen“ zeigt Verträge, deren KI-Analyse noch nicht geprüft ist (das, was „Prüfen“ öffnet). Prüfbedürftige Warnungen stehen weiterhin als Aufgaben unter „Fristen & Aufgaben“.

**Tests:** Backend `test_pr4_equipment_work_item.py` (Fristwarnungen erzeugen keine Aufgaben; Altbestand ausgeblendet, Fristtyp als Filter abgelehnt), `test_register_grid.py` (Archiv-Ansicht, neue Standardansichten). Frontend `test/areas.test.tsx` (Reiter, Adresse, Rollen, Verwaltungsnavigation), `test/register-grid.test.tsx` (Archiv wiederherstellen, Prüfen-Ansicht, letzte Ansicht bleibt), `test/work-queue.test.tsx` und `test/shell.test.tsx` angepasst; `test/contract-list-preferences.test.tsx` mit der alten Tabelle entfernt.

**Verifikation:** Backend 1586 passed / 3 skipped / 0 failed (Wegwerf-Container). Frontend `npm run verify` grün (46 Testdateien); `/fristen` 111 kB, `/archiv` und `/review` 110 kB, Vertragsseite 143 kB. Playwright 168/168 (eigener Build-Ordner `NEXT_DIST_DIR=.next-e2e`; Bildvergleich-Referenzen erneuert). Nebenbei: `next dev` behält kompilierte Seiten länger (`onDemandEntries`), sonst verwarf er im Testlauf Seitenpakete (404, leere Seite); Benutzerzeilen brechen neben der Bereichsnavigation um statt überzulaufen; überflüssige „Zurück zu Einstellungen“-Links entfernt.

## 2026-10-06 – Vertragsregeln, KI-Übersicht am Vertrag, häufige Fragen, Sicherheitsseite

Branch `feature/stammdaten-hub`. Anlass: Vergleich mit einem Wettbewerber (Zefort) – übernommen, was zu Medflux passt (Regeln als Spalten, KI-Übersicht mit Prüfstatus, Fragevorschläge), bewusst nicht: E-Signatur, Vertragserstellung aus Vorlagen, CRM-Anbindungen.

**Status:** umgesetzt.

**Umgesetzt:**
- **Vertragsregeln** („Playbooks“): Die Administration legt unter Stammdaten → Vertragsregeln fest, was jeder Vertrag erfüllen soll (Kündigungsfrist mindestens, Laufzeit höchstens, Verlängerung höchstens, Preiserhöhung höchstens, jährliche Kosten höchstens, Pflichtangabe vorhanden; optional nur für bestimmte Vertragstypen). Das System prüft im Code gegen die gepflegten Vertragsdaten – nie die KI; fehlt eine Angabe, lautet das Ergebnis „Angabe fehlt“. Vertragsliste: Spalten „Vertragsregeln“ (Erfüllt/Unvollständig/Verstoß) und „Regelverstöße“, Standardansicht „Regelverstöße“. Stammdaten: Spalte „Verstöße“ je Regel mit Link in die gefilterte Liste. Vertragsseite: Abschnitt „Vertragsregeln“ mit Ergebnis und Begründung je Regel. Neue Tabelle `contract_rule`, Migration `n5c7d9e01006` (auf einer Wegwerf-DB hoch/runter/hoch geprüft). Code: `backend/app/rules/service.py`, `backend/app/api/routes/rules.py`, `frontend/components/master-data/definitions/rules.tsx`, `frontend/components/contracts/detail/ContractRulesSection.tsx`.
- **KI-Übersicht am Vertrag** (`AiFillSummary`): „KI hat N Angaben aus dem Dokument übernommen“ mit noch nicht bestätigten/bestätigten/korrigierten Angaben, Status „Prüfung offen“/„Geprüft“ und „Jetzt prüfen“.
- **Häufige Fragen im KI-Assistenten** auf Vertragsseiten (Leistungsumfang, Laufzeit/Kündigung, Kosten, Reaktionszeiten, Preisanpassung) – ein Klick stellt die Frage.
- **„Vertrag hinzufügen“** in der Vertragsliste (`AddContractMenu`): Dokument importieren oder ohne Dokument anlegen.
- **Sicherheit & Datenschutz** (`/sicherheit`, alle Rollen): nur belegbare Aussagen (lokale Speicherung, keine externen KI-Dienste, PBKDF2-Passwörter, Rollen, Vertraulichkeit, Historie, zweistufiges Löschen) und was die IT selbst sicherstellt (Verschlüsselung der Datenträger, Datensicherung).

**Offene Punkte / Hinweise:**
- Die Adressen der KI-Dienste sind standardmäßig lokal (127.0.0.1), werden aber im Code nicht auf lokale Ziele beschränkt; eine falsch konfigurierte Adresse würde nicht abgewiesen. Empfehlung: in `backend/app/core/config.py` beim Start erzwingen (fail closed).
- Medflux verschlüsselt die Dateiablage nicht selbst. Zwei-Faktor-Anmeldung, SSO (Active Directory/Entra) und Pflicht zum Passwortwechsel bei der ersten Anmeldung fehlen noch.
- Favoriten (Stern am Vertrag) bewusst zurückgestellt; die Ansicht „Meine Verträge“ deckt den häufigsten Fall ab.
- Produktiv- und Entwicklungsdatenbank müssen auf `n5c7d9e01006` migriert werden (`python -m alembic upgrade head`), sonst lädt die Vertragsliste nicht (Tabelle `contract_rule` fehlt).

**Tests:** Backend `tests/test_rules.py` (alle Regelarten ohne Raten, Pflege nur durch Administration, Ergebnis je Vertrag, Spalten der Vertragsliste, Verstöße je Regel, deaktivierte Regeln), `tests/test_register_grid.py` (Standardansichten). Frontend `test/rules-and-contract-help.test.tsx` (Regeln pflegen, Ergebnis am Vertrag, KI-Übersicht, Fragevorschläge, Menü „Vertrag hinzufügen“). Playwright-Journey 11 (Regel anlegen, Spalten in der Vertragsliste, Regel deaktivieren); neue Seiten im axe- und Layout-Durchlauf.

**Verifikation:** Backend 1588 passed / 3 skipped / 0 failed. Frontend `npm run verify` grün (47 Testdateien); Vertragsseite 144 kB, Stammdaten-Seiten 120 kB. Playwright 179/179 (Bildvergleich-Referenzen erneuert: Vertragsliste mit „Vertrag hinzufügen“).

## 2026-10-06 – Farben, Schrift und Gestaltung nach Marktvergleich

Branch `feature/stammdaten-hub`. Grundlage: Vergleich von zehn führenden Vertragsmanagement-Anbietern (Ironclad, Icertis, Juro, SpotDraft, Agiloft, Concord, Sirion, LinkSquares, ContractSafe, Zefort; Schriften und Farben im Browser gemessen). Entscheidung des Product Owners, dokumentiert oben in `docs/VISUAL_IDENTITY.md`.

**Status:** umgesetzt (nur über Design-Tokens, keine Komponentenänderung nötig).

**Umgesetzt:**
- **Eine Markenfarbe:** Teal `#0b7368` (Hover `#095c54`) für Hauptaktion, Links und aktive Navigation statt Blau. Blau nur noch für Information und den Fokusring; Violett bleibt KI. Helles Teal `#14b8a6` nur als Fläche/Logo (als Text nur 2,5:1).
- **Warme Flächen:** Hintergrund „Papier“ `#f6f6f2` und warme helle Graustufen; Textstufen unverändert.
- **Heller Seitenbanner** (Mein Tag, Organisationen, Entwickler) statt dunkelblau, mit dunkler Variante im dunklen Design.
- **Schrift:** Inter bleibt für alles; Seitentitel in *Source Serif 4* (selbst gehostet, SIL OFL, `--font-display`; zurück auf Inter mit einer Zeile). In Tabellen, Eingaben und Codes sind 1, l und I unterscheidbar (`cv05`, `cv08`).
- Dunkles Design: Teal `#4fd1c0` als Akzent.
- Kontraste rechnerisch geprüft (u. a. weiß auf Teal 5,7:1, Link auf Papier 5,3:1, aktiver Menüpunkt 7,1:1, dunkel 9–10:1).
- Browser-Tests: axe misst erst nach Ende der Ein-/Ausblendungen (vorher Mischfarben mitten in der Animation); `scripts/run_e2e.ps1 -UpdateSnapshots` schreibt alle Referenzbilder neu (`--update-snapshots=all`), damit kleine Farbänderungen nicht in alten Referenzen hängen bleiben.

**Verifikation:** Frontend `npm run verify` grün (47 Testdateien); Playwright 179/179 mit neuen Referenzbildern (hell, dunkel, Windows-Kontrastmodus, 1440/900/390 px).

**Offen:** Kurzer Test mit 3–5 Anwendern aus dem Vertragsmanagement (Wirkung von Farbe und Titelschrift).

### Nachtrag 2026-10-06 – Gestaltungsideen aus Squarespace-Vorlagen

Aus den beliebtesten Squarespace-Vorlagen (Kategorie „Professional Services“) und deren eigener Oberfläche übernommen, was zu einer Arbeitsanwendung passt (keine großen Bilder, keine lauten Farben):
- **Flache Karten:** Karten, Abschnitte, Kennzahlen und Leerzustände ohne Schatten, nur mit feiner Linie; Schatten bleiben für Schwebendes (Menüs, Seitenleisten, Dialoge).
- **Leichte Bereichsnavigation** (Stammdaten, Verwaltung): ohne Kasten, aktive Seite mit Markierung links – wie eine Filterliste.
- **Aktive Filter als Chips** in allen Stammdaten-Listen („Suche: „…“ ×“, „Krankenhaus: … ×“, „Mit deaktivierten ×“, „Alle zurücksetzen“); Filter-Chips neutral grau statt Informationsblau.
- **Einheitlicher Seitenkopf** auch auf „Rollen & Rechte“ und „Benutzerverwaltung“ (vorher eigene Kopfzeilen ohne Titelschrift).

**Verifikation:** Frontend `npm run verify` grün; Playwright 179/179 mit neuen Referenzbildern.

### Nachtrag 2026-10-06 – Farbwelt der Anmeldeseite auf allen Seiten

Entscheidung des Product Owners (Bildschirmfoto der Anmeldeseite als Vorgabe): Die Farben der Anmeldeseite gelten für alle Seiten. Hauptaktion, Links und aktive Navigation wieder in Navy `#0f4c81` (statt Teal); Hintergrund wieder kühles Hellblaugrau (`#f4f7f9`/`#eaf0f4`/`#f8fafc`) mit den weichen Lichtflecken der Anmeldeseite (Teal oben links, Navy unten rechts) auf jeder Seite (`body`, Tokens `--glow-teal`/`--glow-navy`, dunkle Variante abgeschwächt, im Windows-Kontrastmodus aus). Teal bleibt Markenbegleiter. Beibehalten: Serifen-Seitentitel, flache Karten, heller Seitenbanner, Filter-Chips, leichte Bereichsnavigation. Nur Design-Tokens, `shell.css` (Rahmen durchsichtig) und eine Regel in `components.css` geändert.

### Nachtrag 2026-10-06 – Gestaltungsdurchgang (Analysen, Mein Tag, Vertragsliste)

Durchsicht der aktuellen Seiten anhand der Referenzbilder; behoben:
- **Analysen:** Der alte KI-Block (Kennzahlen doppelt zur Portfolio-Übersicht, „unknown: 3“, leere „To-dos“-Karte, „0/0 Pflichten verletzt“) ist ersetzt durch eine Karte „Aus der KI-Analyse“: Risiko je Vertrag auf Deutsch (Hoch/Mittel/Niedrig/Nicht bewertet) mit Link in die gefilterte Vertragsliste, offene Aufgaben und Archiv mit Links, Pflichten der Vertragspartner nur, wenn die Analyse welche gefunden hat (`components/analytics/AiPortfolioNotes.tsx`). „Fragen an das Portfolio“ ohne Fachjargon („ohne Frontend-Neuberechnung“ entfernt), Eingabe und Knopf in einer Zeile, Ergebnis mit Links. Einheitlicher Seitenkopf. Diagrammkarten nicht mehr auf Zeilenhöhe gestreckt.
- **Mein Tag:** Kennzahlkarten oben ausgerichtet (Wert sprang ohne Untertitel nach unten); Link „Zu den Kündigungsentscheidungen“ statt des alten Seitennamens.
- **Vertragsliste:** Seitentitel „Vertragsliste“ wie im Menü (vorher „Vertragsregister“); Auswahl „Gesellschaft → Abteilung“ ist auf dem Telefon eingeklappt, damit die Verträge sofort sichtbar sind.
- Browser-Tests: Warten auf Animationen höchstens 2 s und nur für laufende Animationen.

**Tests:** `test/analytics-notes.test.tsx` (neu). **Verifikation:** `npm run verify` grün (48 Testdateien); Playwright 179/179.

### Nachtrag 2026-10-06 – Design-System angewendet (claude.ai-Artefakt „MedFlux“)

Abgleich mit dem Design-System-Artefakt: alle 91 Farb-Tokens, Abstände, Radien, Größen und Schriftstile stimmen mit `tokens.css` überein (nur rgb/rgba-Schreibweise unterschiedlich). Angewendet wurden die Regeln, in denen der Code abwich:

- **Rahmen der Eingabefelder** erreichen jetzt 3:1 (vorher 1,6:1 hell / 1,9:1 dunkel, die im Design-System dokumentierte Ausnahme): neues Token `--color-border-control` (hell `#7d8d9c`, dunkel `#62748a`), genutzt vom globalen Feldstil, dem Suchfeld oben und 22 älteren Feldregeln in `app/*.css`; Hover dunkler (`--color-text-muted`).
- **Satzschreibung:** Tabellenköpfe (`.data-table`, `.rg-table`), Kennzahl-Beschriftungen, Abschnittsköpfe der Übersteuerungen, Protokoll-Aktionen, Legende der Darstellungseinstellungen, Statuskacheln im Entwickler-Dashboard und Benachrichtigungstyp nicht mehr in Großbuchstaben. Eyebrow-/Kicker-Stile bleiben.
- **Produktname** `MedFlux` in allen Oberflächentexten und im Fenstertitel (`PageHeader`).
- **Kennzahlen:** `KpiTile` zeigt ohne Wert „—“ mit „Noch keine Daten“ und während des Ladens „…“ (`loading`). Mein Tag blieb bei fehlgeschlagenem Laden dauerhaft auf „…“ bzw. zeigte 0 Fristen – jetzt ehrlicher Leerzustand bzw. Fehlerhinweis; jährliche Kosten ohne gepflegte Finanzdaten zeigen „—“ statt „0,00 €“.

**Dateien:** `app/styles/tokens.css`, `components.css`, `shell.css`, `app/globals.css` und weitere `app/*.css`, `components/ui/KpiTile.tsx`, `components/ui/PageHeader.tsx`, `components/dashboard/MyDay.tsx`, Seiten mit Produktnamen, `docs/FRONTEND_CONVENTIONS.md`. **Tests:** `test/kpi-tile.test.tsx` (neu), `test/shell-roles.test.tsx` angepasst. **Verifikation:** `npm run verify` grün (49 Testdateien); Playwright 179/179 inkl. axe hell/dunkel/forced-colors, visuelle Referenzen aktualisiert.

**Offen:** Das Design-System-Artefakt nennt noch die Kontrast-Ausnahme und Karten mit `shadow-sm` (Code: flache Karten) – bei Bedarf dort nachziehen.

### Nachtrag 2026-10-06 – Richtung „Sachlich-institutionell“ übernommen (Paket MedFlux-Sachlich)

Ruhiger, flacher Auftritt für das Arbeitsumfeld eines öffentlichen Krankenhauses, vollständig aus dem Design-System-Paket übernommen (Komponenten unverändert, nur Werte und Stile):

- **Tokens** (`app/styles/tokens.css`, hell und beide dunklen Blöcke): `--color-border-strong` `#7d8c9b` / `#64768a` (3,4:1 / 3,6:1, ersetzt das kurzzeitige `--color-border-control`, alle Feldregeln zeigen wieder auf `--color-border-strong`); `--glow-teal`/`--glow-navy` transparent; `--color-highlight-from/to` weiß bzw. `#151e28`; `--color-highlight-eyebrow` Navy `--blue-700` bzw. `#8cc0f2`; `--shadow-sm: none`.
- **Seiten:** `body` flach `--color-bg` ohne Lichtflecken; hervorgehobener Seitenkopf weiße Fläche mit Haarlinie, `--radius-md`, ohne Schatten, Titel 24 px (Sonderregeln für Knöpfe im Kopf entfernt, normale Knöpfe gelten).
- **Anmeldeseite:** flacher Hintergrund, Lichtkreise entfernt, Karte mit `--color-border` und `--shadow-md`, Feldfokus Navy statt Teal, Link-Unterstreichung in Textfarbe (`brand-identity.css`, `auth.css`).
- **Keine Verläufe, Teal nur im Logo:** Admin-Kopf flach, Aktivitätspunkt Navy, Entwickler-Statuspunkt `--color-success-fill`, Entwickler-Formularknopf Navy, Lebenszyklus-Hauptknopf ohne Verlauf (Standard-`btn-primary`). Verbleibende Verläufe sind funktional: Pfeil der Auswahlliste und Skeleton-Schimmer.
- Doku: Entscheidung oben in `docs/VISUAL_IDENTITY.md`, Farbzeile und Rahmenregel in `docs/FRONTEND_CONVENTIONS.md`, `CLAUDE.md`.

**Verifikation:** `npm run verify` grün (49 Testdateien); Playwright 179/179 inkl. axe hell/dunkel/forced-colors, visuelle Referenzen aktualisiert. Kein Commit (Arbeitsstand auf `feature/stammdaten-hub` noch uncommittet).
- **Titelbild (Cover) aus dem Paket:** neue Komponente `components/brand/BrandCover.tsx` (flache Navy-Flächen, Blatt mit Haarlinien, eine Teal-Marke, Serifen-Schriftzug „MedFlux“, Token `--text-cover`). Auf der Anmeldeseite ab 900 px Breite und 700 px Höhe: Logo oben links, Design-Schalter oben rechts, darunter Titelbild und Anmeldekarte; auf dem Telefon nur Logo und Karte. Verify grün, Playwright 179/179.

### Nachtrag 2026-10-10 – Restructure + „Ruhe & Signal“ (Plan v2.0, Phasen 0 und A–I)

Plan `docs/architecture/MEDFLUX_RESTRUCTURE_PLAN_20261010.md`; Fortschritt je Phase `docs/medflux-restructure-progress.md`;
Abschlussbericht `docs/medflux-restructure-report.md`. Branch `design/ruhe-signal`, ein Commit je Phase.

- **A Datenwahrheit:** Summen mit Abdeckung (unbekannt nie 0, Währungen getrennt), eine Laufend-Definition, `term_status`, `not_evaluable`, Stichtag `Europe/Berlin`.
- **B Signale:** `Signal` mit sechs Stufen (Farbe + Form + Wort), neue Tokens, neutrale Kennzahlen, `EmptyState calm`.
- **C Glocke:** Abzeichen = ungelesene eigene Benachrichtigungen; Arbeitsvorrat getrennt; `/postfach` = Protokoll; Wiedervorlage → Termine „Nur meine“.
- **D Verträge:** Reiter Bestand / Zu prüfen / Archiv mit Zahlen, Listenzustand in der Adresse, Weiterleitungen mit Parametern, neue Seitenleiste.
- **E Vertragsakte:** neue Reiternamen, Prüfreihenfolge, `/nachweise` → Vertrag, Schutz vor doppelten Prüfaktionen (409 bei veraltetem Stand), Import nur mit Krankenhaus.
- **F Fristen:** Überfälliges zuerst, Herkunft je Termin, ehrliche Leerzustände.
- **G Mein Tag v3:** Lagebild, drei ruhige Kennzahlen, Arbeit nach Dringlichkeit; Analysen mit Datenqualität statt Doppelliste.
- **H Stammdaten/Verwaltung:** „Lieferanten zuordnen“, Krankenhaus/Abteilung einheitlich, Mitgliederzahl erklärt, Protokoll mit deutschen Feldnamen, Geräte verlinkt.
- **I Abschluss:** tote Stile und Alias-Tokens entfernt, `SourceLink` entfernt, Doku (CLAUDE.md, Integrationskarte, Konventionen, Visual Identity).

**Verifikation:** Backend pytest (Docker-Postgres) grün bis auf 8 umgebungsbedingte Fälle wie in der Baseline; `npm run verify` grün; Playwright siehe Fortschrittsdatei. Keine Migration.
**Nächster Schritt:** Review des Branches, kurzer Test mit 3–5 Anwendern (Lagebild, Signale), dann Merge nach `main`.

### Nachtrag 2026-10-10 – Zahlungs- und Wartungserinnerungen, Prüfmodus (Restpaket WP2–WP4)

Branch `feature/finance-reminders-review-mode` (auf `design/ruhe-signal`). Abgleich des Arbeitsplans mit dem Code: WP2–WP4 waren bis auf diese Punkte durch H3–H7 erledigt (Status oben im Arbeitsplan).

- **Zahlungszeitpunkt** je Finanzeintrag (`payment_timing`: im Voraus / nachträglich / nicht gepflegt); KI-Vorschlag nur bei eindeutigem Wortlaut der Zahlungsbedingungen.
- **Zahlungserinnerung** (`payment_reminder`): Systemtermin „Zahlung fällig“ 14 Tage vorher, nur mit gepflegtem Zeitpunkt; Finanzänderungen gleichen die Termine sofort ab.
- **Wartungserinnerung:** Registerfelder „Nächste Wartung“ und „Wartung alle (Monate)“, Systemtermin „Wartung fällig“ einen Monat vorher, Folgetermin nach Erledigung.
- **Prüfmodus der Organisation** (Verwaltung → Allgemein): manuell oder nicht-kritische Angaben mit eindeutigem Beleg automatisch übernehmen (abgeleiteter Zustand „Automatisch übernommen“, kein Prüf-Eintrag, kritische Angaben immer manuell, Änderung protokolliert, Recht `review.settings`).
- **Analysen:** Hinweis „Verträge ohne gepflegte Kosten“ zählt jetzt auch Verträge in Arbeit (vorher 0, solange kein Vertrag lief).
- **Aufräumen:** ungenutzte `SettingsNavigation` und Alias-Tokens `--accent`/`--muted` entfernt.

**Migration:** `o6d8e0f12007` (additiv; upgrade/downgrade/upgrade auf Wegwerf-DB geprüft, ORM gegen migriertes Schema abgeglichen).
**Tests:** neu `backend/tests/test_reminders_review_mode.py`, Vitest `review-mode`, Erweiterungen in `contract-finance` und `fact-confirm-display`. Ergebnisse der Gesamtläufe im Commit.
**Nächster Schritt:** Import-Assistent; danach WP5-Drilldown und Leistungstest.

### Nachtrag 2026-10-10 – Entwicklung gebündelt, Import-Assistent, Analysen-Drilldown

Branch `feature/developer-hub-import-wizard` (auf `feature/finance-reminders-review-mode`).

- **Entwicklung:** eine Seite `/developer` mit Reitern (Übersicht inkl. Organisationen, Dokumentverarbeitung, UI-Bausteine); Eintrag im Kontomenü statt in der Seitenleiste; alte Adressen leiten weiter.
- **Import-Assistent:** Schritt „Erfassung“ (KI mit manueller Prüfung / KI mit automatischer Übernahme nur nach Freigabe / manuelle Eingabe mit gespeichertem Original), serverseitige Prüfung, Bestätigung bei mehreren Dateien, `contract.intake_mode`; automatische Übernahme gilt nie für Verträge mit ausdrücklich manueller Prüfung.
- **Fehlgeschlagene Importe** auf der Importseite (verständliche Meldung, erneute Analyse, Vertrag); technische Rohtexte der Verarbeitungsläufe nur noch für Administration/Entwicklung.
- **Analysen:** „Kosten nach Bereich“ – Krankenhaus → Abteilung → Verträge mit Abdeckung, Link in die Vertragsliste; Leistungstest mit 1.000 Verträgen.

**Migration:** `p7e9f1a23008` (additiv). **Tests:** `test_import_wizard.py`, `test_analytics_drilldown.py`, Vitest `import`, `portfolio-drilldown`. Gesamtläufe im Commit.
**Offen:** Betrag einer Vorauszahlung, Extraktions-Benchmark (WP2.4).

### Nachtrag 2026-10-11 – Vertragsliste: eine Werkzeugleiste, Schnellfilter, gelöschte Verträge nur mit Recht

Branch `feature/register-list-toolbar` (auf `feature/developer-hub-import-wizard`). Plan (gegen den Code geprüft, mit Entscheidungen des Owners): `docs/architecture/VERTRAEGE_LISTE_PLAN_20261011.md`.

- **Gelöschte Verträge** (`business_status = geloescht`) nur noch für Administration und Vertragsmanagement: neues Recht `contract.view_deleted`; Raster, Werte, Baum und Export blenden sie für andere Rollen serverseitig aus – gleich ob über die Option, einen Statusfilter, eine alte Ansicht oder einen Link. Die Standardansicht „Gelöschte Verträge“ und der Statuswert „Gelöscht“ werden ihnen nicht angeboten. Vorher sahen alle Lesenden sie.
- **Werkzeugleiste:** Suche, Ansicht (mit „Ansicht verwalten“), „Weitere Filter (n)“ als Seitenleiste, „Darstellung“ (Spalten, Gruppierung, „Standardspalten“), Excel-Export. Der Baum Krankenhaus → Abteilung neben der Liste ist ersetzt durch den Schnellfilter „Abteilung“ (gleiche Zahlen, inkl. „ohne“); dazu Schnellfilter Status und Vertragspartner.
- **Ein Filterzustand:** Schnellfilter, Seitenleiste und Chips schreiben dieselben `GridSpec.filters`; die Zahl an „Weitere Filter“ zählt nichts doppelt. „Alle zurücksetzen“ behält Ansicht, Reiter, Bereich und Darstellung. Jede Änderung springt auf Seite 1. Spalten und „Gelöschte einbeziehen“ stehen jetzt auch in der Adresse. Krankenhaus-/Abteilungsfilter, die es im gewählten Bereich nicht gibt (z. B. nach einem Bereichswechsel), werden mit Hinweis entfernt.
- **Weitere Filter:** Ich verantwortlich, kündbar in 30 Tagen, Kosten unbekannt, fehlende Angaben (Krankenhaus, Abteilung, Partner, verantwortliche Person), Vertragstyp, Kostenbereich, jede andere Bedingung über den bisherigen Filter-Editor. Unbefristete Verträge gelten nicht als unvollständig.
- **Seitenkopf:** Titel und „Vertrag hinzufügen“ in einer Zeile (nur Vertragsliste, `className="reg-header"`); Schnellfilter links und Aktionen rechts in einer Zeile.
- **Tabelle:** Nr. und Kurzbeschreibung als eine Spalte „Vertrag“ (beide sortierbar, Suche unverändert), ohne Beschreibung „Vertrag <Nr.>“; Ergebniszeile mit Anzahl und Summen (`CoverageValue`) über der Tabelle; Standardspalten: Vertrag, Vertragspartner, Vertragstyp, Status, Kündbar bis, Jährliche Kosten („Mögliches Ende“ unter Darstellung). Gespeicherte Ansichten behalten ihre Spalten.
- Neuer Baustein `components/ui/Popover.tsx`.
- Nebenbei: Kontrollkästchen in Stammdaten-Formularen überlappten das Nachbarfeld (`master-data.css`).

**Keine Migration.** **Tests:** neu `backend/tests/test_register_deleted_visibility.py`, `frontend/test/register-filters.test.tsx`; angepasst `test_register_grid.py`, `register-grid.test.tsx`, Playwright-Journeys/-Helfer; neuer Layout-Test „erste Zeile ohne Scrollen“ bei 1366×768 und 1920×1080.
**Verifikation:** Backend pytest komplett (Docker-Postgres) 1628 bestanden, 3 übersprungen, 0 Fehler; `npm run verify` grün (55 Testdateien); Playwright 176/176 (Wegwerf-DB, inkl. axe hell/dunkel/forced-colors, Layout 1440/900/390 und neu 1366×768/1920×1080); Bildreferenzen `vertragsliste` und `rollen` (neue Zeile „Gelöschte Verträge ansehen“) bewusst aktualisiert. Journey 9 (Benutzerimport) schlug in einem Lauf an „target-size“ fehl, weil die feste Kopfzeile den Knopf „Vorlage herunterladen“ verdeckt; am Ausgangsstand `74ea4c5` identisch reproduziert, also nicht durch diese Änderung, und im nächsten Lauf grün (wackelig).
**Offen:** Partnerfilter arbeitet weiter mit dem Namen statt der Kennung; Abteilungsnamen sind krankenhausübergreifend nicht eindeutig (die Auswahl setzt deshalb immer das Krankenhaus mit). Gelöschte Verträge sind außerhalb der Liste (z. B. direkter Link auf die Vertragsakte) nicht zusätzlich gesperrt.
- **Nachtrag (gleicher Tag): Status zuerst und farbig.** Status ist die erste Standardspalte und erscheint als `StatusBadge` (Farbe + Form + Wort): In Arbeit = Info (blau), Gültig = bestätigt (grün), Gekündigt = Warnung (gelb), Beendet = neutral (grau), Gelöscht = kritisch (rot); Zuordnung `BUSINESS_STATUS_TONE` in `lib/domain-api/register.ts`. Kostenhinweis in der Ergebniszeile steht jetzt neben dem Betrag. Verifikation: pytest 1628/3 übersprungen, `npm run verify` grün, Playwright 176/176, Bildreferenz `vertragsliste` aktualisiert.

### Nachtrag 2026-10-11 – „Direkt zur Stelle“, Phase 1 (Vertragsdaten)

Plan: `docs/architecture/DIREKT_ZUR_STELLE_PLAN_20261011.md` (Entscheidungen: ganze Bearbeitung öffnen und Cursor ins Feld; Karte „Was fehlt noch?“; alle vier Phasen).

- **Mechanismus:** `lib/fix-targets.ts` (`contractHref`, `registerHref`, `baseFieldKey`), `components/ui/MissingList.tsx` (jede fehlende Angabe ist ein Knopf oder Link, Screenreader „… erfassen“). Vertragsakte versteht `?feld=<key>` und `?abschnitt=<id>`.
- **Vertragsdaten:** „Für „Gültig“ fehlen noch …“ und „Fristen noch nicht berechenbar. Es fehlen …“ sind Sprungziele: Bearbeitung öffnet sich, der Cursor steht im Feld, das Feld ist hervorgehoben, die Adresse trägt `feld=` (Abbrechen/Speichern räumt sie auf). Ohne Vertragsart führt ein Laufzeitfeld zur Vertragsart mit Hinweis; ohne Bearbeitungsrecht wird nur hingesprungen („Nur Lesen …“); eine offene Bearbeitung bleibt erhalten. Leere Felder haben „Erfassen“ direkt am Feld; „Aufbewahrung: Nicht festgelegt“ hat „Festlegen“; „KI hat N Angaben übernommen“ führt je Angabe zum Feld.
- **Tests:** neu `frontend/test/direct-jump.test.tsx` (9), Playwright-Journey 12; `contract-register.test.tsx` angepasst. Verifikation: `npm run verify` grün (56 Testdateien), Playwright 176 + Journey 12 grün. Keine Backend-Änderung.
- **Nächster Schritt:** Phase 2 (übrige Vertragsakte, Ziele aus dem Backend, Karte „Was fehlt noch?“).

### Nachtrag 2026-10-11 – „Direkt zur Stelle“, Phase 2 (übrige Vertragsakte)

- **Backend nennt Ziele:** Vertragsregeln (`target`, `rule_kind`, je Regelart deterministisch: Kündigungsfrist, Laufzeit/Mindestlaufzeit, Verlängerung, Preisanpassung, Pflichtfeld, Kosten → Finanzen), Hinweise der Entscheidungsvorlage (Prüfung, Kosten, Erinnerungsempfänger, Dokument), Finanzhinweise (`note_items`: „Kein Vertragsende bekannt“ → Laufzeit, „Anpassungsdatum angenommen“ → Feld). Texte unverändert, keine Migration.
- **Vertragsakte:** neue Karte **„Was fehlt noch?“** oben in „Übersicht“ (Pflichtfelder für „Gültig“, Laufzeit, Kosten, verantwortliche Person, KI-Prüfung, Dokument, Regeln ohne Angabe – jeder Eintrag ein Link; ohne Lücken unsichtbar). „Handlungsbedarf“ führt je Aufgabe/Warnung an den richtigen Ort (vorher taten Nicht-Prüf-Aufgaben nichts). Leere Kopf-Fakten (Vertragsende, Kündbar bis, Jährliche Kosten) haben „Laufzeit erfassen“ / „Kosten erfassen“. Aufgaben unter „Fristen & Aufgaben“, Finanz- und Regelhinweise, „nicht gepflegt“ / „Frist unbekannt“ in der Entscheidungsvorlage, „Basiert auf ungeprüften KI-Werten“, „Prüfung erforderlich“ und die Schnellansicht der Liste führen direkt zur Stelle. `?abschnitt=entries` öffnet das Formular „Finanzeintrag anlegen“.
- **Technik:** Reiter folgt der Adresse (Links auf derselben Seite wechseln den Reiter); manueller Reiterwechsel entfernt `feld`/`abschnitt`; `lib/fix-targets.ts` mit `workItemTarget`, `warningTarget`, `asFixTarget`, `fixLabel`, `sectionAnchor`.
- **Tests:** neu `backend/tests/test_direct_targets.py`, Erweiterung `test_renewal_brief.py`; `frontend/test/direct-jump-contract.test.tsx`; Playwright-Journey 13. Verifikation: pytest 1630 bestanden / 3 übersprungen; `npm run verify` grün (57 Testdateien); Playwright 178/178.
- **Nächster Schritt:** Phase 3 (Mein Tag, Vertragsliste, Fristen & Aufgaben, Benachrichtigungen, Analysen, Import, Verwaltung, Geräte).

### Nachtrag 2026-10-11 – „Direkt zur Stelle“, Phase 3 (Listen und Übersichten)

- **Mein Tag:** Lagebild-Themen sind Links (Liste, Termine, Prüfliste, Entscheidungen); Kachel „Jährliche Kosten“ führt bei fehlenden Kosten zu „Verträge ohne Kosten“; „nicht bewertbar“ führt zu den Laufzeitangaben (ein Vertrag: direkt in die Akte).
- **Vertragsliste:** Verträge aus einer nach Lücken gefilterten Liste öffnen dort, wo die Lücke behoben wird (ohne Kosten → Finanzen, ohne Verantwortliche → Zuständigkeit, Laufzeit unvollständig → Laufzeit, ohne Erinnerungsempfänger → Feld, Prüfung → Prüfung …); Zellen „Unvollständig“ (Laufzeit, Regeln) sind Links; Ergebniszeile „Verträge ohne Kosten anzeigen“.
- **Fristen & Aufgaben:** Aufgaben haben „Kosten erfassen“ / „Im Vertrag erledigen“ je Typ; „Ungeprüfte KI-Werte“ → Prüfung; „nicht berechenbar“ → Akte bzw. Liste; fehlende Jahreskosten → „Kosten erfassen“.
- **Benachrichtigungen (Backend):** Links je Aufgabentyp (`app/work_queue/targets.py`, gleiche Zuordnung wie `workItemTarget`), Freigaben → `?abschnitt=intelligence`. Einsicht „Kündigungsfrist in 90 Tagen ohne Erinnerungsempfänger“ hat jetzt `filters` (Frist bald **und** kein Empfänger), statt alle bald fälligen Verträge zu zeigen.
- **Analysen, Import, Verwaltung, Geräte:** „Teilsumme …“, „Keine gepflegten Finanzposten“, Drilldown (fehlende Kosten, Kosten/Laufzeit je Vertrag), „N Verträge erfordern manuelle Prüfung“ → Prüfliste, fehlgeschlagener Import → Dokument im Vertrag, Verwaltungs-Kennzahlen, Geräte „Zu prüfen“ → Verknüpfungen.
- **Offen:** Stammdaten „{n} ohne Vertrag“ (Partnerliste hat keinen Adressfilter); Balken in Analysen führen weiter zur Dimension, nicht zu „ohne Kosten“.
- **Tests:** `test_direct_targets.py` (Benachrichtigungslinks), `frontend/test/direct-jump-lists.test.tsx`, `import.test.tsx` angepasst. Verifikation: pytest 1631 / 3 übersprungen; `npm run verify` grün (58 Testdateien); Playwright 177 + Analysen-Referenz bewusst aktualisiert (neuer Link).

### Nachtrag 2026-10-11 – „Direkt zur Stelle“, Phase 4 (immer erreichbar)

- **Strg+K:** Auf jeder Vertragsakte (alle Reiter) stehen die Lücken aus „Was fehlt noch?“ als Befehle ganz oben („Dieser Vertrag“: „Vertragsbeginn erfassen“, „Kosten erfassen“, „KI-Werte prüfen“ …); Enter springt zur Stelle. Mechanik: `lib/page-commands.ts`; Berechnung `useContractGaps` (lädt nach Änderungen an der Akte neu).
- **Regel:** `docs/FRONTEND_CONVENTIONS.md` §5b „Direkt zur Stelle“; CLAUDE.md ergänzt.
- **Tests:** neu `frontend/test/command-palette-page.test.tsx`; `direct-jump-contract.test.tsx` auf den Hook umgestellt; Playwright-Journey 14 (legt einen unvollständigen Vertrag an, springt per Strg+K, archiviert ihn wieder). Verifikation: pytest 1631 / 3 übersprungen; `npm run verify` grün (59 Testdateien); Playwright 179/179.

### Nachtrag 2026-10-11 – Erneut aus dem Dokument erfassen, Phase 1 (sichere Grundlage)

Plan: `docs/architecture/ERNEUT_ERFASSEN_PLAN_20261011.md` (Entscheidungen: immer Vergleich vor Übernahme; nur Administration und Vertragsmanagement; Modellwahl für dieselben Rollen; Phase 4 „Stelle im PDF markieren“ gehört dazu).

- **Kern:** Ein Lauf erzeugt nur eine *Kandidaten*-Extraktion (gleicher Weg wie der Import: Claim, kanonisches Dokument, Harness, Nachweise, Validierung). Die Vertragswahrheit ändert sich erst, wenn eine Person im Vergleich Angaben auswählt; dann wird die akzeptierte Extraktion um genau diese Fakten (mit Fundstellen) ergänzt und über den normalen Akzeptanzweg (`_persist_pipeline`) übernommen – Fristen, Kosten, Warnungen, Aufgaben rechnen neu, von Hand gepflegte Werte bleiben (nur Vorschlag). Nicht erneut gefundene Angaben werden nie gelöscht. Übernahme nur auf dem Stand, auf dem der Lauf gestartet wurde (sonst 409).
- **Backend:** Tabelle `contract_reextraction` (Migration `q8f0a2b34009`, auch Benachrichtigungsart `reextraction`); `app/reextract/facts.py` (Vergleich neu/abweichend/unverändert/nicht erneut gefunden, Zusammenführen, deutsche Anzeige), `app/reextract/service.py` (Warteschlange mit Advisory-Lock – eine Auswertung gleichzeitig –, Abbrechen, Verwerfen, Glocke an die startende Person), `DocumentProcessingService.extract_candidate`/`apply_candidate`, `AIService(model_override=…)` für ein anderes installiertes Modell nur in diesem Lauf. API `GET/POST /api/contracts/{id}/reextraction`, `…/models`, `…/{run}/apply|discard|cancel`; Recht `contract.reanalyze` (Administration, Vertragsmanagement); Scope und Recht vor jeder Modellabfrage. Die alte, ungenutzte Route `POST /api/documents/{version}/reanalyze` (übernahm sofort und löschte nicht wiedergefundene KI-Werte) ist entfernt.
- **Vertragsakte:** Dokumente → Dokument: Abschnitt „Erneut aus dem Dokument erfassen“ mit Dialog (Nur fehlende Angaben / Ganzes Dokument, Erweitert: Dokument neu lesen, Modell), Wartestand mit Abbrechen, Vergleichstabelle (Neues mit Fundstelle vorausgewählt, Abweichungen nie, Fundstelle „S. n“ öffnet die Seite im PDF), ehrliche Meldung ohne neue Angaben mit nächsten Schritten. Hinweis im Kopf der Akte, solange ein Lauf läuft oder ein Ergebnis wartet; Glocke führt direkt zum Ergebnis (`href` in `/api/inbox`).
- **Noch nicht (Phase 2):** Die Harness sucht im Modus „Nur fehlende Angaben“ noch das ganze Dokument ab (der Vergleich ist bereits auf die gewählten Angaben begrenzt); Seitenhinweis wird gespeichert, aber noch nicht genutzt. Verträge ohne bisherige KI-Analyse (z. B. manuell erfasst) können noch nicht erneut erfasst werden.
- **Tests:** neu `backend/tests/test_reextraction.py` (9: Vergleich, Zusammenführen ohne Löschen, Menschwerte bleiben, ein Lauf je Vertrag, veralteter Stand, Fehler, Rechte/Scope vor Modellabfrage), `frontend/test/reextraction.test.tsx` (8, inkl. axe). Migration auf Wegwerf-DB: upgrade → downgrade → upgrade.
- **Verifikation:** pytest 1641 bestanden / 3 übersprungen; `npm run verify` grün (60 Testdateien).
- **Nächster Schritt:** Phase 2 (gezielte Suche nach fehlenden Feldern in der Harness, Seitenhinweis, „Im Dokument suchen“ am leeren Feld).

### Nachtrag 2026-10-11 – Erneut aus dem Dokument erfassen, Phase 2 (gezielte Suche)

- **Harness:** `HarnessV3.analyze(..., focus_fields=, focus_pages=)` – nur Packs mit den gesuchten Feldern, Katalog auf sie begrenzt, statt der Seitenauswahl je Pack (höchstens 5 Seiten) die genannten Seiten bzw. das ganze Dokument (Chunks teilen bei Bedarf), Zusatzhinweis mit deutschen Formulierungen; genannte Seiten werden zuerst auch als Bild gelesen (Vision, sofern das Modell es kann). Gleiche Nachweisregeln: ein Wert ohne wörtliches Zitat wird auch bei gezielter Suche verworfen. Gezielte Suche ohne Fund ist ein gültiges Ergebnis („nicht im Dokument“), kein Fehler.
- **Ablauf:** Modus „Nur fehlende Angaben“ und Seitenhinweis gehen vom Lauf bis in die Harness (`extract_candidate(focus_fields, focus_pages)`).
- **Oberfläche:** Dialog mit „Wo steht es? (optional)“ (z. B. „4“, „4–6“, „4, 7“; höchstens 20 Seiten). In „Vertragsdaten“ steht an leeren Feldern, die im Dokument stehen können, neben „Erfassen“ **„Im Dokument suchen“**: öffnet Dokumente → Dokument mit dem Dialog und genau diesem Feld (`?suchen=<feld>`, `documentSearchHref`); Zuordnung Feld → Angaben liefert das Backend (`field_search`).
- **Nicht gemacht:** Vergleich auf dem lokalen Extraktions-Benchmark (KI-Läufe nur auf Anfrage).
- **Tests:** neu `backend/tests/test_harness_focus.py` (4); `test_reextraction.py` (+1, Fokus bis zur Harness); `frontend/test/reextraction.test.tsx` (10), `direct-jump.test.tsx` (+2).
- **Verifikation (Phasen 1+2):** pytest 1646 bestanden / 3 übersprungen; `npm run verify` grün (60 Testdateien); Migration auf Wegwerf-DB auf/ab/auf. Playwright (nach Phase 1): 177/179 – beide Abweichungen sind die Bildreferenz „Rollen & Rechte“ (neue Zeile „Erneut aus dem Dokument erfassen“), wird mit Phase 3 bewusst erneuert.

### Nachtrag 2026-10-11 – Erneut aus dem Dokument erfassen, Phase 3 (Einbindung)

- **„Was fehlt noch?“** hat den Knopf **„Fehlende Angaben im Dokument suchen“** (nur mit Recht, ohne laufende Auswertung, wenn etwas fehlt); er öffnet den Dialog mit allen fehlenden Angaben (`?suchen=fehlende`, `MISSING_SEARCH`).
- **Strg+K** auf der Vertragsakte: zusätzlich „Fehlende Angaben im Dokument suchen“ unter „Dieser Vertrag“.
- Glocke (Link direkt zum Ergebnis) und Verlauf („Erneute Erfassung gestartet/übernommen/verworfen“) kamen schon mit Phase 1.
- **Regel:** `docs/FRONTEND_CONVENTIONS.md` §5b um „Im Dokument suchen“ ergänzt.
- **Tests:** `frontend/test/reextraction.test.tsx` (+2: Karte, Link „fehlende“, kein zweiter Dialog während einer Auswertung); Playwright-Journey 15 (Dialog → Seitenhinweis → Vergleich → Übernehmen, axe; die Schnittstelle der erneuten Erfassung wird im Browser beantwortet, weil in der Testumgebung keine lokale KI läuft – das Backend ist durch pytest abgedeckt). Bildreferenz „Rollen & Rechte“ bewusst erneuert (neue Zeile „Erneut aus dem Dokument erfassen“).
- **Verifikation:** `npm run verify` grün (60 Testdateien); Playwright 180/180 (inkl. Journey 15 und axe hell/dunkel/forced-colors, Layout 1440/900/390).

### Nachtrag 2026-10-11 – Erneut aus dem Dokument erfassen, Phase 4 (Stelle markieren)

- **Ablauf:** Dokumente → Dokument → „Angabe aus dem Text übernehmen“: Text der angezeigten Seite, so wie MedFlux sie gelesen hat (auch Texterkennung – funktioniert also auch bei Scans, anders als eine Markierung im PDF-Bild). Stelle markieren (oder wörtlich einfügen), Feld wählen, Vorschau „Wird gespeichert als: 01.01.2025“, Übernehmen. Auch aus dem Ergebnis „Keine zusätzlichen Angaben gefunden“ erreichbar („Stelle im Dokument markieren“).
- **Ohne Modell, nichts geraten:** `app/register/from_document.py` liest den Wert per Code (Datum numerisch/als Wort/ISO, Dauer mit Ziffer, Zahlwort oder „zwölf (12) Monate“, Zahl, Prozent, Kündigungstermin, Text) und lehnt Mehrdeutiges ab („mehrere Daten …“). Gespeichert wird nur, wenn die Stelle wörtlich auf dieser Seite steht (gleiche Regel wie für KI-Nachweise). Felder: Kurzbeschreibung, Vertragsgegenstand, interne Nummer, Beginn/Ende, Laufzeit, Mindestlaufzeit, Kündigungsfrist, Kündigung zum, Verlängerung, Gekündigt am/zum, Preisanpassung (%, Index, Datum, Intervall), Wartung (Datum, Intervall).
- **Fundstelle:** `contract_field_provenance` hat `source_document_version_id`, `source_page`, `source_quote` (Migration `r9a1b3c45010`, Fremdschlüssel `NOT VALID`). Der Wert gilt als von Hand gepflegt (gleicher KI-Wert → „bestätigt“); jede andere Änderung (Formular, KI) entfernt die Fundstelle. „Vertragsdaten“ zeigt „S. n“ (Zitat als Tooltip) und öffnet das Dokument an dieser Seite. Verlauf: „Angabe aus dem Dokument übernommen“.
- **API:** `GET /api/contracts/{id}/documents/{version}/pages/{n}/text` (Lesen), `POST /api/contracts/{id}/register/from-document` (`contract.edit`; `dry_run` nur Vorschau).
- **Tests:** neu `backend/tests/test_register_from_document.py` (6), `frontend/test/source-capture.test.tsx` (3, axe); `direct-jump.test.tsx` (+1 Fundstelle), `reextraction.test.tsx` (+1); Playwright-Journey 16 (eigener Vertrag mit PDF-Anhang; Seitentext und Prüfung werden im Browser beantwortet, weil ohne KI-Analyse kein gelesener Text vorliegt). Migration auf Wegwerf-DB auf/ab/auf.
- **Verifikation:** pytest 1652 bestanden / 3 übersprungen; `npm run verify` grün (61 Testdateien); Playwright 181/181.
- **Plan abgeschlossen** (alle vier Phasen). Offen: Verträge ohne bisherige KI-Analyse (manuell erfasst) können noch keine *KI*-Neuerfassung starten – „Angabe aus dem Text übernehmen“ braucht dort ebenfalls gelesenen Text, der erst mit einer Analyse entsteht; Vergleich auf dem lokalen Extraktions-Benchmark steht aus (KI-Läufe nur auf Anfrage).

### Nachtrag 2026-10-11 – KI-Prüfung in den Kopf der Vertragsakte

- Die Karte „KI hat N Angaben aus dem Dokument übernommen“ stand nur im Reiter „Vertragsdaten“. Jetzt ein Knopf im Kopf der Akte, auf jedem Reiter sichtbar: **„✦ KI-Werte prüfen · 3“** (ersetzt die Plakette „KI-Prüfung offen“). Er öffnet eine Liste der noch nicht bestätigten KI-Werte mit „Bestätigen“ je Feld, „Alle bestätigen“ und „Im Dokument prüfen“; jeder Name führt zum Feld. Ohne Bearbeitungsrecht nur ansehen; ohne offene Werte, aber mit offener Dokumentprüfung: „KI-Prüfung offen“; sonst kein Knopf. `components/contracts/detail/AiReviewButton.tsx`; `AiFillSummary.tsx` entfernt.
- **Behoben:** Die Karte zählte Zeiträume doppelt (Anzahl + Einheit), z. B. „4 noch nicht bestätigt“ bei 3 Feldern.
- **Tests:** neu `frontend/test/ai-review.test.tsx` (5, axe); alter Kartentest entfernt. Verifikation: `npm run verify` grün (62 Testdateien), Playwright 181/181.

### Nachtrag 2026-10-11 – Erneute Erfassung und Prüfung „Angaben“

- **Neue prüfbare Angaben:** Laufzeit, Kündigungsfrist, Kündigungstermin, Verlängerungszeitraum (aus der akzeptierten Extraktion, Lesemodell `extracted_terms`; Belege werden wie bei allen Angaben über den Feldnamen verknüpft; nicht kritisch, damit laufende Prüfungen nicht neu gesperrt werden).
- **Neuer Wert → wieder prüfen:** Übernimmt eine erneute Erfassung einen Wert für eine bereits geprüfte Angabe, wird sie wieder geöffnet – mit dem **neuen** Wert als Original und wirksamem Wert und dem Hinweis „Neuer Wert aus der erneuten Erfassung – bitte erneut prüfen.“ (vorher blieb die alte Bestätigung samt altem Wert stehen). Abhängige berechnete Angaben (z. B. Kündigungsfrist → letztes Kündigungsdatum) ebenso. Eine abgeschlossene Prüfung wird „Änderung nach Prüfung“. Danach werden die Vertragsdaten neu abgeglichen (eine frühere Korrektur gilt nicht für den neuen Wert). Neu gefundene, vorher leere Angaben erscheinen ohnehin als „zu prüfen“.
- **Korrigieren/Bestätigen in der Prüfung wirkt auf die Vertragsdaten:** Für Beginn, Ende, Laufzeit, Mindestlaufzeit, Kündigungsfrist, Kündigungstermin, Verlängerung wird der korrigierte Text wie eine markierte Dokumentstelle gelesen („6 Monate“, „01.04.2025“, „zum Quartalsende“) und ins passende Feld übernommen; nicht lesbar → 422, es wird nichts gespeichert. Bestätigen bestätigt auch den KI-Wert im Feld. Nur mit Bearbeitungsrecht (Prüfer ohne `contract.edit` ändern die Vertragsdaten nicht) und nur mit angemeldetem Konto.
- **Dateien:** `app/contracts/review/material.py`, `review/service.py` (`reopen_after_reextraction`, `reopen_note`), `app/reextract/facts.py` (`REVIEW_FACTS`, `REVIEW_TO_REGISTER`), `app/register/service.py` (`review_register_changes`, `apply_review_to_register`), `app/api/routes/contracts.py`, `contract_reextraction.py`, `FactReviewPanel.tsx`. Keine Migration.
- **Tests:** neu `backend/tests/test_reextraction_review.py` (4); `frontend/test/fact-confirm-display.test.tsx` (+1). Verifikation: pytest 1656 bestanden / 3 übersprungen; `npm run verify` grün (62 Testdateien); Playwright 181/181.
- **Offen:** Werte, die über „Angabe aus dem Text übernehmen“ gesetzt werden, landen nur in den Vertragsdaten (mit Fundstelle), nicht als eigener Eintrag in der Prüfung.

### Nachtrag 2026-10-11 – Mehrere Verantwortliche, Kostenstelle ohne Aufteilung

- **Ursache „Verantwortliche Person“ leer:** Die Organisation „Stiftung Hospital Zum Heilgen Geist“ hat keine Benutzer; das einzige Konto (Entwickler) gehört zur Organisation „Krankenhaus“. Jetzt sagt das Formular das („In dieser Organisation gibt es noch keine Benutzer. Benutzer anlegen“) statt still „Nicht zugewiesen“ zu zeigen. Außerdem sind alle Benutzer der Organisation wählbar (passende zur Zuordnung zuerst, übrige unter „Weitere Benutzer der Organisation“) – vorher blendete die Oberfläche Benutzer anderer Abteilungen aus.
- **Mehrere Verantwortliche** (Entscheidung: wie die Hauptverantwortliche): „Hauptverantwortlich“ + „Weitere Verantwortliche“ (hinzufügen/entfernen). Weitere bekommen die Erinnerungen in der Glocke, sehen den Vertrag unter „Ich verantwortlich“, dürfen ihn auch vertraulich sehen und stehen in der Entscheidungsvorlage; Vertragsliste hat die Spalte „Weitere Verantwortliche“. Tabelle `contract_responsible` (Migration `s0b2c4d56011`), `PATCH /api/ownership/contracts/{id}` mit `further_responsible_account_ids` (nur Benutzer der Organisation; die Hauptverantwortliche nie doppelt).
- **Kostenstellen-Aufteilung:** Ohne Aufteilung zeigt der Kasten die Kostenstelle aus der Organisationszuordnung mit 100 % und Jahresbetrag („aus der Organisationszuordnung“); „Auf mehrere Kostenstellen aufteilen“ beginnt mit ihr. Ohne Kostenstelle: Link „In der Organisationszuordnung festlegen“. Kein „Summe 0 %“ mehr. Backend liefert `primary_cost_center` in den Finanzdaten (auch für Lesende).
- **Tests:** neu `backend/tests/test_further_responsible.py` (3); `contract-ownership-roles.test.tsx` (+2), `contract-finance.test.tsx` (+2). Migration auf Wegwerf-DB auf/ab/auf. Verifikation: pytest 1659 bestanden / 3 übersprungen; `npm run verify` grün (62 Testdateien); Playwright 181/181.

### Nachtrag 2026-10-11 – Vertragsakte: Kopf, Kästen, Risiko

- **Übersicht:** Karte „Organisation & Zuständigkeit“ (Krankenhaus, Abteilungen, Kostenstelle, Haupt- und weitere Verantwortliche; für alle Rollen, Lesemodell `assignment`). Kachel „Risiko“ entfernt, Kachel „Vertragsbeginn“ ergänzt.
- **Kopf:** Status farbig wie in der Vertragsliste (gemeinsames `BUSINESS_STATUS_TONE`; vorher leere lokale Tabellen); „Vertragsbeginn“ als erste Angabe; Vertragspartner als farbiger Chip (zugeordnet → öffnet `/stammdaten/vertragspartner?id=…`, nur Text → „zuordnen“); „⚠ Was fehlt · N“ als Knopf mit Liste (statt Karte in der Übersicht).
- **Risiko:** „Risiko hoch“ ist klickbar: berechnet aus den aktiven Warnungen (je mit Link zur Stelle), „Bestätigen“ (gilt nur für den bestätigten Wert), „Anders einschätzen …“ mit Pflicht-Begründung, „Auf berechneten Wert zurücksetzen“. Ein festgelegtes Risiko gilt überall, bis es zurückgesetzt wird (`risk_level` = festgelegt sonst berechnet; `risk_computed` aus den Warnungen). Migration `t2c4d6e78012`, `POST /api/contracts/{id}/risk` (`contract.edit`), Verlauf „Risiko bestätigt oder festgelegt“.
- **Vertragsdaten:** Jeder Kasten hat Bearbeiten / Abbrechen / Speichern und Einklappen in der Ecke (`components/ui/CollapsibleSection.tsx`, eingeklappte Kästen merkt sich der Browser); mehrere Kästen gleichzeitig, Abbrechen verwirft nur den Kasten. Organisationszuordnung ebenso. „Interne Nummer“ ist die automatisch vergebene, eindeutige Vertragsnummer (nicht mehr von Hand); ein früher eingetragener Wert steht als „Frühere interne Nummer“ darunter.
- **Nebenbei:** PDF-Knöpfe mindestens 32 px hoch (WCAG-Zielgröße); axe-Fehler in Playwright nennen jetzt die betroffenen Elemente; Journeys 14/16 archivieren ihren Testvertrag auch bei einem Fehlschlag (vorher verfälschte ein Rest die Bildreferenzen).
- **Verifikation:** pytest 1662 bestanden / 3 übersprungen; `npm run verify` grün (64 Testdateien); Playwright 181/181; Migration auf Wegwerf-DB auf/ab/auf.

### Nachtrag 2026-10-11 – Vertragsseite „Ruhe & Signal“ (Plan `Claude outputs/تعليمات-Claude-Code-Vertragsseite.md`)

- **Entscheidungen:** auf dem bestehenden Branch; „Offene Punkte“ als Abschnitt in der Übersicht plus Sprung-Knopf im Kopf; Risiko-Popover und farbiger Partner-Chip bleiben; Zuordnung der Schweregrade freigegeben (Kritisch → Prüfen hoch → KI-Prüfung → Prüfen → Hinweis; Warnungen mit Prüfbedarf folgen ihrem Schweregrad); Punkt 11 umgesetzt (Kopf zeigt nur unbestätigte KI-Werte, „Offene Prüfungen“ heißt „Ungeprüfte Angaben“). Status bleibt farbig (frühere Entscheidung), nicht neutral wie im Plan.
- **Umgesetzt:** Kopf (Brotkrümel, Kennungen mono, Partner · Abteilung · Kostenstelle, Signalzeile, vier Fakten mit stillen Herkunftsmarken, Laufzeitleiste `ContractTermBar`, Knöpfe mit Symbol), Reiter mit Arbeitssymbolen, `OpenPoints` statt Karte/Handlungsbedarf/Kachelreihe, Leistungsumfang mit Zusammenfassung, SLA mit „Nicht im Vertrag gefunden“/„Unbekannt“, ruhige leere Vertragsanalyse, Seitenleiste (Zuständigkeit, Daten & Nachweise, Herkunft der Werte) ab 1180 px. `ValueOriginBadge` zeigt gepflegt/berechnet als graue Marke, KI-Vorschlag/Fehlt als Signal.
- **Feste Laufzeit:** kein „Kündbar bis“ im Kopf, kein kritischer Punkt; Leiste sagt „Feste Laufzeit – endet ohne Kündigung“; unbefristet: Text statt Leiste. Fehlender Kündigungstermin heißt „Kündigungsfrist erfassen“ (führt zum Feld), fehlendes Ende „Laufzeit & Kündigung ergänzen“. Backend: `register_facts.term_model`.
- **Nicht umgesetzt / offen:** Prüfung unter Farbsehschwäche-Simulation und Dark Mode nur über die bestehenden axe-Durchläufe (hell/dunkel/forced-colors), keine manuelle DevTools-Simulation.
- **Verifikation:** pytest 1662 / 3 übersprungen; `npm run verify` grün (66 Testdateien, neu `contract-term-bar`, `open-points`); Playwright 187/187 inkl. neuer Referenz „vertragsakte“ (Desktop/Telefon) und Layout 1920/1366/1000/390.

### Nachtrag 2026-10-11 – Kostenstelle direkt an der Abteilung

- **Abteilung anlegen/bearbeiten:** optionales Feld „Kostenstelle“. Neue Nummer → Kostenstelle für diese Abteilung angelegt (Name = Abteilung); bestehende freie Nummer desselben Krankenhauses → verknüpft; Nummer einer anderen Abteilung → 409 mit deren Namen. Beim Bearbeiten ersetzt eine neue Nummer die bisherige Verknüpfung, leer löst sie (die Kostenstelle bleibt). Liste zeigt die Kostenstellen-Nummer(n).
- **Organisationszuordnung:** Abteilung wählen setzt ihre Kostenstelle, Kostenstelle wählen setzt ihre Abteilung; alle Kostenstellen des Krankenhauses wählbar (passende zuerst).
- **Tests:** neu `backend/tests/test_department_cost_center.py`; `contract-ownership-roles.test.tsx` (+1), `master-data.test.tsx` angepasst. Verifikation: pytest 1663 / 3 übersprungen; `npm run verify` grün; Playwright 187/187.


### Nachtrag 2026-10-11 – Vertragstyp in der Zuordnung, Dokumente entfernen

- **Vertragstyp:** In der Organisationszuordnung wählbar (gespeichert über die Vertragsdaten; eine nicht mehr passende Kategorie wird geleert). Steht im Kopf als Chip vor dem Vertragspartner und in der Karte „Zuständigkeit“ (mit Kategorie; fehlt er, „Festlegen“). Lesemodell `assignment.contract_type`/`contract_category`.
- **Dokumente entfernen** (Entscheidung: Entfernen statt Löschen): „Entfernen“ für Admin/Vertragsmanagement (`document.attach`) mit Bestätigungsdialog und optionalem Grund. Die Zuordnung wandert in `contract_document_removed` (Migration `u3d5e7f89013`), Datei und Verlauf bleiben, die Inhaltssuche-Seiten des Dokuments werden aus dem Vertrag genommen. „Entfernte Dokumente (N)“ unter der Liste mit „Wiederherstellen“. Das Hauptdokument lässt sich erst nach Festlegen eines anderen entfernen (409). Routen `POST /api/contracts/{id}/documents/{link}/remove`, `POST …/documents/removed/{id}/restore`; `GET …/documents` liefert `removed`. Verlauf: „Dokument entfernt“/„Dokument wiederhergestellt“, das Hinzufügen bleibt sichtbar. Der Marker „Hauptdokument“ ist jetzt blau (Information).
- **Tests:** `test_contract_documents.py` (+1), `test_further_responsible.py` erweitert; `contract-documents.test.tsx` (+1), `contract-ownership-roles.test.tsx` (+1), `contract-assignment.test.tsx` angepasst. Migration auf Wegwerf-DB auf/ab/auf.
- **Nächster Schritt:** Alle Kästen einklappbar; danach Vertragslöschung (Rollen) und Abteilungsstruktur.

### Nachtrag 2026-10-11 – Kästen einklappbar, Abschnitte je Vertragstyp

- **Jeder Kasten einklappbar:** `lib/box-collapse.ts` (in `ClientNav`) gibt jedem Abschnitt mit Überschrift im Inhaltsbereich einen Knopf rechts oben; Zustand je Seite und Kasten im Browser; Sprünge zu Abschnitten klappen auf (`revealBox`). Regel in `docs/FRONTEND_CONVENTIONS.md` §3.
- **Abschnitte je Vertragstyp** (Plan `docs/architecture/VERTRAGSPROFIL_ABSCHNITTE_PLAN_20261011.md`): Leistungsumfang, SLA, Wartung und Geräte nur, wo der Vertragstyp sie vorsieht (Wartung/Service: alle; Dienstleistung/Lizenz u. Ä.: Leistungsumfang + SLA; Miete/Leasing/Kauf: Geräte; Versicherung u. Ä.: keine). Ausgeblendet wird nur, was leer ist; ohne Vertragstyp alles. Übersicht nennt Ausgeblendetes mit „Trotzdem anzeigen“; Offene Punkte zählen ausgeblendete Abschnitte nicht. Je Vertragstyp anpassbar (Stammdaten → Vertragstypen → „Abschnitte“, „Standard verwenden“). Migration `v4e6f8a90014` (`catalog_contract_type.sections`), `app/register/sections.py`, Lesemodell `sections`.
- **Tests:** neu `backend/tests/test_contract_sections.py` (2), `frontend/test/box-collapse.test.tsx`; `contracts-detail.test.tsx` (+1). Migration auf Wegwerf-DB auf/ab/auf.

### Nachtrag 2026-10-11 – Vertragskopf: alles anklickbar, Kennfarben, KI-Prüfung; Aufgaben zuerst

- **Vertragskopf:** Jede Angabe führt zur Quelle bzw. zur Stelle, an der sie gepflegt wird: Vertragsnummer → Vertragsdaten, „Nr. lt. Dokument“ → Fundstelle, Vertragstyp/Abteilung/Kostenstelle → Organisationszuordnung, Vertragspartner → Stammdaten, Beginn/Ende → Vertragsdaten oder Fundstelle, „Kündbar bis“ und Laufzeitleiste → Fristen, Kosten → Finanzposten oder Fundstelle. Vertragstyp, Vertragspartner, Abteilung und Kostenstelle tragen je eine eigene Kennfarbe mit Symbol und Wort (Ausnahme in `docs/VISUAL_IDENTITY.md`, Tokens `--color-tag-*`). Fehlt der Vertragstyp, steht „Vertragstyp festlegen“ im Kopf.
- **KI-Prüfung im Kopf:** „KI-Prüfung · N“ (unbestätigte KI-Werte zum Bestätigen) bzw. „KI-Prüfung offen“, wenn nur die Prüfung am Dokument offen ist.
- **Fristen & Aufgaben:** Reiter „Aufgaben“ zuerst und Standard (ohne Aufgaben-Recht weiter „Termine“).
- **Verifikation:** `npm run verify` grün (67 Testdateien); Playwright 187/187 (Bildreferenzen bewusst erneuert: Einklapp-Knöpfe, Kopf, Reiterfolge).

### Nachtrag 2026-10-11 – Gerätearten statt Geräteseite (Plan `docs/architecture/GERAETEARTEN_PLAN_20261011.md`)

- **Idee:** Verträge nach Geräteart einordnen (z. B. alle Wartungsverträge für CTs), filtern und vergleichen. Die Seite „Geräte“ ist aus dem Menü entfernt; `/equipment` leitet zu Analysen → Gerätearten, die Gerätedetails bleiben aus dem Vertrag erreichbar.
- **Stammdaten → Gerätearten:** Liste je Organisation nach Bereich (Medizintechnik, IT, Haustechnik, Sonstiges) mit zuständiger Abteilung und Suchbegriffen; Standardliste (CT, MRT, Röntgen …, Server, Netzwerk, Drucker …, Aufzug, Klima/Lüftung …) wird einmalig angelegt. Pflegen: Administration und Vertragsmanagement (`device_type.edit`).
- **Am Vertrag (Verknüpfungen → Geräte):** Gerätearten mit optionaler Anzahl und Notiz; die Gerätearten der verantwortlichen Abteilung stehen in der Auswahl zuerst; Vorschläge aus im Dokument gefundenen Geräten (ganzes Wort, Bezeichnung oder Suchbegriff) übernimmt nur eine Person. Verlauf „Gerätearten geändert“; Zuständigkeitskarte zeigt die Gerätearten.
- **Vertragsliste:** Spalte und Schnellfilter „Geräteart“ (Mehrfachwert: ein Vertrag mit CT und MRT erscheint unter beiden).
- **Analysen → Gerätearten vergleichen:** je Geräteart laufende Verträge, Geräte und jährliche Kosten mit Abdeckung; eine Geräteart öffnet alle Verträge nebeneinander mit Kosten je Gerät – nur wenn Kosten und Anzahl gepflegt sind und der Vertrag nur diese Geräteart abdeckt, sonst „nicht berechenbar“ mit Grund. Verträge ohne Geräteart werden genannt und verlinkt.
- **Nebenbei:** Einklapp-Pfeil größer und dunkler.
- **Technik:** Migration `w5f7a9b01015` (`catalog_device_type`, `contract_device_type`), `app/register/device_types.py`, Rasterspalte `device_types` (`GridRow.lists`), Bericht `device_type_comparison`, Nutzungszähler in den Stammdaten.
- **Tests:** neu `backend/tests/test_device_types.py` (4), `frontend/test/device-types.test.tsx` (4); `equipment.test.tsx` prüft die Weiterleitung. pytest 1670 bestanden / 3 übersprungen; `npm run verify` grün (68 Testdateien); Migration auf Wegwerf-DB auf/ab/auf.
- **Offen:** Migrationen `u3d5e7f89013`, `v4e6f8a90014`, `w5f7a9b01015` noch nicht auf der lokalen Datenbank des Nutzers (Freigabe ausstehend).

### Nachtrag 2026-10-11 – Abschnitte je Vertragstyp: der Typ entscheidet

- **Rückmeldung:** Vertrag 000002 von Wartung auf Miete umgestellt – Leistungsumfang und SLA blieben sichtbar. Ursache: die Regel „Abschnitt mit Inhalt bleibt sichtbar“ griff, weil die KI Leistungen (Wartung, Inspektion, Software-Updates) und Servicezeiten gelesen hatte.
- **Änderung:** Von der KI gelesene Angaben halten Leistungsumfang, SLA und Geräte nicht mehr sichtbar; der Hinweis nennt sie („mit Angaben aus dem Dokument“), „Trotzdem anzeigen“ zeigt sie. Gepflegte Wartungsdaten und Gerätearten halten ihren Kasten weiter sichtbar. Plan Entscheidung 3 angepasst.
- **Außerdem:** Migrationen `u3d5e7f89013`, `v4e6f8a90014`, `w5f7a9b01015` auf der lokalen Datenbank angewendet (Freigabe des Nutzers); die Vertragsliste meldete vorher „Verbindung zum Server fehlgeschlagen“, weil die Tabelle `contract_device_type` fehlte.
- **Tests:** `contracts-detail.test.tsx` angepasst.

### Nachtrag 2026-10-11 – Erinnerungen, feste Laufzeit, Doppelklick, Kostenstelle

- **Feste Laufzeit:** „Berechnete Fristen“ zeigt kein „Kündbar bis“ und nur ein „Vertragsende“.
- **Erinnerungen:** Erste Erinnerung standardmäßig **4 Monate** vor Kündigungstermin bzw. Vertragsende (vorher 3; das Feld „Erinnerung am“ zeigte ohne Angabe „–“). Leeres Feld zeigt „4 Monate vor der Frist (Standard)“. **Weitere Erinnerungen** (Tage/Wochen/Monate, bis zu 10) im Kasten „Erinnerung & Verantwortung“; jede wird vom Tageslauf genau einmal gesendet (`contract.reminder_extra_leads`, `contract_deadline.extra_remind_on`, Migration `x6a8b0c12016`, `app/register/reminders.py`, `PUT /api/contracts/{id}/reminders`, Verlauf „Erinnerungen geändert“).
- **Doppelklick** auf den Kopf eines Kastens klappt ihn auf/zu (überall; nicht auf Knöpfen, Links, Feldern).
- **Kostenstelle:** wählbar aus verantwortlicher **oder** nutzender Abteilung (gruppiert: Verantwortliche Abteilung · Nutzende Abteilungen · Weitere); die Wahl ändert die Abteilungsrollen nicht mehr, und das Anhaken einer nutzenden Abteilung leert die Kostenstelle nicht mehr.
- **Tests:** `test_deadlines_units.py` (+2), `test_deadlines_api.py` (+1, Standard 4 Monate), `reminder-leads.test.tsx`, `box-collapse.test.tsx`, `contract-ownership-roles.test.tsx`. pytest 1673 / 3 übersprungen; `npm run verify` grün (70 Testdateien); Migration auf Wegwerf-DB auf/ab/auf.

