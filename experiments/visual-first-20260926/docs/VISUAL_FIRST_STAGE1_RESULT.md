# MedFlux Visual-First isolated implementation â€” initial delivered unit
This module is an **isolated candidate pipeline**, NOT a production replacement or a finished end-to-end MedFlux integration.
- First vision pass uses original page image bytes, has no OCR observations in its input.
- Independently launch OCR first pass; preserve image SHA-256, page, and optional region.
- Reconcile by page, field label, value, and region; repeated values and differences remain disputed.
- Same selected vision model can revisit original images with bounded attempts, but a second model response never proves truth.
- No reconciled claim can be directly written as a verified Contract fact: existing Harness V3 must verify original evidence.
- The current source clone includes prior uncommitted Harness fixes, launcher, Postgres modifications. No production DB or original working-tree files modified by this step.
Next: connect call adapters to chosen Qwen/Docling behind a default-off experiment flag, add Harness V3 bridge, run A/B with human gold truth; separately add rebuildable lexical/ACL archive experiment.
