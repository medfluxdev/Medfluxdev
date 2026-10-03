# MedFlux Reliability Audit – 2026-09-15

## Scope

Repository/runtime audit focused on the hospital contract-analysis path: startup/readiness, PostgreSQL, import/idempotency, Document Intelligence, OCR fallback, Harness engine selection, multimodal Ollama transport, evidence binding, persistence, Contract 360 failure semantics, frontend timeout/error states, tests, CI and release gate.

This audit records defects found in this pass and corrective controls. It does not replace real-contract UAT. A green automated suite proves covered invariants; it cannot certify semantic accuracy for every hospital contract.

## Findings and fixes

1. **Critical – image-only PDFs were rejected before AI.** The orchestrator required text units before selecting the Harness. PDFs with real pages now reach V3 local vision.
2. **Critical – production default was V2/text-only despite V3 vision code.** Defaults are now Harness V3 and `qwen3-vl:8b-instruct`; V2 requires explicit `v2-compat`.
3. **Critical – stale private `.env` values could keep V2 active after an update.** Historical `HARNESS_ENGINE=v2` now migrates safely to V3 at engine selection.
4. **Critical – page-batch vision could suppress the only quotable path for a fully scanned page.** Textless visual blocks retain direct bounded transcription.
5. **Critical – V3 observed images but could not accept image-only facts because evidence lookup searched only canonical block text.** It may now fall back only to exact `VisionObservation.visible_text`; descriptions/inferences never count as evidence. Vision-only evidence is review-required.
6. **High – semantic grounding did not receive exact visual transcription.** Grounding escalation now receives those transcription rows alongside canonical context.
7. **High – frontend styled `analysis_failed` as successful/green import.** It is explicitly labeled as analysis failure with critical tone.
8. **High – synchronous local AI browser requests timed out after 120 seconds.** Import/retry/reanalysis use a bounded 30-minute client window.
9. **High – Windows launcher assumed a fixed Docker container and checked only process liveness.** It now tries an existing Windows PostgreSQL service, then an existing local cluster without initialization/overwrite, then Docker Compose, and uses `/ready` for database-aware backend readiness.
10. **High – primary OCR/layout Document Intelligence could become a single point of failure.** PDF processing now falls back locally to PyMuPDF page discovery so V3 can still render and analyze the protected original; no cloud fallback is used.
11. **Medium – runtime docs/defaults described V2 + text model as production.** Runtime defaults, `.env.example`, README and architecture docs are aligned with V3 + local vision.
12. **Regression gap – the prior “scanned” V3 test still contained text on page 1.** Coverage now includes a truly textless scan and review-required visual evidence.

## Safety invariants retained

- AI remains local; no cloud/external AI service was introduced.
- Deterministic code remains authoritative for calculations and warnings.
- Missing/unresolved facts are not fabricated.
- Duplicates remain idempotent; retry/reanalysis stays explicit.
- No original contract or database record is deleted by these fixes.
- Vision-derived evidence is never promoted to unreviewed certainty.

## Release/UAT gate

Before a hospital demonstration, use the same real contracts intended for UAT and verify:

- Ollama logs show actual model calls during a new image-heavy import.
- diagnostics show `prompt_version=harness-v3`, `ai_call_count > 0`, expected vision/section stages and selected vision model.
- Contract 360 values agree with the source and critical values navigate to evidence.
- image-only facts are visibly review-required.
- duplicate/retry/reanalysis behavior is explicit.
- PostgreSQL/Ollama/backend/frontend restart cleanly through the supported launcher.
- no analysis failure is presented as successful truth.
