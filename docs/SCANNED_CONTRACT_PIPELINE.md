# Scanned Contract Intelligence — JAMAL v1

## Objective

Treat signed scanned hospital contracts as a first-class input type.

## Processing rule

MedFlux must use the least expensive path that preserves trustworthy evidence:

1. clean text-native PDF page → native text/layout
2. OCR page with usable text → OCR evidence
3. OCR page with tables/forms/visual structure → OCR + vision
4. image-only/sparse page → vision transcription + targeted OCR/layout recovery

Vision does not replace evidence. It supplies visual relationships and recovery
observations; accepted material facts still pass deterministic evidence
resolution and schema validation.

## Hybrid page flow

```text
canonical page
  -> deterministic page route
  -> native/OCR text retained
  -> bounded page image only when route requires vision
  -> vision returns exact visible text + layout relationships
  -> semantic packs consume fused page source
  -> evidence resolver locates exact quote/region
  -> unsupported fact fails closed
```

## Safety invariants

- local processing only
- no silent provider/model switch
- no contract-specific hardcoding
- no invented serials/dates/tax/service facts
- visual-only evidence is review-required unless source text/region is recoverable
- calculations remain deterministic code
- clean native PDFs must not pay a vision-cost penalty

## Benchmark

Use a real scanned contract and compare current vs JAMAL v1 for:

- identity
- lifecycle
- service scope
- tables/pricing
- service contacts
- evidence page/bbox
- unsupported facts
- latency, calls and memory

Production integration should happen only after this path materially improves
accuracy/evidence without weakening fail-closed behavior.
