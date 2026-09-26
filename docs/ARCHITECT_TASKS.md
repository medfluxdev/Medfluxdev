# MedFlux architecture QA tracker

Updated 2026-09-26. This checklist is intentionally isolated on `audit/finance-provenance-20260926`; nothing here authorizes a production merge or deployment.

## Verified
- [x] Read finance harness/cost engine source directly.
- [x] Added isolated finance provenance guard and regressions.
- [x] Read-only local inventory confirmed experiment files and exact Visual-First page re-anchor source.
- [x] Diagnosed first finance CI failure as runner/service provisioning: job emitted zero steps and no runner assignment. Changed audit-only Postgres service from 18 to stable 17 to obtain a real executable test run.

## Required gates
- [ ] Finance audit CI executes and passes; never infer success from a green commit alone.
- [ ] Page provenance: systematic +/-1 model page offsets alone must not establish source provenance. Require independent page/literal corroboration or uncertainty + human review.
- [ ] Add wrong-page, mixed-offset, malformed-region and duplicate-literal regression cases.
- [ ] Privately inspect all original Frankfurt page images and compare extracted fields/omissions/page references to a human gold set. Do not publish contract text.
- [ ] Keep ambiguous financial amounts unverified until original clause evidence and human decision agree.
- [ ] Verify archive tenant/ACL/revision behavior and UI review states without adding another model.
- [ ] Mandatory cleanup: inventory experimental/temporary files, remove only proven-unused artifacts in isolated workspace, retain useful regressions, document deletions.
- [ ] Re-run targeted + full tests and read-only end-to-end benchmark after cleanup.
- [ ] Owner acceptance before integration/deployment.

## Evidence
- Local read-only inventory: JAMAL-OC-PC Actions run 36209029304.
- Page re-anchor source audit: JAMAL-OC-PC Actions run 36209109827.
- First finance CI attempt: medflux Actions run 36208884046 — failed before any job step/runner was assigned, therefore no test result exists.
