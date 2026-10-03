# MedFlux — New Chat Handoff (GitHub canonical)

Checkpoint: 2026-09-30 Europe/Berlin. This is the GitHub-accessible complete handoff, incorporating the live source-review ledger and project plans. It is a source handoff, NOT a test-pass report. Reply to Jamal in friendly Syrian Arabic.

## Start of next chat
1. Fetch latest HEAD, recent commits, this handoff, and authoritative live docs on the branch BEFORE any edits. The hourly automation and interactive sessions are one workflow; reconcile concurrent progress and do not overwrite newer work.
2. Keep the BIG PICTURE: ONE coherent MedFlux hospital contract platform. Systematically review the ENTIRE frontend/backend source, find and FIX defects, eliminate unused/dead/duplicate code and technical debt with small safe verified commits, preserve full workflow: three genuine imports, AI extraction and evidence, contract 360, finance, lifecycle, equipment, scoped floating Qwen, responsive UX, tenant permissions, archive and auditable deletion.
3. Repository: jamallionjan-dev/medflux. ONLY working branch: feature/integrated-release-build-20260929. HEAD at handoff: 596452fe2cd0de868f17b41cf6797be0482e4249 (may advance). Protected JAMAL and Ahmed's independent machine/package/release/branch release/ahmed-pilot-package-20260929 untouched. Do not merge/deploy/trigger Actions.
4. Existing unified hourly source-review automation ID 6abc4b2f979c8191af6051c80885b608 enabled, Europe/Berlin; older canonical oversight automation 6ab7c40316d48191ac952dfa9ca2796c also enabled. Each run must reconcile same branch and append shared ledger.
5. No interim OpenCode runs. Write source-only regressions but NEVER claim tests executed. Heavy CPU/DB, dependency installs require owner approval; GPU/Ollama requires explicit owner approval. At the END, after owner approval, ONE comprehensive OpenCode acceptance on safe fast-forward: inspect/test/report only, never edit or commit.
6. User-reported priority: actual medical equipment names missing from contracts. Recent changes: group extraction prompt enumerates devices from headings/annexes/tables even absent serials; source-label omission triggers manual review instead of silent success; frontend ContractWorkspace now falls back to system_name/model/type/category when device_name missing; regression sources authored NOT RUN. STILL OPEN: trace actual accepted extraction persistence/canonical ContractEquipment association and display on real multi-page PDF and DOCX, verify DB/UI end-to-end with owner-approved test. Never call this fully solved prematurely.
7. Other recent fixes: equipment hospital/department SQL scope moved BEFORE limit; actor organization checks on equipment list/detail, notifications, dashboard, billing, intelligence, reports, lifecycle, work queue collaboration and contract portfolio; frontend review/archive/evidence pagination and stale-response guards; PDF source evidence/assistant fixes. All require final validation.
8. Immediate source-review follow-ups: inspect extraction-to-persistence device-name path, verify source-only tests align with actual signatures (especially backend/tests/test_equipment_omission_review.py and frontend equipment fallback); review stale-detail test await/act; check reports/billing/action test expectations; examine dead code, duplicate implementations and technical debt across repository, not just route patches. Append actual commits and next actions to docs/AUTONOMOUS_SOURCE_REVIEW_CHECKLIST.md every batch.

## Authoritative ledger snapshot (refresh original before working)

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

## Notification and dashboard read isolation checkpoint
- Reconciled feature HEAD `f4f8ddc` before changes; inspected notifications, dashboard, and activity. Activity already invokes `current_actor` plus role guard; no edit there. Notifications had org/workspace filters but lacked explicit actor/org check; added before queries (`c8f630a`) and source-only four-case regression (`849649d`). Dashboard overview likewise added actor/org guard before aggregation (`a78e1c3`) and four-case source regression (`178e93f`, refined `69b456e`). Both preserve explicit auth-disabled actor-absent local mode but deny known cross-org actors. TESTS NOT EXECUTED; source review only. Next review whether dashboard test mocks align with existing dashboard model, other API read boundaries, and eventual owner-approved comprehensive acceptance. No protected/release branches, heavy tests, Actions or deployment touched.

## Equipment scope-before-limit and actor isolation checkpoint
- Reconciled feature HEAD `b19c426` and inspected ownership, operations export, equipment routes/service. Found equipment list applied hospital/department filtering AFTER service SQL LIMIT, risking truncated visible results. Moved scope predicates into service SQL before limit (`1848cc3`) and wired route to pass scope directly; added explicit actor/org guards to equipment list and detail (`f304454`), preserving explicit auth-disabled missing-actor local mode. Added source-only route guard and SQL scope tests (`428cbf4`). TESTS NOT EXECUTED. Ownership routes already use current_actor and org checks; operations export uses optional_identity/enforce_org in auth-enabled mode, worth follow-up to confirm actor-session compatibility. No protected or release branch, Actions, merge, OpenCode run, or heavy tests touched.

## Equipment names omitted from contract extraction (owner-reported)
- Owner reports that actual medical device/equipment names mentioned in contracts are missing from application output. Confirmed equipment prompt/schema, equipment verifier, evidence verification and chunk merge exist, but real end-to-end extraction/persistence on owner's contract has NOT been verified. Updated group prompt to enumerate explicitly covered devices across headings, annexes and equipment tables even without serial numbers (`90306dd`, escape refinement `f8b28a8`). Added conservative source-label omission detection when AI returns empty equipment: flag contract for manual review rather than inventing a name (`a4131a3`, corrected implementation `67fbf0b`). Added source-only omission regression tests (`c2855c5`), NOT EXECUTED. This does NOT establish that names are now correctly extracted/saved/displayed. Next inspect equipment persistence and review UI mapping; owner-approved final acceptance should include actual multi-page PDF/DOCX equipment-list contract and database/UI assertions. No GPU/Ollama calls, heavy tests, merge, deploy, or release branch touched.

## Contract equipment display fallback checkpoint
- Reconciled feature HEAD `cb05f09` before writes. Traced accepted equipment in `contracts/detail/service.py`: returned `device_name`, `system_name`, `model`, and other fields. Review material also reads system/device/model. Found `ContractWorkspace.tsx` equipment card title ignored `system_name` and `model` when `device_name` absent, showing generic `Gerät` instead. Added display fallback to system/model/type/category (`2d6d3ce`); authored source-only detail page regressions for system-only and model-only equipment (`e61708f`, assertion refinement `8bd7c80`). TESTS NOT EXECUTED. Remaining: verify accepted extraction persistence and canonical `ContractEquipment` association on real PDF/DOCX; cannot claim end-to-end resolution yet. No GPU/Ollama, heavy tests, protected or release branches, merge, deploy or Actions touched.


## Integrated finish plan snapshot (refresh original before working)

# MedFlux integrated workspace — finish criteria

Development branch: feature/integrated-release-build-20260929.
Do not merge protected JAMAL, alter Ahmed's independent installation, or run expensive workloads without owner approval.

## Product experience
1. Retain existing design and eight responsive screens. Preserve route, selected contract, folder, scroll position and work context while the Qwen assistant opens, collapses or resizes.
2. Floating Qwen must be connected to the actual backend with authenticated organization and hospital/department scope; only the administrator chooses a supported vision model. No mock success, no unauthorized cross-contract citations. Show loading, errors, cancellation and exact evidence links.
3. Contract 360: import, extraction, review, source PDF, calculations, lifecycle, billing, archive and permissions all use live typed backend APIs.
4. Navigation: dashboard, contracts, review, work queue, equipment, analytics, archive, audit, admin and settings remain coherent; responsive keyboard-accessible focus and dialogs.
5. Deletion is separate from archival: server opt-in, admin-only, request/confirm/cancel/restore, audit, no hard deletion. The administrative queue must paginate.

## Final integration acceptance — one OpenCode run after source completion
- Fetch and fast-forward the approved feature branch in the existing local checkout; do not touch Ahmed's independent machine, branch or release package.
- Install dependencies only after permission; confirm environment and isolated DB before migration.
- Frontend typecheck/lint/build and backend test suite; targeted lifecycle, archive, deletion, authorization, organization/scope, document evidence and assistant API checks.
- End-to-end walkthrough of the real UI on desktop/tablet/mobile; test actual backend and Ollama only with explicit GPU approval.
- Confirm navigation and Qwen panel preserve work context; no claims of actual integration until verified.
- Deliver a single consolidated report with pass/fail evidence, reproduction and remaining blockers. No automatic protected-branch merge or deployment.

## Current status
Deletion administration and archive wiring have source commits but have not been locally tested. UI screenshots and interaction-only mocks are not evidence of real backend/Ollama integration.

## Pre-acceptance source inventory (not a test result)
- [x] Server-gated deletion request, confirm, cancel and restore endpoints with audit events.
- [x] Server-gated administration page and paginated queue with stale-response isolation.
- [x] Archive action in the active contract workspace and organization isolation on archive endpoints.
- [x] Targeted source-level regression tests authored (not yet executed).
- [ ] Complete actual floating assistant with authenticated, scope-bound backend conversation and verifiable contract evidence; the existing AI status/test/selection endpoints are not a conversation assistant.
- [ ] Inspect all affected frontend/backend routes, existing tests and imports together; resolve failures before requesting the one-shot local acceptance run.
- [ ] Prove frontend build, backend tests, real browser workflows and optional GPU tests on the approved local environment.

Do not report zero outstanding tasks or zero defects until the remaining source work and the final acceptance evidence actually support those claims.

## Full-workflow source review resumed (2026-09-30)
- Inspected the integrated finish criteria, current assistant audit, route inventory, and review/archive/work-queue/evidence pages plus their shared contract API types. This is a route-level pass, **not** a completed full-repository audit.
- Review and archive pages previously fetched only the first 100 records with no pagination; both now use backend page/has_more and generation guards so stale requests cannot overwrite the current organization/page. Archive restore moves back one page when the last row is restored.
- Continue examining work queue, evidence and contract workflow source, tests, dead branches, duplicates, and cross-organization asynchronous state before final acceptance. No OpenCode execution or test pass is claimed.


## Assistant technical debt snapshot (refresh original before working)

# Integrated assistant: scoped technical-debt audit (2026-09-30)

This audit is based on direct source inspection of the integrated assistant route, its regression tests, floating frontend component, shared API client, source-region route, and assistant stylesheet. It is **not** a full-repository scan or an executed test report.

## Corrected in this branch
- Repaired five incomplete direct route invocations in `test_ai_assistant_guard.py` after the FastAPI response argument was added. The previous calls would fail before reaching their intended assertions.
- Invalidated in-flight assistant requests immediately when the rendered account, organization, or contract context changes, and blocked rendering replies from canceled requests.
- Added bounded responsive dimensions and overflow/focus handling for the floating assistant, reducing clipped evidence and controls.
- Earlier commits revalidated account/membership scope and source identity after model inference, and restricted original-PDF lookup by tenant and fresh membership.

- Keyed the floating assistant by account and organization to reset chat state across tenant switches; moved contract-context invalidation out of React render and into a layout effect.
- Replaced the accepted-evidence document-link join with a correlated EXISTS filter so multiple roles for one document do not duplicate evidence rows or consume the eight-item budget.

- Reject whitespace-only prompts server-side and normalize leading/trailing whitespace; added regression cases for empty, whitespace and oversized input.
- Abort outstanding source-region requests when assistant contract/organization context changes or the component unmounts; ignore aborted lookup results.

- Connected assistant evidence IDs to the existing contract evidence tab and PDF viewer via a deep link; the destination resolves evidence against the loaded contract and checks the document version is linked. This reuses the existing source-navigation implementation instead of introducing a second viewer.

- Preserved all original evidence IDs as `merged_evidence_ids` when the contract detail read layer deduplicates identical physical evidence. Assistant deep links now resolve through these aliases without bypassing the loaded contract/document membership check; added DB-free alias regression tests (not yet executed).

- Extended DB-free deduplication regressions for input ordering and immutable source alias lists; removed an unused test helper parameter.
- Made missing assistant evidence deep links visibly report an unavailable source in the contract evidence tab, and clear stale source IDs during manual contract tab navigation.

- Removed evidence-page changes from the PDF document-loading effect dependencies: page navigation no longer triggers a full PDF fetch. Removed the persistent refinement-key guard and reset geometry/page count on document reload, preventing stale source highlights across documents.

- Corrected PDF viewer navigation effect so manual page changes are not overridden by a previously selected evidence target. Source-region refinement now also runs for page-only evidence; it draws no fallback highlight without real geometry and reports successful exact resolution distinctly.

- Fixed a Python local-variable shadow of SQLAlchemy `exists()` in the assistant evidence query; corrected a whitespace-validation test fixture that previously supplied literal backslash characters rather than newline/tab escapes.
- Added render-generation invalidation to the PDF viewer so an older asynchronous `getPage()` or cancelled render cannot overwrite the newly selected page during rapid navigation.

- PDF source overlay now resets canvas dimensions on every page/source change (including no-evidence pages), preventing stale rectangles from carrying across pages with different geometry. Page rendering now clears old dimensions and reports real page-load/render failures while ignoring cancelled stale renders.

- Source-region resolver no longer labels a unique fallback token as exact; repeated token hits are rejected and repeated phrase hits are coarse rather than merged into a false precise location. Canonical token-only fallback is also coarse. Added regression fixtures for repeated/unique ambiguous text (not executed). Accurate per-word OCR on scanned contracts still depends on validated atomic word geometry and final real-document QA; do not promise exact boxes where geometry is unavailable.

- Invalid explicit source-page hints now return no location rather than silently searching unrelated pages; PDF handles are closed after lookups. Added a focused regression (not executed).
- PDF viewer now renders stored extraction rectangles only as approximate dashed regions. It uses the precise solid highlight and exact-location wording only after successful original-PDF source-region refinement; no implied word-level proof from a narrow but unverified stored box.

- Tightened text-layer source precision: a single returned rectangle is exact only when the PDF text layer also has one matching phrase occurrence. Added unique/repeated phrase regression cases. Multi-line phrase normalization and scanned OCR word precision remain final-acceptance items; tests not yet executed.

- PDF source search now normalizes whitespace to recognize unique line-wrapped phrases and checks proximity before merging their search rectangles as exact; ambiguous repeated phrases remain coarse. Corrected repeated-source fixtures to use newline escape sequences. Real-document visual confirmation and isolated tests remain pending.

## Outstanding validation / debt (do not mark complete without evidence)
1. Run Python compilation and targeted assistant/source-region tests in the isolated OpenCode acceptance environment; none of the fixes above have been executed here.
2. Run frontend TypeScript checks, lint, build and desktop/tablet/mobile interaction checks; review layout-effect cleanup and remount behavior under React Strict Mode. Verify PDF page changes do not refetch the document and evidence refinement reruns correctly when revisiting a source.
3. Exercise an actual accepted PDF extraction, a DOCX paragraph extraction, stale membership, changed evidence, no configured model, aborted request and organization switch using an isolated database.
4. The assistant now links to the contract evidence tab, whose existing viewer supports evidence navigation. The separate source-region check still reports exact/coarse/not-found text only. Verify the deep link, evidence-alias regression tests, and visual highlighting with real accepted PDF data; do not claim verified exact navigation.
5. The assistant is bounded to one contract and eight evidence excerpts. This is not organization-wide semantic search or full-contract retrieval; no unsupported capability should be advertised.
6. The source-region endpoint reads PDF bytes before resolving geometry; benchmark resource usage with approved realistic PDFs during final acceptance.
7. Audit the remaining repository beyond this scoped file set for truncated code, unreachable branches, duplicated implementations and dead TODOs before release.

## Non-negotiable acceptance
No Ahmed machine/package/release-branch changes. No protected-branch merge, deployment, Actions run, GPU/model load or heavy DB run without the agreed approval. OpenCode performs one consolidated final acceptance, safe fast-forward and report only, never edits or commits.

