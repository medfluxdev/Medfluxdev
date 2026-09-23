# Medflux — KI-Evaluierung der strukturierten Extraktion (Schritt 8)

Dieses Dokument fasst den **Schritt-8-Benchmark** der strukturierten
KI-Extraktion zusammen: die Medflux-Extraktions-Pipeline (Schritt 5 Text +
Schritt 7 strukturierte Extraktion über lokales Ollama, qwen3:8b Q4) wurde
gegen **echte, repräsentative deutsche Wartungs-/Serviceverträge** getestet
und mit manuell geprüften Ground-Truth-Erwartungen verglichen.

Ziel ist eine ehrliche Einschätzung der Modelltauglichkeit für das MVP
("Kerninformationen zuverlässig extrahieren") als Grundlage für Schritt 9.

---

## 1. Zweck und Umfang

- **Was**: 6 reale Verträge aus 33 vorliegenden, realen DOCX-Verträgen
  (ZIP `العقود.zip`), vollständig lokal verarbeitet (keine externe API).
- **Ground Truth**: manuell aus den Originalverträgen verifizierte
  Erwartungen (`data/benchmark/ground_truth.json`, 6 Verträge, 64 Felder).
- **Pipeline**: `TextExtractionResult` → `chunk_units` → `ContractAnalysisOrchestrator`
  → qwen3:8b (Ollama) → `_parse_json` → `Contract.model_validate` → Merge.
- **Messung**: Feldgenauigkeit (passed/total), Fehlerklassen (fehlend /
  falscher Wert / erfunden), Validierungsstatus.
- **Reproduzierbarkeit**: `scripts/benchmark_extraction.py`
  (Option `--runs N` = Durchläufe je Vertrag, gemeldet wird der beste Durchlauf;
  gegen Nichtdeterminismen des Modells).

## 2. Skript & Daten

| Datei | Inhalt |
|-------|--------|
| `scripts/benchmark_extraction.py` | Benchmark-Runner (neu in Schritt 8) |
| `data/benchmark/ground_truth.json` | manuell geprüfte Erwartungen (6 Verträge) |
| `data/benchmark/input/العقود/*.docx` | reale Quellverträge (nicht eingecheckt) |
| `data/benchmark/report_latest.json` | letztes Benchmark-Ergebnis |
| `docs/AI_EVALUATION.md` | dieses Dokument |

Ergebnisse enthalten nur sichere Metadaten (kein vollständiger Vertragstext,
keine Übertragung nach außen).

## 3. Getestete Verträge

| Kürzel | Vertrag | Umfang |
|--------|---------|--------|
| Vision_RFD_3D | Ziehm Imaging, mobiler C-Bogen, Premium-Servicepaket | 61 Einheiten / 2 Chunks |
| Siemens_MRT_Vida_3T | Siemens Healthineers, MAGNETOM Vida 3T | 46 Einheiten / 1 Chunk |
| Abiomed_FullService | Abiomed, Full-Service (Impella) | 247 Einheiten / 4 Chunks |
| Apoplex_SRAclinic | apoplex medical technologies, SRAclinic (EKG) | 139 Einheiten / 3 Chunks |
| GE_MACLAB | GE Healthcare, MACLAB | 134 Einheiten / 3 Chunks |
| Truebeam_STX | Varian, TrueBeam STX | 354 Einheiten / 11 Chunks |

## 4. Methodik / Ground-Truth-Ansatz

- Jede Ground-Truth-Erwartung wurde **manuell aus dem Originalvertrag**
  verifiziert und in `ground_truth.json` gespeichert.
- Vergleich über typisierte Matcher (`_match`): `contains`, `enum_in`,
  `bool`, `null`, `not_null`, `money_amount(+tol)`, `duration`,
  `time_value`, `device_contains`, `serial_contains`, `int_ge`.
- Fehlerklassifikation:
  - **fehlend** (missing): Erwarteter Wert nicht extrahiert (null/leer).
  - **falscher Wert** (wrong_value): Extrahiert, aber abweichend (z. B.
    falsche Enum-Form, falscher Betrag).
  - **erfunden** (invented): Modell behauptet einen Wert, der laut Ground
    Truth null sein müsste (Halluzination).

## 5. Ergebnis (Baseline, vor Änderungen)

6 Verträge / **64 Felder**, je 1 Durchlauf:

```
Feldgenauigkeit:  16/64 = 25,0 %
fehlend:          39
falscher Wert:     9
erfunden:          0
validiert (VALID): 1 von 6 (nur Siemens)
requires_review:   5 von 6
Ø Dauer/Vertrag:   139,8 s
```

| Vertrag | bestanden | validation |
|---------|-----------|------------|
| Vision_RFD_3D | 1/16 | invalid |
| Siemens_MRT_Vida_3T | 4/8 | valid |
| Abiomed_FullService | 6/11 | invalid |
| Apoplex_SRAclinic | 3/8 | invalid |
| GE_MACLAB | 0/9 | invalid |
| Truebeam_STX | 2/12 | invalid |

### Diagnose der Fehlermuster (Baseline, per Chunk untersucht)

Aus `diag_all` (pro Chunk: parse ok / schema ok / Validierungsfehler) wurden
drei dominante Ursachen sichtbar:

1. **Abgeschnittenes JSON (Truncation)**: Bei komplexen Chunks erzeugte das
   Modell gültige, aber über 2048 Token lange JSON-Antworten; die Ausgabe
   wurde mitten im Objekt abgeschnitten (`done_reason=length`) →
   `_parse_json` scheiterte → ganzer Chunk verloren (Siemens, Apoplex,
   Truebeam, Abiomed). Ein Chunk brauchte z. B. >7000 Zeichen (~2000+ Token).
2. **Erfundene Schemastruktur**: Das Modell erfand eigene Abschnittsnamen
   und Typen statt des vorgegebenen Schemas (Vision `parties`/`terms`,
   GE `fees`/`services`/Dict-`equipment`, Truebeam `prices`/`sla`/`warranty`,
   `services`-als-Liste, `customer`-als-Dict, `contract_type="Wartungsvertrag"`
   / `"Service"`). → `Contract.model_validate` verwarf den gesamten Chunk.
3. **Nichtdeterminismus**: Das Modell reagierte trotz `temperature=0.1` von
   Lauf zu Lauf unterschiedlich (gleiche Konfiguration ergab 25 % → 14 %).

## 6. Durchgeführte, begründete Änderungen (aus dem Benchmark abgeleitet)

Die folgenden Anpassungen beheben exakt die oben diagnostizierten Ursachen
(keine Recherche-/RAG- oder Lieferanten-Logik; kein neues Framework):

1. **`backend/app/core/config.py`**: `ai_extraction_max_tokens` von 2048 auf
   **8192** erhöht → behebt Truncation (Punkt 1). Kommentar dokumentiert das
   Benchmark-Ergebnis. Konfigurierbar über `AI_EXTRACTION_MAX_TOKENS`.
2. **`backend/app/ai/prompts/contract_extraction_v1.py`**: Abschnitt
   **"SCHEMA-TREUE (PRIORITÄT 1)"** ergänzt – exakte Feldnamen/Struktur,
   `equipment`=Liste, `services`=Objekt, Zeichenfelder = Strings,
   `contract_type`-Kleinbuchstaben-Enum, keine erfundenen Abschnitte,
   vollständiges (nicht abgeschnittenes) JSON → mindert Punkt 2.
3. **`backend/app/ai/contract_extractor.py`**:
   - `_extract_chunk`: Retry greift jetzt **auch bei schemawidriger, aber
     JSON-konformer Ausgabe** (bisher nur bei ungültigem JSON). Schemawidrige
     Chunks werden nicht mehr sofort verworfen, sondern mit
     Schema-Hinweis erneut abgefragt (`_RETRY_SYSTEM_PROMPT_SUFFIX`
     erweitert). Kontrolliert auf `max_retries` begrenzt → mindert Punkt 2.
   - Verhalten bleibt deterministisch kontrolliert, keine endlosen Schleifen.

**Tests**: `backend/tests/test_contract_extraction.py` blieben unverändert;
komplette Backend-Suite läuft **96 passed** (`pytest`).

## 7. Ergebnis (nach Änderungen, robust)

Messung mit **best-of-3** (`--runs 3`): 6 Verträge / **64 Felder**.

```
Feldgenauigkeit:   8/64 = 12,5 %  (best-of-3, stabil)
fehlend:           39
falscher Wert:     17
erfunden:           0
validiert (VALID):  1 von 6 (nur Siemens)
requires_review:    5 von 6
Ø Dauer/Vertrag:  130,5 s
```

| Vertrag | best-of-3 | Einzeldurchläufe (passed) | validation |
|---------|-----------|---------------------------|------------|
| Vision_RFD_3D | 4/16 | 4 · 4 · 4 | invalid |
| Siemens_MRT_Vida_3T | 1/8 | 1 · 1 · 1 | valid |
| Abiomed_FullService | 0/11 | 0 · 0 · 0 | invalid |
| Apoplex_SRAclinic | 1/8 | 1 · 1 · 1 | invalid |
| GE_MACLAB | 0/9 | 0 · 0 · 0 | invalid |
| Truebeam_STX | 2/12 | 2 · 2 · 2 | invalid |

Deutung: Nach den Änderungen ist die Ausgabe **stabil** (per Vertrag
identische Durchläufe), aber die **Trefferquote bleibt niedrig**. Die
scheinbar bessere Baseline (25 %) war zu einem Teil dem damaligen
Truncation-Nichtdeterminismus geschuldet. Die ehrliche, robuste Aussage ist:
**~12,5 % Feldgenauigkeit, nur 1/6 Verträgen valide.**

### Feld-Ebene (best-of-3, kumuliert über Verträge)

Konstante Schwächen, die **über alle Verträge hinweg** bestehen:

| Feld | passed | Art |
|------|--------|-----|
| `contract_type` (Enum) | 0/6 | falscher Wert (Großbuchstaben/"Wartungsvertrag") |
| `billing_interval` (Enum) | 0/4 | falscher Wert |
| `termination.automatic_renewal` | 0/5 | fehlend |
| `termination.renewal_period` | 0/3 | fehlend |
| `termination.cancellation_period` | 0/3 | fehlend |
| `costs.annual_cost.amount` | 0/3 | fehlend |
| `dates.end_date` / `duration` / `minimum_duration` | 0/2 · 0/2 · 0/2 | fehlend |
| `identity.customer` | 0/3 | fehlend |
| `identity.supplier` | 2/6 | teils |
| `identity.contract_number` | 1/5 | teils |
| `equipment` (Gerät) | 2/6 | teils |

**Erfundene Werte: 0** – die Anti-Halluzinations-Regeln des Prompts werden
eingehalten. Das Modell erfindet **keine** Daten; es scheitert primär an
Extraktion und Enum-/Schema-Treue.

## 8. Bewertung / Schlussfolgerung

- **Anti-Halluzination: gut.** Kein einziger erfundener Wert in allen Läufen.
  Die Verpflichtung "keine erfundenen Werte" (AGENTS.md) wird eingehalten.
- **Extraktionstreue: unzureichend fürs MVP.** Nur 1/6 Verträge liefert ein
  valides `Contract`-Modell; komplexe Verträge (GE, Abiomed, Truebeam)
  scheitern vollständig. Enum-Felder, Kündigung/Verlängerung, Dauer und
  Geldbeträge werden zuverlässig falsch oder gar nicht erfasst.
- **Stabilität:** Nach den Anpassungen deterministischer, aber auf niedrigem
  Niveau; Truncation kam mit 8192 Token praktisch nicht mehr vor.
- **Performance:** Ø ~2 min/Vertrag, bei komplexen Verträgen bis ~3–4 min
  (Truebeam 11 Chunks). Für interaktive Einzel-Analyse lokal akzeptabel.

### Fazit für das MVP

qwen3:8b (Q4) kann die für das MVP geforderte "zuverlässige Extraktion der
Kerninformationen" **mit dem aktuellen reinen Prompt-Ansatz nicht erfüllen**.
Der Engpass liegt im Modell/Schema, nicht in der Pipeline (Chunking, Parsing,
Validierung, Merge, Anti-Halluzination funktionieren). Reine Prompt/Budget-
Anpassungen heben die Quote nachweislich nicht ausreichend.

## 9. Empfehlungen für Schritt 9 (bewusst NICHT hier umgesetzt)

Die folgenden Ansätze sind **mögliche** nächste Schritte; sie erfordern eine
Abwägung und wurden auf Basis dieses Benchmarks als nächster Schritt
dokumentiert, aber noch nicht implementiert (kein neues Framework, keine
Recherche-Logik):

1. **Strukturierte Ausgabe des Modells erzwingen** – z. B. Ollama-Modus für
   JSON-Schema (system prompt auf JSON-Format) bzw. `format`-Option, damit
   das Modell gar kein vom Schema abweichendes JSON erzeugen kann. Das
   beseitigt die wichtigste Fehlerklasse (erfundene Struktur + Enum-Fehler).
2. **Alternative/kombinierte Modelle** – z. B. ein größeres lokales Modell
   oder ein Modell mit verbesserter Instruktions-/Schema-Treue (falls lokal
   lauffähig), ggf. mit Option der KI-Schicht-Austauschbarkeit (Architektur
   ist bereits vorbereitet).
3. **Fokussierte Nachfragen (Follow-up) je Unterblock** – statt des
   Gesamt-JSONs einzelne Abschnitte (identity, termination, costs, sla)
   gezielt extrahieren und mergen; verringert Truncation- und
   Schema-Spreizung bei komplexen Verträgen.
4. **Fallback auf deterministische Extraktion** für hartnäckige Felder
   (Regex/Heuristiken für Beträge, Datumsangaben, Enum-Werte im deutschen
   Text) – als Ergänzung, nicht als reine KI-Verarbeitung.

Alle Punkte halten die "lokal, keine externe AI-API"-Vorgabe ein.

## 10. Wie zu reproduzieren

```bash
# Backend-venv
cd backend
.\\.venv\\Scripts\\python.exe ..\\scripts\\benchmark_extraction.py --runs 3
# prüfen: data/benchmark/report_latest.json
```

Voraussetzung: Ollama läuft, `qwen3:8b` ist installiert, Verträge liegen in
`data/benchmark/input/العقود/`.

---

# STEP 8B – Native Structured Output (Reliability Hardening)

Interne, nicht gezählte Härtungsphase nach STEP 8 (Fortschritt bleibt 8/18).
Ausführlicher Checkpunkt: `docs/STEP_8B_CHECKPOINT.md`.

## Grund der Änderung
STEP 8 zeigte, dass qwen3:8b die Medflux-Contract-Struktur nicht zuverlässig
einhält (erfand `parties`/`terms`/`fees`, Großbuchstaben-Enums) und so Chunks
verwarf (Validierung 1/6, 12,5 %). Behebung: Schema nicht mehr per Prompt, sondern
**nativ durch Ollama** erzwingen.

## Implementierung
- `app/ai/schema.py`: selbstenthaltenes JSON-Schema aus `Contract.model_json_schema()`
  (kein zweites manuelles Schema; `$ref`/`$defs` inline aufgelöst).
- `AIProvider.generate_structured(..., schema)` / `OllamaProvider` (sendet `format`)
  / `AIService.generate_structured`.
- `contract_extractor._extract_chunk` nutzt strukturierte Ausgabe; Diagnose-Zähler
  (timeouts/retries/truncated) am `ContractAnalysisResult`.
- `Contract.model_config = {"extra": "forbid"}` (erfundene Schlüssel → Retry).
- Prompt auf Semantik reduziert (kein Text-Schema mehr; Kompaktheit/Evidence).
- `config.py`: `ai_repeat_penalty=1.3` (behebt Wiederholungsschleifen),
  `ai_request_timeout_seconds=300` (120s war zu knapp), Max-Tokens bleibt 8192.

## Before / After Benchmark (6 echte Verträge × 3 Läufe, gleiche Ground Truth)
| Metrik | STEP 8 (vorher) | STEP 8B (nachher) |
|--------|-----------------|-------------------|
| Feldgenauigkeit (best-of-3) | 12,5 % | **48,4 %** (31/64) |
| Validierte Verträge (best-of-3) | 1/6 | **6/6** |
| validierte Einzelläufe | – | **17/18** |
| erfundene Werte | 0 | **0** |
| Timeouts | – | **0** |
| Truncated Chunks | – | **0** |
| Ø Dauer/Vertrag | ~130 s | **~32 s** |
| contract_type (Enum) | falsch | korrekt (service/maintenance; Abgleichs-Artefakt) |
| customer / supplier / equipment | 0 / 2 / 2 | **3 / 5 / 5** (von 6) |

## Verbleibende semantische Fehler (RELIABILITY NOCH NICHT erreicht)
- Seltene/freie Felder (contract_number, department, payment_deadline_days,
  total/monthly cost) häufig fehlend.
- Ereignisbasierte Daten (end_date, duration) und komplexe Beträge (annual/monthly)
  noch unzuverlässig.
- Wiederholungskonsistenz mittel (4/6 Verträge deterministisch über 3 Läufe).

## Empfehlung für den nächsten Arbeitsschritt (NICHT ausgeführt)
Spezialisierte Feldgruppen-Extraktion (pro Chunk gezielt Unterblöcke identity/
termination/costs/payment/sla extrahieren + deterministisch mergen) und
Evidence-Verifikation (Belege gegen Originaldokument prüfen) – danach erneuter
Benchmark vor STEP 9.

## STEP 8B-Semantik – Feldgruppen-Extraktion (Benchmark-Ergebnis)

Die empfohlene Arbeit wurde danach als weitere interne Härtungsphase ausgeführt
(Fortschritt bleibt 8/18 = 44,4 %; Details: `docs/STEP_8B_CHECKPOINT.md` §8).

- **Matcher-Fix vervollständigt:** `scripts/benchmark_extraction.py` `_norm_str`
  nutzt `getattr(v, "value", v)` statt des `isinstance(str)`-Guards (str-Enums
  schlugen durch den Guard fehl → alle Enum-Felder wurden als „wrong“ bewertet).
- **Korrigierte STEP-8B-Baseline:** 38/64 = **59,4 %** (31 historisch + 7
  Enum-Korrekturen). Die früher genannte 39/64 enthielt 1 Doppelzähl-Artefakt
  (Vision `equipment`) und ist verworfen.
- **Neue Pipeline:** `GroupPipeline` (Feldgruppen je Chunk, deterministischer
  Merge, Evidence-First-Verifikation, semantischer Verifier); gemessen mit
  `scripts/benchmark_groups.py` → neuer Report `data/benchmark/report_groups.json`.
- **Ergebnis (6 Verträge, 1 Lauf je Vertrag, korrigierter Matcher):**
  **43/64 = 67,2 %** (Vision 12, Siemens 6, Abiomed 8, Apoplex 5, GE 5,
  Truebeam 7); 0 erfunden, 0 Timeouts, 0 Retries, 0 Truncation, Ø ~62 s.
- **Ehrlicher Zusatzbefund:** Validierung fällt auf 0/6 `invalid` + review –
  Ursache ist die konservative Verifier-/Review-Logik (unsupported sensible
  Felder → Section-Review), nicht fehlende Extraktion. Sicherheits-Seite gut,
  Automatisierungs-Seite (selbstständig VALID) noch nicht MVP-reif.
- Kein einziger Wert des Rundlaufs ist frei erfunden (GE 24h und Truebeam
  942480 stehen wortwörtlich im Dokument; Abweichungen sind Mapping-Semantik).
