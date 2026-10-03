# MedFlux architecture QA tracker

Updated 2026-09-27. This checklist is intentionally isolated on `audit/finance-provenance-20260926`; nothing here authorizes a production merge or deployment. Evidence added on `step3/integration-20260926` marks the items verified there.

## Verified
- [x] Read finance harness/cost engine source directly.
- [x] Added isolated finance provenance guard and regressions.
- [x] Read-only local inventory confirmed experiment files and exact Visual-First page re-anchor source.
- [x] Diagnosed first finance CI failure as runner/service provisioning: job emitted zero steps and no runner assignment. Changed audit-only Postgres service from 18 to stable 17 to obtain a real executable test run.

## Required gates
- [x] Isolated Windows runner finance suite executed on the branch and passed: 25 tests, 5 third-party deprecation warnings, GitHub JAMAL-OC-PC Actions run 36242489078. GitHub-hosted audit CI remains separately unavailable; do not claim hosted CI success.
- [x] Page provenance: systematic +/-1 model page offsets alone must not establish source provenance. Require independent page/literal corroboration or uncertainty + human review. **Verified on `step3/integration-20260926`:** `_financial_classification_verified` binds periodicity only via (a) a period anchor AND exactly one money literal equal to the proposed amount on the same page, or (b) a corroborated Visual-First row (same page + matching value) that itself carries a period anchor; the page-wide `page_texts` acceptance path was removed. No offset-only claim survives.
- [x] Add wrong-page, mixed-offset, malformed-region and duplicate-literal regression cases. **Added in `tests/test_financial_classification_gate.py` (12 cases):** same-page annual 5k + one-time 12k E2E, anchor-on-other-amount-in-same-quote, two-amounts same page cross-binding, corroborated-row period+amount requirement, multiple amounts/periods, currency variants (incl. numeric value), positive annual acceptance, unverified rejections, legacy unaffected. Visual-First region/isolation cases remain in `test_visual_first_isolated.py`.
- [ ] Privately inspect all original Frankfurt page images and compare extracted fields/omissions/page references to a human gold set. Do not publish contract text.
- [x] Keep ambiguous financial amounts unverified until original clause evidence and human decision agree. **Background/unverified vision echoes now force PARTIAL + review reasons (`test_visual_evidence_fail_closed.py`);** classification predicate is fail-closed on multiple/zero amounts.
- [x] Verify archive tenant/ACL/revision behavior and UI review states without adding another model. **Verified on `step3/integration-20260926`:** auth-on production-like env (AUTH_ENABLED=true, non-default secret, no insecure opt-in, DB-backed) — `test_auth_e2e`, `test_auth_route_boundary_e2e`, `test_auth_security`, `test_auth_review_provenance` 20/20 passed; `test_security_runtime_config`+`test_runtime_security_posture` 26/26 passed under the same auth-on env; archive ACL/tenant + work-queue revision E2E 18/18 in standard test env. Known env mismatch (reported separately, not a regression): two unauthenticated archive-route probes (`test_archive_route_unknown_org_404`, `test_unarchive_route_unknown_org_404`) expect 404 but get 401 under auth-on because they never log in — correct fail-closed auth; tests are designed for the auth-off test env.
- [x] Mandatory cleanup: inventory experimental/temporary files, remove only proven-unused artifacts, retain useful regressions, document deletions. **Done for the integration-branch inventory (28 files vs `origin/JAMAL`):** removed unused `_SPACER_SEPARATORS` and fixed mojibake euro sign in `visual_first`, retained all live helpers. `v3_perception.py` documented as pre-existing dead module (zero importers, on `origin/JAMAL` baseline) — removed only with explicit owner approval.
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

## 2026-09-26 local Visual-First deterministic baseline

- Ran existing local experimental `test_visual_first_bridge.py` and `test_visual_first_isolated.py` against a **Python-only copy** of the experimental application inside the runner's temp directory, NOT in the active OpenCode worktree. Tests used the existing interpreter read-only, with no actual database/Ollama/GPU.
- **18 passed, 5 warnings**, and exact temp copy cleanup succeeded: [GitHub workflow 36242759351](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36242759351).
- Independently inspected the real local `visual_first.py`: its reconciler uses page + normalized label + region overlap + value matches; all its outputs still require Harness V3 source verification. The experimental bridge nevertheless silently re-anchors uniformly shifted Qwen page labels, so we must prove robust protection from wrong-page literal collisions via additional regressions, not count this baseline as full-page evidence validation.
- Verified finance retry **25 passed, 5 warnings** AND owned temporary workspace cleanup completed: [workflow 36242610955](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36242610955). These are **43 executed targeted tests across two suites**, not 43 unique guarantees and not a complete full-system regression.
