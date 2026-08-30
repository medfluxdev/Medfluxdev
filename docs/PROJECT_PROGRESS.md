# Medflux – Projektfortschritt

## Projektziel
Ein lokales, schlankes KI-System für deutsche Krankenhäuser zur Analyse und Überwachung von Wartungs- und Serviceverträgen.

Das System soll:
- Verträge lokal als PDF/DOCX importieren
- Inhalte vollständig lokal analysieren
- wichtige Vertragsdaten strukturiert extrahieren
- Vertragsende und Kündigungsfristen überwachen
- jährliche/monatliche/Gesamtkosten auswerten
- Warnungen und Handlungsbedarf anzeigen
- Quellen/Seiten für extrahierte Angaben anzeigen
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
- OCR: lokal, nur wenn nötig
- Zielhardware MVP: RTX 3070 8 GB VRAM, Ryzen 7 5800X, 32 GB RAM
- Architektur: KI-Schicht austauschbar, damit später ein stärkeres Krankenhaus-Modell verwendet werden kann

---

# Gesamtplan

## Schritt 1 – Projektdefinition & Architektur
Status: ABGESCHLOSSEN

Ergebnisse:
- Projektumfang festgelegt
- MVP bewusst klein gehalten
- lokale KI als Kern festgelegt
- AI-Backend von UI/Business-Logik getrennt
- grundlegender Tech-Stack gewählt

## Schritt 2 – Repository & OpenCode-Grundstruktur
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Git-Repository im Projekt-Root `Medflux` angelegt (eigene `.git`-Historie)
- Ordnerstruktur nach AGENTS.md erstellt (frontend, backend, data, docs, scripts)
- `docs/PROJECT_PROGRESS.md` mit vollständig erhaltener Historie
- `.env.example` als Vorlage erstellt sowie `.gitignore` (schützt `data/` und Secrets)
- `README.md` mit Projektüberblick, Tech-Stack und Quickstart
- `docker-compose.yml` für Backend + Frontend (optional Ollama)
- Backend-Gerüst: FastAPI-App, Settings (pydantic-settings), Health-Route, Tests
- Frontend-Gerüst: Next.js 14 / React 18 / TypeScript, strikte Typisierung, API-Helper
- `AGENTS.md` als maßgebliche Projektanweisungen
- `scripts/setup.ps1` als Einmal-Initialisierung

Geänderte Dateien:
- AGENTS.md, README.md, .env.example, .gitignore, docker-compose.yml
- backend/: requirements.txt, app/main.py, app/core/config.py, app/api/routes/health.py,
  app/ (Package-Gerüst), tests/test_health.py, pytest.ini, Dockerfile, README.md, .gitignore
- frontend/: package.json, tsconfig.json, next.config.js, app/, lib/api.ts,
  Dockerfile, README.md, .gitignore
- docs/PROJECT_PROGRESS.md (Projektname: Medflux, Historie erhalten)
- scripts/: setup.ps1, README.md
- data/: contracts, database, backups mit .gitkeep

Tests/Ergebnis:
- Backend: `pytest` → 2 Tests bestanden (root, health) in ~0,5 s
- Frontend: `npm run build` → kompiliert erfolgreich, statische Seite erzeugt
- `.env` aus `.env.example` erzeugt (nicht eingecheckt)

Bekannte Probleme:
- Python 3.10/venv: keine
- Hinweis: `pytest.ini` setzt asyncio-Loop-Scope auf `function` (Zukunftssicherheit)

Nächster Schritt:
- Schritt 3 – Vertrags-Datenmodell definieren (Kernfelder, CONTRACT_SCHEMA.md)

## Schritt 3 – Vertrags-Datenmodell definieren
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Stark typisiertes Vertrags-Datenmodell mit Pydantic-Modellen im Backend
- Wiederverwendbare Werte: Money, Duration, TimeValue, FlexibleDate (explizit/ereignisbasiert/unbekannt)
- Quellen-Nachweis: SourceEvidence (Seite, Quelltext, Confidence, Methode, Prüfbedarf)
- Abschnittsmodelle: Identity, Equipment (mehrere pro Vertrag), Dates, Termination,
  Costs, Payment, Services, SLA, Review, AnalysisMetadata
- Enums: ContractStatus, ContractType, ReviewStatus, RiskLevel, TimeUnit,
  BillingInterval, ExtractionStatus, ValidationStatus u. a.
- Validierung: Confidence in [0,1], Beträge >= 0, Seiten >= 1, keine negativen Fristen
- Unbekannte Werte als null (kein Platzhalterstring)
- EXTRACTED vs. CALCULATED klar getrennt; Berechnungen (latest_cancellation_date,
  Warnstufen, Kostenaggregation) bewusst NICHT enthalten
- Umfangreiche Doku in docs/CONTRACT_SCHEMA.md

Wichtigste technische Entscheidungen:
- FlexibleDate (nicht rohes Datum) erlaubt explizit/unbekannt/ereignisbasiert
- Money als eigener Typ (nicht nur String) für strukturierte Geldangaben
- model_name behalten (KI-Metadata) via protected_namespaces=()
- latest_cancellation_date ist KEIN Extraktionsfeld (Schritt 9 berechnet es)

Geänderte Dateien:
- backend/app/models/enums.py (neu)
- backend/app/models/evidence.py (neu)
- backend/app/models/values.py (neu)
- backend/app/models/contract.py (neu)
- backend/app/models/__init__.py (Exports)
- backend/tests/test_contract_models.py (neu)
- docs/CONTRACT_SCHEMA.md (neu)

Tests/Ergebnis:
- `pytest` → 15 Tests bestanden in ~0,6 s, keine Warnungen
  (vollständiger Vertrag, Minimalvertrag, ereignisbasierter Beginn,
   Geldwerte, Quellennachweis, ungültige Confidence, negative Frist,
   negative Beträge, Seitenzahl, TimeValue, FlexibleDate)

Bekannte Probleme:
- Keine offenen Schritte-3-Probleme
- Hinweis: Berechnete Felder bewusst noch nicht vorhanden (folgen in Schritt 9)

Nächster Schritt:
- Schritt 4 – Dokument-Import (PDF/DOCX)

## Schritt 4 – Dokument-Import
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Lokaler Import von PDF/DOCX-Dateien (mehrere pro Request, unabhängig verarbeitet)
- Validierung: Endung + MIME (wo erkennbar), leere Datei, Größenlimit
- Lokale, sichere Ablage unter data/contracts/<document_id>/original.<ext>
- SHA-256-Berechnung für jede Datei (Integrität, Duplikat-Erkennung, Audit)
- Duplikat-Erkennung über lokalen JSON-Manifest-Index (.index.json), kein Überschreiben
- Pfadsicherheit: Nutzerdateiname nie als Pfad; kein Path-Traversal
- Deutschsprachige Meldungen, keine Tracebacks für Nutzer
- API: POST /api/documents/import (multipart, Mehrfachdatei, strukturierte Antwort)
- Frontend: /import-Seite (deutsch) mit Dateiauswahl, Drag & Drop, „Import starten“,
  Ergebnisliste pro Datei (Importiert/Duplikat/Fehlgeschlagen)
- Größenlimit konfigurierbar über MAX_UPLOAD_SIZE_MB (Settings, nicht hartkodiert)
- python-multipart für Multipart-Uploads hinzugefügt

Geänderte Dateien:
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
- Backend: `pytest` → 28 Tests bestanden in ~0,6 s, keine Warnungen
  (13 STEP-3-Modelle, 13 STEP-4-Import, 2 Health)
  STEP 4: PDF, DOCX, Batch, unsupported Ext, leere Datei, zu groß,
  Duplikat, sicherer Pfad, SHA-256, partieller Batch, MIME-Konflikt, API-Endpunkt
- Frontend: `npm run build` → kompiliert erfolgreich, /import-Seite erzeugt

Bekannte Probleme:
- Keine offenen Schritte-4-Probleme
- Hinweis: Duplikat-Index ist eine reine JSON-Datei (keine DB) – wird in Schritt 10
  durch echte Persistenz abgelöst
- Hinweis: uuid-Kollision bei der ID-Vergabe praktisch ausgeschlossen

Nächster Schritt:
- Schritt 5 – Text-Extraktion (PDF/DOCX, Seitenzuordnung, OCR-Fallback)

## Schritt 5 – Text-Extraktion
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Lokale Textextraktion ohne KI: PDF über PyMuPDF, DOCX über python-docx
- PDF seitenweise mit echten Seitennummern (Seitenzuordnung für spätere Quellenanzeige)
- DOCX in Dokumentreihenfolge: Absätze + Tabellen mit Indizes (Paragraph/Tabelle-Zählung)
- Deterministische Erkennung textarmer/gescannter Seiten über `TEXT_POOR_THRESHOLD = 50`
  (substantive Nicht-Leerzeichen-Zeichen pro Seite)
- OCR-Fallback nur für textarme Seiten; OCRProvider mit `enabled`-Flag, tesseract_cmd, ocr_lang ("deu")
- Graceful Degradation: Tesseract nicht installiert → `OCRUnavailableError`, deutsches Handlungs-Hinweis-
  Feld, Partieller Erfolg bleibt 200
- Deutsche Fehlermeldungen (ERR_PDF_CORRUPT/ERR_DOCX_CORRUPT), keine Tracebacks für Nutzer
- Normalisierung nicht-unterbrechender Leerzeichen (U+00A0 → Leerzeichen, bei deutschen Preisen/Datum)
- API: POST /api/documents/{document_id}/extract (200 Erfolg/teilweise/fehlgeschlagen, 404 unbekannte ID)
- Pfadsicherheit: nur interne document_id-Pfade; SourceType PAGE für PDF / PARAGRAPH+TABLE für DOCX
- OCR-Konfiguration in Settings (config.py) und .env.example (OCR_ENABLED/TESSERACT_CMD/OCR_LANG)

Geänderte Dateien:
- backend/app/documents/extraction/schemas.py (neu: FileType, SourceType, UnitMethod, ExtractionUnit,
  TextExtractionResult)
- backend/app/documents/extraction/ocr.py (neu: OCRProvider, OCRUnavailableError)
- backend/app/documents/extraction/pdf.py (neu: extract_pdf_units, Seiten/Schwellwert/OCR-Warnung)
- backend/app/documents/extraction/docx.py (neu: extract_docx_units, Absätze+Tabellen)
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
- Backend: `pytest` → 46 Tests bestanden in ~1,3 s
  (STEP 5: Normal-PDF, Mehrseiten-PDF+Seitennummern, textarm→OCR, OCR nicht verfügbar,
   DOCX-Absätze/-Tabellen/-Indizes, Umlaute, €, Preisformat 5.916,67 €, Datum, beschädigte
   PDF/DOCX (graceful), unbekannte ID, Quellen-Traceability, Originaldatei unverändert,
   API-Extraktion + 404)
- Frontend: `npm run build` → kompiliert erfolgreich (keine Frontend-Änderungen nötig)

Bekannte Probleme:
- Tesseract-Binary nicht installiert → OCR deaktiviert (graceful, deutsches Hinweisfeld).
  OCR wird erst nach Installation von Tesseract funktionieren (Konfiguration steht bereit).
- PyMuPDF/swig DeprecationWarnings bei Import (nicht blockierend)
- Hinweis: KI-Extraktion von Vertragsfeldern bewusst NICHT Teil von Schritt 5 (folgt in Schritt 7)

Nächster Schritt:
- Schritt 6 – Local-AI-Anbindung (Ollama, Qwen3 8B Q4, Health Check, ModelProvider-Schnittstelle)

## Schritt 6 – Local-AI-Anbindung
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Ausschließlich lokale KI (Ollama) – keine externen KI-APIs (OpenAI, Anthropic, Gemini, Azure)
- Provider-Abstraktion `AIProvider` (base.py): health_check(), model_info(), generate()
- `OllamaProvider` über httpx: GET /api/tags (Modell-Liste), POST /api/chat (Generierung)
- Nur der konfigurierte lokale Ollama-Endpunkt (127.0.0.1:11434) wird angesprochen
- Default-Modell `qwen3:8b` (konfigurierbar über OLLAMA_MODEL); nicht Qwen-spezifisch gebaut
- Zeitüberschreitung, Verbindungsfehler, HTTP-Fehler, ungültiges JSON, leere Antwort behandelt
- Saubere interne Exceptions (AIProviderError + Unterklassen) mit deutschen Nutzer-Meldungen
- Modell nicht installiert → „Das lokale KI-Modell qwen3:8b ist nicht installiert.“ (kein Modellwechsel/-Download)
- Ollama nicht erreichbar → „Die lokale KI ist derzeit nicht verfügbar.“ (keine Roh-Exceptions)
- Status-API: GET /api/ai/status (provider, available, model, model_available, message)
- Test-API: POST /api/ai/test (dev only, minimal deutsches System-Prompt, kein STEP-7-Prompt)
- Konservative Generierung: AI_TEMPERATURE=0.1, AI_MAX_TOKENS=256, Timeout=120 s
- Thinking-Modus (Qwen3) standardmäßig aus: `ollama_think=false` → Antwort direkt in
  `message.content` (kein Aufzehren des Token-Budgets durch Gedankenschritt)
- Logging von Provider/Modell/Dauer/Erfolg – NICHT von vollem Vertragstext
- Router in main.py registriert; kein RAG/Embeddings/Vektor-DB
- Keine Vertrags-Extraktion umgesetzt (folgt in Schritt 7)

Geänderte Dateien:
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
- Backend: `pytest` → 70 Tests bestanden in ~1,3 s
  (inkl. neuem Test, der das Senden von `think`- und Streaming-Optionen prüft;
   Alle mit gemockter Ollama-API via httpx.MockTransport, ohne echte Verbindung)
  STEP 6: Provider-Konfiguration, Ollama verfügbar/nicht verfügbar, Modell
  verfügbar/fehlt, erfolgreiche Generierung, Timeout, HTTP-Fehler, ungültige Antwort,
  leere Antwort, Status-API, Test-API, deutsche Meldungen, „kein externer Provider“,
  ungültige Eingabe (422)
- Frontend: `npm run build` → kompiliert erfolgreich (keine AI-UI gebaut, wie gefordert)

Bekannte Probleme:
- Hinweis: Qwen3-Modelle haben einen „Thinking“-Modus. Ist er aktiv, kann das
  Token-Budget aufgezehrt werden und die Antwort landet nicht in `message.content`
  (→ „keine Antwort“). Deshalb ist `OLLAMA_THINK=false` (Standard) gesetzt; das
  Modell antwortet dann direkt.
- Hinweis: Kein weiteres Modell automatisch bezogen; ein Wechsel erfolgt nur über
  `OLLAMA_MODEL`.

Nächster Schritt:
- Schritt 7 – Strukturierte KI-Extraktion (JSON-Schema, deutsche Prompts,
  Quelle + Seite + Confidence, „nicht gefunden“ statt Halluzination)

## Schritt 7 – Strukturierte KI-Extraktion
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Implementiertes:
- Vollständig lokale Pipeline: TextExtractionResult (Schritt 5) → deterministisches
  Chunking → strukturierte Extraktion je Chunk über die lokale KI (AIService/AIProvider
  → Ollama, qwen3:8b) → strikte JSON-Ausgabe → Parsing → Pydantic-Validierung gegen
  das Contract-Schema (Schritt 3) → deterministisches Multi-Chunk-Merging → Contract-Modell
- KEINE DB-Persistenz (folgt in Schritt 10); KEINE Berechnungen (Kündigungstermin,
  Kostenaggregation, Warnstufen) – reine Fakten-Extraktion durch die KI (folgt in Schritt 9)
- Versionierter Extraktions-Prompt `contract_extraction_v1` (deutsch, JSON-only,
  Anti-Halluzination: fehlende Werte als null, keine Platzhalter, ereignisbasierte
  Daten als condition statt erfundener Kalenderdaten, semantische Geld-Klassifikation)
- Quelle + Seite/Confidence/Prüfhinweis: SourceEvidence für PDF (Seite) und DOCX
  (Absatz/Tabelle/Zelle, page=null, keine erfundenen Seiten); Confidence 0..1,
  unter 0.50 zusätzlich requires_review; source_text nur wörtlich und kurz (≤ ~120 Zeichen)
- Robustes JSON-Parsing (_parse_json) + kontrollierter Retry bei ungültigem JSON
- Deterministiches Chunking (chunk_units): Einheiten bis 6000 Zeichen gebündelt,
  über-große Einheit bildet allein einen eigenen Chunk (Quellzuordnung bleibt erhalten)
- Multi-Chunk-Merging (_merge/_deep_merge): kein Überschreiben durch null,
  Listen-Deduplizierung, widersprüchliche Werte → requires_review (kein stilles Auflösen)
- Ergebnis-Modell ContractAnalysisResult (status, validation_status, requires_review,
  contract, model, prompt_version, chunk_count, processing_duration) + Orchestrator
- API: POST /api/documents/{document_id}/analyze (404 bei unbekannter ID)
- Konfiguration: AI_EXTRACTION_MAX_TOKENS=2048, AI_MAX_CHUNK_CHARACTERS=6000
  (config.py + .env.example)
- Umgang mit dem „Thinking“-Modus von Qwen3 bestätigt (OLLAMA_THINK=false):
  Antwort landet direkt in message.content (thinking_key_present: False)

Geänderte Dateien:
- backend/app/ai/contract_extractor.py (neu: chunk_units, _parse_json,
  StructuredContractExtractor, ContractAnalysisResult, _merge/_deep_merge,
  ContractAnalysisOrchestrator)
- backend/app/ai/prompts/__init__.py (neu)
- backend/app/ai/prompts/contract_extraction_v1.py (neu: versionierter Prompt)
- backend/app/ai/base.py + service.py + providers/ollama.py (max_tokens-Param,
  AIService.generate_text)
- backend/app/core/config.py (ai_extraction_max_tokens=2048, ai_max_chunk_characters=6000)
- backend/app/models/evidence.py (SourceEvidence: source_type, paragraph_index,
  table_index, cell_index für DOCX; protected_namespaces=())
- backend/app/ai/schemas.py (AIStatus protected_namespace-Warnung behoben)
- backend/app/api/routes/documents.py (POST /analyze-Endpunkt)
- backend/tests/test_contract_extraction.py (neu)
- docs/STRUCTURED_AI_EXTRACTION.md (neu)
- .env.example (AI_EXTRACTION_MAX_TOKENS, AI_MAX_CHUNK_CHARACTERS)

Tests/Ergebnis:
- Backend: `pytest` → 96 Tests bestanden in ~1,15 s
  (STEP 7: Chunking deterministisch/über-große Einheit, JSON-Parsing, Retry bei
   ungültigem JSON, Validierung, Merge ohne Überschreiben, Listen-Deduplizierung,
   Konflikt → requires_review, Fehlermeldungen, Orchestrator, /analyze-Endpunkt +
   404; alles mit gemockter Ollama-API via httpx.MockTransport)
- Frontend: `npm run build` → ✓ Compiled successfully, statische Seiten erzeugt
- Realer lokaler Smoke-Test (synthetischer PDF-Wartungsvertrag, qwen3:8b):
  status: success, validation_status: valid, requires_review: false, Dauer ~38,6 s;
  extrahiert u. a. Vertragsnummer WM-2024-0001, Lieferant Siemens Healthineers,
  Vertragstyp maintenance, 2 Geräte (CT SOMATOM go.Top + MRT MAGNETOM Vida),
  Laufzeit 2024-07-01 bis 2027-06-30 (36 Monate), 6-Monats-Kündigungsfrist,
  automatische Verlängerung (12 Monate), Jahreskosten 24.500 EUR, Monatskosten
  2.041,67 EUR, Gesamtwert 294.000 EUR, Zahlung/Leistungen/SLA (4h, 24/7);
  Quelle Seite 1, Confidence 1.0

Bekannte Probleme:
- Keine echten Verträge im Repository (nur .gitkeep); der Smoke-Test lief mit
  einem synthetischen PDF-Fixture. Formale Benchmark folgt in Schritt 8.
- Ermittelt im Smoke-Test: qwen3:8b bricht bei 1024 Tokens ab
  (done_reason: length, JSON mitten im String) → AI_EXTRACTION_MAX_TOKENS=2048
  (done_reason: stop). Wert für qwen3:8b kalibriert, formal in Schritt 8 gebenchmarkt.
- Der Prompt erlaubt zusätzliche, nicht im Schema vorhandene JSON-Schlüssel;
  Pydantic ignoriert diese (kein hartes Ausgabeschema erzwungen) – ggf. in
  Schritt 8 prüfen.
- source_text-Begrenzung (≤ ~120 Zeichen) ist eine weiche Prompt-Anweisung;
  das Modell schreibt sie gelegentlich ausführlicher.
- OCR weiterhin nur optional (Tesseract nicht installiert, Graceful Degradation)

Nächster Schritt:
- Schritt 8 – Benchmark mit echten Verträgen (20–30 Testfälle, manuell
  vergleichen, Prompt/Schema iterativ verbessern, Halluzinationsrate messen)

## Schritt 8 – Benchmark mit echten Verträgen
Status: ABGESCHLOSSEN
Datum: 28.08.2026

Testkategorien:
- Beginn/Ende
- Kündigungsfrist
- automatische Verlängerung
- Kosten
- Dienstleister
- Reaktionszeiten
- Leistungsumfang
- Halluzinationsrate

Ziel:
- 20–30 reale Verträge als Testset
- Ergebnisse manuell vergleichen
- Prompt/Schema iterativ verbessern

Implementiertes:
- Reale, repräsentative Verträge als Benchmark-Grundlage: aus der vom Nutzer
  bereitgestellten ZIP `العقود.zip` (33 echte DOCX-Verträge) nach
  `data/benchmark/input/العقود/` entpackt (nicht eingecheckt)
- Manuell geprüfte Ground-Truth für 6 Sample-Verträge in
  `data/benchmark/ground_truth.json` (Vision RFD 3D, Siemens MRT Vida 3T,
  Abiomed Full-Service, Apoplex SRAclinic, GE MACLAB, Truebeam STX; 64 Felder)
- Benchmark-Runner `scripts/benchmark_extraction.py` (nutzt die vorhandene
  Pipeline Schritt 5 + Schritt 7): typisierte Matcher (contains, enum_in, bool,
  null/not_null, money_amount+tol, duration, time_value, device_contains,
  serial_contains, int_ge), Fehlerklassifikation (fehlend/falsch/erfunden),
  JSON-Report nach `data/benchmark/report_latest.json`; Option `--runs N`
  (best-of-N gegen Modell-Nichtdeterminismus)
- Ergebnis-Dokumentation in `docs/AI_EVALUATION.md`

Durchgeführte, begründete Änderungen (aus Benchmark-Fehlern abgeleitet):
- `config.py`: `ai_extraction_max_tokens` 2048 → 8192 (behebt abgeschnittenes
  JSON / Truncation bei komplexen Verträgen, done_reason=length)
- `prompts/contract_extraction_v1.py`: Abschnitt „SCHEMA-TREUE (PRIORITÄT 1)“
  ergänzt (exakte Feldnamen/Struktur, equipment=Liste, services=Objekt,
  contract_type-Kleinbuchstaben-Enum, keine erfundenen Abschnitte,
  vollständiges JSON)
- `contract_extractor.py`: Retry greift jetzt auch bei schemawidriger, aber
  JSON-konformer Ausgabe (bisher nur bei ungültigem JSON);
  `_RETRY_SYSTEM_PROMPT_SUFFIX` um Schema-Hinweis erweitert

Geänderte Dateien:
- scripts/benchmark_extraction.py (neu)
- data/benchmark/ground_truth.json (neu)
- data/benchmark/report_latest.json (generiert)
- docs/AI_EVALUATION.md (neu)
- backend/app/core/config.py (ai_extraction_max_tokens=8192)
- backend/app/ai/prompts/contract_extraction_v1.py (SCHEMA-TREUE-Abschnitt)
- backend/app/ai/contract_extractor.py (Retry auch bei Schema-Abweichung)

Tests/Ergebnis:
- Backend: `pytest` → 96 Tests bestanden (~1,2 s, unverändert)
- Benchmark (6 echte Verträge, 64 Felder):
  - Baseline (vor Änderungen, 1 Lauf): 16/64 = 25,0 %; 39 fehlend, 9 falsch,
    0 erfunden; nur 1/6 validiert
  - Nach Änderungen (best-of-3): 8/64 = 12,5 %; 39 fehlend, 17 falsch,
    0 erfunden; nur 1/6 validiert (Siemens); Ø ~130 s/Vertrag
- Konstante Schwachstellen: contract_type/billing_interval (Enum) immer falsch,
  termination.*, Dauer/Daten und Geldbeträge fehlen zuverlässig
- Halluzinationsrate: 0 (Anti-Halluzination wird eingehalten)
- Schlussfolgerung: qwen3:8b (Q4) mit reinem Prompt-Ansatz erfüllt die
  „zuverlässige Extraktion“ des MVP nicht; Ansätze dafür in STEP 9-Abschnitt
  von docs/AI_EVALUATION.md (z. B. strukturierte Modell-Ausgabe erzwingen)

Bekannte Probleme:
- qwen3:8b weicht trotz verstärktem Prompt vom Schema ab (u. a. contract_type
  als Großbuchstabenwert) und liefert nur ~12,5 % Feldgenauigkeit
- Modell-Nichtdeterminismus: Lauf-zu-Lauf-Varianz; nach den Änderungen stabil,
  aber auf niedrigem Niveau
- Realer Datenbestand (33 Verträge) wird nicht eingecheckt (data/ ist gitignored)
- Für langsame OCR-CPU-Bewehrung: Truebeam/komplexe Verträge bis ~3–4 min

Hinweis — STEP 8B (interne Härtung, zählt NICHT als neuer Schritt):
- Nach dem abgeschlossenen STEP 8 erfolgte eine nicht gezählte Härtungsphase
  «STEP 8B – Extraction Reliability Hardening» (Details:
  docs/STEP_8B_CHECKPOINT.md und STEP-8B-Abschnitt in docs/AI_EVALUATION.md).
- Kern: native strukturierte Ausgabe über Ollama (`format`=JSON-Schema aus dem
  Pydantic-Modell), `repeat_penalty=1.3` (behebt Wiederholungsschleifen),
  `ai_request_timeout_seconds=300`, `extra="forbid"` auf Contract.
- Ergebnis (6 echte Verträge × 3 Läufe, gleiche Ground Truth): best-of-3
  Feldgenauigkeit 31/64 = 48,4 %; Validierung 6/6 (17/18 Einzelläufe valid);
  0 erfunden, 0 Timeouts, 0 Truncation, Ø ~32 s. Schema-Konformität/Enums behoben;
  semantische Feldabdeckung noch nicht MVP-reliabel (Kosten, Fristen, seltene
  Felder). Fortschritt bleibt 8/18 = 44,4 %.

Hinweis — STEP 8B-Semantik (Feldgruppen-Extraktion, weitere interne Phase):
- Matcher-Fix vervollständigt (scripts/benchmark_extraction.py `_norm_str`:
  `getattr(v, "value", v)`; der frühere `isinstance(str)`-Guard war bei
  str-Enums wirkungslos und wertete ALLE Enum-Felder falsch). Korrigierte
  STEP-8B-Baseline: 38/64 = 59,4 % (31 + 7 Enum-Korrekturen; die früher
  genannte 39/64 enthielt 1 Doppelzähl-Artefakt bei Vision `equipment`).
- Neue Pipeline: `GroupPipeline` (Feldgruppen je Chunk, deterministischer
  Merge, Evidence-First-Verifikation gegen Original-DOCX, semantischer Verifier).
  Neuer Runner `scripts/benchmark_groups.py`; neuer Report
  `data/benchmark/report_groups.json` (historischer `report_latest.json`
  bleibt unverändert).
- Ergebnis (6 Verträge, 1 Lauf je Vertrag, korrigierter Matcher): Feldgenauigkeit
  **43/64 = 67,2 %** (Vision 12, Siemens 6, Abiomed 8, Apoplex 5, GE 5,
  Truebeam 7; Baseline korr. 38/64); 0 erfunden, 0 Timeouts, 0 Retries,
  0 Truncation, Ø ~62 s (Truebeam ~156 s, 11 Chunks/44 Gruppen).
- Ehrlicher Zusatzbefund: Validierung fällt auf 0/6 `invalid` + requires_review –
  konservative Verifier-/Review-Logik (unsupported sensible Felder), nicht
  fehlende Extraktion; Security gut, Automation noch nicht selbstvalid.
  Fortschritt bleibt **8/18 = 44,4 %**.

Hinweis — Dokument-Ingestion / Qualitäts-Check Benchmark v2 (Diagnose, kein Schritt):
- Neues PDF-Korpus aus `Desktop\العقود الجديدة.zip` nach
  `data/benchmark_v2/input/` extrahiert (Original-Archiv und Legacy-`data/benchmark/`
  unangetastet; kein neues Ground Truth).
- Ergebnis der Textschicht-Diagnose (36 PDFs, 355 Seiten): **34× scanned_image,
  2× partial_text (nur Kopf-/Metadaten-Layer: BD Service „Docusign Envelope ID…",
  1-seitiges CCE-Konditionsblatt), 0× native_text, 0× unreadable**. Gesamt nur
  3.095 native Zeichen (Ø 8,7/Seite) → der neue PDF-Korpus ist praktisch
  vollständig ein OCR-Korpus; qwen3:8b-Benchmarks dort sind erst nach OCR sinnvoll.
- Neue, testbare Klassifikationslogik: `backend/app/documents/quality.py`
  (+ `scripts/document_quality_inspection.py`, Report
  `data/benchmark_v2/document_quality.json`, Doku
  `docs/DOCUMENT_QUALITY_EVALUATION.md`; fokussierte Tests 9 passed).
- OCR-Ist-Zustand: Abstraktion vorhanden und lokal (`OCRProvider`,
  `extract_pdf_units` rastet textarme Seiten mit 300 dpi, Seiten-Evidence bleibt
  über `ExtractionUnit`/Page-Index erhalten, `ocr_lang="deu"` konfiguriert) –
  aber **Tesseract-Binary ist auf dieser Maschine NICHT installiert**
  (pytesseract/Pillow/fitz vorhanden; kein choco/scoop/PATH) ⇒
  `is_available()=False`. Es wurde NICHTS installiert; lokale Optionen geprüft.
- Fortschritt bleibt **8/18 = 44,4 %**.

Hinweis — Quell-Navigation in extrahierten Einheiten/Nachweisen (interne Phase):
- Vorarbeiten für STEP 14 „Quelle anzeigen öffnet passende PDF-Seite“: Die Schritt-5-
  Textextraktion trägt jetzt deterministisch Koordinaten-Metadaten mit, damit die
  Quellenanzeige ohne erneute Extraktion/Re-OCR auskommt.
- `app/documents/geometry.py` (neu): `ocr_pixels_to_pdf_rect` rechnet OCR-Bildpixel
  deterministisch in PDF-Punkte um (72/inch, Ursprung oben links, y nach unten;
  Seitenrechteck-basiert, robust gegen Clips/Skalierung).
- `app/documents/extraction/pdf.py`: native Wort-Boxen je Seite (`page_words`,
  PyMuPDF) sowie OCR-Wort-Boxen je gerasteter Seite (300 dpi) werden als
  `SourceBox(page, x0,y0,x1,y1,text,confidence)` an jeder `ExtractionUnit`
  mitgeführt (`bbox`=Einhüllende, `boxes`=Wort-Boxen, `ocr_confidence`=Mittelwert
  gültiger Konfidenzen; negative/nicht vorhandene Konfidenzen => None).
- `app/documents/extraction/schemas.py`: `ExtractionUnit` um optionale `bbox`/
  `boxes`/`ocr_confidence` erweitert (default wertefrei ⇒ alle bestehenden
  Aufrufer unverändert gültig).
- `app/models/evidence.py`: `SourceEvidence` um `document_id`, `bounding_box`
  (PDF-Punkte) und `ocr_confidence` erweitert (alles optional, rückwärts-
  kompatibel).
- `app/ai/groups/evidence.py`: `verify_evidence` füllt den `bounding_box` eines
  PDF-Nachweises aus den echten Wort-Boxen der belegten Seite (nur Boxen, deren
  Text im Quelltext vorkommt; sonst die Einheiten-Region) und übernimmt die
  Einheiten-OCR-Konfidenz – Mathematik statt Raterei, niemals erfundene
  Koordinaten.
- Sicherheit/Ist: Es werden KEINE Bild- oder Seitenrender-Koordinaten gespeichert;
  die Workspace-Logik „KI extrahiert Fakten, Code berechnet/zeigt“ bleibt
  unangetastet. Kein neues Rendering für die Anzeige nötig.

Geänderte Dateien (interne Phase):
- backend/app/documents/geometry.py (neu)
- backend/app/documents/extraction/schemas.py (SourceBox, ExtractionUnit+Boxen)
- backend/app/documents/extraction/pdf.py (Wort-Boxen native+OCR, Konfidenz-Mittel)
- backend/app/models/evidence.py (document_id, bounding_box, ocr_confidence)
- backend/app/ai/groups/evidence.py (deterministische Bounding-Box-Anreicherung)
- backend/tests/test_source_navigation.py (neu)

Tests/Ergebnis:
- Backend: `pytest` → **132 Tests bestanden** in ~2 s
  (neu: 14 Quell-Navigations-/Geometrie-/Kompatibilitätstests; alle 118
  Bestands-Tests weiterhin grün).
- Frontend: keine Frontend-Änderungen nötig.
- Bekannte Einschränkung: OCR-Koordinaten fallen erst an, wenn Tesseract
  installiert ist (native PDF-Seiten bringen auch ohne OCR Boxen mit).

Hinweis — STEP 8B/DI (Lokale Dokument-Intelligence-Schicht, interne Phase):
- Ziel: Aufbau einer minimalen, provider-neutralen Document-Intelligence (DI)-
  Schicht in `backend/app/documents/intelligence/` und Messung der OCR-Qualität
  auf 3 repräsentativen Original-PDFs, BEVOR STEP 9 die Qwen-Extraktion auf den
  Bestand anwendet. Fortschritt bleibt **8/18 = 44,4 %**.
- Kanonisches Modell `canonical.py` (Medflux-eigen, keine Provider-Abhängigkeit):
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
  Mapping→kanonisch inkl. BOTTOMLEFT→PDF-Punkte-Umrechnung, OCR-Konfidenz,
  Warnungen aus `result.errors`. `native_provider.py` nutzt die Schritt-5-
  Extraktion (Method.NATIVE).
- Wichtige Fehlerbehebungen während der Diagnose: (1) `_assign_page_text`
  zählte bei leeren Elementen (Bilder) den Trenner nicht → Span-Offsets nach
  einem Bild verschoben → Quell-Navigation schlug fehl; (2) Docling lieferte
  Items doppelt (Body+Floats) → Dedup je Seite/Box/Textlänge; beide als
  Regressionstests abgesichert.
- Ergebnisse der 3-PDF-Diagnose (`scripts/document_intelligence_diagnosis.py`,
  JSON-Reports unter `data/benchmark_v2/di_reports/`, Hervorhebungs-Render im
  Original-PDF-Kontext als PNG, Token-Scans, GT-Abgleich, PDF-vs-DOCX,
  Lesereihenfolge-HF-Check):
  - **Vision RFD 3D** (5 S., 36,6 s): 66 Elemente, 4 Tabellen; Geld
    `13.115,00`→Seite 4 = GT 13115,00 (match 1/1 DOCX); Datum 13.06.2017→S.1;
    GT 6/7 (einziger Miss: Seriennummer liegt im Scan als „21115" vor, im
    Legacy-DOCX-Brief ebenfalls „21115", Gerätetabelle nennt 24445 →
    dokumentierte Disparität, für STEP 14/9 mit Konfidenz statt Annahme).
  - **GE MACLAB** (6 S., 33,5 s): GT 2/2 (CA-15120, MacLab); Geld im deutschen
    `-,`-Format erkannt, DOCX-Vergleich **3/3 match**; Datum 16. April 2025;
    Prozentwerte 2,5–25 %, negative Abdunkler (5 % Eigenleistung) korrekt.
  - **Truebeam STX** (14 S., 94,2 s): GT 4/6 – fehlende 2 sind reine
    Datumsformat-Differenz (GT ISO 2018-01-27 vs. Scan „27. Januar 2018",
    beide Werte sind IM OCR-Text vorhanden); Gesamtwert **792.000,00** und
    inkl. MwSt. **942.480,00** (19 %), Geräte-Seriennummer H192469, Klausel
    „Kündigungsfrist"→Seite 11; DOCX-Geldabgleich 4/6 (2 Abweichungen sind
    Nur-Noise „000,00"/„480,00" aus einem OCR-Tippfehler 150,480,00).
  - Lesereihenfolge/HeaderFooter-Sharing: HF-Anteil 0,0 für alle (Docling
    klassifiziert bei Scans keine PAGE_HEADER/FOOTER-Elemente) → Check
    trivially grün; verbleibender Hinweis für STEP 9-Prompting.
  - Negation/Deutsch/Englisch: Negationsbegriffe PDF≈DOCX (7≈7, 20≈20,
    123≈127), deutsche Zeichenähnlichkeit hoch (77/89, 177/193, 726/743).
- Sicherheit/Datenlebenszyklus-Entscheidungen (RECORD, keine Umsetzung):
  - DI-Schicht speichert NUR extrahierte Texte/Struktur/Koordinaten in
    `data/benchmark_v2/di_reports/` (gitignored); Original-PDFs werden beim
    Rendern NIE modifiziert (fitz `new_shape()` in-memory).
  - Kein neues Ground Truth, kein Produktions-Cache, keine Konfidenz-Mischung:
    OCR-/Layout-Konfidenz verbleibt in der DI-Schicht; KI-semantische
    Konfidenz (STEP 7/8B-Semantik) bleibt getrennt.
  - Cache-/Reprozess-Vertrag für STEP 9: canonical-json je Quelle + SHA-256 +
    Pipeline-Hash + Verarbeitungszeit in Provenance; `--refresh` zur
    Reproduktion; keine zusätzlichen Artefakte nötig.
- **Entscheidung Sicherungspunkt (Gate B)**: Docling+RapidOCR als KERN-OCR/
  Layout/Tables-Schicht für STEP 9 geeignet, MIT Pflicht-Vorgaben:
  1) OCR-Zeichen-Konfidenz je Element in die SourceEvidence-Auswertung
     übernehmen (String-Hypothese > 0,999 über vollständigem Wort-Box-Abgleich);
  2) Serien-/Werte-Disparität (Vision „21115"vs„24445") nur über
     Dokumenten-Konsistenz + Konfidenz auflösen, nie erraten;
  3) komplexe Kostentabellen (Truebeam: 2 vs. 14 DOCX-Tabellen) via
     Lese-Reihenfolge-Fallback (Werte sind im Text vorhanden);
  4) German-Month-Datumsform („27. Januar 2018") beim Parsing mitnehmen.
- Geänderte Dateien:
  - backend/app/documents/intelligence/{canonical,provider,native_provider,
    docling_provider,__init__}.py (neu)
  - backend/tests/test_document_intelligence.py (13 fokussierte Tests)
  - scripts/document_intelligence_diagnosis.py (neu)
  - data/benchmark_v2/di_reports/* (generiert, gitignored)
  - docs/PROJECT_PROGRESS.md (dieser Hinweis)
- Tests/Ergebnis: `pytest` → **145 Tests bestanden** (132 Baseline + 13 DI;
  inkl. Regressionen für Span-Offsets bei leeren Elementen und Item-Dedup).
- Ressourcen: Vision 36,6 s / GE 33,5 s / Truebeam 94,2 s auf CPU; Modelle
  nach erstem Lauf im HF-Cache, seither offline verwertbar
  (`offline_after_setup=True`).

Hinweis — STEP 8B/DI korrektive Härtung (interne Phase, Fortschritt bleibt 8/18 = 44,4 %):
- Anlass: Gate B war erteilt, vier dokumentierte Pflichtvorgaben wurden in einer
  internen 10-Phasen-Härtung geschlossen; anschliessend Gate-Entscheidung A–E.
- Phase 1 – Legacy-Review (`C:\Users\JAMAL\Desktop\Medflux_Legacy`, READ-ONLY):
  Konzepte statt Kopie. Übernommene Konzepte: char-gewichtete Sprachanteile,
  Kopf-/Fuss-Band-Heuristik (~12 %), mittlerer positiver OCR-Konfidenzwert,
  Bild-Abdeckungsstatistik, deutsche Text-Nachbereitung. Abgelehnt (dokumentiert):
  LightTableDetector (cv2/Tesseract-Gitterlinien), Tesseract-Leser-Pipeline,
  Legacy-Schemas/Provenance-/Offsets-Services (skaffold, schema-gebunden);
  Legacy-Tests nicht portabel → übernommene Tests: 0.
- Phase 3A – Evidenz-Brücke `intelligence/evidence.py`: `evidence_from_element/`
  `evidence_from_cell` → SourceEvidence mit `ocr_confidence` (Recognition) STRENG
  getrennt von `confidence=None` (semantisch, erst spätere KI-Stufe) und
  `extraction_method=PROGRAMMATIC`; BoundingBox nur bei vorhandener Region.
- Phase 3B – Disparität `intelligence/disparity.py`: `ValueCandidate`+
  `classify_values()` → CONSISTENT/SINGLE/CONFLICT/UNDETERMINED, NIE Raten;
  Original-Wortlaut bleibt erhalten. Erkannte Realität: Vision Seriennr.
  „21115" (Scan+Brief) vs. „24445" (Gerätetabelle) → CONFLICT, review_required.
- Phase 3C – Deutsche Daten `intelligence/dates.py`: Monatsnamen + übliche
  Abkürzungen (Jan./Feb./März§/Apr./Jun./Jul./Sep./Okt./Nov./Dez.),
  numerisch DD.MM.YYYY; „27. Januar 2018"→2018-01-27; ungültig/ereignisbasiert
  („ab Übergabedatum", „32. Januar") → None (kein Erfinden).
- Phase 3D – Kostentabellen `intelligence/table_normalize.py` (Verifikation
  auf Truebeam): table_p5_12 ist Zell-strukturiert (Zeile „TrueBeam STx -
  H192469 - Essentials" mit 8× €99.000,00; „€99,000,00"-Zellen → review);
  die kritischen Beträge ausserhalb der Tabelle (792.000,00 / 942.480,00 auf
  S.2/4/5) sind DETERMINISTISCH über „ein Label links in derselben y-Bande"
  belegbar (`trust=geometry`, Beträge 792000.00/942480.00); „150,480,00" unter
  Label „MwSt. 19.0 %" bleibt `review_required` (suspicious_ocr_token) – als
  MwSt-Ausweis (942.480,00−792.000,00) für den Menschen prüfbar. Keine
  supplier-spezifischen Regeln (z. B. „×9" wird nie interpretiert).
- Phase 4 – Strukturrollen `intelligence/structure.py`: deterministischer
  Nachbereitungs-Pass `apply_structural_roles()` (y-Banden oben/unten ≤8 %,
  Wiederholung auf ≥2 Seiten, Seitenzahl-Muster) setzt NUR
  `metadata["structural_role"]` = header/footer/page_number; Text wird nie
  gelöscht (schützt z. B. vor Docusign-Envelope-ID-Dominanz). In
  `docling_provider` aktiviert (`settings.structural_roles=True`) und in der
  Provenance als `preprocessing="structural_roles_v1"` festgehalten.
  Diagnose-Ergebnis auf den 3 Scans: 0 markierte (echte Negativprobe – die
  Scans enthalten KEINE wiederkehrenden Band-Zeilen/Seitenzahlen); der Pass
  lief auf allen Seiten und meldet sich per Warning; Funktionseinheit ist per
  Unit-Test belegt.
- Phase 5 – Token-Sicherheit `intelligence/token_safety.py`: nur UNAMBIVALENTE
  Muster normalisiert (`792.000,00`→Decimal(792000.00), `1.234,-`→1234.00);
  verdächtige OCR-Muster (`150,480,00`, `5.916.67`, `792,000,00`) → 
  `suspicious`/„manueller Review erforderlich", Prozent-/Datum-/Serien-Tokens
  separat klassifiziert.
- Phase 6 – Quell-Navigation `scripts/source_navigation_diagnostics.py`
  (nur Cache, kein Docling): 6/6 Ziele programmatisch gefunden + hervorgehobene
  Render-PNGs + Manifest `source_navigation_diagnostics.json` – Vision: Datum
  13.06.2017 (S.1) + 13.115,00 (S.4); GE: Datum 16. April 2025 (S.1) + 3.429,-
  (S.5); Truebeam: 942.480,00 (S.2) + Phrase „Kündigungsfrist" (S.11).
  **VISUAL HUMAN VERIFICATION PENDING** – das Modell kann keine Bilder sehen;
  die programmatische Verifikation (Seite/Element/Span/Region/Render) ist von
  einem Menschen im Original-PDF zu bestätigen, getrennt berichtet.
- Phase 8 – Manifest `scripts/manifest_verification.py`: alle 3 kanonischen
  Ergebnisse `all_ok=True` (source_sha256, provider+Version, RapidOCR+Version,
  ocr_lang, dpi=None dokumentiert, preprocessing, CANONICAL_SCHEMA_VERSION
  „1.1.0", created_at, warnings). Keine duplizierten Metadaten.
- Geänderte/neue Dateien:
  - backend/app/documents/intelligence/{canonical,provider,docling_provider}.py
    – Provenance erweitert (dpi/preprocessing/canonical_schema_version),
    Strukturrollen-Pass eingebunden
  - backend/app/documents/intelligence/{evidence,disparity,dates,token_safety,
    structure,table_normalize}.py (neu)
  - backend/tests/test_di_hardening.py (neu: 33 fokussierte Tests)
  - scripts/{truebeam_table_diagnosis,source_navigation_diagnostics,
    manifest_verification}.py (neu)
  - data/benchmark_v2/di_reports/{truebeam_table_diagnosis,
    source_navigation_diagnostics,manifest_verification}.json (generiert)
- Tests/Ergebnis: `pytest` (backend) → **178 bestanden** (145 + 33 neue
  Härtungs-Tests; 0 Fehler). Einmaliger `--refresh` der 3 Canonicals nach dem
  Strukturrollen-Einbau (kein breites Reprocessing); Timing danach
  Vision 47,2 s / GE 39,0 s / Truebeam 101,2 s, Diagnoseergebnisse gegenüber
  Baseline unverändert korrekt.
- **Gate-Entscheidung: GATE A** – OCR-Token-Sicherheit, Quell-Navigation
  (programmatisch 6/6), Konfliktbehandlung und finanzielle
  Label->Wert-Beziehungen sind deterministisch belegt und getestet;
  verdächtige Werte werden nie erraten, sondern als Review markiert.
  Verbleibender, NICHT-Code-blockierender Follow-up: visuelle Bestätigung der
  Hervorhebungs-Render durch einen Menschen. STEP 9 beginnt ausschliesslich
  nach expliziter Freigabe.
- **Korrektur nach Abschluss (Quell-Navigation – EXAKTE Wort-/Segment-Geometrie;
  korrektiv, KEIN neuer Hauptschritt, Fortschritt bleibt 8/18 = 44,4 %)**.
  Temporäres Gate: **GATE D – SOURCE MAPPING INSUFFICIENT**. Die bisherige
  Quell-Navigation hob ELEMENT-/Absatz-Boxen hervor (grossflächig, OPAK
  dunkelrot) und rechnete im kanonischen View-Raum ohne die Original-PDF-
  Rotation (Vision/GE: rotation=270, Landscape-MediaBox). Die alten Renders
  galten damit NICHT als „visuell bestätigt"; GATE A wird bis zur menschlichen
  Bestätigung der korrigierten Renders als vorläufig ausgesetzt geführt (Gate D).
  Korrektur (4 Ursachen):
  1) Koordinatensystem: `page_view_to_mediabox()` wandelt kanonische View-
     Koordinaten deterministisch in den Original-MediaBox-Raum (Rotation
     0/90/180/270, TopLeft, mit Kreislauf-Prüfung gegen `medibox_to_view`);
     Medienabstände/rotation kommen pro Seite aus dem Original-PDF
     (`Page.original_width_pt/original_height_pt/pdf_rotation`).
  2) Opake Farbe: fitz' `fill=(r,g,b,a)` wird NICHT als Alpha interpretiert →
     jetzt `fill_opacity≈0.22` + dünne Umrisslinie, keine destruktive Farbe;
     Original-PDFs bleiben byte-identisch (per SHA geprüft).
  3) Box-Granularität: neue `WordRegion`-Boxen an `Element.word_regions`
     (granularity word|segment|line|element) aus docling ProvenanceItem
     (charspan+bbox) im `docling_provider`; Element-Box NUR als explizit
     markierter letzter Ausweg (guard: coarse_element_box/oversized →
     „EXACT_GEOMETRY_UNAVAILABLE").
  4) Temporär nötiger `--refresh` (fachlich erforderlich für word_regions +
     Original-Seiten-Metrien; KEIN breites Reprocessing; Diagnose danach
     unverändert korrekt).
  Ergebnis: neues Modul `intelligence/highlight.py`, neuer Render-Modul `scripts/
  source_navigation_diagnostics.py` (EXAKT-Modus), `di_reports/highlights_exact/`,
  Manifest `source_navigation_exact.json`. **6/6** Ziele gefunden; **5/6**
  programmatisch exakte Box-Geometrie (Vision Datum S.1; GE Datum S.1 +
  3.429,- S.5; Truebeam 942.480,00 S.2 + „Kündigungsfrist" S.11). 1/6 ehrlich
  nur Element-Box: 13.115,00 (S.4) liegt AUSSCHLIESSLICH in Tabellenzellen;
  docling liefert für Zellwerte keine Wort-/Segment-Box → coarse_element_box,
  transparent gerendert und markiert. Render-Ort aller 6 per Umriss-Abgleich
  pixel-genau gleich der Umrechnung (overlap=YES). Neue fokussierte Tests
  `tests/test_source_navigation_exact.py` (20): Rotation-Roundtrips 0/90/180/
  270 inkl. Media-Box-Erhalt, Span→Segment-Auflösung, Phrase über 2 Segmente,
  Guard-Schutzregeln, transparentes Render auf synthetischem PDF (Original-SHA
  byte-identisch, halbtransparentes fill_opacity, kein opaker RGBA-Trick).
  Gesamt: **198 Tests bestanden** (178 + 20), 0 Fehler.
  **Gate bleibt D (temporär), bis ein MENSCH die Renders visuell am Original-
  PDF bestätigt hat** (VISUAL HUMAN VERIFICATION PENDING – das Modell kann
  keine Bilder sehen). Danach Übergang in „Gate A – bestätigt" OHNE
  automatische Freigabe. STEP 9 beginnt NICHT vor expliziter Freigabe.

Nächster Schritt:
- STEP 9 – Date & Cost Engine (Berechnungen). Beginnt NICHT automatisch; erst nach
  expliziter Freigabe und – wie in docs/STEP_8B_CHECKPOINT.md empfohlen – nach
  spezialisierter Feldgruppen-Extraktion + Evidence-Verifikation.
  Vorbedingung: menschliche Bestätigung der `highlights_exact/`-Renders
  (Aufhebung Gate D), danach Gate-A-Übergang ohne automatische Freigabe.

### Korrektur-Analyse (Diagnose; Gate D bleibt; NOCH KEIN Fix)

Menschliche VISUELLE Prüfung der 6 Renders = **1/6 PASS** (nur GE Datum S.1).
Damit ist Gate D bestätigt und die Ursachen-Klärung abgeschlossen:

- Transparenz/Lesbarkeit: PASS (kein opaker Überzug mehr).
- Exakte Geometrie: 5 Ziele visuell falsch positioniert (Vision Datum S.1,
  Vision 13.115,00 S.4, GE 3.429,- S.5, Truebeam 942.480,00 S.2,
  Kündigungsfrist S.11).

Diagnose-Ergebnis (nur Cache + Original-PDF-Inspektion, kein Docling-Refresh,
kein Qwen, keine Benchmark; Artefakt `di_reports/source_navigation_diagnosis.json`,
Tool `scripts/source_navigation_diagnose.py`):

1) Text↔BBox-Zuordnung ist NICHT auf unserer (kanonischen) Ebene gebrochen:
   IN ALLEN 5 Fällen erfüllt der dem BBox zugeordnete Segment-/Element-Text die
   Invarianz „Text enthält Ziel" (INVARIANT_CANONICAL=True). Ein reiner
   Text-Containment-Check kann diesen Fehler NICHT erkennen.
2) Die Zuordnung ist im PROVIDER (Docling/RapidOCR) falsch/instabil:
   - Dokumente sind REINE SCANS (keine native Text-Schicht; get_text/search_for
     liefern nichts) → einzige Geometriequelle ist Docling.
   - Auf den betroffenen Seiten ist die BBox-y-Folge NICHT monoton zur
     Element-/Text-Reihenfolge; Richtungs-Wechsel (direction_flips) 2–12.
     Pass-Seite GE S.1: 0 Flips (global umgekehrte, aber atomare Paarung →
     Highlights weiterhin korrekt). Genau die Flipp-Seiten schlagen fehl.
   - Multi-Zeilen-Absätze werden von Docling zu EINEM TextItem/ProvenanceItem
     mit EINER BBox kollabiert (z. B. Truebeam S.11 10.1-Paragraf, 677 Zeichen,
     eine BBox, die real die Sektoren 10.4–10.6 trägt).
   - Betragsnähen in Tabellen/Formularen erhalten oft die REIHEN-BBox (Label
     und Wert teilen den Y-Band, z. B. Truebeam S.2 label/value je y=381–390),
     keine Wort-Box.
   - Tabellenzellen (Vision 13.115,00, S.4): Zellen-BBoxen von Docling liegen in
     einem inkonsistenten Koordinatenraum (Y-Spiegelung relativ zur Element-
     Region; keine Überschneidung) → nur Gesamt-Tabellen-Box verfügbar, die
     real den „Servicepaket"-Beschreibungsbereich überdeckt.
   - Vision S.1: unmittelbar aufeinanderfolgende Texte „Anlagen" (y151–165) und
     „13.06.2017" (y546–563) liegen visuell ~400 pt auseinander → Paarung der
     kurzen Zeilen beim Provider vertauscht; BBox des Datums liegt auf leerer
     Fläche (Tinte 0.0).
3) Schlussfolgerung: Der verbleibende Defekt ist die Text-Span→Geometrie-
   Assoziation DES PROVIDERS, nicht unsere Umrechnung/Span-Mathematik. Eine
   Korrektur muss die (text,bbox)-Paare atomar (pro OCR-Zeile, nicht pro
   Absatz) aus Docling nehmen (oder pro Wort) und zusätzlich deterministisch
   verifizieren (BBox-y-Monotonie zur Text-Reihenfolge; Tinte an der BBox;
   für Zellen: Koordinatenraum-Abgleich mit der Tabellen-Region). KEIN breites
   Reprocessing, KEIN Koordinaten-System-Rewrite (bereits ausgeschlossen).
   Fix erfolgt NACH Freigabe dieser Diagnose als nächster Arbeitsschritt.
   Gate D bleibt bis zur visuellen Bestätigung durch einen Menschen.

### Korrektur umgesetzt – Atomische OCR-Geometrie (Gate D; Bestätigung weiterhin ausstehend)

Die Diagnose wurde akzeptiert und die Fix-Architektur umgesetzt: atomare
OCR-Geometrie (RapidOCR) als Geometrie-EIGENTÜMER statt Paragraph-Level-Provenienz.

**Ergebnis (6/6 Ziele navigieren programmatisch EXAKT zur richtigen Seite):**

| Vertrag | Ziel | Präzision | Seite | Quelle-OCR-Einheit | Conf. |
|---------|------|-----------|-------|--------------------|-------|
| Vision RFD 3D | 13.06.2017 | EXACT_WORD | 1 | p1_l11_w0 | 1.000 |
| Vision RFD 3D | 13.115,00 | EXACT_WORD | 4 | p4_l41_w0 (valid. Zelle) | 1.000 |
| GE MACLAB     | 16. April 2025 | EXACT_LINE | 1 | p1_l28 | 0.989 |
| GE MACLAB     | 3.429,- | EXACT_WORD | 5 | p5_l33_w1 | 0.631 |
| Truebeam STX  | 942.480,00 | EXACT_WORD | 2 | p2_l38_w1 | 0.986 |
| Truebeam STX  | Kündigungsfrist | EXACT_WORD | 11 | p11_l40_w5 | 1.000 |

Pixel-Umriss-Abgleich an den gerenderten Views: alle 6 Boxen liegen auf Tinte
(ink_frac 0.15–0.29, auch rotierte Seiten rot=270 korrekt zurückgedreht) →
Defekt ist geschlossen; Highlights sind atomar belegt.

**Implementiert (Dateien):**
- `canonical.py` → Schema 1.2.0: `GeometryPrecision`-Enum (word/line/table_cell/
  coarse_element/estimated); `AtomicUnit` (unit_id, kind, text, bbox over page,
  precision, confidence, provider, parent_line_id, canonical_offset/length,
  aligned); `Page.atomic_units`; Provenienz-Felder `geometry_provider`/-version;
  Rückwärtskompatibilität erhalten (Defaults).
- `atomic_ocr.py` (neu): RapidOCR-Erfassung pro Seite (Zeilen via `to_json()`,
  Wörter via `return_word_box`/`word_results`), Skala fest aus View-Pixel vs.
  kanonischer Seitenabmessung; deterministische Alignment (globaler
  SequenceMatcher über Token-Folge + lokaler Anker-Fallback für isolierte/
  rotierte Zeilen, Präfix-tolerante OCR-Abschneidung); Wort-Offsets via
  casefold-`find` im alignierten Zeilen-Slice (nie erfunden).
- `table_cells.py` (neu): deterministische Y-Spiegel-Reconciliation der
  Docling-Zell-BBoxes (Identität vs. Y-Spiegel, entschieden über OCR-Wort-
  Mittelpunkt-Belegung); nur validierte `docling_cell`-Einheiten mit
  `VALIDATED_TABLE_CELL`; nie Gesamt-Tabellen-Box als exakt.
- `highlight.py`: neuer atomarer Auflöser `resolve_target_atomic` →
  EXACT_WORD / VALIDATED_TABLE_CELL / EXACT_LINE / COARSE_FALLBACK /
  TARGET_NOT_FOUND, Containment-Invariante (normalisierter Zieltext ∈
  Einheitstext); `render_transparent_boxes` (Box-basiert).
- `scripts/atomic_geometry_augment.py` (neu): fokussierter Refresh (NUR die
  3 Diagnose-PDFs, ~85 s, 11.551 atomare Einheiten; Text/Layout des Caches
  unverändert). KEIN Docling-Refresh, KEIN Qwen, KEIN Benchmark.
- `scripts/source_navigation_diagnostics.py` → atomarer Modus, Report
  `source_navigation_atomic.json` (je Ziel: page, target, source OCR unit,
  precision, boxes View+MediaBox, confidence, alignment method,
  Anomalie-Signale, render), Renders in `di_reports/highlights_atomic/`.

**Tests:** `tests/test_atomic_geometry.py` (21, davon 4 neue: Modell-Roundtrip,
Zeilen-/Wort-Alignment, lokaler Anker-Fallback inkl. rotierter Euro-Zeile,
Präfix-Toleranz, Auflöser-Klassifikationen, Tabellenzell-Y-Spiegel/-Identität).
Vollsuite: **219 passed, 0 Fehler**.

**Gate bleibt D (temporär):** Die programmatische Geometrie ist verifiziert,
die Renders müssen aber weiterhin von einem MENSCHEN am Original-PDF bestätigt
werden (`VISUAL HUMAN VERIFICATION PENDING`). Kein automatischer Gate-A-Übergang.


Status: OFFEN

Wichtig:
Die KI extrahiert Fakten.
Der Code berechnet:
- spätesten Kündigungstermin
- Tage bis Frist
- Tage bis Vertragsende
- Jahreskosten aus Monatskosten
- Monatskosten aus Jahreskosten
- aggregierte Gesamtkosten
- Warnstufen

## Schritt 9 – Date & Cost Engine
Status: ABGESCHLOSSEN
Datum: 30.08.2026

Ziel (aus STEP-9-Vorgabe):
- Deterministische, erklärbare Date & Cost Engine, **getrennt** vom
  extrahierten/source-of-truth `Contract`-Modell.
- Pure Funktionen `(contract, as_of_date) -> ContractCalculationResult`.
- Kein Qwen, kein neuer OCR/Docling-Lauf, keine STEP-8B-Benchmark-Änderung,
  keine externen Werte – bei fehlenden/kollidierenden Eingaben:
  `NOT_CALCULABLE` / `REVIEW_REQUIRED` / `CONFLICT`, niemals fabriziert.

Implementiertes (neues Paket `backend/app/contracts/calculation/`):
- `models.py`: Berechnete Resultat-Modelle, strikt getrennt vom Extrakt.
  - `CalculationStatus` (str-Enum): CALCULATED / EXPLICIT / NOT_CALCULABLE /
    REVIEW_REQUIRED / CONFLICT.
  - `DateTimeResult`, `DifferenceResult`, `MoneyFieldResult`: jedes Feld =
    Wert + Status + Erklärung + Eingabe-Provenienz (`inputs`) + `review_required`.
  - `CalcDuration`, `RenewalBoundary`, `DateCalculationKind`, `TaxBasis`
    (UNKNOWN/NET/GROSS), `CalculatedDateField`, `ContractStatusDerivation`,
    `RecurringCostNormalized`, `CostCategory`, `CalculateContractCosts`,
    `ContractCalculationResult` (calculation_version="step9-1.0").
- `calendar_.py`: Kalenderbewusste Arithmetik. Monate mit dokumentierter
  End-of-Monat-Regel (31.01.+1 Monat → 28.02., Schaltjahr → 29.02.; Tag wird
  auf letztes gültiges Datum geklemmt). Kein „Monat=30 Tage", kein „Jahr=365 Tage".
- `dates.py`: Date Engine. `calculate_contract_end_date` (A explizit / B
  start+duration kalenderbewusst / C ereignisbasiert→NOT_CALCULABLE / D
  Konflikt explizit-vs-abgeleitet→CONFLICT), `calculate_latest_cancellation_date`
  (nur bei klarer Relation „zum Vertragsende"; freie Formulierung/Quartal →
  REVIEW_REQUIRED, nie still gerechnet), `calculate_renewal_boundaries`
  (automatische Verlängerung nur mit `automatic_renewal=True` + `renewal_period`
  + bekannter Grenze), `compute_days_until` (negative Tage = vergangen, NICHT
  auf 0 geklemmt), `derive_contract_status` (ACTIVE/EXPIRED/UNKNOWN;
  TERMINATED nur bei expliziter Markierung).
- `money.py`: Decimal-Grenze. Geld nur als `Decimal`; `float` wird an der
  Berechnungsgrenze **stringbasiert** konvertiert (0.1+0.2==0.3). Bestehender
  `Money.amount` (float) bleibt unverändert (Rückwärtskompatibilität).
  `scaling_factor` nur für explizit wiederkehrende Perioden
  (monthly×12, quarterly×4, semi_annual×2, annual×1); ONCE/HOURLY/UNKNOWN
  werden NICHT annualisiert.
- `costs.py`: Cost Engine. `normalized_recurring` aus EINER wiederkehrenden
  Quelle; bei zugleich vorhandenem annual+monthly wird übereinstimmend
  (exakt/toleriert ≤0,5 %) korroboriert, sonst CONFLICT. `total_contract_value`
  wird NICHT automatisch addiert. Kategorien (Stundensatz/Reise/Material/
  Ersatzteile/cond. Zusatzkosten) nie blind addiert. Mehrere Währungen →
  `currency_conflict`, kein FX. `tax_basis` bleibt UNKNOWN (keine 19 %-Annahme).
- `engine.py`: `calculate_contract(contract, as_of_date)` orchestriert die
  Date/Cost Engine und aggregiert `overall_review_required` + `review_reasons`.

Geänderte Dateien:
- neu: `backend/app/contracts/calculation/__init__.py`
- neu: `backend/app/contracts/calculation/models.py`
- neu: `backend/app/contracts/calculation/calendar_.py`
- neu: `backend/app/contracts/calculation/money.py`
- neu: `backend/app/contracts/calculation/dates.py`
- neu: `backend/app/contracts/calculation/costs.py`
- neu: `backend/app/contracts/calculation/engine.py`
- neu: `backend/tests/test_calculation_engine.py`
- unverändert: `app/models/*` (source of truth), Document-Intelligence-/Quell-Navigation.

Tests/Ergebnis:
- Neu: 72 fokussierte Tests in `tests/test_calculation_engine.py`
  (Kalender- und Datumslogik, Kündigungs-Relation streng ohne Default-Annahme,
  as_of-abhängige wiederholte Verlängerungen mit expliziter Boundary-Konvention,
  Konflikt-Propagation, TERMINATED-Verhalten, Sicherheits-Invarianten;
  Geld: monthly→annual, quarterly→annual, semiannual→annual, annual, einmalig
  ausgeschlossen, 0.1+0.2==0.3, annual+monthly korroborierend/konflikt,
  unbekannte Periode/fehlender Betrag/Währungsmismatch, Stundensatz/Reise/
  Material nicht blind-addiert, Steuerbasis unbekannt, zero vs None,
  scaling_factor, Währungsrundung, kein verstecktes Datum).
- **STEP-9-Korrektheits-Härtung** nach finaler Review: strenge Kündigungs-
  Relation (keine Default-Annahme), wiederholte automatische Verlängerungen
  relativ zu `as_of_date` (bounded-arithmetisch), Konflikt-Propagation in
  abhängige Datumsberechnungen. Details: `docs/STEP_9_CHECKPOINT.md` §9–§12.
- Volle Backend-Suite: **291 passed** (219 Bestand + 72 STEP-9, keine
  Regressionen).

Bekannte Probleme / bewusst NICHT unterstützt (STEP-9-Grenzen):
- `EXPIRING_SOON` (Warnstufe) folgt in Schritt 11.
- Keine Mehrwertsteuer-/Netto-/Brutto-Ableitung (nur future-safe `tax_basis`).
- Kein FX/Mehrwährung-Rechnen; Kündigungsfrist nur bei klarer Relation
  „zum Vertragsende".
- Keine Persistenz/API-Anbindung (folgt Schritt 10).

Nächster Schritt:
- Schritt 10 – Datenbank (SQLite-Persistenz der Extraktions- und der
  STEP-9-Berechnungsergebnisse). **STOP – kein STEP 10-Start in dieser Sitzung.**

## Schritt 10 – Datenbank
Status: OFFEN

MVP:
- SQLite

Tabellen:
- contracts
- contract_files
- contract_analysis
- contract_sources
- alerts
- settings

## Schritt 11 – Warnsystem
Status: OFFEN

Warnstufen:
- 180 Tage
- 90 Tage
- 60 Tage
- 30 Tage
- 14 Tage
- 7 Tage
- abgelaufen

Besondere Warnungen:
- Kündigungsfrist
- automatische Verlängerung
- unklare Vertragsdaten
- fehlende Kostenangabe

## Schritt 12 – Dashboard
Status: OFFEN

Kern-KPIs:
- aktive Verträge
- bald auslaufende Verträge
- kritische Kündigungsfristen
- jährliche Gesamtkosten
- Gesamtvertragswert

Bereiche:
- Handlungsbedarf
- Kosten nach Dienstleister
- Verträge nach Status

## Schritt 13 – Vertragsliste & Suche
Status: OFFEN

- Volltextsuche
- Dienstleister
- Vertragsnummer
- Gerät/System
- Status
- bald fällig
- kritisch

## Schritt 14 – Vertragsdetailansicht
Status: OFFEN

Bereiche:
- Übersicht
- Kosten
- Laufzeit
- Kündigung
- Leistungen
- Risiken
- Originaldokument
- Quellen

Spezialfunktion:
- "Quelle anzeigen" öffnet passende PDF-Seite

## Schritt 15 – Benutzeroberfläche & Design
Status: OFFEN

Ziel:
- moderne deutsche Krankenhaus-Optik
- klar
- wenig Navigation
- responsive
- Light/Dark Mode optional

Navigation MVP:
- Übersicht
- Verträge
- Import
- Einstellungen

## Schritt 16 – Benutzer/Login & Audit Minimalversion
Status: OFFEN

- lokaler Login
- Benutzername/Rolle
- Analyse erstellt von
- Vertrag geändert von
- Zeitpunkt protokollieren

## Schritt 17 – Export & Backup
Status: OFFEN

- CSV/Excel Export
- lokale Datenbanksicherung
- Dokument-Backup
- Restore-Konzept

## Schritt 18 – Release Candidate & Krankenhaus-Pilot
Status: OFFEN

- Security Review
- Datenschutz-Dokumentation
- Installationsanleitung
- Offline-Betrieb testen
- Performance testen
- Pilot-Demo mit echten Verträgen
- Liste offener Punkte für Krankenhaus-Deployment

---

# Aktueller Fortschritt

Gesamtschritte: 18

Abgeschlossen: 9
In Arbeit: 0
Offen: 9

Fortschritt: 9 / 18 = 50,0 %

Aktuell abgeschlossen:
- Schritt 1 – Projektdefinition & Architektur
- Schritt 2 – Repository & OpenCode-Grundstruktur
- Schritt 3 – Vertrags-Datenmodell definieren
- Schritt 4 – Dokument-Import (PDF/DOCX)
- Schritt 5 – Text-Extraktion (PDF/DOCX)
- Schritt 6 – Local-AI-Anbindung (Ollama)
- Schritt 7 – Strukturierte KI-Extraktion
- Schritt 8 – Benchmark mit echten Verträgen
- Schritt 9 – Date & Cost Engine

Nächster Schritt:
- Schritt 10 – Datenbank

---

# Wo haben wir angefangen?
Wir haben mit der Produktidee begonnen:
Lokale KI zur Analyse deutscher Wartungsverträge für Krankenhäuser.

Danach wurde der Umfang bewusst reduziert:
kein großes ERP, sondern ein fokussiertes lokales Contract-Intelligence-System.

# Wo stehen wir jetzt?
Die Produktidee und Architektur sind definiert.
Projekt-Setup (Schritt 2), Vertragsdatenmodell (Schritt 3), Dokument-Import
(Schritt 4), Text-Extraktion (Schritt 5), Local-AI-Anbindung (Schritt 6),
die strukturierte KI-Extraktion (Schritt 7) und der Benchmark mit echten
Verträgen (Schritt 8) sind abgeschlossen: sicherer PDF/DOCX-Import,
seitenbasierte Textextraktion, eine lokale Ollama-Anbindung mit
austauschbarer Provider-Abstraktion sowie eine strukturierte, lokale
Extraktion von Vertragsfakten (JSON-Schema, deutsche Prompts,
Quelle+Seite/Confidence, Anti-Halluzination, Multi-Chunk-Merging).
Backend: 96 Tests laufen; Frontend baut erfolgreich. Der Schritt-8-Benchmark
gegen 6 reale Verträge zeigt: 0 erfundene Werte (Anti-Halluzination hält),
aber nur ~12,5 % Feldgenauigkeit und 1/6 validierten Vertrag – qwen3:8b (Q4)
mit reinem Prompt-Ansatz erreicht die geforderte Zuverlässigkeit noch nicht
(Ansätze im STEP-9-Abschnitt von docs/AI_EVALUATION.md). Noch keine
DB-Persistenz (Schritt 10) und keine Berechnungen (Schritt 9).

# Wo haben wir aufgehört?
Direkt nach dem Benchmark mit echten Verträgen (Schritt 8). Das Ergebnis ist
in docs/AI_EVALUATION.md dokumentiert; die Extraktion über qwen3:8b-Q4-Prompt
liegt bei ~12,5 % Feldgenauigkeit (0 erfunden), nur 1/6 Vertrag validiert.
Seither ergänzt: STEP 9 – deterministische Date & Cost Engine (berechnet
Ende/Kündigungsfrist/Kosten EXAKT in Code, strikt getrennt vom KI-Extrakt).

# Was machen wir als Nächstes?
1. Schritt 10 – Datenbank (SQLite)
2. Schritt 11 – Warnsystem
3. Dashboard
4. Vertragsliste & Suche

---

# OpenCode-Arbeitsregel

Nach JEDEM abgeschlossenen Schritt muss OpenCode diese Datei aktualisieren:

1. Status des Schritts auf ABGESCHLOSSEN setzen
2. Datum eintragen
3. kurz dokumentieren, was implementiert wurde
4. geänderte Dateien auflisten
5. Tests/Ergebnis notieren
6. bekannte Probleme notieren
7. nächsten Schritt festlegen
8. Fortschritt (x/18 und Prozent) aktualisieren

Kein neuer Hauptschritt beginnt, bevor PROJECT_PROGRESS.md aktualisiert wurde.

---

# Repository-Struktur (Medflux)

```text
Medflux/
├─ frontend/
│  ├─ app/
│  ├─ components/
│  └─ lib/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ ai/
│  │  ├─ contracts/
│  │  ├─ documents/
│  │  ├─ alerts/
│  │  ├─ database/
│  │  └─ models/
│  └─ tests/
├─ data/
│  ├─ contracts/
│  ├─ database/
│  └─ backups/
├─ docs/
│  ├─ PROJECT_PROGRESS.md
│  ├─ ARCHITECTURE.md
│  ├─ CONTRACT_SCHEMA.md
│  └─ AI_EVALUATION.md
├─ scripts/
├─ .env.example
├─ README.md
├─ AGENTS.md
└─ docker-compose.yml
```

---

# Definition of Done für MVP

Das MVP ist fertig, wenn:

1. mehrere PDF/DOCX-Verträge importiert werden können
2. Qwen lokal analysiert
3. Kerninformationen zuverlässig extrahiert werden
4. Ergebnisse gespeichert werden
5. Kündigungsfristen programmatisch berechnet werden
6. Warnungen erscheinen
7. jährliche Kosten aggregiert werden
8. Dashboard funktioniert
9. Vertragsliste funktioniert
10. Vertragsdetail + Quellenanzeige funktioniert
11. keine externe KI-API notwendig ist
12. ein lokales Backup möglich ist

---

Letzte Aktualisierung: 30.08.2026
Projektphase: Schritt 9 abgeschlossen (9/18 = 50,0 %). Die deterministische
Date & Cost Engine (STEP 9) berechnet Ende/Kündigungsfrist/Kostenwiederkehr
rechnexakt in Code (kalenderbewusst, Decimal, erklärbar, getrennt vom KI-Extrakt):
291 Backend-Tests (219 + 72 STEP-9) grün, einschließlich der STEP-9-Härtung
(Kündigungs-Relation streng, wiederholte Verlängerungen as_of-abhängig,
Konflikt-Propagation). STEP 8B/DI-interne Härtung (Quell-
Navigation exakt) bleibt verifiziert; Document-Intelligence-/Quell-Navigation-
Codebasis unverändert.
Nächster Hauptschritt: STEP 10 – Datenbank (SQLite-Persistenz), erst nach
expliziter Anweisung.
