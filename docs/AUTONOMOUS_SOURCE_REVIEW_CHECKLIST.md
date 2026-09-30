# MedFlux — autonomous source review and repair checklist

Branch: `feature/integrated-release-build-20260929`. This is the persistent execution checklist, not evidence of completed testing. Resume from GitHub state on every scheduled run. Mark a box only after inspecting the relevant source and record actual commit IDs in the execution log below.

## 1. Inventory and defect discovery
- [ ] Inventory every tracked frontend/backend source file, route, API client, schema, migration, and test; maintain a reviewed-files register and remaining count.
- [ ] Inspect truncated/incomplete code, TODO/FIXME, dead branches, duplicate implementations, inconsistent imports/types, and swallowed errors. Distinguish intentional placeholders from defects.
- [ ] Map frontend screens to actual backend endpoints, authentication/scope checks, response types, and tests. Prioritize broken real user workflows over cosmetic fixes.
- [ ] Track each confirmed defect with file/line, impact, proposed fix, status, and commit. Do not claim a repository-wide scan until every category is covered.

## 2. Core workflow completion
- [ ] Import: validate three real import paths, progress/errors, deduplication, document ownership, and resume behavior.
- [ ] Extraction/review: source-backed facts, accepted/rejected evidence, review queue pagination, lifecycle transitions, stale state and permissions.
- [ ] Contract 360: document/PDF navigation, calculations and provenance, billing, lifecycle, equipment links, archival/restoration, deletion administration.
- [ ] Organization hierarchy: tenant/hospital/department scoping in queries, mutations, evidence links, and asynchronous UI context changes.
- [ ] Floating AI assistant: authenticated scoped contract context, cancellation, bounded evidence, actual source deep links, administrator-only model choice, no invented citations.
- [ ] Remaining routes: dashboard, contracts, work queue, equipment, analytics, archive, audit, admin, settings; desktop/tablet/mobile navigation and accessibility.
- [ ] Audit backend services, route ordering, data models, migrations and tests against frontend expectations.

## 3. Fix and regression discipline
- [ ] Make bounded source fixes directly on this feature branch, with focused regression tests and meaningful commits; update the log each run.
- [ ] Check that fixes do not introduce duplicate logic, cross-tenant access, stale responses or misleading success states.
- [ ] Record unverified assumptions and blockers instead of declaring tests passed.
- [ ] Revisit the PDF exact-highlight/OCR alignment only in the context of the complete evidence workflow and real-document acceptance.

## 4. Final acceptance — only after source completion and owner approval
- [ ] One consolidated OpenCode acceptance: safe fast-forward, isolated environment, backend tests, frontend typecheck/lint/build, real UI walkthrough, scoped auth/evidence tests.
- [ ] Real PDF/DOCX source and visual highlight verification; optional Ollama/GPU and heavy database work only with explicit approval.
- [ ] Consolidated pass/fail report with reproductions, remaining blockers and approved release readiness decision.

## Non-negotiable boundaries
Never modify protected `JAMAL`, Ahmed's machine/package/release branch, or deploy/merge/run GitHub Actions. No interim OpenCode acceptance. No dependency installs, heavy CPU/DB, GPU/Ollama/model runs without explicit owner approval. A scheduled run may be blocked by connector permissions or execution limits; record the blocker and continue safe inspection on the next run.

## Execution log
- 2026-09-30: Existing source work resumed on the feature branch. Review page pagination/stale-response fix `5f6ef45488ab0fdd53a09707362ad38d9e72834f`; archive pagination/stale-response fix `c138c102087f8a88772d55698263d4fa34cd7189`; finish-plan log `79b37325e6a5d0c5a41e92f0ca3759096c180fe0`. These source edits have **not** undergone the final acceptance tests.
- 2026-09-30: Hourly autonomous review/repair schedule enabled; at the time of checklist creation, its reported last-run time was null. This file establishes GitHub-persistent progress tracking; it does not imply an unattended run has already completed.

- 2026-09-30 immediate run: inspected `frontend/app/work-queue/page.tsx`, `frontend/lib/domain-api/workQueue.ts`, `frontend/app/nachweise/page.tsx` and contract API/types previously inspected. Work queue had a fabricated fallback organization and unguarded overlapping fetches/mutations; removed fallback and added request/context generation guards (`aec7895e10d8b060e4bb91e9c28dc3b371a5302c`). Evidence page had unguarded contract-list/detail requests that could show stale cross-organization or cross-contract evidence; reset dependent state and guard both request lifecycles (`449858af53d2cf457930cd164850298eeb4ca7a8`). Source edits only; no runtime tests executed. Remaining: review work queue backend scoping and evidence list pagination/search (currently first 100 contracts), then continue full inventory.\n\n## Next run
Inspect work queue backend authorization and evidence list pagination/search; then continue route-by-route and backend-by-backend. Append reviewed file paths, verified defects, commits, remaining work and blockers to this file each run.

## Latest source-review checkpoint
- Reviewed work-queue route, service and regression tests. Fixed SQL ordering so allowed contract scope is applied before the result limit. Commits: 15158f8, c4c1b7e, 94a727f. Tests authored but not executed. Next: collaboration endpoint authorization and evidence-list navigation.

## Collaboration authorization checkpoint
- Inspected backend collaboration GET/PUT/comment routes and frontend collaboration panel. Fixed collaboration update lookup to require matching organization, blocked writes from actors whose organization differs from the requested work item, and rejected whitespace-only comments. Source commit `de6866d`; authored DB-free guard tests `c118639` and corrected whitespace fixture `2ffbb0e`. Tests not executed. Further audit: membership scope for assignee, frontend async save/comment stale-state and cross-organization switching, plus evidence-page contract pagination.

## Collaboration UI checkpoint
- Inspected `frontend/components/work-queue/WorkItemCollaborationPanel.tsx` and `frontend/lib/domain-api/workQueueCollaboration.ts`. Added per-context generation guards for stale load/save/comment completions, reset state on task/organization change, and blocked overlapping writes (`40f882c`). Parent remounts panel by organization and work item (`854b046`). Source changes not yet runtime-tested. Next: evidence-page first-100-contract limitation and user-visible search/pagination; check collaboration backend assignee scope.

## Evidence pagination checkpoint
- Reviewed evidence browser and contract list response schema. Added 100-contract page navigation with backend has_more/total_count, and clear prior detail immediately when page changes. Commits: 7723c98 and 75309a0. Not runtime tested. Next: add frontend regression for navigation, inspect backend contract search authorization and work-queue collaboration scope; continue full inventory.

## Evidence navigation follow-up
- Inspected evidence page and existing frontend test setup. Added guard against fetching an obsolete page while organization resets (`a6c6678`). Authored evidence pagination regression cases for forward/back navigation and selection replacement (`e90b79d`, refined `38cfdd1`). Tests not executed. Still pending: actual stale-response test and full backend contract search scope review.

## Contract portfolio scope checkpoint
- Inspected `backend/app/api/routes/contracts.py`, `backend/app/contracts/search/service.py`, and existing search test coverage. SQL service already applies organization and workspace-contract predicates before count/pagination; portfolio route lacked its own explicit actor/organization mismatch check (detail route already had one). Added route guard (`6393540`) and DB-free cross-organization route regression (`80fd6ad`). Source-only review; test not executed. Continue backend mutation scope and frontend evidence navigation edge cases.

## Document content-route checkpoint
- Inspected contract mutation route guards and original-document content route. Mutation endpoints reviewed use actor organization and scoped-contract checks; no change required in this pass. Confirmed document content MIME allowlist previously accepted mismatched allowed extension/type pairs, and zero-length suffix byte ranges were accepted. Corrected both (`8c054ef`); authored mismatched PDF/DOCX MIME regressions (`0691d60`). Tests not executed. Next: test byte-range boundary handling, inspect document-version contract binding and additional backend endpoints.

## Original document range and binding checkpoint
- Inspected document download route and `DocumentPersistenceService.resolve_bytes_for_version`: the storage service already checks organization, contract existence and ContractDocument binding before reading original bytes. Hardened byte-range parser to return 416 on unsupported units, malformed/multiple/zero suffix and unsatisfiable ranges (`99671ff`). Added source-level valid/invalid range regression cases (`10bad69`). Tests not executed; continue source review and final acceptance preparation.

## Billing scope checkpoint
- Inspected contract billing endpoints and ownership authorization patterns. Billing basis and invoice reconciliation previously relied on contract organization and workspace scope but lacked an explicit actor/organization match in their shared loader. Added request actor guard for both (`88e7063`) and DB-free missing/cross-org actor regressions (`499e84c`). Tests not executed. Continue other intelligence routes and eventual one-shot acceptance only with owner approval.

## Intelligence read-route actor-scope checkpoint
- Reconciled latest branch HEAD and prior interactive commits before edits. Inspected `backend/app/api/routes/intelligence.py` and prior billing guard. Five intelligence read routes (graph, obligations, policies, actions, events) had organization/workspace filters but no explicit request actor/organization match. Added shared `_org` actor check and request parameters (`c5cafce`); authored DB-free absent/cross-org regression (`621d358`). Tests NOT EXECUTED. Next inspect intelligence actions/analytics and other read routes, plus frontend evidence stale-detail regression. Both scheduled and interactive sessions must reconcile this same ledger and branch HEAD before writing.
