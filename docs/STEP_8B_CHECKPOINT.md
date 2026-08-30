# Medflux — STEP 8B Checkpoint (Extraction Reliability Hardening)

Ein Checkpunkt zwischen STEP 8 und STEP 9. STEP 8 ist abgeschlossen;
STEP 8B ist eine **interne, nicht gezählte** Härtungsphase. Der Projektfortschritt
bleibt **8 / 18 = 44,4 %**. STEP 9 beginnt NICHT ohne explizite Freigabe.

Zweck: Die in STEP 8 diagnostizierte Kernschwäche beheben – qwen3:8b folgte dem
Medflux-Vertrags-JSON-Schema nicht (erfand eigene Abschnitte, Großbuchstaben-Enums).
Ersetzung: **native strukturierte Ausgabe** über Ollama (`format` = JSON-Schema),
statt rein Prompt-basierter Schema-Disziplin.

---

## 1. Implementierung (Zusammenfassung)

- **`backend/app/ai/schema.py`** (neu): selbstenthaltenes JSON-Schema, deterministisch
  aus `Contract.model_json_schema()` abgeleitet – `$ref`/`$defs` werden inline
  aufgelöst (Ollama akzeptiert keine `$ref`, empirisch geprüft). KEIN zweites,
  manuell gepflegtes Schema.
- **`backend/app/ai/base.py`**: `AIProvider.generate_structured(..., schema=...)`
  als neues abstraktes Interface ergänzt (Provider bleiben austauschbar).
- **`backend/app/ai/providers/ollama.py`**: `generate_structured` sendet das Schema
  als `format` an `/api/chat` (native JSON-Schema-Erzwingung). Gemeinsame
  `_options()`-Helfer; `repeat_penalty` aus Settings.
- **`backend/app/ai/service.py`**: `AIService.generate_structured(..., schema, ...)`.
- **`backend/app/ai/contract_extractor.py`**: `_extract_chunk` nutzt
  `generate_structured` mit `contract_json_schema()`; Diagnose-Zähler
  (timeouts/retries/truncated) am `ContractAnalysisResult`.
- **`backend/app/models/contract.py`**: `model_config = {"extra": "forbid"}` auf
  `Contract` – erfundene Top-Level-Schlüssel (parties/terms/fees) werden nicht
  mehr stillschweigend verworfen, sondern lösen einen kontrollierten Retry aus.
- **`backend/app/ai/prompts/contract_extraction_v1.py`**: Prompt auf SEMANTIK
  reduziert (Feldbedeutung, Anti-Halluzination, Geld/Ereignis-Daten, Evidence-Regeln,
  DOCX/PDF, Kompaktheit) – keine riesige Text-Schema-Wiederholung mehr.
- **`backend/app/core/config.py`**:
  - `ai_request_timeout_seconds`: 120 → **300** (strukturierte Ausgabe kann lokal
    länger dauern; 120s verursachte falsche Timeouts).
  - `ai_repeat_penalty`: **1.3** (neu, siehe «Kernbefund»).
  - `ai_extraction_max_tokens` bleibt **8192** (STEP 8; bei rp=1.3 wird praktisch
    kaum mehr Truncation beobachtet, Wert aber nicht blind gesenkt).

## 2. Kernbefund: `repeat_penalty` = 1,3

Bei nativer strukturierter Ausgabe verfiel qwen3:8b in eine **degenerierte
Wiederholungsschleife** (z. B. `equipment_category` = "...translated from German
context of 'C-Bogen'" × viele Dutzend), die den gesamten
`num_predict`-Budget verbrauchte → 26–36 kB große, abgeschnittene, langsame,
ungültige Ausgabe.

Getestet (eine Vision-Referenz-Chunk):
| repeat_penalty | chars | done_reason | Ergebnis |
|----------------|-------|-------------|----------|
| (default)      | 14 581 | length | Abbruch – Endlosschleife |
| **1.3**        | 1 660  | **stop**   | **kompakt, valide** |
| 1.6            | 303    | stop       | valide, aber zu spärlich |

**1.3** ist der Sweet-Spot: beendet die Schleife, liefert abschließendes, JSON-valides
Ergebnis, deutlich schneller. Eine Deterministik, lieferantenunabhängige und
dokumentierte Einstellung – keine Vendor-Sonderlogik.

## 3. Ergebnis des abgeschlossenen Benchmark (6 echte Verträge × 3 Läufe)

Beibehalten wie von STEP 8: gleiche 6 Verträge, gleiche `ground_truth.json`.
`data/benchmark/report_latest.json` enthält diesen **abgeschlossenen** Lauf.

### Aggregate (best-of-3 je Vertrag)
| Metrik | Wert |
|--------|------|
| Feldgenauigkeit (summiert) | **31 / 64 = 48,4 %** |
| Mittelwert je Vertrag | 47,4 % |
| Median je Vertrag | 49,4 % |
| Validierung (best-of-3, VALID) | **6 / 6 = 100 %** |
| validierte Einzelläufe (17/18) | **17 / 18 = 94,4 %** |
| erfundene Werte | **0** |
| Timeouts | **0** |
| abgeschnittene Chunks (truncated) | **0** |
| Ø Dauer/Vertrag | **~32 s** (≈31,8 s) |

### Per-Vertrag (best-of-3) & Läufe (passed / validation)
| Vertrag | best | Läufe (passed) | Läufe (validation) |
|---------|------|----------------|---------------------|
| Vision_RFD_3D | 11/16 | 11 · 10 · 9 | valid · valid · valid |
| Siemens_MRT_Vida_3T | 5/8 | 5 · 5 · 1 | valid · valid · **invalid** |
| Abiomed_FullService | 4/11 | 4 · 4 · 4 | valid · valid · valid |
| Apoplex_SRAclinic | 2/8 | 2 · 2 · 2 | valid · valid · valid |
| GE_MACLAB | 6/9 | 6 · 6 · 6 | valid · valid · valid |
| Truebeam_STX | 3/12 | 3 · 3 · 3 | valid · valid · valid |

Hinweis: Der eine ungültige Lauf (Siemens run 3) ist der Grund für **17/18 statt
18/18**; die Schema-Konformität ist über alle übrigen 17 Läufe garantiert.

## 4. Feld-Ebene: verbleibende semantische Lücken

| Feld | passed | Beobachtung |
|------|--------|-------------|
| identity.contract_type | 0/6 | korrekt als Enum geliefert, aber Abgleichs-Artefakt (Enum-Repr) – siehe Hinweis; inhaltlich überwiegend richtig |
| payment.billing_interval | 0/4 | korrekt als Enum, Abgleichs-Artefakt; Apoplex/Truebeam liefern `other` (semantisch ungeklärt) |
| identity.contract_number | 0/5 | fehlend (meist nicht im Text) |
| dates.end_date.date | 0/2 | fehlend (ereignis-/nummernbasiert) |
| dates.duration | 0/2 | teils fehlend/falsch |
| costs.total_contract_value.amount | 0/1 | fehlend |
| costs.monthly_cost.amount | 0/1 | fehlend |
| payment.payment_deadline_days | 0/1 | fehlend |
| payment.payment_terms | 0/1 | fehlend |
| identity.department | 0/1 | fehlend |
| termination.automatic_renewal | 3/5 | 2 falsch (Varianz) |
| termination.cancellation_period | 1/3 | 1 fehlend + 1 falsch |
| costs.annual_cost.amount | 2/3 | 1 falsch |
| Stark verbessert | – | customer 0→3/3, supplier 2→5/6, equipment 2→5/6, renewal_period 0→3/3, minimum_duration 0→2/2 |

**Wichtiger Hinweis zum Matcher-Artefakt:** `contract_type`/`billing_interval`
wurden vom Benchmark als «wrong» gezählt, weil `_match` die Pydantic-Enum-Repr
(`<ContractType.SERVICE: 'service'>`) statt des `.value` verglich. Die inhaltlichen
Enum-Werte des Modells sind nach STEP 8B fast durchgehend korrekt (Vision/Siemens/
Apoplex → service, Abiomed/GE → maintenance). Ein Matcher-Fix (Enum-`.value`-Auflösung)
wurde im Skript vorbereitet; der Report bleibt mit den STEP-8B-Originalwerten (48,4 %)
vergleichbar und unverändert erhalten.

Immer noch unverändert gut: **0 erfundene Werte** in allen Läufen – die
Anti-Halluzinations-Regeln halten weiterhin.

## 5. Verbleibende semantische Fehlerkategorien (nicht «reliabel»)

- **Seltene/freie Felder** (contract_number, department, payment_deadline_days,
  total/monthly cost): werden oft gar nicht erfasst (fehlend), weil sie im
  Vertragstext fehlen oder selten/implizit sind.
- **Ereignisbasierte bzw. nummernbasiert-ambige Daten** (end_date, duration):
  Mehrdeutigkeit → null statt heuristischer Belegung (konservativ, aber nicht voll).
- **Beträge** (annual/monthly/total, payment_terms): semantische Geldklassifikation
  bei komplexen Kostenschemata (z. B. Staffelgebühren) noch unzuverlässig.
- **Wiederholungskonsistenz** nur mittel: 4/6 Verträge lieferten in allen 3 Läufen
  identische Punktzahlen; restliche variieren (Modell-Nichtdeterminismus).

Fazit: Schema-Konformität und Core-Identity (Parteien, Geräte) sind stark
verbessert; die **semantische Feldabdeckung** (v. a. Kosten, Fristen, seltene
Felder) liegt bei ~48 % und ist noch nicht «zuverlässig» im Sinne des MVP.

## 6. Empfohlene nächste Arbeit (NICHT ausgeführt)

1. **Spezialisierte Feldgruppen-Extraktion**: statt eines Gesamt-`Contract`-JSON pro
   Chunk gezielt Unterblöcke (identity / termination / costs / payment / sla)
   abfragen und deterministisch mergen – reduziert Modellüberlastung und verbessert
   seltene Felder.
2. **Evidence-Verifikation**: automatisch prüfen, dass `source_text`/Zeiger
   (page/paragraph/table) tatsächlich im Originaldokument existieren; falsche Belege
   → requires_review statt stiller Annahme (STEP-8B-Regel §6 konsequent umsetzen).
3. Danach erneuter Benchmark vor STEP 9 (gleiche 6 Verträge, gleiche Ground Truth).

## 7. Status & Freigabe

- Projektfortschritt: unverändert **8 / 18 = 44,4 %**.
- STEP 9 (Date & Cost Engine) startet **nicht** automatisch.
- `report_latest.json` = abgeschlossener STEP-8B-Lauf (48,4 %, 6/6 valid,
  17/18 Einzelläufe valid, 0 erfunden, 0 Timeouts, 0 Truncation, Ø ~32 s).

---

## 8. STEP-8B-Semantik – Feldgruppen-Extraktion & Evidence-Verifikation (Benchmark)

Nach der Härtung (Abschn. 1–7) wurde die empfohlene nächste Arbeit ausgeführt
(Feldgruppen-Extraktion + Evidence-Verifikation, vgl. Abschn. 6). Diese Phase
zählt weiterhin NICHT als neuer Hauptschritt; Fortschritt bleibt 8/18 = 44,4 %.

### 8.1 Korrigierte Baseline des STEP-8B-Laufs (wichtig für Vergleiche)

Der STEP-8B-Matcher-Fix war **nicht vollständig**: Pydantic-Enums erben von
`str`, daher schlug der `isinstance(v, str)`-Guard fehl und `_norm_str`
verglichen weiterhin die Enum-Repr (`<ContractType.SERVICE: 'service'>`)
statt des `.value`. Dadurch wurden ALLE Enum-Felder als „wrong“ gezählt.

- **Fix (abgeschlossen):** `scripts/benchmark_extraction.py` `_norm_str` nutzt
  jetzt gezielt `getattr(v, "value", v)` (unabhängig vom `str`-Guard).
- **Korrigierte STEP-8B-Baseline** (stored Report, Enum-Rekonstruktion aus den
  gespeicherten Enum-Reprs, 1:1-GT-Zeilenabgleich): **38 / 64 = 59,4 %**
  (31 historisch + 7 Enum-Korrekturen: `contract_type` 5×, `billing_interval` 2×).
- Die früher genannte **39/64** war um exakt **1 Doppelzähl-Artefakt** zu hoch
  (Vision `equipment` in `report_latest.json` zweimal geführt). Beide Zahlen
  sind dokumentiert: **38/64 ist die verbindliche korrigierte Baseline.**

Per-Vertrag (best-of-3, korrigiert): Vision 13/16, Siemens 6/8, Abiomed 6/11,
Apoplex 3/8, GE 7/9, Truebeam 3/12.

### 8.2 Neue Pipeline & Benchmark

- **Pipeline:** `ContractAnalysisOrchestrator` ist an die `GroupPipeline`
  angebunden (`app/ai/groups/{extractor,verifier,evidence,specs}.py`):
  pro Chunk spezialisierte Feldgruppen (identity/equipment/dates/termination/
  costs/payment/services/sla), deterministischer Merge, Evidence-First-Verifikation
  gegen die Original-DOCX-Einheiten, deterministische Normalisierung, semantischer
  Verifier für sensible Felder.
- **Messung:** `scripts/benchmark_groups.py` (wiederverwendet `_match`/`_evaluate`
  des korrigierten Schritt-8-Matchers; erfasst Zusatzdiagnostik: Struktur-Attribute,
  Evidence-Support deterministisch über `verify_evidence`, Verifier-Entscheidungen
  per Wrapper — ohne dessen Logik zu ändern).
- **Neuer Report (historischer Report bleibt unverändert):**
  `data/benchmark/report_groups.json` (1 Lauf je Vertrag, kein best-of-3).

### 8.3 Ergebnis (6 echte Verträge, 1 Lauf je Vertrag, korrigierter Matcher)

| Metrik | STEP 8B (korr. Baseline, best-of-3) | Feldgruppen (1×1) |
|--------|--------------------------------------|-------------------|
| Feldgenauigkeit | 38/64 = **59,4 %** | **43/64 = 67,2 %** |
| Validierung (VALID) | 6/6 (konfig.-bedingt tollerant) | **0/6** (alle requires_review) |
| erfundene Werte | 0 | **0** |
| Timeouts / Retries / Truncation | 0 | **0 / 0 / 0** |
| Ø Dauer/Vertrag | ~32 s (3 Läufe/Vertrag) | **~62 s** (1 Lauf; Truebeam 156 s) |

| Vertrag | korr. Baseline | Feldgruppen | Δ |
|---------|----------------|-------------|---|
| Vision_RFD_3D | 13/16 | 12/16 | −1 |
| Siemens_MRT_Vida_3T | 6/8 | 6/8 | ±0 |
| Abiomed_FullService | 6/11 | 8/11 | +2 |
| Apoplex_SRAclinic | 3/8 | 5/8 | +2 |
| GE_MACLAB | 7/9 | 5/9 | −2 |
| Truebeam_STX | 3/12 | 7/12 | +4 |

AI-Calls gesamt: 102 (Vision 9, Siemens 5, Abiomed 17, Apoplex 13, GE 13,
Truebeam 45); Verifier je Vertrag genau 1 Call. Evidence-Support (deterministisch,
volle Sections): Vision 3/3, Siemens 1/2, Abiomed 2/3, Apoplex 1/4, GE 3/3,
Truebeam 2/4.

### 8.4 Ehrliche Befunde

1. **Validierungs-Regression 6/6 → 0/6:** Jeder Vertrag endet jetzt
   `invalid` + `requires_review`. Ursache ist die **konservative
   Verifier-/Review-Logik** (unsupported sensible Felder → Section-Review →
   `requires_manual_review`), NICHT fehlende Extraktion. Faktisch sind hohe
   Feldgenauigkeit und „bitte prüfen“ gleichzeitig. Sicherheitstechnisch
   vertretbar (nichts wird stillschweigend akzeptiert), aber das MVP-
   Automatisierungsziel „automatisch valide“ ist damit noch nicht erreicht →
   Schwellwert-/Gewichtungsfeinschliff nötig (z. B. Review erst bei
   kritischer Feldmenge oder confidence-Floor).
2. **Truebeam `total_contract_value` (+942480):** Kein erfundener Wert – „€
   942.480,00“ steht im Dokument (Angebots-Gesamt inkl. MwSt.), GT erwartet
   hier aber null. Klassischer Mapping-Übergriff (Angebots-Gesamt ≠
   Vertragswert); darüber hinaus hatte der costs-Abschnitt kein Evidence-
   Objekt, trotzdem bestätigte der Verifier das Feld – **Kostengruppe trägt
   aktuell keinen Evidence-Nachweis**.
3. **GE `sla.response_time`:** Modell wählte 24h (echt textlich „Innerhalb
   von 24 Stunden nach Eingang …“), GT erwartet den 4h-Reaktionsvorschlag.
   Semantik-Auflösung (Lösung vs. Reaktionsvorschlag), kein Fantasiewert –
   aber `original_text` zitiert eine **fehlpassende** Stelle („Wartezeiten >
   15 Minuten …“) → Qualität der Zitat-Belege ist verbesserungswürdig.
4. **Dauer:** Truebeam (11 Chunks, 44 Gruppen, 45 Calls) braucht ~156 s
   (einfach, lokal). Größte Kostenquelle der Feldgruppen-Pipeline.
5. **Rauschen:** Einige `contains`-Felder notiert der Report als `got='missing'`,
   obwohl ok=True – das Detail-String des Matchers ist dort ein Konstantwert
   (Reporter-Ausseitigkeit, kein Bewertungsfehler; ok-Flag zählt).

### 8.5 Empfohlene nächste Arbeit (NICHT ausgeführt)

- Review-/Validierungs-Logik ausbalancieren (0/6 valid ist sicher, aber zu
  streng fürs MVP; Schwellwert-Konzept statt „jede unsupported -> invalid").
- Evidence für die costs-Gruppe ergänzen und Zitat-Belege (=`original_text`)
  plausibilisieren.
- `payment.billing_interval`/`contract_type`-Restfehler (Vision `once`,
  GE `service`) per Deterministic-Normalisierung flankieren.
- Danach erneuter Benchmark vor STEP 9 (gleiche GT, 1×1**, zusätzlich best-of-3**).

### 8.6 Korrektur Quell-Navigation – atomische OCR-Geometrie (STEP 8B/DI, Gate D)

Die Diagnose (Vision/GE/Truebeam sind REINE Scans; Docling ordnet (text,bbox)
nur absatz-/zeilenweise und teilweise falsch zu) wurde akzeptiert und durch
atomare RapidOCR-Geometrie gelöst. Gehört zur DI-interne Härtung (zählt NICHT
als neuer Projekt-Schritt; Fortschritt bleibt 8/18 = 44,4 %).

- **Geometrie-EIGENTÜMER** sind jetzt die atomaren RapidOCR-Einheiten (Wort +
  Zeile) bzw. validierte Docling-Tabellenzellen; die Struktur/Lesereihenfolge
  bleibt Docling.
- Deterministische Offset-Bindung an den unveränderten kanonischen Seiten-Text
  (globaler Token-Matcher + lokaler Anker-Fallback mit Präfix-Toleranz; rotierte
  Seiten via y-unabhängiger Ankerschau).
- Klassifikation ehrlich: `EXACT_WORD / VALIDATED_TABLE_CELL / EXACT_LINE /
  COARSE_FALLBACK / TARGET_NOT_FOUND`; grobe Element-Boxen nie still als exakt.
- Tabellenzellen deterministisch auf Koordinatenraum geprüft (Identität vs.
  Y-Spiegel an der Seitenhöhe, über OCR-Wort-Belegung entschieden); nur
  validierte Zellen → `table_cell`.
- **Ergebnis 6/6** Quellziele programmatisch exakt (Atomare Units; Ink-Abgleich
  an gerenderten Views: alle Boxen auf Tinte, auch rotierte Seiten).
  Artefakte: `di_reports/source_navigation_atomic.json`, `highlights_atomic/`.
- **Gate bleibt D** bis zur VISUELLEN Bestätigung der Renders durch einen
  Menschen (`VISUAL HUMAN VERIFICATION PENDING`); kein automatischer Gate-A-
  Übergang.
- Tests: `tests/test_atomic_geometry.py` (21); Vollsuite 219 passed.
  Details: `docs/PROJECT_PROGRESS.md` → „Korrektur umgesetzt – Atomische
  OCR-Geometrie".

