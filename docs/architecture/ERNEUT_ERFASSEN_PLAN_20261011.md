# Plan: Re-extract from the document inside the contract ("Erneut aus dem Dokument erfassen")

Date: 2026-10-11 · Status: proposal, decisions open (section 8) · Owner: product owner

## 1. Goal

When the first analysis missed facts (or got them wrong), the user can start a new extraction **from inside the contract**, see what the new run found, and take over only what is better – without ever losing values that are already there.

## 2. What exists today (code facts)

| Area | State |
|---|---|
| Backend endpoint | `POST /api/documents/{version}/reanalyze` → `DocumentProcessingService.reanalyze_document` exists. Org scope and document visibility are checked (`_preflight_document`); viewers are blocked by the auth middleware; there is no dedicated permission. |
| Frontend | `reanalyzeDocument()` in `lib/domain-api/documents.ts` exists but **no screen uses it**. Retry for failed imports is only on `/import`. |
| Runtime | Runs synchronously inside the HTTP request (minutes on an 8 GB GPU). |
| Result handling | The new extraction is **accepted immediately** as the contract's truth (`accept_extraction`, `project_contract(..., replace_missing=True)`). `sync_from_extraction` **clears AI-owned values the new run does not find** (action `cleared`). Human values are safe (only `ai_proposed_value`). |
| Determinism | Ollama runs at `temperature 0`, the canonical document is **cached** (`_load_cached_canonical`), same prompt, same model. |
| Harness | `HarnessV3` works in packs (`core`, `commercial`, `payment`, `operations`) with field catalogs (`_field_catalog`) and keyword-based page selection (`_pack_pages`); optional vision reading per page. |

## 3. Analysis – what really gives better results

1. **A plain "try again" gives (almost) the same result.** Same cached text + same model + same prompt + temperature 0 = same answer. A button that only repeats the run would create false hope. Better results need a *changed input*:
   - **Targeted search for the missing fields** (biggest lever): a small field catalog (only the missing keys) leaves much more of the 8k context for source text, and the pages can be chosen for those fields instead of for a whole pack. Long contracts are currently split into page chunks per pack; a missing start date on page 9 can be outside what the `core` pack saw.
   - **User hint "Wo steht es?"** (page or passage): the strongest signal we can get; the human knows the contract.
   - **Read the document again**: rebuild the canonical document (OCR) and add vision reading for scans – useful when the first run used the native fallback without OCR or the text layer is poor.
   - **Another installed model** (e.g. larger or vision model) for this run only.
2. **A rerun must never make the contract worse.** Today it can: values found the first time disappear when the second run misses them, and evidence is replaced. → The new run must be a **candidate**, compared with the current state, and applied **field by field by a person**.
3. **The rules stay the same:** AI proposes facts with evidence (quote + page), code calculates deadlines and costs, missing stays missing, human values win, no external AI, org scope before any model call.

## 4. User experience

### 4.1 Entry points (follow "Direkt zur Stelle")
- **"Was fehlt noch?" card** (Übersicht): button **"Fehlende Angaben im Dokument suchen"** – opens the dialog with exactly those fields preselected.
- **Empty field in Vertragsdaten**: next to "Erfassen" a second action **"Im Dokument suchen"** (one field preselected).
- **Dokumente → Dokument**: **"Erneut analysieren …"** (whole document).
- **Strg+K** on the contract: "Fehlende Angaben im Dokument suchen".
- Shown only with permission `contract.reanalyze` and when an original document exists; otherwise the existing "Vertragsdokument hinzufügen" gap applies.

### 4.2 Dialog "Erneut aus dem Dokument erfassen"
- **Umfang**: ( ) *Nur fehlende Angaben* (default, checklist of the missing fields, all checked) · ( ) *Ganzes Dokument neu analysieren*.
- **Wo steht es? (optional)**: page selection ("Seite 4–5") – later also a marked passage in the PDF (phase 4).
- **Erweitert** (collapsed): *Dokument neu lesen (Texterkennung/Bild)* – suggested automatically when the first run had no OCR or little text; *Modell* – installed local models, current one preselected.
- Honest note: "Dauert einige Minuten. Sie können weiterarbeiten; die gepflegten Daten bleiben unverändert, bis Sie Ergebnisse übernehmen."
- Button **"Suche starten"**.

### 4.3 While it runs
- Banner in the contract header: "Dokument wird erneut ausgewertet … (gestartet 14:02, Modell qwen3-vl:8b)" with **Abbrechen**.
- One run per contract at a time; with one GPU, runs are queued ("Wartet – 1 Analyse vor dieser").
- When done: bell notification "Neue Angaben für Vertrag X gefunden (3)" linking to the comparison (Direkt zur Stelle).

### 4.4 Result: "Ergebnis prüfen" (comparison)
One table, grouped, each row with source quote + page (click → PDF highlight):

| Group | Example | Default |
|---|---|---|
| **Neu gefunden** (field was empty) | Vertragsbeginn: – → 01.01.2025 (S. 4) | checked |
| **Abweichend vom KI-Wert** | Kündigungsfrist 3 → 6 Monate | not checked |
| **Abweichend von gepflegtem Wert** (human) | shown as proposal only | not checked, needs explicit choice |
| **Gleich / bestätigt** | collapsed ("7 Angaben unverändert") | – |
| **Nicht erneut gefunden** | current value is **kept**, never cleared | – |

Actions: **"Ausgewählte übernehmen"**, "Alle neu gefundenen übernehmen", **"Verwerfen"**. Afterwards: toast + deadlines/costs recalculate; applied facts appear in "KI hat N Angaben übernommen" and need the normal review (critical facts always need a person).

If nothing new was found: "Keine zusätzlichen Angaben gefunden." plus next steps as links: *Andere Seite angeben*, *Anderes Modell versuchen*, *Selbst erfassen* (→ `?feld=`).

## 5. Technical design (extend, no parallel pipeline)

### 5.1 Data
- New table `contract_reanalysis` (org-owned): `id`, `contract_id`, `document_version_id`, `mode` (`missing_fields` | `full`), `fields` (jsonb), `page_hint` (jsonb), `reread_document` (bool), `provider_id`/`model_id`, `status` (`queued` | `running` | `ready` | `failed` | `applied` | `discarded` | `cancelled`), `candidate_extraction_id` (FK `extraction`, not accepted), `summary` (counts per group), `requested_by`, timestamps, sanitized `message`. Migration with the usual naming; FK onto populated tables `NOT VALID`.
- The candidate is a normal `extraction` row (with evidence) that is **never** referenced by `contract.accepted_extraction_id` until applied.

### 5.2 Processing
- `DocumentProcessingService.reanalyze_document(..., focus_fields, page_hint, reread, model_override, candidate=True)` – same path, new parameters:
  - `reread=True` skips `_load_cached_canonical` and stores a new canonical artifact.
  - `model_override` must be an installed, available local model; otherwise fail closed (no fallback). `AIService` still pins exactly one model per run.
  - `candidate=True`: run harness + evidence resolver + financial gate + schema validation as today, save the extraction, **stop before** `accept_extraction`/`project_contract`/`sync_from_extraction`.
- `HarnessV3.analyze(..., focus_fields=None, focus_pages=None)`: only packs whose selectors cover a focus field; catalog limited to the focus fields; pages = hint pages first, then `_pack_pages` with `fallback_all`; short field-specific guidance ("Look for the contract start; it may be phrased as 'Beginn der Leistungen', 'tritt in Kraft' …"). Deterministic source signals unchanged.
- **Background execution**: `POST /api/contracts/{id}/reanalysis` returns 202 + run; a single worker processes the queue (advisory lock, one GPU run at a time); `GET /api/contracts/{id}/reanalysis/current`; `POST …/{run}/cancel`. Org scope + `contract.reanalyze` checked before queuing (no model call for foreign contracts).

### 5.3 Compare and apply (code, not AI)
- `register/reanalysis.py`: pure `compare(current_contract, provenance, accepted_extraction, candidate) -> rows` (group, current value + origin, new value, evidence).
- `apply(run, selected_keys, actor)`: build a merged extraction = accepted facts + selected candidate facts (with their evidence), accept it through the **existing** acceptance + calculation path with `replace_missing=False` and `sync_from_extraction(..., replace_ai_values=False)` for unselected keys; human fields get only `ai_proposed_value` unless explicitly chosen. Locks the contract row; 409 if the accepted state changed since the run started (existing `expected_accepted_extraction_id` check).
- Activity log: "Erneute Erfassung gestartet / übernommen (Felder …) / verworfen", plus `FactReview` states reopen for changed facts (existing material-change logic).

### 5.4 Permissions and safety
- New `contract.reanalyze` → admin, contract_manager (decision 8.2). Model choice only with the same permission.
- Confidential contracts via `scoped_contract_ids` as everywhere.
- Contract text stays local; providers remain localhost-only.

## 6. Phases

| Phase | Content | Tests |
|---|---|---|
| **1 – Safe foundation** | Table + migration, candidate mode, background queue, compare + apply/discard API, permission; UI: "Erneut analysieren …" in Dokumente (whole document, options *neu lesen* and *Modell*), run banner, comparison screen. The existing direct-accept `reanalyze` route switches to candidate mode (no more silent clearing). | Never clears existing values; human values only as proposal; stale-state 409; cross-org 404 before model call; viewer/reviewer 403; one run at a time. Vitest for dialog + comparison; e2e with mocked provider. |
| **2 – Targeted search** | `focus_fields`/`focus_pages` in the harness; "Nur fehlende Angaben" mode; page hint; "Im Dokument suchen" next to empty fields. | Harness: only focus packs called, catalog limited, hint pages included; benchmark comparison on the local benchmark set (no real contracts in the repo). |
| **3 – Integration** | "Was fehlt noch?" button, Strg+K command, bell notification with link, history entries, docs (`FRONTEND_CONVENTIONS`, integration map, `PROJECT_PROGRESS`). | e2e journey: missing start date → search → compare → apply → gap disappears. |
| **4 – From the PDF (optional)** | In the PDF viewer, mark a passage → "Als Vertragsbeginn übernehmen": the quote and page become the evidence, code parses the value (date/amount/duration normalizers), the field is saved as `manual` with evidence. Highest accuracy, no model needed. | Parser + evidence tests, accessibility of the selection flow. |

## 7. Measuring "better results"
- Per run: fields searched, found, applied, rejected → shows whether targeted search really helps.
- Applied candidates become cases for the extraction benchmark (WP2.4), locally only.

## 8. Decisions needed

1. **Applying**: always via the comparison screen (recommended) – or automatically fill *empty* fields with newly found values?
2. **Who may start it**: admin + contract_manager (recommended) – or also reviewers?
3. **Model choice in the dialog**: yes, for the same roles (recommended) – or always the configured model?
4. **Phase 4 (mark passage in the PDF)**: include (recommended, it is the most reliable path when the AI keeps missing a value) – or later?
