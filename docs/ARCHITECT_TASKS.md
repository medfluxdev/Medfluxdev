# MedFlux architecture QA tracker

Updated 2026-09-26. This checklist is intentionally isolated on `audit/finance-provenance-20260926`; nothing here authorizes a production merge or deployment.

## Verified
- [x] Read finance harness/cost engine source directly.
- [x] Added isolated finance provenance guard and regressions.
- [x] Read-only local inventory confirmed experiment files and exact Visual-First page re-anchor source.
- [x] Diagnosed first finance CI failure as runner/service provisioning: job emitted zero steps and no runner assignment. Changed audit-only Postgres service from 18 to stable 17 to obtain a real executable test run.

## Required gates
- [x] Isolated Windows runner finance suite executed on the branch and passed: 25 tests, 5 third-party deprecation warnings, GitHub JAMAL-OC-PC Actions run 36242489078. GitHub-hosted audit CI remains separately unavailable; do not claim hosted CI success.
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

## 2026-09-26 isolated regression evidence

- Source tested: fresh temporary clone of `audit/finance-provenance-20260926`, never original or OpenCode working directory.
- Runner: JAMAL-OC-PC self-hosted Windows; used existing pytest-capable interpreter read-only.
- Command scope: `tests/test_finance_provenance_audit.py` + `tests/test_harness_v3.py` with no GPU/model or real DB.
- Outcome: **25 passed, 5 deprecation warnings**; [workflow log](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36242489078).
- Limitations: pipeline e2e with original nine-page PDF, financial UI, full suite and visual page source verification remain untested in this run.
- Local inventory: experiment is on branch `master` with zero *tracked* changes (`-uno` intentionally did not examine untracked files); protected original `Medflux-Integrated-Test` has six tracked changes. Treat all local work as valuable. [Audit run](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36242364975).
