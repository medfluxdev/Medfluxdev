# MedFlux isolated trial — first Frankfurt import / analysis failure

Date: 2026-10-01. Reporter: Jamal. Evidence: screenshot of MedFlux import-result UI provided in conversation. This report transcribes visible evidence; the screenshot itself is NOT archived as a binary in GitHub by this commit.

## Runtime context (from OpenCode local trial report)
- Active checkout `feature/integrated-release-build-20260929` at `7c9c0a0c7a623538a7a16677b1d5f4b0aabd6fd9`; immutable stable snapshot points to same commit.
- Isolated DB `medflux_trial_20261001` on WSL PostgreSQL 18.6 `127.0.0.1:55432`; do not touch 5432.
- Ollama configured with `openbmb/minicpm-v4.5:latest`, reported `completion, vision` and `/api/ai/status available:true` during startup.
- Frontend `localhost:3000`, backend `127.0.0.1:8000`, auth enabled, insecure dev false.

## Screenshot observations
- Import summary: 1 imported, 0 successful analyses, 1 analysis failure, no duplicates.
- The visible document label begins `KH RAV-00074 Optis M Next LFZ 04.06.2025 - 03.06.2029.pdf` and references Frankfurt/Nordwest. Confirm exact stored original filename/document ID from logs rather than relying on this visual transcription.
- UI shows `فشل التحليل` (analysis failed), `مطلوب الامتحان` (review required), manual-review link and reanalysis button.
- File storage/import succeeded; AI analysis acceptance did NOT. **Do not equate an imported file with an accepted contract analysis.**
- Import screen did not expose the required organizational selection workflow described in Ahmed's supplied organizational requirements document.

## Root cause: UNKNOWN
A model failure is **not established** by this screenshot. Possible failure stages include local PDF page rendering/OCR, Ollama request/model, response parsing/schema, source-evidence checks, bounded-call limits, and persistence. These are investigation hypotheses, not findings.

## Safe diagnostic plan
1. Preserve trial database, original PDF, current model, current process logs and failed draft. Do not re-import/reanalyze yet; no destructive cleanup.
2. Inspect existing `trial-logs` for this exact import's request/trace and correlate its document ID with backend analysis error. Redact credentials, tokens and patient/contract-sensitive text in shared excerpts.
3. Check model name and availability at failure time; distinguish transport/timeouts, OCR/vision errors, extraction/validation rejection and persistence errors.
4. Compare recorded per-page evidence and analysis state with the UI result. Report exact failing stage and safe minimal fix, if identifiable.
5. Only after diagnosis and Jamal's approval, rerun the same document on the isolated DB; optionally compare against a suitable installed Qwen vision model. Do not claim `qwen3.5:4b` has image support without checking its local model metadata.
6. Separately implement missing organizational import fields to match the supplied source requirements; do not invent new organizational policy.

## Acceptance
Report actual error/trace, cause, any proposed code change, and one repeatable focused test. Keep original GitHub stable branch and the current local trial intact until explicitly authorized.
