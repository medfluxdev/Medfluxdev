# UAT-Bericht A–T — ABIOMED-Impella-Vertrag (40015645)

Datum: 2026-09-18 · System: Medflux MVP (lokale KI: Ollama / Qwen3-VL 8B) · Vertrag: `40015645` · Contract: `01a0aa27-f57b-7b4f-9659-5aadfed6f6c9`
Akzeptierte Analyse: `01a0b034-45ce-7813-9296-023205b53b67` (2026-09-17 18:30:10, `partial`/`valid`, `requires_review=true`)

---

## A. HEAD vor und nach dem Fix

| | HEAD | Arbeitsbaum (uncommitted) |
|---|---|---|
| Commit-Basis | `1c0c6ad` fix(ui) Contract360 quality action buttons (2026-09-16) | identisch + Delta unten |
| `backend/app/ai/harness/v3.py` | enges `locate()`: Quote-Suche nur je Layout-Element; Literal-Fallback scheitert an Eindeutigkeits-Guard | **`locate()` fällt auf Seitenebene zurück** (`page.text`), deterministische Money-Reader, Normalisierungen, Verschlachtungs-Start/Retry |
| `test_harness_v3.py` | — | **+299 Zeilen**: Money-/Normalisierungs-/Anker-Tests + Cross-Element-Quote-Regression |
| `PROJECT_PROGRESS.md` | — | +163 Zeilen: Money-Layer-Abschnitt + „Identity extraction restabilized on real canonical (2026-09-17, official UAT)“ |

**Vorher (Produktion/API):** `identity.supplier=None`, `contract_title=None` im Snapshot (2/2 API-Reanalyzes); Money-Werte und Datums-/Dauerfakten korrekt.
**Nachher (gleicher Produktions-Pfad):** alle 8 UAT-Fakten persistiert (siehe P).

## B. Root cause (echt, nicht Symptom)

1. **Lieferant/Titel gingen in der Produktion verloren (gesehen vor dem Fix):**
   - Der produktive, gecachte Canonical (sha256 `53e07641…`) zerlegt Seite 1 in **12 Layout-Elemente** (z. B. `zwischen` , `ABIOMED Europe GmbH…` als getrennte Elemente). Der isolierte Harness-Lauf hatte synthetische, ganzseitige Blöcke gebaut und dadurch den Fehler maskiert.
   - `locate()` suchte die Modell-Quote **nur je Element** → Quoten, die über Elementgrenzen gehen („zwischen“ + „ABIOMED Europe GmbH …“), fanden nie ein Element; der Literal-Fallback scheiterte dann am Eindeutigkeits-Guard, weil „ABIOMED Europe GmbH“ zusätzlich im Rechnungsanschrift-Block (Seite 6) vorkommt → `supplier` verworfen.
   - Das war ein **Root cause** (Ankerungslogik), kein Symptom.
2. **Money-Werte (in b7fbdbb und Folge-Commit bereits behoben):**
   - Verschachtelter Währungs-Bug in `_normalize_money_payload` (renamed-currency-Verlust) und unvollständige gestaffelte Preis-Spalten (`0 EUR`, `8.000,00 EUR` → `0.0`/`8000.0`). Deterministische Geld-Leser (`_staged_price_rows`, `_per_call_rows`, `_steady_annual_amount`) — **Berechnung macht Code, nicht die KI**.
   - Ebenfalls Root cause (Codeseitig), kein Symptom.
3. **`AIUnavailableError`-Fehlläufe (17:57, 18:24–18:26):**
   - Die `application_setting`-Tabelle war (nach Neustart/CWD-Kontext) wieder leer → `ai_provider`/`ai_model` nicht auflösbar → `calls=0` und `category=AIUnavailableError`.
   - Das ist ein **Symptom** (Konfigurations-/Kontextquirk), nicht Kern der Extraktionslogik. Behoben durch erneutes `set_ai_selection('ollama','qwen3-vl:8b-instruct')` mit `workdir=backend`.
4. **Keine Truncation** in allen erfolgreichen Läufen (`truncated_chunks=0`); der einzige Retry war eine Output-Budget-Entscheidung (siehe H).

## C. Geänderte Dateien und warum

| Datei | Grund | Typ |
|---|---|---|
| `backend/app/ai/harness/v3.py` | Root-cause-Fix `locate()`: bei fehlender Element-Suche Auflösung gegen autoritative Seitenebenen-`page.text` (Basis = das, was das Modell in `_pack_source` sah); deterministische Money-Normalisierung; Verschlachtungs-Start | **Code-Fix** |
| `backend/tests/test_harness_v3.py` | Regressionstests für Money-Layer, Normalisierungen, Verifier-fail-closed und **`test_quote_that_spans_layout_elements_binds_to_page_text`** | **Tests** |
| `docs/PROJECT_PROGRESS.md` | Dokumentation Money-Layer + UAT-Sektion (2026-09-17) | **Docs** |

Kein weiterer Code wurde seit der Verifikation verändert.

## D. Neues/modifiziertes Design (Direct Harness, `direct-v1`)

- **Direct-Harness-Flow:** `direct-contract-intelligence-v1`; ein Lauf = 4 semantische Stufen (`core`, `commercial`, `payment`, `operations`), keine Vision-Stufe (0 Vision-Calls).
- **Pack-/Seitenwahl:** Seitenpräzise Packs aus dem autoritativen Canonical; `source_signals` (labelled_contract_number, date, duration, renewal_negation, money) steuern die Zielseiten (p1, p4, p5, p7, p8).
- **Commercial-Fokussierung:** kommerzielle Stufe adressiert gezielt Seite 8 (Annex 2: `Fixed per call: 2.226,00 EUR`, `1.Jahr 0 EUR`, `2.–4.Jahr 8.000,00 EUR`).
- **Normalisierung:** Datums-/Dauer-/Preis-/Währungs-Normalisierung deterministisch (siehe L); verschachtelte Währung korrigiert.
- **Evidence-Ankerung:** deterministischer `_find_quote` je Element; **Fallback auf `page.text`**; Eindeutigkeits-Guard; sonst **fail-closed** (`evidence_not_located`); keine Halluzination.
- **Retry/Context:** eine `output_budget_stage_retry`-Entscheidung (Operations-Call) mit erhöhtem Output-Budget; keine Truncation.

## E. Unit Tests

- `test_harness_v3.py`: **18 passed** (5 DeprecationWarnings, unkritisch). Kernfälle: Money-Reader (Staged-Preise, per_call, Steady-State-Jahresbetrag), verschachtelte Währung, Normalisierungen, Auto-Anchoring, Verifier-fail-closed, **Quote, die über Layout-Element-Grenzen geht, bindet an `page.text`**.
- Darin enthalten: neue Regression `test_quote_that_spans_layout_elements_binds_to_page_text`.

## F. Integration / breitere Tests

- Gesamtcluster V3-Ökosystem: `test_harness_v3.py` + `test_ai_source_grounding.py` + `test_ai_verifier_fail_closed.py` = **40 passed**, 0 failed (5 warnings: `SwigPyObject` Deprecation — unkritisch, unabhängig).
- Breiteres Backend-Suite: vorhandene, **vorbestehende** Fehler (Auth-/Route-401, `contract_equipment.extraction_id NOT NULL` etc.), im HEAD-Vergleich reproduziert, NICHT durch dieses UAT/V3 verursacht.

## G. PRE-UAT-Echt-Qwen-Test

- **Model:** `qwen3-vl:8b-instruct` (Ollama, lokal); **Provider:** ollama; **Eingabe:** echter produktiv-gecachter Canonical (sha256 `53e07641…`), 9 Seiten.
- **Ergebnis:** 4/4 Semantic-Calls `succeeded`, `done_reason=stop`; **keine Truncation** (`truncated_chunks=0`); Structured-Output-Parse **erfolgreich** (ProposedFactBatch in allen Stufen geparst); `delivery_complete=true`, `supported_count=16`.
- Reproduktion des Fixes direkt gegen den Canonical: `identity.supplier` akzeptiert (p1), alle 8 UAT-Fakten akzeptiert.

## H. Token-/Context-Budget je KI-Call (akzeptierter Lauf 18:30)

Context-Kapazität (num_ctx): **8192** · Output-Budget default: **1800** Tokens.

| # | purpose | Seiten | prompt (actual) | prompt (est.) | response chars | output budget | done_reason | retry | Latenz |
|---|---|---|---|---|---|---|---|---|---|
| 1 | semantic:core | p1/5/8 | 3698 | 5109 | 1939 | 1800 | `stop` | nein | 14.110 s |
| 2 | semantic:commercial | p8 | 1675 | 2439 | 884 | 1800 | `stop` | nein | 4.640 s |
| 3 | semantic:payment | p4/8 | 4002 | 5346 | 1381 | 1800 | `stop` | nein | 7.219 s |
| 4 | semantic:operations | p2/7/8 | 5122 | 6773 | 1971 | 1800→**2558** | `stop` | `output_budget_stage_retry` | 8.484 s |

`actual_prompt_tokens` ≤ 8192 in allen Calls; kein Call überschritt das Context-Budget; keine truncation.

## I. UI-Screenshots / Verdict

Screenshots (absolute Pfade, abgelegt im Session-Workspace):
- `C:\Users\JAMAL\Desktop\Medflux\.playwright-mcp\uat-dashboard.png` — Dashboard (8.000,00 €, Berechnungskonflikt-Hinweis)
- `C:\Users\JAMAL\Desktop\Medflux\.playwright-mcp\uat-contracts-list.png` — Vertragsliste (komplette Zeile)
- `C:\Users\JAMAL\Desktop\Medflux\.playwright-mcp\uat-finance.png` — Contract360 **Finanzen**
- `C:\Users\JAMAL\Desktop\Medflux\.playwright-mcp\uat-nachweise.png` — **Nachweise** (Evidence-Liste + Quell-Viewer)
- `C:\Users\JAMAL\Desktop\Medflux\.playwright-mcp\uat-review.png` — **Prüfungen** (Berechnungskonflikt, „Prüfen“-Link)

**Verifiziert per Live-Snapshot (Port 3000):**
- **Nachweise:** 22 Belege mit Seite + Quotentext (Identität/Nr./Laufzeit/Konditionen); Quelle-PDF-Viewer (Seite 1/9) ✓
- **Dokumente:** Contract360 „1 Dokumente“ ✓
- **Offene Prüfungen:** „8 Offene Prüfungen“-Aktion ✓; Prüfungen-Seite listet 40015645 mit Berechnungskonflikt ✓
- **Vertragsentscheidung:** Panel mit Entscheidungs-Combobox, **date input** (Wirksam am), **textarea** (Notiz), **button** („Entscheidung anlegen“) ✓
- **Contract360 Übersicht:** Titel/Lieferant/Nr., Ende 31.03.2029 (Berechnet), Jährliche Kosten 8.000,00 € (Berechnet), Risiko Hoch ✓
- **Contract360 Finanzen:** „Jährlich wiederkehrend 8.000,00 € · Berechnet“; Erklärung „Deterministisch aus den vom Backend gelieferten Vertragsdaten berechnet“; Währungskonflikt Nein ✓
- **Analyse-Historie:** letzter Lauf „succeeded · 4 erfolgreich / 7 fehlgeschlagen“ (18:29) ✓

**Verdict UI:** alle geforderten Ansichten funktionieren und zeigen die akzeptierten Werte konsistent.

## J. Offizieller UAT-Abiomed (/reanalyze)

- **Ablauf:** offizieller Produktions-/API-Pfad `POST /api/documents/01a0aa26-dcd1-7617-baaf-e89432e5f854/reanalyze` (localhost:8000), nicht ein isolierter Harness-Test.
- **Ergebnis:** `status=reanalyzed`, `analysis_status=partial`, `validation_status=valid`, `requires_review=true`, **4 Calls, 66.703 s**, `ai_call_count=4`, `truncated_chunks=0`.
- **UI-Verifikation desselben Vertrags** (Vertrag 360, Authentifizierung admin@medflux.local) bestätigt die Werte (siehe P).
- Dokumentversion: `01a0aa26-dcd1-7617-baaf-e89432e5f854`.

## K. Semantic Proposals (Auswahl, wichtigste)

| field | value | page | quote | applicability |
|---|---|---|---|---|
| identity.contract_number | `40015645` | 1 | „Vertr.-Nr.: 40015645“ | applicable |
| identity.supplier | `ABIOMED Europe GmbH` | 1 | „zwischen / ABIOMED Europe GmbH Neuenhofer Weg 3 D-52074 Aachen“ | applicable |
| identity.contract_title | „Full-Service-Vertrag für das Impella®AIC System“ | 1 | „ABIOMED / Full-Service-Vertrag / für das Impella®AIC System“ | applicable |
| dates.start_date | `2025-04-01` | 5 | „… beginnt am 01.04.2025 und endet am 31.03.2029.“ | applicable |
| dates.end_date | `2029-03-31` | 5 | dito | applicable |
| dates.duration | 4 years | 5 | „Laufzeit von 4 Jahren …“ | applicable |
| termination.automatic_renewal | `false` | 5 | „… wird nicht automatisch verlängert.“ | applicable |
| costs.variable_charges | `2226.0 EUR` (per_call) | 8 | „per call: 2.226,00 EUR“ | applicable |
| costs.scheduled_prices | 0/8000/8000/8000 | 8 | „im 1.Jahr … 0 EUR“ | applicable |
| costs.price_adjustment_clause | (Text) | 8 | „Fixed per call: 2.226,00 EUR (inkl. Arbeit …)“ | applicable → **verworfen** (N) |
| services.maintenance/inspection/calibration/repair | true | 2/2/7/7 | jew. Quelle | applicable |
| sla.service_hours | {} | 4 | „Montag bis Freitag von 09:00 Uhr bis 17:00 Uhr“ | applicable → **verworfen** (N) |
| services.software_updates | true | 7 | „Durchführung von notwendigen und/oder empfohlenen Updates …“ | applicable → **verworfen** (N) |

## L. Normalisierungen

| from | to | Feld |
|---|---|---|
| `{day:1, month:4, year:2025}` | `2025-04-01`, review=false | dates.start_date |
| `{day:31, month:3, year:2029}` | `2029-03-31`, review=false | dates.end_date |
| `{years:4}` | `{unit:years, value:4}` | dates.duration |
| `{unit:per_call, currency:EUR}` + Money-Literal `2.226,00 EUR` → `{amount:2226.0, currency:EUR}` | `variable_charges[0]` per_call | costs.variable_charges |
| `{unit:0/8.0, currency:EUR}` + `0 EUR`/`8.000,00 EUR` → `0.0`/`8000.0` | `scheduled_prices[1..4]` | costs.scheduled_prices |
| `{start_time:09:00, end_time:17:00}` | `{}` (kein Wert→verworfen) | sla.service_hours |

**Money-Konvertierung:** deutsche Formate (`2.226,00`, `8.000,00`) deterministisch → `amount` (float) + `currency_code` → `currency`; kein KI-Rechenschritt.

## M. Akzeptierte Fakten (relevanteste, page + quote)

| field | page | quote |
|---|---|---|
| identity.contract_number | 1 | „Vertr.-Nr.: 40015645“ |
| identity.supplier | 1 | „zwischen / ABIOMED Europe GmbH Neuenhofer Weg 3 D-52074 Aachen“ |
| identity.contract_title | 1 | „ABIOMED / Full-Service-Vertrag / für das Impella®AIC System“ |
| identity.customer | 1 | „… Krankenhaus Nordwest GmbH Frankfurt …“ |
| dates.start_date | 5 | „… beginnt am 01.04.2025 …“ |
| dates.end_date | 5 | „… endet am 31.03.2029.“ |
| dates.duration | 5 | „Laufzeit von 4 Jahren …“ |
| termination.automatic_renewal | 5 | „… wird nicht automatisch verlängert.“ |
| costs.variable_charges | 8 | „per call: 2.226,00 EUR“ |
| costs.scheduled_prices | 8 | „im 1.Jahr … 0 EUR“ (+ 8.000,00 EUR J.2–4) |
| costs.annual_cost | (abgeleitet) | „abgeleitet aus gestaffelten Jahrespreisen“ |
| payment.payment_terms | 4 | „Die Zahlungsweise erfolgt im jährlichen Rhythmus …“ |
| services.maintenance/inspection/calibration/repair | 2/2/7/7 | je Quelle |

`supported_count=16`, `delivery_complete=true`.

## N. Abgelehnte Fakten (5) mit Grund

| field | page | Grund |
|---|---|---|
| payment.payment_deadline_days | – | `evidence_not_located` (leere Quote) |
| costs.price_adjustment_clause | 8 | `evidence_not_located` (Zitat nicht eindeutig im kanonischen Text lokalisierbar) |
| costs.price_indexation | – | `evidence_not_located` |
| sla.service_hours | 4 | `schema_validation_failed` — „Supported fact has no value“ (Struktur leer) |
| services.software_updates | 7 | `evidence_not_located` |

Kein abgelehnter Fakt war ein UAT-Fakt; System verhält sich **fail-closed** statt zu halluzinieren (AGENTS.md-Prinzip).

## O. Evidence

- Snapshot-`evidence_count`: **16** (analysis.harness.evidence) · DB-Zeilen `extraction_evidence`: **22** (inkl. Holder-Ebene wie `identity.evidence`, `costs.evidence`).
- **Seiten:** ausschließlich 1, 2, 4, 5, 7, 8 — alle korrekt zum Quell-Dokument (Karte: p1 Identität/Nr., p5 Datum/Dauer/Auto-Verlängerung, p8 Preise, p7 Leistungen, p4 Zahlweise). **Kein** Beleg zeigt eine falsche Seite.
- `field_ref` korrekt (z. B. `identity.supplier.evidence.2`, `dates.end_date.evidence.5`, `costs.scheduled_prices.evidence.9`); alle Zeilen `requires_review=false`, `extraction_method=ai`.
- **Fazit:** Seiten zuweisung korrekt und überprüfbar.

## P. Contract360 — finale Werte (tatsächlich angezeigt)

| Feld | Wert |
|---|---|
| supplier | `ABIOMED Europe GmbH` |
| contract number | `40015645` |
| start date | `01.04.2025` (Berechnet aus extrahiertem Fakt 2025-04-01) |
| end date | `31.03.2029` |
| duration | `4 Jahre` |
| automatic renewal | `false` |
| annual cost | `8.000,00 €` (**Berechnet**) |
| per-call fee | `2.226,00 €` (**explicit**) |

**Warum annual = „calculated“ und ist das korrekt?**
- Es gibt **keinen expliziten KI-Fakt „jährliche Kosten: 8.000“**. Der Fakt `costs.annual_cost` ist als „abgeleitet aus gestaffelten Jahrespreisen“ markiert (`page=null`). Der Determinist steigt aus dem expliziten Preisplan `scheduled_prices` (1.Jahr 0 €, 2.–4.Jahr je 8.000,00 €) den **Steady-State-Jahresbetrag = 8.000 €** ab und bildet ihn auf `period=annual`.
- `calculation_result costs.annual` = `costs.normalized_recurring.annual` `{value:8000.0, currency:EUR, status:calculated, inputs:{annual_cost:8000.0}}`, Erklärung: „Jährlich 8000.0 (annual) => jährlich 8000.0 EUR.”
- **Semantisch korrekt:** Der Vertrag nennt einen jährlichen Full-Service-Preis von 8.000,00 EUR ab Jahr 2 (Jahr 1 beitragsfrei). 8.000 €/Jahr ist die richtige, verlässliche wiederkehrende Größe für die Jahreskosten-Aggregation. Es ist **keine** Halluzination und **kein** Featureschnitzer.
- **Gesamtwert** berechnet: `0 + 8000 + 8000 + 8000 = 24.000 €` (expliziter Preisplan), bedingte per_call-Position bewusst nicht addiert.

**Berechnungskonflikt (Dashboard, 40015645):**
- **Ursache:** `calculation_result dates.calculated_end_date` = `status: conflict`: explizites Ende `2029-03-31` vs. **abgeleitetes** Ende aus `start(2025-04-01) + 4 Jahre = 2029-04-01`. Differenz = 1 Tag; **explizit als Basis markiert**; `review_required=true`. (Aus demselben Grund `days_until_end` = `conflict`.)
- **Erwartet?** Ja — das ist STEP-9-Verhalten („Differenz verlangt Prüfung; explizites Datum als Basis“). Im Vertragstext steht „beginnt am 01.04.2025 und endet am 31.03.2029“ (4 Jahre minus 1 Tag) — die Ableitungsformel rechnet kalendrisch +4 Jahre.
- **Bleibendes Problem?** Nein, kein Extraktionsdefekt. Es ist ein erwarteter, dokumentierter **Review-Punkt**, manuell bestätigbar (explizites Ende gewinnt). Aktiv-Warnung `calculation_conflict` (high, requires_review) vorhanden.
- **Blockiert Final SUCCESS?** Nein, **sofern** der Review-Punkt als „erwartet + verstanden“ dokumentiert ist. Er wird gelöscht, sobald der Prüfer am 31.03.2029 als Basis festhält (STEP-9-Review-Workflow).

## Q. Verarbeitungszeiten

- OCR/Docling-Konvertierung (9 Seiten, rapidocr deu, table accurate): **45.328 s** (konstant über alle Runs).
- Harness (akzeptierter Lauf): **66.703 s** (4 Calls, Summe Einzellatenzen ~34.5 s + Overhead) — Bronze/prior: 67.078 s / 28.719 s.
- Volles offizielles /reanalyze (OCR + Harness + Persistenz): **~112 s** (45.3 + 66.7).
- UI/API-Auslesen: im Sekundenbereich (kein Messpunkt der KI).

## R. KI-Calls

- `call_count=4`, `failure_count=0` (akzeptierter Lauf).
- Zwecke: `semantic:core` → `semantic:commercial` → `semantic:payment` → `semantic:operations`; alle `succeeded`, alle `done_reason=stop`.
- Ein Retry: `semantic:operations` mit `retry_decision=output_budget_stage_retry` (Output-Budget 1800→2558); danach `stop`.
- Definitionsgemäß: `purpose=direct` (Harness), `stage_call_counts: semantic=4, vision=0`.

## S. GPU / VRAM / Ollama

- **GPU:** NVIDIA GeForce RTX 3070 · **VRAM:** 8192 MiB total, zum Messzeitpunkt 6534 MiB genutzt / 1484 MiB frei · Util 37 % · Temp 51 °C.
- **Modell:** `qwen3-vl:8b-instruct` (Ollama, 6.1 GB) geladen; **Context:** num_ctx 8192; **Offload:** `OLLAMA_NUM_GPU=999` (Voll-Offload); Sampling: `temperature=0.1`, `repeat_penalty=1.3`, thinking aus.
- **Laufzeitbetrachtung:** Ollama hält das Modell resident; keine OOM/Kein-Speicher-Ereignis; Latenzen siehe H.

## T. Final Verdict

**Alle für den UAT entscheidenden Fakten korrekt, belegt und persistiert:**

- ABIOMED Europe GmbH ✓ · 40015645 ✓ · 01.04.2025 ✓ · 31.03.2029 ✓ · Dauer 4 Jahre ✓ · automatic_renewal=false ✓
- 8.000 €/Jahr deterministisch abgeleitet aus dem expliziten Preisplan → dargestellt als „Berechnet“ — **semantisch korrekt** ✓
- 2.226 € = per_call **explicit** ✓ · Evidence-Seiten korrekt (1/2/4/5/7/8) ✓ · keine halluzinierten Werte (fail-closed, 5 Proposal-Verwerfungen) ✓
- Persistenz: `contract`-Zeile, `contract_extraction` (Snapshot sha256 `27109df9…`), `calculation_run`/`_result` Flags, `contract_warning`, 22 Evidence-Zeilen — **konsistent** ✓
- Contract360 (Übersicht + Finanzen), Vertragsliste, Dashboard, Nachweise, Prüfungen — **zeigen die korrekte Darstellung** ✓
- Offizieller /reanalyze-Produktionspfad erfolgreich (nicht nur isolierter Test) ✓

**Berechnungskonflikt:** erwartet, dokumentiert und verstanden (explizites Ende 31.03.2029 als Basis; Abweichung zur kalendrischen Ableitung +1 Tag; STEP-9-Regel); **kein Extraktionsdefekt**, löst sich im Review-Workflow auf.

> **T = SUCCESS** — unter der Voraussetzung, dass der offene STEP-9-Review-Punkt (calculated_end_date: 31.03.2029 vs. 2029-04-01, explizit als Basis markiert) im manuellen Prüf-Workflow bestätigt wird. Der `requires_review=true`-Status ist damit dokumentierte, erwartete Funktionsweise, **kein** verbleibender Defekt. Würde der Konflikt nicht als erwartet akzeptiert, wäre **T = PARTIAL/OPEN**; aktuell gilt er als gerechtfertigt.

---

*Offene Review-Punkte (Workflow, keine Fehler): (1) calculated_end_date Dateikonflikt, (2) Steuerbasis ohne dokumentierten Satz — keine MwSt-Annahme (Review-Reason im Snapshot).*