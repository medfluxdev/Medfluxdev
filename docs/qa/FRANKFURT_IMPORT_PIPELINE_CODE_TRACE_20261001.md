# Frankfurt trial — code-traced import-to-analysis investigation (2026-10-01)

Status: SOURCE REVIEW COMPLETE; ACTUAL LOCAL FAILURE ROOT CAUSE UNCONFIRMED. This is not a runtime test report. Branch based on feature/integrated-release-build-20260929 @ 7c9c0a0c7a623538a7a16677b1d5f4b0aabd6fd9.

## Confirmed user-visible observation
Screenshot: 1 imported; 0 successful analyses; 1 failed analysis; Frankfurt KH RAV-00074 Optis M Next LFZ 04.06.2025 - 03.06.2029 PDF; review required. Import success does NOT establish successful PDF decoding or model invocation. The image does not reveal the exception, active model, diagnostics or actual processing run ID. A second user statement says other models failed too, but no per-run model IDs or logs have been supplied.

## Exact source-code route and checkpoints
1. frontend/app/import/page.tsx handleUpload calls importDocuments (frontend/lib/domain-api/documents); UI separates imported and analysis_failed, offers retry. It currently shows r.message but no operator diagnostic category.
2. backend/app/api/routes/documents.py POST /import: _validate_import_scope; _read_upload_bounded; _processing_service.process; _assign_import_scope; ImportFileResult. Never confuse storage accepted with analysis succeeded.
3. backend/app/documents/processing.py process -> _persist_document: persisted original and duplicate detection; _process_stored claims ProcessingRun, obtains storage.safe_path.
4. _process_stored tries _load_cached_canonical or _build_canonical; PDF _build_canonical calls selected document-intelligence provider (Docling/OCR/layout when configured); on Docling CUDA failure retries device=auto; on remaining provider failure falls back to native_pdf/PyMuPDF without OCR. Validates canonical source SHA256; optional atomic geometry; builds canonical pages/blocks/extraction.
5. _process_stored decides engine using settings.harness_engine; V3 + hybrid_scanned_contracts_enabled -> HybridVisionRuntime.render_region/render_page. Empty text can proceed only in the V3 visual PDF path; other paths persist failed analysis with _SAFE_NO_TEXT.
6. harness_cls(settings).analyze(canonical, image_loader, page_image_loader): inspect backend/app/ai/harness/v3.py for production V3, backend/app/ai/harness/pipeline.py for alternate engine. AIService.harness_runtime pins selected provider/model for one run; Ollama provider discovers via /api/tags and /api/show and generates via /api/chat. A model appearing in 'ollama list' does not prove it was invoked by MedFlux or that image payload was sent.
7. V3 collects bounded call diagnostics; failures can include vision warm-up, schema validation, grounding rejection, no grounded facts, timeout or other exceptions. Check actual run, not conjecture.
8. If analysis.contract is None, _persist_failed_analysis saves extraction status, sanitized error, diagnostic metadata and placeholder contract; logger warning includes call_count/failure_count/last failed purpose/category/type/done_reason. If a contract exists, deterministic calculate_contract and evaluate_contract_warnings run, then _persist_pipeline commits contract, evidence, calculations and status. A thrown processing exception logs 'Document processing failed for version ...' and finalizes a failed run.
9. frontend renders status, generic r.message, manual review and reanalysis. The screenshot's generic wording alone does not identify the failed stage.

## Local evidence required to establish actual cause — no rerun yet
- Correlate existing document_version_id and ProcessingRun ID for Frankfurt in isolated medflux_trial_20261001, PostgreSQL 127.0.0.1:55432 only; READ ONLY.
- Read existing trial logs under C:\Users\JAMAL\AppData\Local\Temp\opencode\medflux-real-contract\trial-logs\; locate 'Harness analysis not accepted', 'Document processing failed', 'Docling CUDA', 'Primary document intelligence failed', 'Vision warm-up failed' and Ollama HTTP errors by timestamp and version ID. Avoid logging document text or credentials.
- Read stored canonical artifact metadata: page count, OCR/native text blocks, warnings and hash match. Check extraction status, model ID, prompt version, failure diagnostics, run status and sanitized error. Confirm selected engine, provider and model at *run time*, not current settings.
- Distinguish failures before model invocation, image transport, provider timeout/OOM, JSON/schema validation, no grounded evidence, and persistence. Do not attribute failure to MiniCPM or Qwen without this evidence.
- Do not re-import, reanalyze, delete placeholder, switch models, touch original DB port 5432 or expose private contract text.

## Important implementation limitations surfaced
- Docling fallback to native PDF explicitly disables OCR. For a scanned PDF, this may produce pages but no stable canonical OCR text, so model vision alone may not yield grounded accepted evidence. This is a CODE PATH RISK, not proven cause of Frankfurt failure.
- The app intentionally fails closed when no grounded facts are accepted. A capable vision model may answer a synthetic image yet fail the full extraction/evidence/schema pipeline.
- User-facing generic failure text conceals the operator diagnostic stage. Preserve safe redaction; improve diagnostics in an authorized admin-only view after identifying actual failure.

## Assistant behavior changes on this branch
- Frontend displays a friendly, proactive initial greeting instead of unsolicited security banner.
- Backend system prompt responds naturally in the user's language and reserves caveats for relevant requests.
- Backend retains organization and membership authorization checks before any model call and after generation. Cross-org attempts are rejected by HTTP 403/404 BEFORE model invocation. Therefore the model cannot personally explain such backend-denied access with the current API; a safe frontend response to a real backend 403/404 would require an explicit, non-leaking error contract. Never reveal cross-org contract existence.
- Changes require local frontend/backend tests and live acceptance; not yet runtime-verified.
