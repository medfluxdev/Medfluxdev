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

## Next run
Start with work queue and evidence-page async state and API wiring; then continue route-by-route and backend-by-backend. Append reviewed file paths, verified defects, commits, remaining work and blockers to this file each run.
