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
