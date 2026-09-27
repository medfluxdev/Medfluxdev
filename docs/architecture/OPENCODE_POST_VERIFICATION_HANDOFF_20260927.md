# POST-VERIFICATION ARCHITECTURE DECISION & OPENCode EXECUTION HANDOFF
Date: 2026-09-27
Status: PATCH 1 CODE AUTHORED ON THIS BRANCH; ALL RUNTIME TESTS PENDING. Do NOT claim feature complete or merge until explicit owner acceptance.
Tested original source reference: integration `4b62abcf9bf58e566b61296b29b8684f87e539d3`. Report `reports/comprehensive-functional-20260927@fd678d41b63f8f7465dddd956496a8560f141833` includes ONLY a report, not implementation.
Parent design: `docs/architecture/SECURE_AI_ASSISTANT_INTEGRATION_PLAN.md`.

## Engineering decision
Preserve original proven import pipeline and current fail-closed money classification. Frankfurt original 9 pages reached partial/requires_review and **zero approved cost fields**. This is acceptable *safety*, NOT complete financial accuracy/readiness. Do not soften evidence gates. Reported >1200 passing tests are cumulative, with overlap, not 1200 unique cases; existing known production-posture test fails under leaked test env. Reported 57 AI calls versus 1+9+2+4 enumerated category breakdown and 297.8-second wall time versus 19.9-second mean merit log-level metric clarification if making hardware capacity claims.
Report confirms manual no-AI import MISSING; AI-direct auto-save EXISTS; AI+human review EXISTS AFTER save, not pre-save approval. No independent budget/actual/forecast schema. Cost center linked to contract but code filter MISSING. PR #10 Ahmad draft remains separate, unmerged and base JAMAL; do not wholesale merge it; evaluate cherry-picks only after comparing to current integration.

## Patch 1 authored now (bounded, independent, lowest risk)
Files changed:
- backend/app/contracts/search/service.py
- backend/app/api/routes/contracts.py
- backend/tests/test_contract_search.py
Adds OPTIONAL `GET /api/contracts?organization_slug=...&cost_center_code=471120` exact match against `CostCenter.code`, using org-scoped EXISTS bound to Contract.cost_center_id, retaining existing workspace-contract scope in `build_contract_search`. No new SQL migration, no change to default query, no finance calculations, no broadened ACL. New regression test checks exact match, cross-org contamination, SQL-looking input, empty authorized workspace.
This patch only adds server-side filter; UX search controls will follow after local test. Never present this as complete Ahmad functionality.

## OpenCode ACTION NOW: test only the authored patch, no architectural improvisation
1. Capture local worktree state, branch, file changes and concurrent processes. Do not touch current 5432, Ollama 11434 or any ongoing processes; never reset uncommitted edits. Fetch branch `design/secure-ai-assistant-20260927` to SEPARATE worktree or clean isolated clone based on integration 4b62abc. Do NOT checkout patch into owner's active production tree. Use existing WSL test PG 55432 (if safely available), temporary local Ollama as needed.
2. Before running, inspect diff to integration `4b62abc`. Explicitly verify no changed schema, sensitive settings, or loss of existing security assertions.
3. Use existing isolated test environment and execute:
   - `python -m compileall -q backend/app backend/tests` (adjust cwd/import path to existing setup);
   - `pytest -q tests/test_contract_search.py` from backend directory with correctly isolated test DB;
   - route boundary/scope/ownership/security suites and `pytest -q` under clean test-only env if feasible; separate production-runtime posture tests without `MEDFLUX_INSECURE_DEV=true`;
   - frontend `npm run verify` if available, unchanged frontend baseline;
   - a real authenticated route query: scoped user cannot retrieve other hospital/department contracts via code filter, even shared code. Verify unscoped cases follow EXISTING policy, not relaxed policy.
4. Return exact command outputs, fixture/migration availability, pass/fail/skipped, SHA. No code edits unless minimal reproduction/patch proposal sent for my review. No GitHub Actions, deploy, PR merge or JAMAL update.
5. If anything fails, STOP implementation; send minimal traceback and exact environment.

## Subsequent integration — assistant authors code on GitHub separately, OpenCode executes/tests locally
Phase A: Ahmad's org domain & contract role links (additive Department.parent_id migration; preserve old flat tree; same-tenant/hospital validation, cycle detection; one responsible plus multi-beneficiary; extend existing cost center UI/contract selectors). PR #10 is a review aid only, not canonical.
Phase B: manual no-AI contract creation and per-upload mode semantics using EXISTING canonical contract/evidence/review APIs; zero invented provenance. Reconcile existing auto-save vs post-hoc review semantics in route/UI, no silent changes to existing import.
Phase C: secure AI assistant tool gateway leveraging live authenticated actor, current scoped contract selectors and object-level access; default-deny every tool/evidence retrieval; bounded allowlisted read tools; no free-form SQL or raw DB connections to Qwen.
Phase D: vision model admission policy extends existing model discovery/selection (do not rewrite). Vision mandatory for document analyzer, real scanned PDF + German financial table benchmark, checksum/version/provider binding, revalidate on changes; admin management permission separate from deployment operator/provider allowlist. Text-only assistant role allowed ONLY if kept separate from image analysis and passes tool compatibility. Reject unsafe fallback and downgrade on test failure.
Phase E: index only proven sanitized/versioned source evidence via LlamaIndex AFTER real environment test; ACL filtering before model context AND source links, guard model prompts vs document injections, re-authorize on role change; deterministic verified financial aggregation.
Phase F: floating assistant UI in existing shell behind flag, citations/page links and missing-evidence disclosures. Audit and security tests: cross-org, cross-hospital, cross-department, revoked mid-conversation, ID guessing, aggregate leakage, prompt injection, model switch. Finally isolated full E2E + authorized Ahmad UAT on his measured hardware.
Financial budgeting/forecast is a separate approved module AFTER organization bindings and real hospital budget/ledger source data; do NOT generate fictional spending values.
No new third-party service when existing MedFlux capability suffices; no duplicated model selector, auth layer or second Ahmad app. Cleanup only with tested removal manifest; never delete historic migrations or user files. Owner approval required before any merge to integration and JAMAL.

## Acceptance for Patch 1
PASS = all regression tests + scoped live route probe green on isolated DB; default list semantics unchanged; zero unapproved file deletions; SHA and rollback documented.
FAIL/NOT RUN = report explicitly, do not continue stage A if security path uncertain.
