# MedFlux — Secure AI Assistant & Ahmad Organization Integration
Status: DESIGN ONLY. Base snapshot: step3/integration-20260926 @ 4b62abcf9bf58e566b61296b29b8684f87e539d3. This branch MUST NOT be merged or executed while the current OpenCode run is active. Owner approval required for merges and destructive cleanup.

## Non-negotiable architecture
- ONE canonical MedFlux. Reuse existing login, organization/tenant scope, model discovery/selection, contracts, source evidence, Docling/Visual-First, cost centers, audit. No Ahmad fork or parallel authorization framework.
- Model is UNTRUSTED. It never receives DB credentials or unrestricted SQL, authorization decisions, administrator credentials, or the ability to override policy. All retrieval and rendering go through backend policy checks against current session/membership on EACH tool invocation. Default deny. Treat prompt and document content as untrusted.
- Read-only AI assistant first; no writes to contracts, finance, organization, user accounts or model settings through chat. Source-backed, never fabricated finance; only verified amounts used for approved totals. Clearly label unverified evidence and missing information.
- Separate two concepts: document-analysis model MUST have working vision support; conversational model may be text-only ONLY if it never performs scanned-document analysis and receives only policy-filtered, verified retrieval results. Admin-approved profile can bind distinct model IDs to these roles. No silent fallback to a text-only document analyzer.
- Only an explicit highest-privilege *organization-scoped* AI model management permission may change that organization's approved model profile. Deployment operator separately controls provider allowlist/endpoint and secrets. No admin of one organization gains another organization's data. Revalidate after version/provider/runtime change. Audit changes.

## Verified current-code anchors
- backend/app/auth/dependencies.py: current_actor authenticates via session cookie and organization slug.
- backend/app/core/scope_context.py: ScopeContextMiddleware derives membership hospital/department restrictions; review middleware ordering and all query paths before relying on it for AI.
- backend/app/database/models/organization_structure.py: Hospital/Department/CostCenter/ContractDepartment already exist. Department has NO parent_id in snapshot. ContractDepartment currently has NO explicit responsible/beneficiary relation type. CostCenter has optional department_id. Do not duplicate these entities.
- backend/app/api/routes/organization_structure.py: existing admin/developer edits and scoped reads. Inspect full role semantics before introducing highest admin.
- Existing model discovery and selection ARE ALREADY IMPLEMENTED: extend their policy, do not rebuild.
- LlamaIndex archive tests reported an environment gap; do not declare retrieval integration proven before live tests.
- Ahmad's source document describes flexible organizational tree, separate responsible vs multiple benefiting departments, hospital-scoped selectors, cost-center code search and admin-editable tree; current phase is organization-contract linkage, later finance analytics depend on it.

## Phased delivery; every phase requires code review and a local acceptance report
### Phase 0: inventory and freeze
1. Wait for OpenCode's current test report. Capture latest integration commit and worktree status; do not overwrite or reset any user/local changes. Inspect actual auth roles, account memberships, contract ACL, model discovery/selection, AI orchestration, Docling, source evidence, retrieval, audit, frontend routing and tests. Classify each requirement EXISTING / PARTIAL / MISSING / UNVERIFIED with file+line references.
2. Define regression baseline; isolate test PostgreSQL (WSL port 55432), never touch production 5432. No GitHub Actions. No duplicate Ahmad app.
3. Resolve existing known environment-sensitive test isolation and LlamaIndex environment gap in their own bounded changes only after baseline.
### Phase 1: organization domain additive migration
1. Add nullable Department.parent_id self-FK, same-hospital/org parent checks, cycle prevention, bounded traversal and scoped tree endpoint. Preserve all existing flat departments as root nodes; avoid destructive data migration.
2. Reuse ContractDepartment and add explicit responsibility/beneficiary semantics via compatible migration after checking existing contract owner fields and API consumers. One responsible department and 0..N beneficiaries, constrained to contract's hospital and org. Preserve old contract associations until reconciled; avoid guessing historic role.
3. Validate cost-center associations and hospital/department consistency; code search scoped by authorized resources; disambiguate full hierarchy paths. Implement admin tree editor and contract import/detail selectors incrementally, retaining old API response contracts or versioning them.
4. Migration downgrade plan, constraints, cross-tenant and cycle tests. Never cascade-delete historical contract evidence when deactivating departments.
### Phase 2: shared policy enforcement for assistant
1. Implement thin AI tool gateway wrapping EXISTING authorization/query services, not a second RBAC engine. Permission matrix: org + hospital + department + object ACL + action. Distinguish relationship to a benefiting department from right to read entire contract.
2. Expose explicit bounded read tools: search_visible_contracts, get_visible_contract_summary, get_visible_evidence, get_visible_cost_centers, summarize_visible_verified_costs. Never unrestricted SQL, cross-org search, unrestricted file paths, bulk exports or admin APIs.
3. On every invocation resolve actor from live authenticated session, recheck membership/revocation and object ACL at retrieval AND before evidence/answer delivery. Re-authorize conversation history and invalidate old retrieved context on scope change. If implementation cannot reliably remove prior context, end conversation on permission change. Apply ACL filtering before retrieval/model context, not only after.
4. Server-enforced limits (time, result count, tokens, page size), query allowlists, audit IDs; log access metadata without sensitive prompts/full contract text by default. Safe 403/404 behavior avoiding object-existence leaks. Red-team injection in uploaded documents.
### Phase 3: model capability admission
1. Extend EXISTING model inventory with verified capability profiles keyed by immutable model digest/version + provider/connector/runtime configuration; metadata claims are insufficient.
2. Require vision-capable document-analysis model with actual image transport, multi-page scanned PDF and German table/amount/date/source-page tests using a sanitized fixture. Verify extraction precision/recall thresholds defined against human gold and fail-closed finance gate. OCR fallback may assist but cannot silently bypass document-vision requirement.
3. Test tool-call compatibility for conversational model OR use a strictly validated server-side orchestration adapter. No model-generated SQL. Separate optional assistant model from mandatory vision document analyzer if architecture permits.
4. Only org AI model manager can activate an approved profile; operator controls trusted provider endpoints. Atomic swap; rollback on failed smoke test. Revalidate when model digest, provider, connector, preprocessing or runtime changes. Explicit unsupported model reason in admin UI; no automatic unsafe fallback.
### Phase 4: retrieval and chat UI
1. Reuse LlamaIndex if its real environment integration is validated; index only allowed, versioned, provenance-linked evidence. Retrieval candidate selection never grants authorization. Enforce ACL in DB before text enters prompt and before source links/download.
2. Floating accessible button and side panel in existing shell, lazy-loaded and behind feature flag. Respect current language/layout, keyboard/focus, loading/cancel/error states. Cite contract ID, page, source excerpt, verified status and navigation link; never invent page evidence.
3. Cost/date questions computed deterministically by backend over authorized verified rows; model narrates returned figures, never calculates authoritative totals itself.
### Phase 5: hard gates and cleanup
1. Security tests: two organizations, two hospitals, same-role different departments, revoked membership mid-chat, hidden contract by ID, retrieval leakage, aggregate count leakage, injection, unauthorized model change, malicious evidence links, concurrent users, switching models.
2. Integration tests: scanned Frankfurt original 9 pages with human gold; Docling/Visual-First/Harness V3; organization assignment; contract owner+multi-beneficiary; numeric cost-center search; source-backed AI chat. Real GPU benchmark on Ahmad's actual hardware only once specs are confirmed.
3. Run compileall, isolated backend suite, frontend lint/vitest/build, migrations upgrade/downgrade on disposable DB, UI smoke and accessibility. Explicitly report PASS/FAIL/NOT RUN and SHA; never claim all green with known failing tests.
4. Cleanup is evidence-based: identify dead code by import/call graph, references, migration lineage and regression tests; delete ONLY after approved diff and green tests. No blanket removal, force pushes, branch resets, production DB operations, or removing old migrations. Keep a removal manifest with rationale and rollback.
5. Owner reviews one coherent PR to integration after current OpenCode run; JAMAL remains protected and unmerged until owner authorizes.

## Division of work
Assistant authors and reviews implementation on a separate GitHub branch, file-by-file against current integration baseline. OpenCode on user's machine ONLY applies exact reviewed commits and runs local tests/benchmarks; it must not redesign architecture, invent duplicate components or modify production data. Any necessary local fixes are reported as minimal patches and independently reviewed before push. This document is a plan, NOT a claim that implementation exists.

## Required report for every phase
Base SHA; changed paths; reused components; new migrations; security invariants; tests run with exact commands and exit codes; failures/not-run; hardware/DB environment; cleanup manifest; screenshots for user-visible features; commit SHA; rollback steps.
