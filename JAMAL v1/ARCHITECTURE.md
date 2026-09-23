# JAMAL v1 — Hybrid Vision + OCR Architecture

## 1. Problem

Hospital contracts often enter the system only after both parties sign them. The retained copy is frequently a scanned PDF. A text-first pipeline therefore receives noisy OCR, flattened tables, missing structure, and weak provenance.

The objective is not “better OCR” alone. The objective is to make MedFlux understand the same visual relationships a human sees while retaining deterministic verification.

## 2. Target pipeline

```text
Document
  ↓
Page classifier
  ├─ text-native page ───────────────┐
  └─ scanned/image-heavy page       │
           ↓                         │
      bounded render                 │
           ↓                         │
   OCR/layout extraction             │
           +                         │
   vision understanding              │
           ↓                         │
      page fusion  ←─────────────────┘
           ↓
 semantic packs
(core / commercial / payment / operations)
           ↓
 evidence locator + verifier
           ↓
 deterministic calculations
           ↓
 Contract360
```

## 3. Core invariants

1. **Local only.** OCR and vision remain local.
2. **No hardcoded contract facts.** ABIOMED is only a benchmark.
3. **No model authority over calculations.** Dates/costs stay deterministic.
4. **No evidence → no accepted material fact.**
5. **No paraphrase-as-evidence.** Quotes must resolve to actual source text/region.
6. **Visual output is provisional.** Vision proposes structure/meaning; code verifies source support.
7. **Use the cheapest reliable path.** Text-native pages do not need full-page vision.
8. **Bound visual compute.** Render only relevant pages/regions at controlled resolution.
9. **Keep provider/model explicit.** No automatic silent model switching.
10. **Preserve auditability.** Page, region/bbox, method, confidence and review state remain traceable.

## 4. Page classification

Each page receives a deterministic routing record:

- `TEXT_NATIVE`
- `OCR_REQUIRED`
- `VISION_REQUIRED`
- `HYBRID_REQUIRED`

Signals may include:

- native text character count
- OCR method markers already present in canonical intelligence
- structural elements without usable text
- tables/forms/check boxes/stamps/signatures
- image-heavy page ratio
- text density and extraction quality

The classifier chooses compute strategy, not legal/commercial meaning.

## 5. OCR + Vision fusion

The fusion record should keep parallel evidence instead of replacing one source with another:

- native text
- OCR text
- OCR/layout blocks + bbox
- vision observations
- page image reference
- confidence/quality signals

Preferred source order for exact textual evidence:

1. native text with trustworthy coordinates
2. OCR/layout text with coordinates
3. visual region evidence when text cannot be recovered exactly

Vision can identify that “8.000 EUR belongs to Jahr 2”, but accepted structured values still need a verifiable page/region anchor.

## 6. Semantic passes

Keep the existing staged V3 approach, but feed each pack the smallest relevant fused page set.

### Core
- supplier
- customer
- contract number
- title
- service contacts

### Commercial
- recurring prices
- scheduled price ladders
- conditional/variable charges
- VAT only if documented

### Payment
- invoicing
- payment terms
- payment start

### Operations
- included/excluded services
- service windows
- SLA
- equipment scope

This reduces prompt size and avoids asking one call to understand the entire scan.

## 7. Visual recovery

Trigger visual recovery only when one of these is true:

- expected material field is missing
- OCR text is contradictory/low quality
- table associations are ambiguous
- checkbox/form state matters
- evidence quote cannot be located but a source region exists

Recovery sequence:

1. render bounded page/region
2. ask a narrow visual question
3. receive structured proposal + cited page/region
4. verify against OCR/native/page geometry
5. accept, reject, or mark review-needed

## 8. Evidence model

Every accepted material fact should preserve:

- field_ref
- document/page
- source type: native / OCR / vision-assisted
- exact snippet when available
- bbox/region when available
- confidence
- verifier result
- review-required flag

Vision-only facts should be visibly marked and should require stronger review when exact text cannot be recovered.

## 9. Model strategy

JAMAL v1 is model-neutral.

A candidate must be benchmarked before production use. Minimum checks:

- image support when vision path is used
- structured output validity
- German contract understanding
- evidence discipline
- latency and memory footprint
- run-to-run stability

No candidate becomes the default because of one successful run.

## 10. Integration boundary

For the first experiment, do **not** modify production processing.

OpenCode should create an adapter that reads the same canonical document and original PDF, runs the experimental page routing/fusion, and emits a standalone JSON result.

Only after the benchmark passes should production integration be proposed.
