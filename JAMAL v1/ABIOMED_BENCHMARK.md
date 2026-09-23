# ABIOMED Benchmark Protocol — JAMAL v1

This document is an evaluation fixture, not extraction logic.

## Goal

Compare the current MedFlux pipeline with the JAMAL v1 hybrid page pipeline on the same scanned ABIOMED contract.

Do not write benchmark truths into generic extraction code.

## Test pages

Prioritize pages that previously exposed weaknesses:

- page 1 — identity/title/customer/supplier
- page 7 — included/excluded service scope
- page 8 — scheduled prices and conditional per-call charge
- page 9 — service contact

OpenCode may inspect additional pages when the current canonical source shows a dependency.

## Known benchmark truths used only for scoring

- supplier: ABIOMED Europe GmbH
- contract number: 40015645
- customer: Krankenhaus Nordwest GmbH Frankfurt
- title/system: Impella® AIC System
- start: 01.04.2025
- end: 31.03.2029
- duration: 4 years
- automatic renewal: false
- service hours: Monday–Friday 09:00–17:00
- annual schedule:
  - year 1: 0 EUR
  - year 2: 8,000 EUR
  - year 3: 8,000 EUR
  - year 4: 8,000 EUR
  - plus VAT
- conditional per-call charge: 2,226 EUR, separate from recurring schedule
- service email: EUFieldService@its.jnj.com
- service phone: +49 241 8860 520

Service-scope scoring must be based on source page 7 and current accepted MedFlux service-fact definitions, not a new ABIOMED-specific parser.

## Required comparison

For each pipeline report:

1. structured JSON validity
2. fields correct / incorrect / missing
3. evidence page correctness
4. exact quote located or not
5. bbox/region available or not
6. hallucinated unsupported facts
7. included_services stability
8. excluded_services correctness
9. legal entity verbatim preservation
10. page-9 contact extraction
11. scheduled-price vs variable-charge separation
12. number of OCR calls
13. number of vision calls
14. model calls
15. elapsed time
16. peak VRAM/RAM if measurable
17. retries/truncations
18. facts forced to review

## Acceptance criteria for moving beyond prototype

The experimental path must not regress existing accepted facts and should satisfy all of:

- zero invented material facts
- legal entity names preserved verbatim
- page-9 contact extracted with page-9 evidence
- scheduled price ladder remains separate from the 2,226 EUR conditional charge
- included service scope no worse than current deterministic Round-3 behavior
- every accepted material fact has locatable evidence
- malformed/ambiguous visual content fails closed
- no cloud calls
- no database mutation during benchmark

A speed regression is acceptable only if it produces a material accuracy/evidence gain and remains operationally practical.

## OpenCode output

Produce a before/after matrix and recommendation:

- KEEP CURRENT
- ADOPT HYBRID FOR SCANNED PAGES ONLY
- ADOPT HYBRID FOR ALL PDF PAGES

Do not integrate or commit production changes as part of the benchmark.
