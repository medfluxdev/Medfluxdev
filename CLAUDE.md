# CLAUDE.md

Guidance for Claude Code in this repository. `AGENTS.md` (German) is the authoritative rule source; this file condenses it and adds what the code actually does today. Where they disagree, the code wins and `AGENTS.md` should be corrected (see "Known drift" below).

## What Medflux is

Local-first contract intelligence for German hospitals: imports PDF/DOCX maintenance and service contracts, extracts facts with a **local** LLM (Ollama), and computes deadlines, costs, warnings and work items **deterministically in code**. No external AI API, ever. The product has grown well past the 18-step MVP (all 18 done since 2026-09-18): Contract 360, intelligence graph (obligations/policies/risk/actions), org structure, ownership, lifecycle, work queue, billing basis, a secure AI assistant and evidence highlighting in the PDF.

The current plan lives in `docs/architecture/WORKPLAN_ORGSTRUKTUR_PHASE1_20261003.md`. WP1 (org structure) is done. Still open: WP2 finance fields, WP3 review provenance, WP4 notifications, WP5 analytics and the import wizard (`docs/architecture/CONTRACT_IMPORT_WIZARD.md`). The latest branch-unification state is in `docs/BRANCH_UNIFICATION_20261004.md` and `HANDOFF_20261004.md`.

## Non-negotiable rules

- **The AI extracts facts; code calculates.** Termination dates, cost aggregation and warning levels belong in `backend/app/contracts/calculation/` and `warnings/`, never in prompts or model output.
- **No invented values.** A missing fact stays `null`/empty and is marked "nicht gefunden" or needs review. Every accepted fact needs evidence: source text, page (PDF only; never invent pages for DOCX), confidence and, where available, a bounding box. Unsupported critical claims are flagged for review, never replaced.
- **Fail closed:** config validation, model selection (no default model, no silent fallback), test DB identity, evidence verification and org scope (a cross-org request returns 404/403 *before* any model call).
- **The backend is authoritative** for calculations, permissions and truth. The frontend only presents. `organization_slug`, `hospital_id` and `department_id` are context, never authorization.
- **Contract content stays local.** Never send contract text or PDFs to external services. Never add network calls to non-localhost AI endpoints.
- **Never commit secrets or data:** `.env`, `backend/.env`, `data/`, `backend/data/`, logs (they may contain contract content). Never print the contents of `backend/.env`. Document variables only in `.env.example`.
- **Real contracts:** the folder `عقود حقيقية لتدريب النموذج/` (36 real hospital contract PDFs) is tracked in git, which contradicts the data rules. Don't add files to it, don't upload or quote its content, and leave the decision about removing it to the owners.
- **Progress tracking:** after each completed main step, update `docs/PROJECT_PROGRESS.md` (status, date, files, tests, issues, next step). Don't start a new main step before doing so.
- **Feature Definition of Done** (`CONTRIBUTING.md`, `docs/INTEGRATION_BASELINE.md`): model + migration → API → org/hospital/department scope → `frontend/lib/domain-api` consumer → UI loading/empty/error/permission states → audit event → backend + frontend tests → docs/integration map → CI green.
- **One implementation per concern.** Extend the existing architecture, don't build parallel versions. `DocumentProcessingService` is the only processing path. Prove code is obsolete before deleting it.
- **Git hygiene:** preserve uncommitted work. No reset/stash/clean/force-push, no `git branch -D`, never `--prune` together with `--tags`, unless the user asks explicitly. On this machine use Windows git, not WSL git (WSL git leaves stale `.git/*.lock` files).

## Repository layout

```text
backend/            FastAPI app (app/), alembic/, tests/ (flat test_*.py), scripts/, conftest.py, pytest.ini
frontend/           Next.js 14 App Router, components/, lib/, test/ (Vitest)
scripts/            operational PowerShell/Python helpers; read scripts/README.md first, some are destructive
docs/               progress log, architecture, QA traces, pilot docs, dated handoffs
design-reference/   approved static HTML mockups (medflux_final_design_system/)
experiments/        archived visual-first/LlamaIndex work; not wired into the app, excluded from tests
data/               local contracts/backups/benchmarks (git-ignored)
*.bat (root)        Windows launchers (see "Running locally")
```

Don't create nested project folders (`Medflux/Medflux`, `vertragsmonitor-ai`).

## Commands

All backend commands run **from `backend/`** with the project venv (`backend\.venv\Scripts\python.exe`), never global Python. Watch for a contaminated `PYTHONHOME`/`PYTHONPATH`.

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
python -m alembic upgrade head          # migrations are never run at app startup
python -m compileall -q app tests       # cheap syntax gate used by CI

# Frontend
cd frontend
npm install            # npm only; pnpm lockfiles were removed on purpose
npm run dev            # http://localhost:3000
npm run verify         # lint + vitest + next build (the CI gate)
npx tsc --noEmit -p tsconfig.json       # there is no typecheck script
npx vitest run test/contracts.test.tsx  # single file;  -t "name" to filter

# Pre-merge (CONTRIBUTING.md)
cd backend && pytest -q ; cd frontend && npm run verify ; docker compose config
```

### Backend tests: PostgreSQL only, guarded

There is no SQLite path: the app and its tests are Postgres-only (psycopg v3, synchronous SQLAlchemy 2, PG18 for server-side `uuidv7()`). `backend/conftest.py` → `app/testing/test_database.py` creates a random schema `medflux_test_<uuid>`, runs `Base.metadata.create_all` (not Alembic), enables `pg_trgm` and drops the schema afterwards. If the identity check fails it raises `UsageError`, and it never falls back to a product DB.

- **Locally:** the URL is taken only from `MEDFLUX_TEST_DATABASE_URL` (or `MEDFLUX_TRIAL_DSN`). It must point exactly at the isolated WSL cluster `127.0.0.1:55432/medflux_trial_20261001`, user `sr415_flow`. `DATABASE_URL` and `.env` are ignored, and port 5432 is rejected. **If neither variable is set, pytest blocks on a hidden password prompt**, so always set it, or use `MEDFLUX_UNIT_ONLY=1` for pure unit tests (DB tests then skip or fail).
- Also set `APP_ENV=test`, `AUTH_ENABLED=false`, `MEDFLUX_INSECURE_DEV=true`, `APP_SECRET_KEY=test-only-secret`. See `scripts/run_wp1_tests.bat` and `scripts/medflux_test_db.ps1 status|prepare|verify|test`; details in `docs/TEST_DATABASE.md`.
- **In CI:** `DATABASE_URL` must be exactly `127.0.0.1:5432/medflux`, user `medflux`.
- Single test: `.venv\Scripts\python.exe -m pytest -q tests/test_x.py::test_name`.
- There are no custom markers. Ollama is always mocked. Drift tests are opt-in via `DRIFT1_MIGRATED_TEST_DATABASE_URL`.
- Run focused tests while working and the full suite (~1400 tests) once at the end. Don't rerun OCR/AI benchmarks unless asked.

## Running locally (databases)

Three setups exist (`docs/DATABASE_CONFIGURATION.md`):

1. **Docker Compose:** `postgres:18` on 5432, plus backend :8000 and frontend :3000; Ollama is commented out.
2. **Windows pilot/dev:** the WSL PG18 cluster on **55432** (`START_MEDFLUX_PILOT.bat`). Don't also set `DATABASE_URL`.
3. **CI:** Postgres service, configured automatically.

`START_MEDFLUX_LOCAL.bat` and `Start Software.bat` target 5432 (Docker/local service), check Ollama at :11434, start the backend, wait for `/ready` and then start the frontend. `STOP_MEDFLUX_LOCAL.bat` stops everything. Don't trust `backend/.env` to tell you which DB a running backend uses; check the actual connections. Never run writes against an unidentified cluster.

## Backend architecture (`backend/app/`)

- `main.py`: builds the FastAPI app. Middleware from outermost in: SecurityHeaders → RequestId → LoginRateLimit → CORS → LocalAuth → ScopeContext. It registers all routers from `api/routes/` (`demo.py` is dead and unregistered). Routes are `/api/<area>`, with tenant scope as the required `organization_slug` query parameter.
- `core/config.py`: pydantic-settings `Settings`. `validate_auth_runtime()` and `validate_database_tls()` run at import, so a bad config fails the import. Pilot/production require auth and secure cookies. Disabling auth requires `MEDFLUX_INSECURE_DEV=true` (forbidden in pilot/production). Relative `DATA_DIR`/`CONTRACTS_DIR` resolve against `backend/`.
- **Import pipeline**, `documents/processing.py` (`DocumentProcessingService`, synchronous within the request):
  1. Size-bounded upload, then SHA-256 dedupe per org. Originals are stored at `<uuid_hex>/original.pdf|docx` and artifacts at `<uuid_hex>/artifacts/<run_uuid>/canonical.json`.
  2. A `ProcessingRun` is claimed.
  3. A canonical document is built with Docling + RapidOCR, falling back to native PyMuPDF. That fallback has **no OCR**, which is a known risk for scans.
  4. The harness runs.
  5. The result goes to `_persist_pipeline`, or on failure to `_persist_failed_analysis` (sanitized German message and a placeholder contract).
- **AI layer** (`ai/`):
  - `AIService` pins one provider + model per run.
  - Providers live in `ai/providers/` (Ollama, LM Studio, llama.cpp, generic OpenAI-compatible, all localhost) and are registered only in `registry.py`.
  - The active model is the user's selection stored in the `application_setting` DB table (`ai/settings_service.py`). `ollama_model` in config is legacy. Vision capability is read from Ollama `model_info`.
- **Harness:** `ai/harness/v3.py` (`HarnessV3`, production, ~4.5k lines; read it in targeted ranges). `pipeline.py` holds the v2 compatibility path. Deterministic source signals go in, the model proposes facts, then the evidence resolver, normalizers, the financial source gate (amount + period anchor in the same quote) and schema validation run. Verifiers live in `ai/groups/` and the versioned German prompt in `ai/prompts/`. The default `HARNESS_CONTEXT_TOKENS` is 8192 (8 GB GPU).
- `contracts/`:
  - `calculation/`: `calculate_contract(contract, as_of_date)`. Pure, no DB, no hidden `now()`, Decimal via `money.to_decimal`.
  - Also `warnings/`, `detail/` (the Contract 360 read model), `search/` (pg_trgm), `overrides/` and `review/`.
- `register/` (contract register, replaces the legacy contract manager; plan in `docs/architecture/HYDMEDIA_GAP_ANALYSIS_AND_INTEGRATION_PLAN_20261004.md`):
  - Editable master fields live as columns on `contract`; their origin is in `contract_field_provenance` (`ai`, `manual`, `ai_confirmed`, `ai_corrected`). A re-analysis may only replace `ai` values; human values get an `ai_proposed_value` instead. The pipeline calls `sync_from_extraction` after each analysis.
  - `terms.py`: deterministic deadlines for five term models (fixed, terminable, terminable with minimum term, auto renewal, perpetual), notice to month/quarter/half-year/year end. Pure, explicit `as_of`.
  - `status.py`: business status workflow (`in_arbeit` → `gueltig` → `gekuendigt`/`beendet` → `geloescht`), separate from the computed `contract.status` and from the review status.
  - `catalogs.py`/`defaults.py`: partners, contract types/categories, lookup lists. Numbers come from `number_range`, allocated under a row lock.
- `deadlines/` + `jobs/daily.py` (H5): system deadlines derived from register terms (`system.py`, missed deadlines stay open until done), daily job (`notify.py`, advisory-locked, idempotent via `notification.dedupe_key`), SMTP/ICS (`mail.py`, stdlib only), inbox/deputies (`service.py`). Scheduler: `REMINDER_SCHEDULER_ENABLED` or `python -m app.jobs.daily`. Tests use a fake transport; never real SMTP.
- `register/documents.py` (H3): typed documents per contract; `DocumentProcessingService.attach_to_contract` stores amendment/termination analysis only as `ai_proposed_value`; framework links are `contract_relation` rows with `relation_type='governs'` (`requires_review=True` = AI suggestion).
- `finance/` (H4): `calc.py` is the pure whole-month calculator (current year / to date / to end / term / annual run rate, per currency, None when the end is unknown); `ai.py` derives entry/service suggestions and price-adjustment kinds from the extraction (assumptions flagged); `service.py` handles entries, services, 100 % cost-centre allocations and accept/dismiss of suggestions.
- `reports/` (H7, 13a): `grid.py` builds register rows in bulk (terms, finance, retention, people) and applies column filters, sort and group sums in Python on the scoped set; `views.py` holds saved views (personal or global, lazily seeded defaults); `exports.py` writes Excel (openpyxl, no formulas from data) and the cover-sheet PDF (PyMuPDF `Story`); `renewal.py` builds the advice-only decision brief before notice deadlines.
- `history/` (H6.2): merged contract history and the organisation-wide log with filters and CSV export. Automatic changes (AI sync, system deadlines, daily-job reminders) are logged with `role_snapshot="system"` via `register.service.log_system_activity`.
- `search/content.py` (§4A): page texts of contract documents in `contract_text_page` (German FTS on separator-normalised text, trigram index only in the migration), filled lazily from canonical artifacts (`ensure_index`, also in the daily job). Optional local embeddings via `SEARCH_EMBEDDING_MODEL` (Ollama, localhost only; empty = off).
- Register grid rows are cached per organisation in `reports/grid.py` (`cached_rows`), validated by a data fingerprint; `contract.maintained_annual_cost` caches the finance run rate for list sorting (refreshed on change and daily).
- Permissions: use `app/auth/permissions.py` (`require(actor, "<key>")`); confidential contracts are hidden centrally in `scoped_contract_ids`.
- Other packages:
  - Domain layer: `contract_intelligence/`, `equipment/`, `work_queue/`, `dashboard/`, `organization_structure/`.
  - `integrations/` holds the connector interface only.
- `models/` holds Pydantic domain models (`Contract`, `SourceEvidence`, `Money`, …). `database/models/` holds the SQLAlchemy ORM.
- **Database conventions:**
  - UUID PKs come from server-side `uuidv7()`. `OrgOwnedMixin`/`organization_id` sit on tenant rows. A naming convention covers `pk_/fk_/ix_/uq_/ck_`.
  - Use `session_scope()` for short transactions and keep expensive work outside them.
- **Alembic migrations:**
  - Files are named `YYYYMMDD_<rev>_<slug>.py`; the current head is `l3a5b7c91004` (contract text search).
  - Add FKs onto populated tables as `NOT VALID` (precedent: step16 `app_user` provenance).
  - Tests don't exercise migrations, so a new migration needs `alembic upgrade head` against a disposable DB.
- **Auth:** a cookie session (`medflux_session`), not JWT. Account roles are admin, contract_manager, reviewer and viewer, plus an `is_developer` flag, with per-org `account_membership`. Passwords use PBKDF2-SHA256. Cookie writes require an allowed `Origin`. Viewers are read-only.
- **Time:** use `datetime.now(timezone.utc)`. Calculations take an explicit date.

## Frontend architecture (`frontend/`)

- Next 14.2 App Router, React 18, strict TypeScript, `@/*` alias. No UI library, no Tailwind, no state library. `"use client"` marks interactive components.
- **API access:**
  - Use only `lib/api.ts` (`apiGet/Post/Put/Patch/Upload/Download`): base URL from `NEXT_PUBLIC_API_URL`, `credentials: "include"`, timeouts, `ApiError`.
  - Typed per-domain wrappers live in `lib/domain-api/*.ts` and types in `lib/*-types.ts`.
  - A 401 fires the `medflux:session-expired` event. `components/auth/AuthProvider.tsx` handles `/api/me` and redirects.
  - Org/hospital/department scope is kept in localStorage and injected by `scopedPath()`.
- **Styling:** global CSS in `app/*.css` (imported in `layout.tsx`) with BEM-like classes and CSS custom-property tokens from `app/design-system.css`/`globals.css`, plus a few CSS Modules. Reuse existing tokens.
- **PDF evidence:** `components/contracts/detail/PdfViewer.tsx` uses `pdfjs-dist` with the worker at `public/pdfjs/pdf.worker.min.js` (keep it in sync with the package version). `lib/source-geometry.ts` handles highlights.
- **UI text is German** and hard-coded (`lang="de"`, no i18n). Accessibility is tested with jest-axe.
- **Security headers and CSP** live in `next.config.js`. Every new origin must be added there.
- **Tests:** Vitest + Testing Library in `test/`. `test/setup.ts` globally mocks `useAuth()` as an admin in org `test-klinik`.
- **Design reference** (`design-reference/medflux_final_design_system/`, `docs/VISUAL_IDENTITY.md`): no visual fixtures. Every data region shows real API data or an honest empty/loading/error/unavailable state. Never hard-code sample contracts or amounts.

## Conventions

- Python: type hints, Pydantic models, minimal comments. Comments, docstrings and user messages are mostly German (ASCII transliteration like `ueber` is common). User-facing errors are German and sanitized; diagnostics are admin-only.
- Commits follow Conventional Commits with a scope: `feat(harness): …`, `fix(migrations): …`, `docs(unification): …`, `chore(...)`, `merge: …`.
- Branches: `main` must stay releasable; work happens on `feature/<domain>-<change>` or `fix/<domain>-<issue>`. No parallel per-person implementations.
- CI (`.github/workflows/`) uses Python 3.12, Node 22 and Postgres 18:
  - `integration-check`: compileall, pytest, frontend verify, Windows launcher regression.
  - `hybrid-check`: targeted harness/document/security tests, then the full suite.
  - `release-gate`: on PRs to main; security tests, `alembic upgrade head`, pytest, verify, `docker compose config` and image builds.

## Known drift and gotchas

- `AGENTS.md` says "SQLite for MVP" and "Qwen3-VL 8B". In reality the system is Postgres-only, and the model is whatever is selected in `application_setting`.
- `.hermes.md` is stale (it says 15/18 and "don't start STEP 16"). Its working rules still apply.
- `MEDFLUX_MASTER_HANDOVER.md` and `HANDOFF_20261004.md` were written on another machine (`C:\Users\JAMAL\...`). Their paths and runtime observations (ports, DB contents, model inventory) may not hold here.
- `installed_models.json` (app runtime dir) is a stale snapshot. Query Ollama live instead (`/api/tags`, `ollama list`).
- On-disk document storage and DB rows have drifted (orphan dirs, empty `.index.json`). Before touching storage, read `docs/DOCUMENT_STORAGE_RECOVERY.md` and `docs/PHASE_2_DOCUMENT_STORAGE_RECOVERY_PLAN.md`. `scripts/rebuild_document_index.py` is dry-run unless `--write` is passed.
- Destructive scripts: `restore_from_backup.py`, `cleanup_product_db.py`, `clean_runtime_v2.py`, `reset_product_data.py`. Never run them without an explicit request.
- Line endings: LF everywhere except `.bat/.cmd/.ps1/.psm1` (CRLF), per `.gitattributes`.
