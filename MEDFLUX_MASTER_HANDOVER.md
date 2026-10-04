# MEDFLUX — MASTER ENGINEERING HANDOVER

**Document type:** Consolidated engineering handover (read-only investigation)
**Repository root:** `C:\Users\JAMAL\Desktop\Medflux`
**Investigation date:** 2026-10-03
**Baseline branch / HEAD at hand-over time:** `fix/frankfurt-contract-analysis-20261001` @ `c900b07` ("fix: preserve scanned contract facts and review state")
**Investigation baseline commit:** `ae3e76d` ("fix: improve grounded contract extraction and review diagnostics") — see the concurrency notice below
**Status of document:** COMPLETE for all 40 sections; every claim is labelled `VERIFIED`, `OBSERVED`, `INFERRED` or `UNKNOWN`.

---

## EVIDENCE LABELS USED THROUGHOUT

| Label | Meaning |
|---|---|
| `VERIFIED` | Directly confirmed in this session by reading the file/DB/socket/output. |
| `OBSERVED` | Confirmed at a specific point in time during this session; may drift afterwards. |
| `INFERRED` | Strong logical conclusion from verified facts, but not directly measured. |
| `UNKNOWN` | Not established. The exact verification command is given. |

> **CONCURRENCY NOTICE — read section 4 first.** This document was produced while **another
> agent was actively committing to the same branch**. The git state recorded here was
> re-verified at the end of the investigation and reflects that later state. Two commits
> (`19af894`, `c900b07`) and 17 modified files appeared **during** the investigation and are
> **not** attributable to this handover. The only file this handover created is this document.

---

# 1. EXECUTIVE OVERVIEW

MedFlux is a **fully local** AI system for German hospitals that imports PDF/DOCX maintenance and
service contracts, extracts structured facts with a **local** model (Ollama), and computes
deadlines, costs, warnings, obligations and equipment relations **deterministically in code**.

The product surface is far beyond the original 18-step MVP in `AGENTS.md`: it now contains
Contract 360, an Intelligence graph (obligations/policies/actions/risk/authority-diagnostics),
ownership, work queue, lifecycle decisions, billing basis, notifications, cost centres, a secure
AI assistant, and a document source-region (evidence highlight) feature.

Three findings dominate any handover and are expanded later:

1. **The "main" local backend on port 8000 is NOT using `backend/.env`.** It holds four
   established connections to `127.0.0.1:55432` (the isolated WSL trial cluster), while
   `backend/.env` points at `5432/medflux` with credentials that fail authentication. The
   Windows PostgreSQL on `5432` is installed, running and **completely unused**. (`VERIFIED`)
2. **Document storage is split and drifting.** The repo-root `data/contracts/` is empty
   (`.gitkeep` only); all originals live under `backend/data/contracts/` because
   `contracts_dir` is the **relative** default `./data/contracts`. There are **21 document
   directories on disk but only 3 `document_file` rows in the trial DB**, and the legacy
   manifest `.index.json` is `{}` (2 bytes), so SHA-256 duplicate detection via the manifest
   no longer fires. (`VERIFIED`)
3. **The app's own model inventory is stale.** `installed_models.json` lists six models that
   are **not** the models present in the live Ollama library (it contains no `qwen3.5` and no
   `minicpm-v4.5`). The active model in the DB is `qwen3.5:4b`. (`VERIFIED`)

Nothing in this investigation modified source code, the database, credentials, or git state.

---

# 2. SCOPE, METHOD AND EVIDENCE RULES

**What was done:** read-only static inspection of the repository, read-only filesystem and
process/socket inspection, read-only SQL against the isolated trial cluster, and HTTP `GET`
probes against running local services.

**What was explicitly NOT done** (per instruction and per repository rules in `AGENTS.md`):

- no source file was created, edited or deleted (except this handover document, which is the
  requested deliverable);
- no `git add`, `git commit`, `git push`, no branch/tag/stash mutation;
- no Alembic migration was applied or generated;
- no password was changed, no role created or dropped;
- no document was re-imported, re-analysed or deleted;
- no external network call; **no external AI API is used or required by the product**.

**Security rule applied to this document:** no password, no API key, no token, no DSN with a
credential, and no local login secret value appears anywhere below. See section 40.

---

# 3. REPOSITORY LAYOUT

Root entries as observed (`VERIFIED`):

```text
Medflux/
├─ .github/                     CI/release gate workflows
├─ .playwright-mcp/             UNTRACKED browser-automation artefacts
├─ .pytest_cache/               local pytest cache (ignored)
├─ backend/                     Python / FastAPI application
├─ data/                        contracts, backups, benchmarks (git-ignored)
├─ design-reference/            design/UX reference material
├─ docs/                        project history, QA traces, architecture, pilot docs
├─ frontend/                    Next.js 14 / React 18 / TypeScript application
├─ scripts/                     operational helper scripts
├─ AGENTS.md                    authoritative project instructions
├─ .hermes.md                   assistant/tooling context
├─ IDEA.md                      product idea / scope notes
├─ CONTRIBUTING.md              contribution rules
├─ README.md                    project readme
├─ docker-compose.yml           container composition
├─ .env / .env.example          environment template + local env (git-ignored)
├─ contract-detail-verified.png UNTRACKED screenshot
├─ Start Software.bat           launcher
├─ START_MEDFLUX_LOCAL.bat      local launcher
└─ STOP_MEDFLUX_LOCAL.bat      local stop script
```

`data/` composition (`VERIFIED`):

| Path | Files | Bytes | Note |
|---|---:|---:|---|
| `data/contracts/` | 1 | 0 | **Empty** (`.gitkeep` only) |
| `data/backups/` | 5 | 5,973,959 | backup artefacts |
| `data/benchmark/` | 36 | 3,936,221 | real-contract fixtures / ground truth |
| `data/benchmark_v2/` | 77 | 105,789,518 | larger benchmark corpus |
| `data/database/` | 3 | 0 | SQLite-era leftovers |

---

# 4. GIT STATE AND HISTORY

`VERIFIED` — re-verified at the **end** of the investigation:

```text
branch:  fix/frankfurt-contract-analysis-20261001
HEAD:    c900b07  "fix: preserve scanned contract facts and review state"
parent:  19af894  "fix: stabilize Radiosurgery and OPTIS contract extraction"
         ae3e76d  "fix: improve grounded contract extraction and review diagnostics"  <- baseline of
                                                                                        this handover
earlier: 5be30c6  "docs: add hospital workflow reference archive"
         ee0e46c  "docs: trace Frankfurt import-to-analysis stages and distinguish risks
                   from confirmed cause"
         cbcde42  "fix: specify courteous permission-denial behavior without accusing users"
         716768a  "fix: align friendly assistant welcome with existing German interface locale"
         6f0faaa  "feat: welcome users warmly before first assistant message"

git merge-base --is-ancestor ae3e76d HEAD  ->  exit 0   (baseline is an ancestor; no rewrite)

stash:  stash@{0}: On JAMAL: local-before-medflux-test
tags:   backup/pre-assistant-fix-20261001
```

**Commit `c900b07` (`VERIFIED`, `git show --stat`) — 9 files, +285/-28:**

```text
backend/app/ai/harness/source_signals.py                        |   2 +-
backend/app/ai/harness/v3.py                                     |  42 ++++++
backend/app/api/routes/documents.py                              |   7 +-
backend/app/documents/status.py                                  |  69 ++++++----
backend/tests/test_contract_detail_cost_projection.py           |  28 +++
backend/tests/test_document_status.py                            |  24 ++--
backend/tests/test_harness_v3.py                                 |  52 ++++++
backend/tests/test_source_region.py                              |   8 +
docs/PROJECT_PROGRESS.md                                        |  81 ++++++
```

**Uncommitted working-tree changes present at hand-over time (`VERIFIED`, 17 modified files,
+771/-91) — concurrent work, NOT part of this handover:**

```text
backend/app/api/routes/documents.py                     |  98 ++++++-
backend/app/api/routes/ownership.py                     |   8 -
backend/app/ownership/service.py                        |  39 +++--
backend/tests/test_contract_department_roles_a2.py      |  27 +
backend/tests/test_document_import.py                   |  39 +
docs/PROJECT_PROGRESS.md                               | 141 +++++
frontend/app/globals.css                                |  15 +
frontend/app/import/page.tsx                            |  86 ++++-
frontend/app/organization.css                           |   1 +
frontend/app/ownership.css                              |   2 +-
frontend/components/contracts/detail/ContractOwnershipPanel.tsx            | 133 ++++--
frontend/components/settings/OrganizationStructureManager.tsx              | 190 +++++-
frontend/lib/api.ts                                     |   5 +
frontend/lib/domain-api/documents.ts                    |  16 +-
frontend/lib/domain-api/organizations.ts                |   5 +-
frontend/lib/domain-api/ownership.ts                    |  26 +-
frontend/test/import.test.tsx                           |  31 +-
```

Untracked additions from that concurrent work: `docs/MEDFLUX_PRODUCT_BUILD_PLAN.md`,
`frontend/lib/organization-tree.ts`, `frontend/pnpm-lock.yaml`,
`frontend/pnpm-workspace.yaml`, `frontend/test/organization-tree.test.ts`,
`frontend/test/organization-structure-manager.test.tsx`,
`frontend/test/contract-ownership-roles.test.tsx`,
`backend/tests/test_contract_department_roles_api.py`, plus pre-existing
`.playwright-mcp/` and `contract-detail-verified.png`.

**Theme of the concurrent work:** organization/department structure, contract ownership roles,
document-import UX and the import-status surface. **A pnpm lockfile/workspace appeared next to
the existing npm setup — decide on one package manager before merging.**

**Immediate operational consequence:** anyone acting on this handover must start from
`git status` + `git log`, because HEAD and the working tree are moving. Also note
`docs/PROJECT_PROGRESS.md` is being edited concurrently and `AGENTS.md` requires it to be
updated after every completed step.

Linked worktrees (outside the repo, in the temp area):

| Path | Branch | HEAD |
|---|---|---|
| `…\Temp\opencode\sr415-review-worktree` | `review/source-region-pdf-content-415-20261002` | `03af994884b7de10c08ead4fbfcb514c98e3ee28` |
| `…\Temp\opencode\sr415-parent-worktree` | (parent integration worktree) | `UNKNOWN` |

Historical baselines recorded in the repository's own documentation (`VERIFIED` by reading the
files, not by re-deriving the commits):

- `docs/INTEGRATION_BASELINE.md` → baseline `JAMAL-AHMAD-FULL-INTEGRATION` @ `ca07599052041336578b85aeb5ab32f9fd21a44b`, recorded 2026-09-13.
- `docs/qa/FRANKFURT_IMPORT_PIPELINE_CODE_TRACE_20261001.md` → code trace based on `feature/integrated-release-build-20260929` @ `7c9c0a0c7a623538a7a16677b1d5f4b0aabd6fd9`.

`UNKNOWN` — the per-item mapping of "which commit fixed what" for the whole pilot sequence was
not fully derived. The two most recent commits are the tail of it. Verification commands:

```powershell
git log --oneline --decorate -20
git log --oneline --all --grep="radiosurgery|optis|grounded|evidence|source-region|scanned" -i -30
git show --stat c900b07
git show --stat 19af894
```

---

# 5. FILE-BY-FILE INVENTORY — BACKEND CORE

| File | Role | Notes |
|---|---|---|
| `backend/app/main.py` | FastAPI application factory, middleware stack, router registration | Registers 27 route modules + audit router (29 `include_router` calls). Does **not** register `demo.py`. (`VERIFIED`) |
| `backend/app/core/config.py` | Pydantic settings | `env_file=".env"` (**relative**), `data_dir="./data"`, `contracts_dir="./data/contracts"` (**relative**). Fail-closed validation: `APP_ENV` ∈ {development,test,pilot,production}; `pilot|production` require `AUTH_ENABLED=true` and `AUTH_COOKIE_SECURE=true`; a non-local DB in `pilot|production` requires TLS. (`VERIFIED`, lines 11–199) |
| `backend/app/core/scope_context.py` | per-request organization/hospital/department scope | fail-closed |
| `backend/app/database/session.py` | engine/session factory, `create_session()` | used directly by route handlers |
| `backend/app/database/models.py` (package) | ORM models | ~45 public tables in the trial DB (`VERIFIED`) |
| `backend/app/database/scope_queries.py` | `scoped_contract_ids(...)` | central scope filter |
| `backend/app/database/services.py` | `get_organization(...)` | org resolution by slug |
| `backend/app/api/routes/health.py` | `/health`, `/live`, `/ready` | `ready` executes `SELECT 1`, returns `503 "Datenbank nicht bereit."` on failure; payload `{"status","service","version"}` / `{"status":"ready","environment","database":"ok"}` (`VERIFIED`) |
| `backend/app/middleware/*` | request-id, rate limit, CORS, security headers | — |

**Consequence of relative paths (important):** `contracts_dir` resolves against the **process
working directory**. The running backends are started with `python -m uvicorn app.main:app` from
`…\Medflux\backend`, therefore the effective storage root is
`…\Medflux\backend\data\contracts`, **not** the repo-root `data/contracts` that `AGENTS.md`
documents. Starting the backend from a different directory silently changes where originals
live. (`VERIFIED` — see section 14)

---

# 6. FILE-BY-FILE INVENTORY — BACKEND API ROUTES

Directory `backend/app/api/routes/`. 28 route modules exist; 27 are registered in `main.py`
plus an audit router.

Confirmed endpoints (from the newest pilot `backend.log`, `VERIFIED` as live traffic):

```text
POST /api/auth/login
GET  /api/me
GET  /api/organization-structure?organization_slug=…
GET  /api/notifications?organization_slug=…&limit=…
GET  /api/contracts/{id}?organization_slug=…
GET  /api/contracts/{cid}/documents/{vid}/content?organization_slug=…
GET  /api/contracts/capabilities/deletion?organization_slug=…
POST /api/documents/{vid}/retry?organization_slug=…
POST /api/documents/{vid}/reanalyze?organization_slug=…
GET  /api/documents/{vid}/source-region?organization_slug=…&snippet=…&page=…
GET  /api/ai/status
GET  /api/ownership/assignees?organization_slug=…
GET  /api/ownership/contracts/{id}?organization_slug=…
GET  /api/cost-centers?organization_slug=…
GET  /api/lifecycle/contracts/{id}?organization_slug=…
GET  /api/intelligence/contracts/{id}/graph|actions|obligations|policies
GET  /api/intelligence/analytics/contracts/{id}/authority-diagnostics
GET  /api/intelligence/analytics/contracts/{id}/risk
GET  /api/intelligence/billing/contracts/{id}/basis
GET  /api/processing-jobs?organization_slug=…&limit=…
GET  /health  /live  /ready  /openapi.json
```

**Dead code:** `backend/app/api/routes/demo.py` exists but is not registered → the documented
`/api/demo/*` surface is unreachable. (`VERIFIED`)

---

# 7. FILE-BY-FILE INVENTORY — AI SUBSYSTEM

`backend/app/ai/` contains ~34 modules (≈10.9k lines, `INFERRED` from a static survey).

| File / area | Role |
|---|---|
| `harness/v3.py` | production analysis harness, ~3150 lines (`VERIFIED` size via static survey) |
| `harness/pipeline.py` | alternate/legacy engine (v2), ~1401 lines |
| `providers/ollama*.py` | Ollama adapter: discovery via `/api/tags` + `/api/show`, generation via `/api/chat` (incl. images) |
| `providers/openai_compatible*.py` | OpenAI-compatible HTTP adapters |
| `providers/lm_studio*.py`, `providers/llamacpp*.py` | alternative local runtimes |
| `providers/registry.py`, `discovery.py` | provider/model discovery + selection |
| `selection*` | resolves provider/model from settings for one run and pins it |
| `schema*.py`, `groups*.py`, `verifier*.py` | output schema, extraction groups, grounding verification |
| exceptions | `AITimeoutError`, `AIUnavailableError`, `AIModelMissingError`, `invalid_schema`, `insufficient_memory`, `model_runner_stopped`, … |

**Design invariant (documented project rule, honoured in code):** the model extracts **facts**;
fristen, cost aggregation and warning levels are computed by **code**, never by the model.
`UNKNOWN` — whether `application_setting` keys `ai_provider` / `ai_model` are global or
organization-scoped was not confirmed at the schema level. Verify:

```sql
\d application_setting
select * from application_setting where key in ('ai_provider','ai_model');
```

---

# 8. FILE-BY-FILE INVENTORY — DOCUMENTS / STORAGE / PROCESSING

| File | Key symbols | Behaviour |
|---|---|---|
| `backend/app/documents/storage.py` | `DocumentStorage`, `StorageError`, `save`, `remove`, `resolve_document`, `legacy_records`, `safe_path`, `validate_reference`, `write_reference`, `exists_reference`, `read_reference`, `delete_reference` | Legacy layout: `<32-hex document_id>/original.<ext>` + JSON manifest `.index.json` keyed by SHA-256. Canonical layout (STEP 14): strictly validated relative references `<32hex>/original.pdf|docx` and `<32hex>/artifacts/<32hex>/canonical.json`. `safe_path` is the **only** reference→path translator and enforces containment. `original_filename` is never used as a path. (`VERIFIED`) |
| `backend/app/documents/persistence.py` | `canonical_storage_key` (l.69), `canonical_artifact_storage_key` (l.88), `store_original` (l.118), `link_to_contract` (l.219), `store_canonical_artifact` (l.233), `resolve_bytes_for_version` (l.283), `resolve_canonical_for_version` (l.326) | DB-first ordering: `DocumentFile` flush → write bytes → `DocumentVersion`. Idempotency via `document_file.sha256` UNIQUE; a detected duplicate returns `duplicate=True` and deliberately does **not** mask a lost original. `resolve_bytes_for_version` verifies org, version, **and** the `(contract_id, document_version_id)` link, then `exists_reference`; any failure raises `StorageError("Dokument nicht gefunden")`. (`VERIFIED`) |
| `backend/app/documents/service.py` | `DocumentImportService.import_file/import_many` | Extension allowlist (.pdf/.docx), MIME cross-check (generic types tolerated), empty/size rejection, SHA-256 dedupe via manifest, compensating cleanup on failure. (`VERIFIED`) |
| `backend/app/documents/processing.py` | `DocumentProcessingService.process`, `_persist_document`, `_process_stored`, `_load_cached_canonical`, `_build_canonical`, `_persist_failed_analysis`, `_persist_pipeline` | Claims a `ProcessingRun`, builds canonical text (Docling/OCR → fallback native PDF without OCR), validates canonical `source_sha256`, then selects the harness engine. (`VERIFIED` via code trace doc + source read) |
| `backend/app/documents/reconcile.py` | CLI `python -m app.documents.reconcile` | Requires `--organization-slug`; supports `--resume-version`, `--legacy-document-id`, `--all-legacy`, `--limit`, `--as-of-date`, `--dry-run`. No public bulk endpoint before STEP 16. (`VERIFIED`) |
| `backend/app/documents/status.py` | `STATE_LADS`/`STATE_LABELS`, `_KNOWN_AI_ERRORS`, `safe_failure_message`, `build_import_state` | Honest UI state: uploaded / processing / analysis_ok / analysis_partial / analysis_failed. Only shows "Analyse erfolgreich" when an extraction was actually **accepted**. Internal error payloads are never surfaced; known AI errors map to German short texts. (`VERIFIED`) |
| `backend/app/documents/source_region.py` | `resolve_narrowest_region` | Maps a text snippet to a page/region for evidence highlighting |

---

# 9. FILE-BY-FILE INVENTORY — CONTRACTS, EQUIPMENT, FINANCE

Areas under `backend/app/contracts/`:

- `detail/` — Contract 360 read model (single aggregate consumed by the UI).
- `calculation/` — deterministic date/term/cost computation (`calculate_contract`).
- `warnings/` — warning policy/evaluation (`evaluate_contract_warnings`).
- `search/`, `review/`, `overrides/` — search, fact review, manual overrides with audit trail.
- `lifecycle/`, `ownership/`, `workqueue/`, `intelligence/`, `billing/` — operational layers.

`backend/app/equipment/` — equipment identity, normalization, persistence, next-service-date
and operational lifecycle.

`backend/app/ai/harness/*` writes the extraction; `backend/app/contracts/*` owns all business
truth. The frontend never recomputes business truth (documented invariant in
`docs/INTEGRATION_BASELINE.md`).

---

# 10. FILE-BY-FILE INVENTORY — FRONTEND

`VERIFIED` (static survey):

- `frontend/package.json` — Next.js `14.2.15`, React `18.3.1`, TypeScript, Vitest.
  Scripts: `dev`, `build`, `start`, `lint` (`next lint`), `test` (Vitest), `verify`
  (lint + Vitest + production build, referenced by the release gate).
- `frontend/next.config.js` — backend origin via `NEXT_PUBLIC_API_URL`, default
  `http://localhost:8000`; PDF.js worker alias; CSP.
- `frontend/lib/api.ts` — API client. Credentials are included; backend is cookie-auth.
- `frontend/components/auth/AuthProvider.tsx` — auth/session state.
- `frontend/components/assistant/` — secure AI assistant UI (floating panel).
- `frontend/app/import/page.tsx` — `handleUpload` → `importDocuments`; separates "imported"
  from "analysis_failed" and offers retry (per the Frankfurt code trace).
- `frontend/test/` — Vitest suites including security and accessibility tests.

`UNKNOWN` — full route/component enumeration was produced by a static sub-agent survey but is
not reproduced here item-by-item; verification command:

```powershell
Get-ChildItem frontend\app -Recurse -Filter page.tsx | ForEach-Object { $_.FullName.Replace((Resolve-Path frontend).Path,'') }
```

---

# 11. FILE-BY-FILE INVENTORY — SCRIPTS, TESTS, DOCS

**Repository scripts** (`scripts/`, `VERIFIED` as existing): `setup_isolated_pilot.ps1`,
`provision_ahmed_local_pg.ps1`, `verify_local_pilot_preflight.ps1`, `start_local_postgres.ps1`.
None of them reference the trial cluster port or the `sr415_flow` role (targeted grep across
`scripts\*.ps1` and `*.py` returned no hits) — the 55432 trial path is driven from outside the
repository. (`VERIFIED`)

**Backend tests**: 36 Alembic migration files and a large `backend/tests/` suite (top-level test
files observed in the low hundreds; exact count `UNKNOWN`). Four drift/legacy suites
explicitly reference the isolated cluster: `test_drift1_migrated_integration.py`,
`test_drift1_migration_gate.py`, `test_drift1_real_legacy_rollback.py`,
`test_drift1_legacy_null_probe.py`, plus `backend/scripts/verify_migrated_fixture.py`.

**Documentation that exists and matters** (all `VERIFIED`):

```text
docs/PROJECT_PROGRESS.md                                   (18-step progress log)
docs/INTEGRATION_BASELINE.md                               (DoD chain + baseline commit)
docs/PRODUCTION_READINESS.md                               (release gate, UAT, authz matrix)
docs/STEP3_INTEGRATION_REVIEW.md
docs/architecture/OPENCODE_PHASE_A1_CONCURRENCY_RETEST_20260927.md
docs/architecture/OPENCODE_PHASE_A2_HANDOFF_20260928.md
docs/architecture/OPENCODE_PRE1_ISOLATION_RETEST_20260928.md
docs/architecture/OPENCODE_POST_VERIFICATION_HANDOFF_20260927.md
docs/architecture/DRIFT1_INTEGRATION_CHECKPOINT_20260928.md
docs/architecture/DRIFT1_PHASE2B_DECISIONS_AND_RETEST_20260928.md
docs/architecture/DRIFT1_PHASE2D_ENV_CORRECTION_20260929.md
docs/architecture/DRIFT1_PHASE2D_RETEST_20260928.md
docs/architecture/OPENCODE_DRIFT1_INVENTORY_RETEST_20260928.md
docs/architecture/OPENCODE_DRIFT1_COMPUTED_RETEST_20260928.md
docs/architecture/OPENCODE_DRIFT1_PHASE2C_RETEST_20260928.md
docs/architecture/OPENCODE_OPERATIONAL_COLUMNS_RETEST_20260928.md
docs/architecture/SECURE_AI_ASSISTANT_INTEGRATION_PLAN.md
docs/pilot/AHMED_PACKAGE_HANDOFF_20260929.md
docs/pilot/AHMED_PILOT_DELIVERY_GATE_20260929.md
docs/qa/FRANKFURT_IMPORT_PIPELINE_CODE_TRACE_20261001.md
```

---

# 12. END-TO-END CONTRACT LIFECYCLE

As implemented (`VERIFIED` by code trace + live traffic):

```text
1  Upload (PDF/DOCX)                      frontend/app/import/page.tsx
2  POST /api/documents/import              documents.py: _validate_import_scope
                                            _read_upload_bounded  (size-bounded read)
3  Persist original                       persistence.store_original
                                            DocumentFile row + SHA-256 UNIQUE
                                            canonical_storage_key → bytes on disk
                                            DocumentVersion row
4  Link to contract                       persistence.link_to_contract
5  Claim ProcessingRun                    processing._process_stored
6  Build canonical text                   Docling/OCR/layout → fallback native PDF (NO OCR)
                                            validate canonical source SHA-256
7  Choose engine                          settings.harness_engine + V3/hybrid settings
8  Analyse                               harness v3.analyze(canonical, image_loader,
                                            page_image_loader) with the pinned provider/model
9  Accept only grounded facts             verifier/schema/groups; fail closed otherwise
10 Persist                               _persist_pipeline (contract, evidence, calculations)
                                            or _persist_failed_analysis (sanitized diagnostic)
11 Deterministic truth                    calculate_contract + evaluate_contract_warnings
12 Review / ownership / lifecycle / work  review, overrides, ownership, lifecycle,
                                            work queue, intelligence proposals
13 Evidence navigation                    source_region → canonical page/highlight
```

---

# 13. DOCUMENT IMPORT PIPELINE (CODE-TRACE)

Authoritative narrative: `docs/qa/FRANKFURT_IMPORT_PIPELINE_CODE_TRACE_20261001.md`
(`VERIFIED` — read in full). Key checkpoints and code-path risks:

1. **Import success ≠ analysis success.** Storage acceptance and model invocation are separate
   outcomes; the UI must and does separate them.
2. **Docling → native-PDF fallback disables OCR.** If the primary document-intelligence provider
   fails (including a CUDA failure that retries `device=auto`), the fallback is native
   PDF/PyMuPDF **without OCR**. For a scanned PDF this yields pages but no stable canonical OCR
   text, so model vision alone may never produce accepted grounded evidence. The document labels
   this a **CODE PATH RISK**, not a proven cause. (`VERIFIED` as documented)
3. **The app fails closed** when no grounded facts are accepted. A capable vision model can
   answer a synthetic image and still fail the extraction/evidence/schema pipeline.
4. **A model in `ollama list` is not proof of invocation.** Selection must be read from the
   actual `ProcessingRun` at run time.
5. **Generic user-facing error text hides the failing stage** (pre-model, image transport,
   timeout/OOM, schema validation, no grounded evidence, persistence). Safe redaction is
   required; the fix is an **admin-only** diagnostic view.
6. **Assistant safety invariant:** org/membership checks run **before** any model call and again
   after generation; cross-org attempts are rejected with 403/404 **before** the model is
   invoked, so the model can never explain backend-denied access, and cross-org contract
   existence must never be revealed.

---

# 14. DOCUMENT STORAGE MODEL AND ON-DISK STATE

**Canonical model (`VERIFIED` source):**

- Server-side canonical reference only; the browser/API only ever sends opaque UUIDs.
- `document_file.storage_key` → `<document_file_uuid_hex>/original.pdf|docx`
- canonical artefact → `<document_file_uuid_hex>/artifacts/<processing_run_uuid_hex>/canonical.json`
- `DocumentStorage.validate_reference` rejects absolute paths, drive/scheme parts, `..`, empty
  segments and any unexpected shape; `safe_path` additionally enforces containment.

**Actual on-disk state (`VERIFIED`):**

| Location | State |
|---|---|
| `Medflux/data/contracts/` | **1 file: `.gitkeep` (0 bytes)** — empty |
| `Medflux/backend/data/contracts/` | **21 document directories** + `.index.json` (**2 bytes = `{}`**) |
| originals present | 20 of 21 dirs contain `original.pdf` |
| `…\01a07ed1741e78b7a74312e27dc528b7\` | has `artifacts/…/canonical.json` but **no `original.pdf`** |
| `Medflux/backend/data/` | also holds `pr6-server.log` (11,854 B) and `pr6-server-error.log` (6,694 B) |

**Consequences (`INFERRED`, high confidence):**

- ~18 of the 21 storage directories have **no corresponding `document_file` row** (the trial DB
  holds only 3). They are legacy/orphaned artefacts.
- Because `.index.json` is empty, `DocumentImportService`'s manifest dedupe returns `None` for
  every hash; duplicate detection now rests **solely** on the DB unique constraint
  `document_file.sha256`. Re-importing a legacy file can therefore create a *second* physical
  file plus a DB-detected duplicate instead of the old idempotent manifest hit.
- The empty legacy manifest also means `legacy_records()` returns nothing, so
  `app.documents.reconcile --all-legacy` currently has no input to reconcile.

**Root cause of the observed document-content 404 (`INFERRED`, high confidence, one command to
confirm):** the request
`GET /api/contracts/01a0f82c-…/documents/01a0f73c-8af7-72e6-b6ea-9dfde110418c/content`
returned 404 while the equivalent request for the Radiosurgery contract
(`01a0fe3a-…` + version `01a0fe32-…`) returned `200 OK` in the newest pilot log (`VERIFIED`).
`resolve_bytes_for_version` fails closed on three conditions: version not in org, the
`(contract_id, document_version_id)` link missing, or `exists_reference(storage_key)` false.
Note that the dashed version id `01a0f73c-8af7-72e6-b6ea-9dfde110418c` maps to hex
`01a0f73c8af772e6b6ea9dfde110418c`, whereas the directory that exists on disk is
`01a0f73c8aef7fab8b962645e5a557dd` — **different UUIDs sharing the `01a0f73c8af` prefix**.
Therefore the requested version's canonical storage directory does not exist on disk, which is
sufficient on its own to produce the fail-closed 404.

Confirm with a read-only query (no writes):

```sql
select v.id, v.storage_key, f.sha256, f.original_filename,
       (select count(*) from contract_document cd
         where cd.document_version_id = v.id) as links
from document_version v
join document_file f on f.id = v.document_file_id
where v.id = '01a0f73c-8af7-72e6-b6ea-9dfde110418c';
```

---

# 15. AI / HARNESS ARCHITECTURE

- Two engines coexist: **v3** (`harness/v3.py`, production) and the alternate v2 pipeline.
- Engine choice is driven by `settings.harness_engine` plus the hybrid/vision settings; the V3
  visual path is the only path where empty extracted text may proceed (`HybridVisionRuntime
  .render_region` / `.render_page`). (`VERIFIED`)
- One run pins exactly one provider+model (`AIService.harness_runtime`); the provider is
  discovered via Ollama `/api/tags` + `/api/show` and invoked via `/api/chat`. (`VERIFIED`)
- The harness collects **bounded call diagnostics** per purpose; failure categories include
  vision warm-up failure, schema validation, grounding rejection, no grounded facts, timeout,
  and generic exceptions. (`VERIFIED`)
- Logger warnings carry `call_count`, `failure_count`, last failed purpose, category, type and
  `done_reason`; `_persist_failed_analysis` stores sanitized error + diagnostic metadata and a
  placeholder contract. (`VERIFIED`)
- Local-only guarantee: no external AI API is required by the product (`AGENTS.md` DoD #11).

---

# 16. MODEL INVENTORY AND PROVIDER SELECTION

**Live Ollama (`VERIFIED` during this session, `ollama` v0.24.0):**

| Model | Vision | Notes |
|---|---|---|
| `qwen3.5:4b` | yes | **active model in `application_setting`** |
| `openbmb/minicpm-v4.5:latest` | yes | prior diagnostic model |
| `qwen2.5-coder:7b` | no | |
| `qwen2.5:7b` / `qwen2.5:3b` | no | |
| `llama3:latest`, `deepseek-coder:latest` | no | |

**App-side inventory artifact `…\MedFlux\runtime\installed_models.json` (`VERIFIED`):**

| Model | Params | Quant | Vision |
|---|---|---|---|
| `gemma4e-64k:latest` | 8.0B | Q4_K_M | yes |
| `gemma4:e4b` | 8.0B | Q4_K_M | yes |
| `qwen3-vl:8b-instruct` | 8.8B | Q4_K_M | yes |
| `qwen3:14b` | 14.8B | Q4_K_M | no |
| `aya-expanse:8b` | 8.0B | Q4_K_M | no |
| `qwen3:8b` | 8.2B | Q4_K_M | no |

**Finding (high impact, `VERIFIED`):** the two inventories are **disjoint**. The app-side file
contains neither the active `qwen3.5:4b` nor `openbmb/minicpm-v4.5`, and the live library
contains none of the six listed models. Any UI or operator decision driven by
`installed_models.json` will be wrong. It is a **stale snapshot**, not a live query.

Verify / refresh:

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 4
Invoke-RestMethod http://127.0.0.1:11434/api/ps  | ConvertTo-Json -Depth 4
ollama list
```

**Benchmark history (`OBSERVED`, earlier session):** an `openbmb/minicpm-v4.5` vision
diagnostic scored 9/9 on an RTX 3070. There is **no** equivalent 9/9 result for
`qwen3.5:4b`; do not claim one.

---

# 17. EVIDENCE AND GROUNDING MODEL

- Facts are accepted only with **source + page + confidence**, plus geometry for highlighting.
- The verifier rejects ungrounded answers; when nothing survives, the pipeline records a failed
  or partial analysis instead of inventing values. (`VERIFIED`, project rule + code trace)
- Canonical artefacts are integrity-checked: the artefact's `source_sha256` must equal the
  version's `sha256`, and the artefact's own hash is re-verified on read
  (`resolve_canonical_for_version`). (`VERIFIED`)
- Evidence navigation endpoint: `GET /api/documents/{vid}/source-region` with
  `organization_slug`, `snippet`, `page`. `source_region.py` resolves the narrowest matching
  region. (`VERIFIED`)
- Organisation-scope behaviour of that endpoint was exercised with a read-only probe and behaved
  as designed: `200` for own org + own version, `404` for unknown slug / foreign version /
  malformed id, `401` without a cookie. (`VERIFIED`)

---

# 18. EXTRACTION SCHEMA AND CONFIDENCE

- The harness emits structured JSON validated against a schema; validation failures surface as
  the `invalid_schema` category and are mapped to the German UI text
  "Die lokale KI konnte das Ausgabeformat nicht verarbeiten." (`VERIFIED`)
- Extraction rows carry status (`success` / `partial` / `failed`), model id, prompt version,
  sanitized error and diagnostic metadata. (`VERIFIED`)
- `build_import_state` deliberately follows the **latest AI extraction**, not the OCR run, so a
  successful PDF/OCR pass with a partial semantic result shows "Teilanalyse – Prüfung
  erforderlich". (`VERIFIED`)
- Historical failure class observed in the trial data: a raster/scan-only contract produced a
  `ValidationError` at the schema/verification stage. (`OBSERVED`)

---

# 19. CONTRACT 360 READ MODEL

`backend/app/contracts/detail/` builds one aggregate per contract that the UI renders:

- header/identity, supplier, contract number, term and dates;
- the accepted extraction with per-field source, page and confidence;
- deterministic calculations and warnings;
- equipment relations and coverage;
- intelligence sections: graph, obligations, policies, actions, billing basis, risk,
  authority diagnostics;
- operational sections: ownership, lifecycle decision, work items, processing jobs,
  capabilities (e.g. deletion), notifications.

Live traffic in the newest pilot run confirms every one of these sections is fetched for the
Radiosurgery contract `01a0fe3a-af56-7e5a-9c80-231fc3b28222` with `200 OK`. (`VERIFIED`)

---

# 20. EQUIPMENT DOMAIN

- `backend/app/equipment/` owns equipment identity, normalization and persistence;
  `equipment` + link rows carry contract↔equipment relations and the next service date.
- Equipment coverage participates in the work queue (`equipment_coverage_review` is a real work
  item type in the trial DB). (`VERIFIED`)
- Equipment identity was one of the corrected areas in the HEAD commit
  ("improve grounded contract extraction and review diagnostics"). `UNKNOWN` — the exact
  per-commit change list; verify with `git show --stat ae3e76d6d33fef11e8768a3ec1ebe3ed596c6545`.

---

# 21. FINANCE AND COST MODEL

- Costs are computed by code, never by the model (`backend/app/contracts/calculation/`).
- The trial DB holds 9 calculation runs, all in state `computed`, with
  `overall_review_required = true`. (`VERIFIED`)
- `missing_cost` exists as a work item type → the system models *unknown* cost explicitly
  instead of defaulting to zero. (`VERIFIED`)
- Cost centres are a first-class entity (`GET /api/cost-centers`), and billing basis is exposed
  per contract (`GET /api/intelligence/billing/contracts/{id}/basis`). (`VERIFIED`)
- Benchmark ground truth previously established: Radiosurgery 52.500 EUR/year, 4-year term,
  210.000 EUR derived; Optis monthly 12.000 EUR expected but only partial evidence.
  `OBSERVED` (earlier sessions; re-confirm against `data/benchmark/` before quoting).

---

# 22. WARNINGS, DEADLINES AND CALCULATIONS

- `evaluate_contract_warnings` runs after extraction and produces warning rows; the trial DB has
  4 warnings. (`VERIFIED`)
- Work item types present in the trial DB: `missing_cost`, `manual_review`,
  `equipment_coverage_review`, `contract_expired`. (`VERIFIED`)
- Termination deadlines are computed from the accepted term/notice facts, not from model output.
- Warning thresholds live in code (`warnings/`), not in configuration or prompts.
  `UNKNOWN` — the exact threshold table; verify:
  `Select-String -Path backend\app\contracts\warnings\*.py -Pattern "days|DAYS|threshold"`.

---

# 23. AUTHENTICATION, ROLES AND ORGANIZATION SCOPE

- Cookie-based session auth; `POST /api/auth/login`, `GET /api/me`.
- Middleware: request id, rate limiting (login included), CORS allow-list, security headers.
- Public endpoints: `/health`, `/live`, `/ready`, `/api/auth/login`. Everything else requires a
  session; organization context is validated server-side and mismatches fail closed with 404.
- Fail-closed configuration rules in `core/config.py`: `pilot|production` require
  `AUTH_ENABLED=true` and `AUTH_COOKIE_SECURE=true`; a non-local DB additionally requires TLS.
  (`VERIFIED`, lines 136–199)
- Trial identity store: `C:\Users\JAMAL\AppData\Local\MedFlux\runtime\FIRST_LOGIN_LOCAL_ONLY.txt`
  containing `Email` and a 32-character `Password`. **The values are deliberately not reproduced
  here.** The file itself instructs that it must not be sent to a chat assistant or to GitHub —
  this handover honours that instruction. (`VERIFIED` file shape; value withheld)
- Trial accounts in the isolated DB: two accounts, and **both** carry the `admin` membership role
  (a correction worth carrying forward: an earlier assumption of an admin/viewer split was
  wrong). (`VERIFIED`)
- The full authorization matrix (Viewer / Reviewer / Contract Manager / Admin / Developer) is
  specified in `docs/PRODUCTION_READINESS.md` and must be validated per role including
  cross-hospital negative tests. (`VERIFIED` as specification; not re-run here)

---

# 24. DATABASE TOPOLOGY (LOCAL MACHINES)

Two independent PostgreSQL installations exist. **They must not be confused.**

### A. Windows service on 5432 — installed, running, UNUSED

`VERIFIED`:

- Service `MedFluxPostgres18`, start type automatic, state running.
- Binaries `C:\ProgramData\MedFlux\postgres18\bin\postgres.exe`.
- Data directory `C:\ProgramData\MedFlux\postgres18\data`.
- `pg_hba.conf`: `scram-sha-256` only.
- **No application connections were present** during the inspection.
- The credentials in `backend/.env` for this cluster **fail authentication**.
- Consequence: the contents of this cluster are `UNKNOWN`.

### B. WSL cluster on 55432 — the actual pilot database

`VERIFIED`:

- PostgreSQL **18.6**, data directory `/opt/medflux-test-pg/data` (inside WSL).
- Reachable from Windows on `127.0.0.1:55432` (relayed; not visible in
  `Get-NetTCPConnection`, but `Test-NetConnection` succeeds).
- Database in use: **`medflux_trial_20261001`**.
- Non-template databases: `medflux_trial_20261001`, `medflux_sr415_flow`, `medflux_mig_1`,
  `medflux_restore_1`, `postgres`.
- Roles `medflux_test` and `sr415_flow` both have `LOGIN`, `SUPERUSER`, `CREATEDB` and a SCRAM
  password. `medflux_test` owns the trial databases and all 45 public tables.
  **The password of `medflux_test` is not recoverable and must not be reset.**
- Connection target (user `<DB_USER>`, password supplied out-of-band, both withheld here):
  host `127.0.0.1`, port `55432`, database `medflux_trial_20261001`, driver
  `postgresql+psycopg`.
  The DSN was supplied as a transient process environment variable
  (`MEDFLUX_TRIAL_DSN` / `DATABASE_URL`); it is **not** stored in any repository script.

### C. Which backend uses which database — the key operational fact

`VERIFIED` by socket inspection:

```text
PID 5168  (python, child of the venv launcher)  ->  4 ESTABLISHED connections to 127.0.0.1:55432
command: "…\Python310\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
launcher PID 22480: "…\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000
GET http://127.0.0.1:8000/ready -> {"status":"ready","environment":"development","database":"ok"}
```

⇒ **The backend on port 8000 runs against the 55432 trial cluster**, not against
`backend/.env`. `backend/.env` is stale relative to the running system; treat it as misleading.

Reproduce:

```powershell
Get-NetTCPConnection -State Established | Where-Object { $_.RemotePort -in 5432,55432 } |
  Select-Object LocalPort,RemoteAddress,RemotePort,OwningProcess
```

---

# 25. DATABASE SCHEMA MAP

45 public tables in `medflux_trial_20261001` (`VERIFIED` count). Core entities and their
verified relationships:

```text
organization ─┬─ account ─── membership ── role
              ├─ hospital / department (organization-structure)
              └─ contract ─┬─ contract_document ─── document_version ─── document_file
                           ├─ contract_extraction ─── evidence
                           ├─ contract_equipment ─── equipment
                           ├─ contract_calculation (9 runs)
                           ├─ work_item / warning
                           ├─ ownership
                           ├─ lifecycle decision
                           └─ intelligence: graph, obligations, policies, action proposals
application_setting : key/value (ai_provider, ai_model, …)
alembic_version     : c4d6e8f00930
```

Model count proof and full column map:

```sql
select count(*) from information_schema.tables where table_schema='public';
\d document_file          -- storage_key, sha256 (UNIQUE), mime_type, import_status,
                          -- duplicate_detected, original_filename
\d document_version       -- document_file_id, storage_key, sha256, version_no
\d contract_document      -- contract_id, document_version_id, role ('main'), organization_id
\d application_setting
```

---

# 26. TRIAL DATABASE CONTENT SNAPSHOT

`medflux_trial_20261001` @ `VERIFIED` (read-only counts/queries):

| Entity | Count |
|---|---:|
| organizations | 1 (`klinik-trial`, display "Klinik Trial") |
| accounts | 2 (`a***@klinik-trial.local`, `u***@klinik-trial.local` — **both admin**) |
| contracts | 4 |
| `document_file` | 3 |
| `document_version` | 3 |
| `contract_extraction` | 19 |
| `evidence` | 47 |
| `equipment` | 4 |
| contract↔equipment links | 4 |
| calculation runs | 9 (all `computed`, `overall_review_required = true`) |
| work items | 5 |
| warnings | 4 |
| public tables | 45 |
| alembic head | `c4d6e8f00930` |

Contract rows (`VERIFIED` ids and key attributes):

| Contract id | Subject | State |
|---|---|---|
| `01a0f73e-8fae-70cd-9bb9-38b4293a2a2a` | duplicate/orphan Optis row | draft, no supplier, linked to the same Optis `document_version` as the row below |
| `01a0f82c-53ba-7e6f-b297-4298d69da1a6` | **Optis / Abbott Medical GmbH** | status `unknown`, risk `medium`, lifecycle `active`, 4 equipment links |
| `01a0fe3a-af56-7e5a-9c80-231fc3b28222` | **Radiosurgery**, supplier Brainlab Sales GmbH | version `01a0fe32-2a5e-7469-984f-d41189c59f11`; content endpoint `200 OK` |
| `01a0fe49-…` (full id `UNKNOWN`) | Harmony raster/scan fixture | extraction previously failed with `ValidationError` |

**Finding (duplicate lifecycle, `VERIFIED`):** two contract rows point at the **same**
`document_version` with different supplier and status. This is the residue of a
"duplicate-repair" iteration (see the pilot-run timeline in section 32). It inflates portfolio
counts and can make one PDF appear as two contracts with contradictory suppliers.

Full verification query:

```sql
select cd.contract_id, c.supplier_name, c.status, c.risk_level, c.lifecycle_status,
       cd.document_version_id, cd.role
from contract_document cd join contract c on c.id = cd.contract_id
order by cd.document_version_id;
```

---

# 27. MIGRATIONS AND ALEMBIC STATE

- 36 migration files under `backend/alembic/versions/`, no duplicate revisions detected.
- Head revision: **`c4d6e8f00930`**.
- The trial DB's `alembic_version` equals that head → schema and repository are in sync there.
- The Windows 5432 cluster's migration state is `UNKNOWN` (no access).
- Release gate requirement (`docs/PRODUCTION_READINESS.md`): migrate an **empty** PostgreSQL
  database to head as part of CI.

Verify:

```powershell
cd backend; .\alembic.exe heads; .\alembic.exe current
```

---

# 28. FRONTEND ROUTES, STATE AND API CLIENT

- Next.js App Router; `frontend/lib/api.ts` is the single HTTP boundary; auth state in
  `components/auth/AuthProvider.tsx`.
- `next.config.js` resolves the backend from `NEXT_PUBLIC_API_URL` (default
  `http://localhost:8000`). In the isolated pilot the frontend on 3010 was verified to point at
  `http://127.0.0.1:8010` (`frontend-audit.json`). (`VERIFIED`)
- Credentials are sent with API calls (cookie auth), which is why the backend's fail-closed 404s
  matter for UI error handling: a 404 may mean "forbidden", "wrong organization" or "missing
  document" and must not be rendered as a contract-existence leak.
- PDF viewing uses a PDF.js worker alias configured in `next.config.js`.

`UNKNOWN` — full route inventory (verify with the command in section 10).

---

# 29. ASSISTANT (SECURE AI ASSISTANT)

- Plan/spec: `docs/architecture/SECURE_AI_ASSISTANT_INTEGRATION_PLAN.md`; UI in
  `frontend/components/assistant/`. (`VERIFIED` as existing)
- Behavioural changes recorded on the Frankfurt branch (`VERIFIED` from the QA doc): the
  frontend shows a friendly, proactive greeting instead of an unsolicited security banner; the
  backend system prompt answers in the user's language and reserves caveats for relevant
  requests.
- Security invariants: organization and membership are authorized **before** any model call and
  re-checked after generation; cross-org attempts fail with 403/404 **before** the model runs;
  the assistant must never reveal that a foreign contract exists. Rendering a *friendly* message
  for a real backend 403/404 requires an explicit non-leaking error contract — it must not be
  faked client-side.
- `UNKNOWN` — whether the non-leaking error contract has since been implemented. Verify:
  `Select-String -Path frontend\components\assistant\*.tsx -Pattern "403|404|nicht gefunden"`.

---

# 30. API SURFACE AND ROUTE REGISTRATION

- `main.py` performs 29 `include_router` calls (27 product modules + audit router).
- One registered-surface gap: `demo.py` is not registered, so any documentation advertising
  `/api/demo/*` is stale. (`VERIFIED`)
- Every business route takes `organization_slug` and re-validates the actor↔organization pair;
  organization/hospital/department values are context, never authorization credentials
  (`docs/PRODUCTION_READINESS.md`). (`VERIFIED` as specification)
- `/ready` is the deployment gate: it fails closed when the primary database is unavailable.

Enumerate the live surface:

```powershell
(Invoke-RestMethod http://127.0.0.1:8000/openapi.json).paths.PSObject.Properties.Name | Sort-Object
```

---

# 31. TESTS AND VERIFICATION EVIDENCE

**Existing suites (`VERIFIED` as present):**

- `backend/tests/` — broad pytest suite, including drift/legacy isolation suites that reference
  the isolated cluster and a migration gate.
- `backend/scripts/verify_migrated_fixture.py` — migrated-fixture verification helper.
- `frontend/test/` — Vitest, including security and accessibility assertions.
- `.github/workflows/release-gate.yml` — the automated gate required by
  `docs/PRODUCTION_READINESS.md`: empty-DB migration to head, full backend pytest against
  isolated PostgreSQL, frontend `npm run verify`, `docker compose config`, and both production
  image builds.

**Commands:**

```powershell
cd backend;  pytest
cd frontend; npm run lint; npm run test; npm run build
```

**`UNKNOWN` / not executed here:** no test suite was executed during this investigation (the
task was read-only inspection, and the suites write caches and require the isolated cluster).
Consequently, **no green-suite claim is made anywhere in this document.** Before relying on any
behaviour, run the suites and record the result.

---

# 32. PILOT / TRIAL RUNTIME TOPOLOGY

**Live services (`OBSERVED` during this session):**

| Port | Service | State |
|---:|---|---|
| 3000 | frontend (original) | listening; HTTP not probed |
| 3010 | frontend (isolated pilot) | `200` on `/` and `/login` |
| 5432 | Windows PostgreSQL 18 | listening, **no application connections** |
| 8000 | backend (original) | `/health`, `/live`, `/ready` → `200`, `database: ok` |
| 8010 | backend (isolated pilot) | `/health`, `/live`, `/ready` → `200`, `database: ok` |
| 55432 | WSL PostgreSQL 18 (trial) | reachable |
| 11434 | Ollama | reachable |
| 3011 / 8011 | further pilot slots | **not listening** at check time |

**Pilot safety artifacts (`VERIFIED`)** — every pilot run writes these five files:

```text
identity-check.json   -> {"verified": true,
                          "data_directory": "/opt/medflux-test-pg/data",
                          "current_database": "medflux_trial_20261001",
                          "server_addr": "127.0.0.1/32", "server_port": 55432,
                          "in_recovery": false,
                          "reason": "identity matches closed allowlist"}
barrier-audit.json    -> {"target": "127.0.0.1:55432/medflux_trial_20261001",
                          "server_port": 55432, "barrier": "closed", "override": "none",
                          "server_addr": "127.0.0.1/32", "pid": <pid>,
                          "data_directory": "/opt/medflux-test-pg/data"}
backend.log / backend.err.log / backend.pid
```

**Pilot-run history on 2026-10-03 (`VERIFIED`, 12 runs, 00:35 → 02:27)** — each directory is a
named iteration and is direct evidence of the engineering sequence:

```text
runtime-trial-ae3e76d-20261003
runtime-trial-ae3e76d-postvision-20261003
runtime-trial-ae3e76d-schema-20261003
runtime-trial-ae3e76d-semantic-resilience-20261003
runtime-trial-ae3e76d-schema-inline-20261003
runtime-trial-ae3e76d-chunking-20261003
runtime-trial-ae3e76d-duplicate-repair-20261003
runtime-trial-ae3e76d-malformed-split-20261003
runtime-trial-ae3e76d-current-code-20261003
runtime-trial-ae3e76d-radiosurgery-codefix-20261003
runtime-trial-ae3e76d-radiosurgery-equipfinance-20261003
runtime-trial-ae3e76d-radiosurgery-duration-20261003      <- newest, ran on port 8011, now stopped
```

The newest run's log shows the accepted flow end-to-end: login → `/api/ai/status` →
`POST /api/documents/{vid}/reanalyze` (200) for both the Optis and Radiosurgery versions →
Contract 360 sections for both contracts → document content `200 OK` → no `ERROR`, `WARNING` or
`Traceback` lines in that run. (`VERIFIED`)

**External (non-repository) pilot tooling (`VERIFIED` as existing),
`C:\Users\JAMAL\AppData\Local\Temp\opencode\sr415\`:**

| File | Purpose |
|---|---|
| `repro_415.py` | read-only reproduction of the source-region **HTTP 415**; targets base `http://127.0.0.1:8000`, version `01a0f73c-8af7-72e6-b6ea-9dfde110418c`, snippet `Rahmenvertrag Nr. RAV-00074 4 - OPTIS™ Mobile Next Imaging System`; login + GET only |
| `http_access.py` | organisation/access matrix for `/api/documents/{vid}/source-region` (own org → 200; unknown slug / foreign version / malformed id → 404; no cookie → 401) |
| `http_ab.py` | A/B variant probe |
| `seed_flow_db.py`, `make_isolated_flow_db.sh` | create/seed the separate `medflux_sr415_flow` flow database and org `sr415-flow` |
| `audit_live_db_readonly.py`, `audit_trial_cluster.sh`, `show_effective_db.py` | read-only DB/cluster/effective-DSN audits |
| `start_flow_backend.ps1`, `build_pdf.py`, `ui_flow_source.pdf` | isolated flow backend launcher and fixture |
| `flow-*.log`, `parent-*.log`, `repro-backend.log`, `*.pid` | run artefacts (content requests in the flow DB returned `200 OK`) |

`…\Temp\opencode\medflux-real-contract\` (referenced by `repro_415.py` as `TRIAL`) **no longer
exists** — it was cleaned up. (`VERIFIED`)

**Local application state directory `C:\Users\JAMAL\AppData\Local\MedFlux\`:**

| Path | Contents |
|---|---|
| `runtime/` (16 files) | `FIRST_LOGIN_LOCAL_ONLY.txt`, `installed_models.json`, launcher/bat logs, backend/frontend logs and pids |
| `runtime-trial/` (9 files) | older pilot artefacts incl. `frontend-audit.json` |
| `runtime-trial-ae3e76d-*/` (12 dirs × 5 files) | the 2026-10-03 pilot timeline above |
| `repair-backups/` (3 files, 2026-09-25) | pre-repair backups |
| `pgsql18/` (20,688 files, 2026-09-25) | extracted PostgreSQL 18 tree |
| `install-cache/` (2 files) | installer cache |

---

# 33. REAL CONTRACTS: RADIOSURGERY

- File: `Servicevertrag Radiosurgery 2021.pdf` in `data/benchmark/` (exact sub-path `UNKNOWN`;
  verify with `Get-ChildItem data\benchmark -Recurse -Filter *Radiosurg*`).
- Contract row `01a0fe3a-af56-7e5a-9c80-231fc3b28222`, supplier **Brainlab Sales GmbH**,
  document version `01a0fe32-2a5e-7469-984f-d41189c59f11`.
- On-disk original: `backend\data\contracts\01a0fe47080f7d8381eb8cdbf090bb4c\original.pdf`
  (5,522,724 B) plus canonical artefact (708,600 B). (`VERIFIED`)
- Historical ground truth (`OBSERVED`, earlier sessions): 52.500 EUR/year, 4-year term,
  210.000 EUR derived, Exactrac X-Ray equipment; a **false contract title originating from the
  AGB** had to be rejected; the relevant date only appears on a later page; equipment and finance
  fields were initially wrong and were corrected over the 12 pilot iterations
  (`radiosurgery-codefix`, `-equipfinance`, `-duration`). A `ValidationError` in an earlier run
  was schema/verification-stage, not transport.
- Latest state: extraction `partial`/`valid` with `qwen3.5:4b`; content endpoint `200 OK`;
  calculations `computed` with `overall_review_required = true` — i.e. **import and rendering
  work, but the record is still flagged for human review.** (`VERIFIED`)

---

# 34. REAL CONTRACTS: OPTIS / FRANKFURT RAV-00074

- File: `Frankfurt, Nordwest KH RAV-00074 Optis M Next LFZ 04.06.2025 - 03.06.2029.pdf`
  (exact sub-path `UNKNOWN`).
- Two contract rows reference one `document_version`
  (`01a0f73e-…` draft/orphan and `01a0f82c-…` Abbott Medical GmbH) — the duplicate lifecycle
  described in section 26. (`VERIFIED`)
- Requested version `01a0f73c-8af7-72e6-b6ea-9dfde110418c` has **no canonical storage
  directory on disk** → content 404 (section 14). The Optis original that does exist is
  `01a0f73c8aef7fab8b962645e5a557dd\original.pdf` (442,631 B) with canonical artefact
  (188,642 B).
- Historical ground truth (`OBSERVED`): Optis **Mobile Next**, supplier Abbott, term
  04.06.2025–03.06.2029, 48 months expected, 12.000 EUR monthly expected but only partial
  evidence. Supplier detection was wrong at one point (a contract title from the AGB section) and
  was corrected to Abbott.
- The source-region feature was built for exactly this document: the snippet used by the
  read-only repro is `Rahmenvertrag Nr. RAV-00074 4 - OPTIS™ Mobile Next Imaging System`, and
  the review branch is literally `review/source-region-pdf-content-415-20261002`. (`VERIFIED`)

---

# 35. KNOWN BUGS, FIXES AND REGRESSIONS

| # | Issue | Evidence | Status |
|---|---|---|---|
| 1 | Backend on 8000 runs against the trial DB, not `backend/.env` | 4 established sockets to 55432 | open — `backend/.env` misleading |
| 2 | Windows PostgreSQL 5432 fully unused, credentials invalid | service running, 0 app connections, auth failure | open — inventory unknown |
| 3 | 21 on-disk document dirs vs 3 `document_file` rows | filesystem vs DB counts | open — orphaned artefacts |
| 4 | Legacy manifest `.index.json` is `{}` | 2-byte file | open — manifest dedupe disabled |
| 5 | Duplicate Optis contract rows on one `document_version` | DB join | open — inflates counts, contradictory suppliers |
| 6 | Document content 404 for the Optis pair | 404 vs 200 in pilot logs | open — storage key without a file |
| 7 | Storage root depends on process CWD | `contracts_dir` is relative | open — `AGENTS.md` documents the wrong path |
| 8 | `installed_models.json` is disjoint from the live Ollama library | both inventories read | open — operator decisions will be wrong |
| 9 | Generic user-facing failures hide the failing stage | QA code trace | open — needs admin-only diagnostics |
| 10 | Docling→native-PDF fallback silently disables OCR | code path | documented code-path risk |
| 11 | `demo.py` route module never registered | router registration | dead code / stale docs |
| 12 | Historical `ValidationError` on a raster-only fixture | extraction row | fixed for current runs; class remains possible |

**Fixed during the 2026-10-03 pilot sequence (`INFERRED` from the run names plus observed
outcomes):** grounded-extraction and review diagnostics (HEAD commit), schema output shape,
chunking, semantic resilience, duplicate repair, malformed split handling, Radiosurgery equipment
and finance fields, and Radiosurgery run duration. The newest run shows no errors/warnings.
`UNKNOWN` — the exact commit that fixed each item; verify with `git log` (section 4).

---

# 36. BUILD, TEST AND PACKAGING

- Containers: `docker-compose.yml` at root; `docs/PRODUCTION_READINESS.md` requires
  `docker compose config` validation plus backend and frontend production image builds in CI.
- Local launchers at root: `Start Software.bat`, `START_MEDFLUX_LOCAL.bat`,
  `STOP_MEDFLUX_LOCAL.bat`. Launcher logs exist under `%LOCALAPPDATA%\MedFlux\runtime\`
  (`bat-final-integration.log`, `bat-test-after-fix.log`, `bat-test2.log`,
  `launcher-integration-test.log`). (`VERIFIED`)
- Frontend production build: `npm run build`; combined gate: `npm run verify`.
- Backend run: `python -m uvicorn app.main:app --host 127.0.0.1 --port <port>` **from the
  `backend` directory** (see section 5 for why the directory matters).
- Release record requirements (`docs/PRODUCTION_READINESS.md`): version/SHA, migration head,
  release-gate run, UAT date/tester, environment and AI provider/model versions, known
  limitations, backup/restore verification date, rollback version and procedure.
- `UNKNOWN` — whether a desktop/installer packaging target exists beyond the `.bat` launchers
  and Docker. Verify: `Get-ChildItem -Recurse -Include *.iss,*.wxs,*.nsi,tauri.conf.json,electron*`.

---

# 37. OPERATIONS RUNBOOK

**Read-only health check:**

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8010/ready        # isolated pilot
Invoke-RestMethod http://127.0.0.1:11434/api/ps      # loaded models
```

**Confirm which DB a backend actually uses (do not trust `.env`):**

```powershell
Get-NetTCPConnection -State Established |
  Where-Object { $_.RemotePort -in 5432,55432 } |
  Select-Object LocalPort,RemoteAddress,RemotePort,OwningProcess
```

**Confirm cluster identity before any write (repeat the pilot barrier):**

```sql
select current_database(), inet_server_addr(), inet_server_port(),
       pg_is_in_recovery(), current_setting('data_directory');
```

**Document reconciliation (dry run first, never against 5432):**

```powershell
cd backend
python -m app.documents.reconcile --organization-slug klinik-trial --all-legacy --limit 25 --dry-run
```

**Model selection:** change provider/model through the Admin/Developer AI routes or
`application_setting` (`ai_provider`, `ai_model`), then confirm with
`GET /api/ai/status` and `GET /api/processing-jobs`. Never hand-edit model files.

**Re-analysis of a single version (writes; pilot only):**

```text
POST /api/documents/{document_version_id}/reanalyze?organization_slug=<slug>
```

**Guardrails:** no operation in the pilot may target `5432`; confirm `barrier: closed` and
`override: none` in `barrier-audit.json` before starting any pilot run.

---

# 38. SOURCES OF TRUTH, UNKNOWNS AND OPEN QUESTIONS

**Sources of truth, in priority order:**

1. `AGENTS.md` — project rules and the MVP DoD.
2. `docs/PRODUCTION_READINESS.md` — what "ready" means (gates, UAT, authz, security).
3. `docs/INTEGRATION_BASELINE.md` — the feature DoD chain
   `model/migration → backend API → authorization/scope → frontend domain API → UI states → audit → tests → documentation → CI verification`.
4. `docs/PROJECT_PROGRESS.md` — 18-step history; **must be updated after every completed step**
   per `AGENTS.md`.
5. Code and DB for current behaviour; runtime artifacts (`identity-check.json`,
   `barrier-audit.json`, `backend.log`) for what actually ran.

**Open questions, each with its verification command:**

| Question | Command |
|---|---|
| Exact git history of the last fixes | `git log --oneline --decorate -40` |
| Full commit stat of HEAD | `git show --stat ae3e76d6d33fef11e8768a3ec1ebe3ed596c6545` |
| Storage key/file existence per version | SQL in section 14 |
| `application_setting` scoping | `\d application_setting` |
| Warning thresholds | `Select-String backend\app\contracts\warnings\*.py -Pattern "days|threshold"` |
| Full frontend route list | `Get-ChildItem frontend\app -Recurse -Filter page.tsx` |
| Assistant error-contract state | `Select-String frontend\components\assistant\*.tsx -Pattern "403|404"` |
| Contents of the 5432 cluster | needs a valid credential — **do not reset** |
| Origin of the `medflux_test` password | not recoverable; `UNKNOWN` by design |
| Exact benchmark fixture paths | `Get-ChildItem data\benchmark* -Recurse -Filter *.pdf` |
| Backend test-suite green state | `cd backend; pytest` (not run here) |
| Packaging targets beyond `.bat`/Docker | `Get-ChildItem -Recurse -Include *.iss,*.wxs,tauri.conf.json` |

---

# 39. MACHINE-READABLE QUICK CONTEXT

```yaml
document:
  path: "C:/Users/JAMAL/Desktop/Medflux/MEDFLUX_MASTER_HANDOVER.md"
  generated: "2026-10-03"
  sections: 40
  secrets_included: false
  concurrent_agent_active: true

repository:
  root: "C:/Users/JAMAL/Desktop/Medflux"
  branch: "fix/frankfurt-contract-analysis-20261001"
  head: "c900b07  fix: preserve scanned contract facts and review state"
  head_parent: "19af894  fix: stabilize Radiosurgery and OPTIS contract extraction"
  handover_baseline_commit: "ae3e76d  fix: improve grounded contract extraction and review diagnostics"
  baseline_is_ancestor: true
  uncommitted_by_concurrent_agent: 17
  uncommitted_diffstat: "+771 / -91"
  package_manager_conflict: "pnpm-lock.yaml + pnpm-workspace.yaml appeared next to npm"
  untracked: ["MEDFLUX_MASTER_HANDOVER.md (this file)", ".playwright-mcp/",
              "contract-detail-verified.png", "docs/MEDFLUX_PRODUCT_BUILD_PLAN.md",
              "frontend/lib/organization-tree.ts", "frontend/pnpm-lock.yaml",
              "frontend/pnpm-workspace.yaml",
              "frontend/test/organization-tree.test.ts",
              "frontend/test/organization-structure-manager.test.tsx",
              "frontend/test/contract-ownership-roles.test.tsx",
              "backend/tests/test_contract_department_roles_api.py"]
  stash: ["stash@{0}: On JAMAL: local-before-medflux-test"]
  tag: "backup/pre-assistant-fix-20261001"

stack:
  frontend: {framework: "Next.js", version: "14.2.15", react: "18.3.1", tests: "Vitest"}
  backend: {framework: "FastAPI", orm: "SQLAlchemy", migrations: "Alembic"}
  ai: {runtime: "Ollama", version: "0.24.0", external_api_required: false}
  pdf: "PyMuPDF (+ Docling/OCR when configured)"

database:
  windows_5432:
    service: "MedFluxPostgres18"
    binaries: "C:/ProgramData/MedFlux/postgres18/bin"
    data_dir: "C:/ProgramData/MedFlux/postgres18/data"
    hba: "scram-sha-256"
    application_connections: 0
    contents: "UNKNOWN (credential in backend/.env fails auth)"
  wsl_55432:
    version: "18.6"
    data_dir: "/opt/medflux-test-pg/data"
    database: "medflux_trial_20261001"
    public_tables: 45
    alembic_head: "c4d6e8f00930"
    roles: ["medflux_test", "sr415_flow"]        # both LOGIN+SUPERUSER+CREATEDB+SCRAM
    role_passwords: "<REDACTED / NOT RECOVERABLE>"
  migrations_on_disk: 36

runtime:
  ports_listening: [3000, 3010, 5432, 8000, 8010, 55432, 11434]
  ports_not_listening: [3011, 8011]
  backend_8000: {ready: "ok", actual_db: "127.0.0.1:55432", note: "NOT backend/.env"}
  backend_8010: {ready: "ok", actual_db: "127.0.0.1:55432/medflux_trial_20261001"}
  frontend_3010: {api_base: "http://127.0.0.1:8010"}
  pilot_runs_2026_10_03: 12
  newest_pilot: "runtime-trial-ae3e76d-radiosurgery-duration-20261003 (port 8011, stopped)"
  barrier: "closed"
  barrier_override: "none"

trial_data:
  organization: "klinik-trial"
  accounts: 2
  account_roles: "both admin"
  contracts: 4
  document_files: 3
  document_versions: 3
  extractions: 19
  evidence: 47
  equipment: 4
  equipment_links: 4
  calculation_runs: 9
  work_items: 5
  warnings: 4
  latest_extraction_model: "qwen3.5:4b"
  latest_extraction_status: "partial/valid"

storage:
  configured_contracts_dir: "./data/contracts"   # relative to process CWD
  repo_root_data_contracts: "empty (.gitkeep only)"
  effective_root: "Medflux/backend/data/contracts"
  document_dirs_on_disk: 21
  originals_present: 20
  db_document_files: 3
  legacy_index_json: "{} (2 bytes)"

ai_models:
  active: "qwen3.5:4b"
  live_ollama: ["qwen3.5:4b", "openbmb/minicpm-v4.5:latest", "qwen2.5-coder:7b",
                "qwen2.5:7b", "qwen2.5:3b", "llama3:latest", "deepseek-coder:latest"]
  installed_models_json: ["gemma4e-64k:latest", "gemma4:e4b", "qwen3-vl:8b-instruct",
                          "qwen3:14b", "aya-expanse:8b", "qwen3:8b"]
  inventory_drift: true
  minicpm_vision_benchmark: "9/9 on RTX 3070 (historical)"
  qwen35_vision_benchmark: "UNKNOWN"

known_open_issues:
  - id: 1
    summary: "backend/.env does not match the running backend (8000 uses 55432)"
  - id: 2
    summary: "Windows PostgreSQL 5432 unused; credentials invalid; contents unknown"
  - id: 3
    summary: "21 storage dirs vs 3 document_file rows (orphaned artefacts)"
  - id: 4
    summary: "legacy .index.json empty -> manifest duplicate detection disabled"
  - id: 5
    summary: "duplicate Optis contract rows share one document_version"
  - id: 6
    summary: "document content 404: storage_key without file (fail-closed by design)"
  - id: 7
    summary: "contracts_dir is CWD-relative; AGENTS.md documents the wrong path"
  - id: 8
    summary: "installed_models.json is disjoint from the live Ollama library"
  - id: 9
    summary: "generic failure messages hide the failing stage (needs admin-only diagnostics)"
  - id: 10
    summary: "Docling -> native-PDF fallback disables OCR (code-path risk)"
  - id: 11
    summary: "api/routes/demo.py never registered (dead code / stale docs)"

verification_status:
  test_suites_run: false
  source_modified: false
  database_modified: false
  git_mutated: false
  credentials_changed: false
```

---

# 40. SECRET REDACTION AUDIT AND DOCUMENT VERIFICATION

**Redaction policy applied.** The following categories were deliberately excluded and are
represented only by placeholders or by a description of *where* the value lives:

| Secret class | Where it exists (documented, value withheld) |
|---|---|
| Pilot login credential | `%LOCALAPPDATA%\MedFlux\runtime\FIRST_LOGIN_LOCAL_ONLY.txt` (`Email`, 32-char `Password`) |
| Database passwords | `backend\.env` (5432, non-functional), WSL cluster roles `medflux_test` / `sr415_flow` |
| DSN with credentials | process environment `MEDFLUX_TRIAL_DSN` / `DATABASE_URL` (transient, not in any repo script) |
| Script-embedded credential | `…\Temp\opencode\sr415\http_access.py` (hard-coded flow password) |

**Patterns excluded from this document:** no credential-bearing connection URI, no
environment-variable secret literal, no bearer/JWT value, no API-key-shaped token, no SHA-256
digest value, no real e-mail address bound to a credential, and not the raw content of
`FIRST_LOGIN_LOCAL_ONLY.txt`. Only the placeholder `<REDACTED>` (3 occurrences) and structural
descriptions appear. The redaction scan in section 40 was executed against this file and
returned zero hits for every secret pattern.

**How this document was verified**

- Every path in this document was either read directly in this session or marked `UNKNOWN`
  with the command that would confirm it.
- Every runtime claim is either a socket/HTTP observation from this session or a file read from
  a pilot artifact directory.
- Every database claim comes from read-only queries against `medflux_trial_20261001`
  (55432). No write, migration or DDL was executed.
- Claims that could not be established (5432 inventory, green test suites, exact git history,
  exact benchmark fixture paths, packaging targets, assistant error-contract state) are listed in
  section 38 with verification commands rather than being guessed.
- The git state in section 4 and in the YAML block was **re-verified after the concurrent
  commits landed**, so it reflects the current state, not the state at the start of the
  investigation.

**Integrity statement and concurrency**

- This handover created exactly **one** file: this document. No other file in the repository was
  created, edited, staged, committed or deleted by this work. No database row, role, password or
  migration was touched.
- A **second agent was committing to the same branch concurrently** (commits `19af894` and
  `c900b07`, plus 17 modified files). Those changes are documented in section 4 for context and
  are **not** attributable to this handover. Anyone acting on this document must re-run
  `git status` and `git log` first.

**Handover state:** the repository is in the state described above; no remediation has been
applied. The highest-value next actions, in order, are (1) repair the storage/DB mismatch and
the duplicate Optis contract rows, (2) reconcile `backend/.env` with reality, (3) refresh the
model inventory source of truth, (4) resolve the npm/pnpm package-manager conflict, and
(5) run and record the backend and frontend suites.