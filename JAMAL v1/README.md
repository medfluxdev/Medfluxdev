# JAMAL v1 — Scanned Contract Intelligence Sandbox

This folder is an isolated experiment for MedFlux scanned/image-only contracts.

## Purpose

Improve extraction quality for signed hospital contracts that arrive as scanned PDFs without changing the current production pipeline.

The sandbox must preserve the MedFlux trust model:

> Vision understands layout → OCR contributes text → code verifies → evidence proves → Contract360 stores.

## Non-goals

- No production integration yet.
- No database/schema changes.
- No frontend changes.
- No cloud OCR or cloud AI.
- No ABIOMED-specific extraction rules.
- No silent model/provider switching.
- No acceptance of a fact that cannot be tied back to source evidence.

## Existing MedFlux components to reuse

The current code already contains important building blocks:

- `backend/app/ai/harness/document.py`
  - `DocumentModel.visual_pages`
  - `Block.needs_vision`
- `backend/app/ai/harness/vision.py`
  - bounded page and region rendering
- `backend/app/ai/harness/v3_perception.py`
  - provider-neutral perception hints
- `backend/app/ai/harness/v3.py`
  - semantic passes
- current evidence verification and fail-closed behavior

JAMAL v1 does not replace these blindly. It proposes a cleaner scanned-document routing/fusion layer around them.

## Experiment target

Start with the ABIOMED scanned contract and compare the current pipeline against JAMAL v1 on pages that stress:

- identity / legal names
- service scope
- pricing tables
- service contact
- evidence/page anchoring

The benchmark must measure extraction quality, evidence correctness, hallucinations, latency, and model/vision calls.

## Files

- `ARCHITECTURE.md` — target architecture and invariants
- `hybrid_pipeline.py` — provider-neutral prototype/orchestration skeleton
- `ABIOMED_BENCHMARK.md` — evaluation protocol and acceptance criteria

## Safety rule

Do not merge this folder into the production pipeline until OpenCode has run an isolated benchmark and produced a before/after report.
