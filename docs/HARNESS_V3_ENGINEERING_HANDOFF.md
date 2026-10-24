# Harness V3 — Engineering Handoff

**Datum:** 10.09.2026 (offizieller GitHub-Migration-Snapshot `MedFlux official repository baseline`)

This document preserves the engineering state of the Contract Intelligence **Harness V3** work so another engineer or AI agent can continue from this repository without the original OpenCode conversation. It is the authoritative continuation point for the V3 validation effort.

Related living documentation: `docs/PROJECT_PROGRESS.md` (PR-6 Phase 3 + PR-6 Real-Model Validation entries) and `AGENTS.md` (project rules). Do not duplicate their content here; this file focuses on the migration-era state and session-only knowledge.

---

## 1. Current architecture

**Semantic authority is the local model (Qwen). Deterministic code never decides semantic meaning — it validates, calculates, enforces integrity and persists.**

- **Qwen (Ollama `qwen3-vl:8b-instruct`) is the semantic authority:**
  - decides document type/purpose, party roles, selections vs alternatives, applicability labels, number-string roles, authority/precedence, contract-global meaning.
- **Deterministic code:**
  - validates evidence (`GroundingBatch`, quote canonicalization against full block text),
  - calculates deadlines, cost aggregation, warning levels (never by the model),
  - enforces integrity (unknown-source-ref rejection, field-type strictness, number-role guard),
  - persists / owns the reanalysis lifecycle.
- **Perception / OCR / layout tools are helpers, not authorities:**
  - `PyMuPDF`/RapidOCR layout + `vision.py` region images are reading aids only; they may be ignored when the text layer is sufficient.

### V3 pipeline (stages in order)

```
perception
  -> section understanding        (visual compute, PROVISIONAL, no global meaning)
  -> global understanding          (ONLY contract-global authority)
  -> contract map                 (observations, selections, number roles, precedence)
  -> applicability / cross-clause reasoning
  -> family resolution            (identity, equipment, dates, termination, costs, payment, services, sla)
  -> evidence grounding           (entailment + quote canonicalization)
  -> deterministic calculation / persistence
```

Non-negotiable invariant: **Qwen decides; code applies.** Never move applicability / authority / selected-plan / number-role / cross-clause meaning into deterministic business rules, and never add contract-specific rules or benchmark hacks.

## 2. Production state

- `harness_engine=v2` (v2.1) **remains the default** in `config.py`.
- Harness V3 exists (`get_harness_class` returns `HarnessV3` for `harness_engine="v3"`) but is **NOT production-ready/default** — the real-model validation failed.
- **No DB/schema change** resulted from the V3 work; the accepted extractions baseline is untouched.

## 3. Real-model validation state (as of this migration)

Validation is read-only by design: runs are never persisted/accepted; the production DB (SQLite at `backend/data/database/`, which is gitignored) and the accepted v2.1 extractions stay untouched.

### Accutron iterations (default config 8192 / 1800 output / 32 calls, `qwen3-vl:8b-instruct`)

| Iteration | Calls | Wall | Key result | Walk of states |
|---|---|---|---|---|
| BEFORE (no fix) | 19 | 373 s | no contract, 81× ContextOverflow | sections only page 5; resolves page-5-only |
| r1 (first fix pass) | 21 | 607 s | no contract | sections pages 3–5; base still ~5.8k, most segments abstain |
| r2 | 12 | 641 s | pipeline TypeError crash | `compact_sections` serialized pydantic `NumberRole` → crash (fixed) |
| r3 | 27 | 1014 s | no contract | section shrink enabled; global stages overflow |
| r4 | 27 | 1014 s | no contract | compact sections/global; segments still page-5-only |
| r5 | 26 | 985 s | no contract | ContractMap rejected (unknown refs) → downstream starved |
| r6 (current) | 32 | 1559 s | no contract, **budget-exhausted** | sections+global fit; identity resolved in 9 segments (18 calls); all later families starved |

Ground truth reached: perception is correct (Guards/alternatives found), deterministic number-role guard works (`Bestellung 452664` → `order_number`). **No grounded contract** was produced in any iteration.

### ABIOMED

- NOT rerun after the Accutron failure (the agreed sequence is Accutron first, stop on failure).
- Prior baseline (pre-fix, default config): 31 calls, 940.8 s, 45 abstain_overflow, no contract; perception correctly found the staged schedule (year 1: 0 EUR, years 2–4: 8.000 EUR); sections only for page 9.

### Exact current blocker (Accutron r6)

1. **ContractMap wholesale rejection (dominant):** one hallucinated source ref in a ContractMap observation raises `ValueError("ContractMap contains unknown source references")` → the **whole map is discarded** → 0 number_roles / 0 selections, applicability starved. Recurred in r5 and r6. This is pre-existing V3 validation strictness, not part of the approved fix.
2. **32-call budget structurally insufficient:** identity alone needed 14 segments (9 ran = 18 calls). The full pipeline needs ~45–55 calls (8 families × resolve+ground + 6 vision + ~5 sections + 2 global + 1 applicability + recovery). After budget exhaustion every later `call()` raises `ContextOverflow` that is indistinguishable at the log level from input overflow.
3. **Output truncation (1800-token cap):** section page 1 and some resolve responses end with `done_reason=length` → one consumed call + lost payload (recorded, not silent).
4. **Applicability starvation when the map is rejected:** with an empty map there is no compact semantic state to reason from.

Diagnostics (`context_decisions`, per-call `estimated_prompt_tokens`, `issues`) are preserved in the temp benchmark JSONs of the original session (`bench_accutron_v3_fixed*.json`); see §11.

## 4. Deferred work — NOT IMPLEMENTED (needs explicit approval)

- **A — ContractMap invalid-ref tolerance:** instead of discarding the whole map on one unknown ref, drop only the observations whose `block_refs`/`related_refs` contain unknown ids, keep the valid remainder, and log an issue. Constraints: stays generic (no contract-specific rules), Qwen remains authority, unreferenced facts are never invented.
- **B — Dynamic family packing / reserve tuning:** reduce per-family `extra_reserve` (currently 1300 in `planner.segments`/`pack_ranked`) so families resolve in 1–2 segments instead of ~9, and/or prioritize the core families (identity/costs/termination) inside the call budget. Constraint: any ordering must not invent or drop facts.
- **C — Benchmark-only higher call budget:** run the second benchmark with a raised `harness_max_calls` (e.g. via the driver env override `HARNESS_MAX_CALLS`). Constraint: benchmark-only; do not change production defaults, and keep runtime context at the hardware-safe level (§7).

Apply A, then B, then rerun Accutron; then C if needed. Do not implement any of these until the user gives the go-ahead.

## 5. Benchmark ground truth (facts used for engineering validation — not the contract text)

These are the acceptance criteria for a future real-model run.

### Accutron
- **Guard TOP selected** (protection plan).
- **1.650 EUR/year applicable** (Guard TOP).
- **350 / 1.250 / 1.075 EUR are alternatives**, not part of the applicable total.
- Minimum term **2 years**; **48 h** response time; repairs **free** in the plan.
- **452664** is **order/reference**, NOT the contract number (deterministic role guard verified).

### ABIOMED
- Contract number **40015645**.
- Supplier **ABIOMED Europe GmbH**; customer **Krankenhaus Nordwest**.
- Term **01.04.2025 – 31.03.2029**, **4 years**, **no automatic renewal**.
- Scheduled fixed prices: year 1 **0 EUR**, years 2–4 **8.000 EUR each** (0/8000/8000/8000).
- Deterministic fixed total **24.000 EUR** across the term.
- Variable: **2.226 EUR per call**, plus **50 % weekend/holiday surcharge**.

## 6. Hardware / runtime constraints (do not ignore)

- Target/MVP hardware: **RTX 3070 8 GB**, Ryzen 7 5800X, 32 GB RAM.
- Model: **qwen3-vl:8b-instruct** (6.1 GB, ~8 GB VRAM).
- `ollama ps` observes **`num_ctx=8192`**, CPU/GPU split 20/80.
- **A 65536-token context request crashed the Ollama server** (`AIUnavailableError`).
- **Do not solve V3 by blindly increasing context.** The planner already sends `options["num_ctx"]`; the hardware window is the real limit. Oversized prompts must be rejected by the planner pre-call (they are) and the pipeline must degrade stage-by-stage honestly.

## 7. Testing state

- Focused V2/V3 tests: `pytest tests/test_harness_v3.py tests/test_harness_v2.py` → **30 passed** (15 + 15). Engine selection verified (v2 default / v3 explicit).
- Comprehensive backend suite baseline at HEAD `a670f98`: **626 passed / 28 failed — all 28 are PRE-EXISTING failures** (reproduced at the friend-review snapshot HEAD), NOT caused by V3.
- **Do not describe the full suite as green.**
- Conventions: backend tests run under `backend\.venv` and use an isolated test schema; tests must never pollute the production DB.

## 8. Git / data safety rules (survive the migration)

- **Never commit:** `.env` / `.env.*` (`.env.example` stays), `backend/data/` (contract PDFs, DBs), any `data/contracts`, `data/database`, `data/backups` (except `.gitkeep`), `data/benchmark*`, PostgreSQL data dirs, `*.gguf`/`*.onnx`/`*.pt` model weights, `.venv`, `node_modules`, `.next`, `__pycache__`, `.pytest_cache`, coverage, `*.tsbuildinfo`, logs.
- Tests run in an isolated schema; **a fresh production DB must remain empty**, and accepted extraction (`Contract.accepted_extraction_id`) is never touched by benchmarks or tests.
- The benchmark driver is read-only by design — it never writes runs/acceptance to the DB.
- Secrets are only ever documented via `.env.example`; anything real stays local and ignored.

## 9. Reanalysis lifecycle and accepted-truth safety

- Accepted extractions are the "true" persisted result a contract is re-evaluated against.
- Reanalysis must go through the documented lifecycle; unaccepted runs are diagnostics only.
- V3 work introduces **no** lifecycle change; if it ever becomes default, its outputs still persist through the same acceptance path.
- Never mutate, delete, or "fix" accepted data as a side effect of benchmark or validation work.

## 10. Migration facts (this snapshot)

- New official remote: `https://github.com/medfluxdev/Medfluxdev.git` (origin), official branch `main`.
- Previous review remote preserved under a descriptive backup name (see `git remote -v`).
- Snapshot commit: `MedFlux official repository baseline` — includes all current source changes, the V3 harness files, tests, documentation, and new docs below. No history rewriting, no force push.
- Local project directory is unchanged: `C:\Users\JAMAL\Desktop\Medflux`.
- V3 remains unfinished and v2 remains default (see §2, §4).

## 11. Session-only engineering knowledge (no longer in-conversation)

- **Benchmark driver:** a standalone read-only script that drives the current production analysis path (`DocumentProcessingService._build_canonical` + the exact harness invocation `_process_stored` uses) against the two stored scanned PDFs. It supports env overrides `HARNESS_CONTEXT_TOKENS`, `HARNESS_OUTPUT_TOKENS`, `HARNESS_MAX_CALLS` and writes JSON results (diagnostics included). It never persists.
- **Stored filename quirk:** the Accutron contract is stored as `Accutorn Service Vertrag.pdf` (typo with "n"). The driver's name filter must be `--name accutorn`.
- **Document sizes:** ABIOMED 9 pages / 123 blocks / ≈9.8k est. tokens; Accutron 5 pages / 99 blocks / ≈7.3k est. tokens.
- **Planner math:** `estimate_tokens = len(bytes) / 3 * 1.35`; `input_budget = capacity − output_tokens − 512`; at defaults (8192 / 1800) input_budget = **5880**. `planner.check` records `include` vs `abstain_overflow` per purpose.
- **Per-family base overhead (measured):** ≈2.2–2.6k est. tokens for most families (identity ≈2.6k, costs ≈4.2k when option clusters are included). After the context-plumbing fix, resolve segments fit at ~4.5–5.1k.
- **Call-usage endgame:** infrastructure alone (vision 6 + sections ~5 + global 2 + applicability 1) ≈ 14 calls before any family resolution; each family costs ≥2 (resolve + ground). This is why the 32-call default is the hard cap to reconsider (deferred work C).
- **Commitment principles for the fix work that was implemented:** per-segment local context (`assemble_bounded`, per-page `sections_context_pages`), compact `semantic_state`/`compact_sections` helpers, dynamic section-batch shrinking on both input overflow and output truncation, and `extra_reserve` on `planner.segments()` / `pack_ranked()`. All of it stays generic — no contract-specific words, no semantic decisions in code.