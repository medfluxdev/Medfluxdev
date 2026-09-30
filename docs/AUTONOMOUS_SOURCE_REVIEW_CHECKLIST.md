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

## Intelligence actions and analytics scope checkpoint
- Re-fetched branch HEAD after prior interactive intelligence read-route work. Inspected `backend/app/api/routes/intelligence_actions.py` and `backend/app/api/routes/intelligence_analytics.py`. Action transition route lacked actor-to-requested-org match before proposal access; fixed (`867e3e7`). Seven analytics endpoints likewise lacked explicit actor/org check; added request-based shared guard (`b05fa9b`). Authored DB-free guard regressions (`cb42f2f`). Tests NOT EXECUTED. Follow-up: confirm auth-disabled development behavior is intentional, inspect other route families and frontend evidence stale-response handling. Both scheduled and interactive sessions must reconcile branch and ledger.

## Evidence stale-detail regression checkpoint
- Verified latest feature HEAD `d73f7be` before resuming and inspected `frontend/app/nachweise/page.tsx` plus existing pagination tests. Existing generation guards appear intended to invalidate old detail requests on page changes; added a delayed page-one detail resolution after page-two selection regression in `frontend/test/nachweise-pagination.test.tsx` (`3a3dc74`). This is TEST SOURCE ONLY; NOT EXECUTED, so the UI guard remains runtime-unverified. Next review other API routes and verify test harness during final owner-approved acceptance. Scheduled and interactive sessions share this ledger.

## Portfolio reporting and auth middleware checkpoint
- Reconciled feature HEAD `1317196` and reviewed `backend/app/api/routes/reports.py`, `backend/app/api/routes/lifecycle.py`, `backend/app/auth/middleware.py`, and app middleware registration. Auth-enabled middleware sets request.state.actor for org-selected authenticated sessions. Portfolio report had org/workspace query filtering but no explicit actor-to-org guard; added pre-aggregate check (`305a8b5`) and DB-free missing/cross-org actor regression (`5964c65`). Tests NOT EXECUTED. IMPORTANT unresolved: auth-disabled local-development mode bypasses actor creation, so the new fail-closed guards across billing/intelligence/reports may change intentionally unauthenticated development behavior; assess configuration and existing test expectations before final acceptance. Lifecycle read/write endpoints likewise need explicit actor/org checks, but defer bounded changes until dev-mode policy is resolved. No heavy tests, Actions, merge or deployment.

## Lifecycle actor scope and explicit development mode checkpoint
- Reconciled feature HEAD `f84395b` before changes; inspected lifecycle routes, config auth defaults and billing regression. All five lifecycle endpoints previously checked org/resource but not actor-to-requested-org. Updated shared `_org` and both GET handlers, existing three write handlers pass request (`96e010a`, simplified `6c41ca9`). In auth-enabled mode missing actor is denied; cross-org actor always denied; auth-disabled local dev with absent actor remains supported. Authored four source-only regression cases (`3ee8dbd`). Tests NOT EXECUTED. Important: previously added billing, intelligence read/actions/analytics, and reporting guards remain fail-closed on missing actor even when auth is explicitly disabled; assess and align their local-development compatibility carefully with security policy and existing test expectations in next bounded review. No runtime verification, merge or deployment.

## Explicit auth-disabled compatibility checkpoint
- Reconciled feature HEAD `2c3eccb` before writes. Inspected config and existing lifecycle policy. Aligned billing (`48dfe04`), intelligence reads (`b949ee3`), intelligence action transitions (`17b7f4a`), intelligence analytics (`f9c61d3`) and portfolio reports (`87f0e50`) with lifecycle's explicit local-development rule: missing actor permitted only if `settings.auth_enabled` is false; a present cross-org actor is denied regardless. Auth-enabled missing actors remain denied. Added source-only local-dev intelligence/report regressions (`b1cc3ac`). TESTS NOT EXECUTED. Existing earlier missing-actor regressions assume auth enabled by default; verify test settings during final acceptance. Next inspect billing/action development-mode regressions and route registration, then resume broader source review. No merge, Actions, OpenCode run or resource-intensive work.

## Billing/action dev-mode test coverage and source audit checkpoint
- Reconciled HEAD `36ac2c9` before new work. Added parameterized source-only regressions for billing and human intelligence action transitions across auth-enabled missing/cross-org actors and explicitly auth-disabled missing/cross-org actors (`a9f59f8`). Verified the previously authored document MIME/range test imports and work-queue collaboration developer membership fixture against route source; no obvious source-level fixture mismatch found. NOT EXECUTED: all new and prior tests still await owner-approved acceptance. Note: work-queue collaboration GET depends on middleware org selection, while writes have explicit actor/org checks; inspect read-side defense in depth next. No merge, Actions, deploy or heavy resource use.

## Work queue collaboration read-side actor guard
- Inspected GET collaboration source: org/workspace resource checks existed but actor/org check relied on auth middleware. Added explicit read guard, preserving only intentional auth-disabled actor-absent local mode (`a160b09`); authored four source-only actor-mode regressions (`5c74819`). TESTS NOT EXECUTED. Next inspect remaining route-level actor boundaries, frontend stale-response cases, and final acceptance readiness. No release branch, protected JAMAL, Actions, merge or deployment touched.
