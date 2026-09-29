# Integrated assistant: scoped technical-debt audit (2026-09-30)

This audit is based on direct source inspection of the integrated assistant route, its regression tests, floating frontend component, shared API client, source-region route, and assistant stylesheet. It is **not** a full-repository scan or an executed test report.

## Corrected in this branch
- Repaired five incomplete direct route invocations in `test_ai_assistant_guard.py` after the FastAPI response argument was added. The previous calls would fail before reaching their intended assertions.
- Invalidated in-flight assistant requests immediately when the rendered account, organization, or contract context changes, and blocked rendering replies from canceled requests.
- Added bounded responsive dimensions and overflow/focus handling for the floating assistant, reducing clipped evidence and controls.
- Earlier commits revalidated account/membership scope and source identity after model inference, and restricted original-PDF lookup by tenant and fresh membership.

## Outstanding validation / debt (do not mark complete without evidence)
1. Run Python compilation and targeted assistant/source-region tests in the isolated OpenCode acceptance environment; none of the fixes above have been executed here.
2. Run frontend TypeScript checks, lint, build and desktop/tablet/mobile interaction checks; review the render-time context invalidation under React Strict Mode.
3. Exercise an actual accepted PDF extraction, a DOCX paragraph extraction, stale membership, changed evidence, no configured model, aborted request and organization switch using an isolated database.
4. The source-region action currently reports exact/coarse/not-found location text. It does not yet open a visually highlighted PDF at the exact source region; do not claim full source navigation.
5. The assistant is bounded to one contract and eight evidence excerpts. This is not organization-wide semantic search or full-contract retrieval; no unsupported capability should be advertised.
6. The source-region endpoint reads PDF bytes before resolving geometry; benchmark resource usage with approved realistic PDFs during final acceptance.
7. Audit the remaining repository beyond this scoped file set for truncated code, unreachable branches, duplicated implementations and dead TODOs before release.

## Non-negotiable acceptance
No Ahmed machine/package/release-branch changes. No protected-branch merge, deployment, Actions run, GPU/model load or heavy DB run without the agreed approval. OpenCode performs one consolidated final acceptance, safe fast-forward and report only, never edits or commits.
