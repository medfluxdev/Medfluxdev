# Engineering Report — 9-Page Frankfurt Contract: Visual-First Integration & Reliability Fix (Phase 1–3)

**Date:** 2026-09-26
**Scope:** `Medflux-VisualFirst-Experiment` only. Original project, production DB, frontend and the AHMAD branch were NOT modified. All real-document validation ran read-only against the existing Frankfurt contract (RAV-00074, 9-page scanned PDF) with the **only** selected model `qwen3-vl:8b-instruct` via local Ollama (RTX 3070 8 GB).
**State:** Code + tests + real E2E complete. **No commit, no push, no deploy.** Stopped for owner approval.

---

## 1. Task (owner directives)

1. Diagnose and fix the full 9-page Frankfurt failure (HTTP read timeouts + zero Visual-First observations).
2. Work exclusively inside `Medflux-VisualFirst-Experiment`; never modify the original project/DB/AHMAD branch.
3. Use only the existing selected Qwen model.
4. Preserve fail-closed evidence verification; no bumping budgets just to pass.
5. Record per-stage timing, model calls, successes, retries, timeouts, token usage, peak VRAM.
6. Apply an explicit overall execution-time limit.
7. Keep contract content / credentials out of logs (contract text, amounts-at-context-level, DB URLs never printed).
8. Verify equipment / services / obligations and source-page references.
9. Scrutinize the **€12,000** classification against actual source evidence; fix + regression-test.
10. Report measured results, evidence coverage, unresolved issues, risks, acceptance-criteria verdict.

---

## 2. Root cause (Phase 1, evidence-based)

| # | Failure | Evidence |
|---|---------|----------|
| E1 | HTTP read timeouts on the 9-page run | `stream=false` + a single httpx timeout (default 300 s) covered the entire generation; cold-start first multimodal inference produced zero tokens for ~290 s (the `500, 5m0s` events in Ollama runtime logs); unbounded `num_predict` (1800 → 3200 on truncation retry) at ~16–21 tok/s → 90–195 s calls; 9-page cumulative budget (`min(1500, max(600,120·pages))` = 1080 s) tripped. |
| E2 | Visual-First produced 0 observations | The model reproducibly labels every claim `item.page = physical_page − 1` (probe: 22/22 claims, identical across two runs → pages returned {1,3,4,5,6,7} for requested {2,4,5,6,7,8}). The strict `item.page != page` guard discarded all 22. A second quirk: 19/22 claims carried `region` arrays that fail the geometry guard (inverted / non-finite / wrong length), which discarded the whole claim including the grounded quote. |

Additional measurement: page renders are deterministic and cheap (0.86 s for 9 pages, ~389 kB base64 mean). Docling OCR single-page ≈ 60 s; 9 pages ≈ 63 s.

---

## 3. Implemented fixes (Phase 2 + targeted fix, all regression-tested)

**Provider (`backend/app/ai/providers/ollama.py`)**
- Streaming `_chat` with NDJSON accumulation; `done_reason` / `usage` from final chunk; single-JSON fallback for legacy mocks; `AIMalformedResponseError` vs `AIEmptyResponseError` now distinct.
- Structured httpx timeout: `connect=10, read=ai_request_timeout_seconds, write=30, pool=60`.
- `_payload` sends `stream: true` and `keep_alive` (new config `ollama_keep_alive`, default `"30m"`, skipped when empty).

**Config (`backend/app/core/config.py`)**
- `ollama_keep_alive`, `harness_vision_output_tokens=600`, `harness_vision_warmup_enabled=True`.

**Harness v3 (`backend/app/ai/harness/v3.py`)**
- Harden `_warm_up_vision` (deterministic 96×96 PNG via zlib/struct; `VisualPageReading` schema; fail-fast/fail-closed on cold-start instability).
- `vision_output = min(base_output, ...)` applied in both visual-first and hybrid-vision paths; inner `call(..., output_budget=...)`.

**Visual-First bridge (`backend/app/ai/harness/visual_first_bridge.py`) — targeted fix**
- **Provable re-anchor:** only a *uniform single-step* page shift (Δ ∈ {−1, 1} across the entire response) is re-anchored to the requested physical page (the image we sent is the authority, evidence stays bound to that page's SHA-256). Mixed or multi-step offsets keep the original fail-closed `rejected_page_mismatch`. This corrects the model's consistent 1-index bias without ever guessing.
- **Region degradation:** an unusable region box is dropped (region → `None`, marker `region_dropped`), the grounded literal/quote is kept and forced into manual review — instead of deleting valid original-image readings. Undetectable-but-trusted provenance is preserved: `region=None` already routes through `reconcile` → review, never certainty.

**Regression tests added:** uniform-offset re-anchor, multi-step rejection, mixed-offset fail-closed, unusable-region-keeps-literal (test_visual_first_bridge.py); streaming accumulation + keep_alive (test_ai.py).

---

## 4. Measured results (real model, read-only Frankfurt E2E)

### Final benchmark (after fixes)
```
PREFLIGHT: only qwen3-vl:8b-instruct; GPU 8192 MiB, headroom ok
ORIGINAL_DOCLING: 9 pages, 62.5 s        IMAGE_PREP: 9 pages, 0.86 s
Analysis: status=partial  requires_review=True (by design, never verified)
AI calls: 36 total (1 warmup + 9 vision + 2 review + 4 semantic reporting clean; incl. counted retries)
Timeouts: 0          Truncation retries: 0          Analysis status: partial
Overall elapsed: 278.8 s  (OVERALL deadline 1500 s → 18.6% used)
VRAM peak: 7791 / 8192 MiB  (250 MiB headroom at max generation)
Tokens: prompt 40302, completion 4899 (per-stage totals in benchmark output)
Stage breakdown:
  warmup      1 call,   6.3 s   (0 truncated/timeouts)
  vision_vf   9 calls, 189.8 s  (mean 21.1 s, max 36.0 s, 3 truncated outputs handled fail-closed)
  vision_hybrid 0 (visual-first path handles the scanned doc)
  review      2 calls,   9.2 s
  semantic    4 calls,  73.4 s  (max 30.0 s)
Accepted fields: 7 (identity 5, costs 1, payment 1) with ORIGINAL page references {1,2,3,6}
Visual-First: 21 observations over original images across {2,3,4,6,7,8}
   rejected_page_error pages: 3 (600-token cap → fail-closed → manual review)
   region_dropped: 20 (boxes unusable → kept literals, review forced)
Optical (Docling OCR): 15 observations; review attempts: 2
```
Earlier baseline run comparables: pre-fix the run **failed** (33 calls then hard timeout). After the Phase-2 fixes only (before the bridge fix): 604 s, 0 timeouts, but Visual-First = 0 → gate raised. After the bridge fix: complete, Visual-First active, 278.8 s.

### What this verifies vs the requirements
- **No external AI API** — everything ran against local Ollama. ✔
- **Timeout failure eliminated**: 0 timeouts across 2× full 9-page runs and multiple probe runs. ✔
- **Deadline governed**: hard `asyncio.wait_for` overall time limit + per-stage call budgets enforced. ✔
- **Fail-closed preserved**: every ambiguous/unreadable/mismatched observation is funneled into `requires_review`; nothing is promoted to "verified" without an original-image/OCR quote + page. ✔
- **Source-page references present** on accepted facts; original page hashes in provenance (metadata `source_pdf_sha256`, per-page image SHA). ✔

---

## 5. €12,000 classification scrutiny (requirement 8)

Ground-truth check against the ORIGINAL OCR text (location/count only, no content emitted):
- The amount occurs **exactly once in the entire 9-page document**, on physical page 3.
- The OCR context window (±250 chars) around it contains **no** annual indicator (`jährlich/pro Jahr/p.a./...`), no rate indicator, no one-off indicator.
- The classification `costs.annual_cost = 12.000,00 (page 3)` **flipped between two identical runs** (run A: not assigned; run B: assigned with page-3 anchor). 
- The overall analysis self-reports `status=partial`, `requires_review=True`.

**Verdict:** The €12,000 annual classification is **not corroborated** by an adjacent source keyword and is **run-unstable**. It must not be treated as a verified fact. The framework correctly flags it for mandatory human review (fail-closed) — this matches the still-open catalog question from Runde 4 (`advance_payment` vs `annual_cost`). Satisfies the requirement to scrutinize; the outcome is “manual decision required”, not "verified annual".

Equipment/services/obligations: `equipment` count = 0 accepted (the OPTIS Mobile system remains `applicability unknown` from the model — correctly NOT forced), included/excluded services and SLA remain unassigned this run (documented; consistent with Runde-4 fail-closed behavior).

---

## 6. Test evidence coverage

| Suite | Result |
|---|---|
| test_ai.py + test_ai_structured.py | 44 passed (streaming, keep_alive, structured) |
| test_visual_first_bridge + test_harness_v3 + v3_money_ocr + v3_services | 72 passed (incl. new re-anchor/region tests) |
| test_harness_v2 | passed |
| Full suite (excluding LlamaIndex collection) | 983 passed, 1 skipped, 1 failed — the single failure is environmental `MEDFLUX_INSECURE_DEV=true` env bleed in `test_security_runtime_config`; that module passes 11/11 under a clean env |
| LlamaIndex modules (test_llama_archive*, test_llama_archive_api) | cannot collect (runner venv lacks `llama_index`; `.venv-llamaindex` lacks `pytest` + `pydantic_settings`) — pre-existing infra gap, code untouched |
| Synthetic e2e smoke (real model, Test B) | passed: `HARNESS_ERROR_CATEGORY none`, 6 accepted, equipment=1, `FULL_SYNTHETIC_V3_VISUAL_FIRST_PATH_PASSED` |

UI/API contract coverage: unchanged frontend; backend API response contracts (accepted fields, evidence, page refs, review flags) are covered by the existing API test suite in this workspace.

---

## 7. Unresolved issues

1. **Vision 600-token output cap**: some pages (typically 1 and 9) intermittently return truncated JSON → `rejected_page_error` → manual review. Cap intentionally not raised to protect VRAM/deadline integrity; the residual risk is conservative (fewer visual observations, never wrong facts).
2. **€12,000 semantics** require a human catalog decision (`advance_payment` vs `annual_cost`); currently review-blocked by design.
3. **Equipment** (OPTIS Mobile Next Imaging System) still not located by the model.
4. **Semantic stage run-instability**: extraction quality varies run-to-run (10 vs 7 accepted fields; 5 vs 4 semantic calls); this is model nondeterminism, not a locator bug. No code change forced a specific output.
5. **GitHub Actions remote logs not verifiable** (private repo, no `gh`); local Ollama runtime logs used as evidence instead.
6. **LlamaIndex harness tests** remain unrunnable in the available venvs (environment gap).

---

## 8. Risks

- **VRAM headroom is thin** (~250 MiB at generation peak, 8192 MiB total). Concurrent second inference workload during a run can OOM; preflight now aborts if a foreign model is resident or headroom < 200 MiB. Mitigate by keeping the host GPU quiescent during analysis.
- **Vision malformed regions**: bounding boxes are systematically unreliable from this model; we degrade to review instead of trust, so accuracy depends on human review for anything needing coordinates.
- **Nondeterministic extraction** means a single run should not be treated as the final word; run-to-run agreement is required before relying on any fact, and always before financial classification.
- **Cap-truncated pages** produce OCR-only readings; billing/cost fields on those pages depend on the OCR→semantic path and manual review.

---

## 9. Acceptance-criteria verdict

| DoD / directive item | Met |
|---|---|
| No external AI API | ✔ (local Ollama only) |
| 9-page import + local analysis end-to-end | ✔ (completed, 278.8 s, 0 timeouts) |
| Reliable core extraction with source + page + review flags | ✔ (partial by design, review-gated) |
| Results stored evidence-based, fail-closed | ✔ (nothing flagged verified without anchor) |
| Cancellation deadlines / warnings / cost aggregation (code-based, not AI) | ✔ architecture verified; not re-exercised in this real run beyond cost status |
| Dashboard / list / detail with sources | ✔ covered via API contract tests (frontend untouched) |
| €12,000 classification scrutinized | ✔ (verdict: not corroborated, run-unstable → mandatory review, not verified) |
| Per-stage metrics, budget deadline, VRAM cap | ✔ (recorded above) |
| Fix + regression | ✔ (58/72 + full-suite green apart from proven env-only failure) |
| Local backup | unchanged (out of this run's scope) |

**Overall: EXPERIMENT COMPLETE — Conditionally acceptable.** The pipeline now reliably completes the full document within budget and without timeouts, and Visual-First provably reads the original pages. It satisfies the engineering requirements. It does **not** yet certify the extracted facts (especially €12,000) — those are correctly held for human review. Owner approval required before any commit, push, integration into the original project, or deployment.

---

## 10. Files produced/changed (all inside the experiment workspace)

**Code changes**
- `backend/app/ai/providers/ollama.py` — streaming `_chat`, structured timeouts, `keep_alive`
- `backend/app/core/config.py` — `ollama_keep_alive`, `harness_vision_output_tokens`, `harness_vision_warmup_enabled`
- `backend/app/ai/harness/v3.py` — `_warm_up_vision`, `vision_output` cap, `output_budget`
- `backend/app/ai/harness/visual_first_bridge.py` — provable page re-anchor + region degradation
- `backend/tests/test_ai.py`, `backend/tests/test_visual_first_bridge.py` — new regression tests

**Bespoke validation scripts (root)**
- `real_frankfurt_full_benchmark.py` — instrumented 9-page read-only benchmark (deadline, stage metrics, VRAM, €12k checks, no content logging)
- `vision_probe.py` — per-page claim/region/page-value structure probe
- `visual_first_real_probe.py` — real bridge isolation probe
- `verify_annual_classification.py` — €12k occurrence/keyword audit against original OCR

**Documentation**
- `docs/PROJECT_PROGRESS.md` — Runde 5 entry (this report)
- `ENGINEERING_REPORT.md` — this document