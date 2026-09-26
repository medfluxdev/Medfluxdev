# MedFlux architecture v1 — independently evolvable domains

**Status:** proposed design, NOT an implementation claim. Branch: `architecture/modular-domains-20260926`. Based on Ahmad's 26 September hospital requirements and a read of existing MedFlux JAMAL repository structure. Do not rebuild existing working modules from scratch.

## Architectural decisions

- **Deployable shape:** local/on-prem **modular monolith** (one backend/API, one frontend, one PostgreSQL database, protected local artifact storage, one bounded processing-worker execution surface). Avoid microservices, distributed transactions, an additional database, and unapproved AI models.
- **Ownership:** each domain owns its API, service/application layer, domain rules, persistence repository and tests. Never write another domain's tables directly. Interactions: typed service interfaces for synchronous queries, transactional outbox / simple persistent internal events for side effects once needed. No event broker in v1.
- **Truth model:** original immutable document -> immutable revision -> processing attempt -> unverified proposed facts -> source-verified facts -> reviewer/approved snapshot -> deterministic calculation snapshot -> notifications and analytics. Provenance, explicit/derived/manual labels and scope checks at every boundary.
- **Security:** backend enforces organization, hospital, department and contract scope regardless of frontend URL/query. Explicit roles and separate scope assignments. Default deny; audit all decisions/edits. Never upload private PDF/contract text to GitHub or cloud LLMs.
- **Rollout:** map existing features first, add anti-corruption adapters, migrate one bounded domain per change, use regression tests before and after; avoid simultaneous rewrite.
- **No cleanup = no completion:** every issue requires changed-files inventory, verified dependency/reference check, removal of only superseded artifacts on isolated branch, preserved regression tests, compile/relevant and full tests, and a cleanup manifest. Never wipe active experiments, production DB or original worktree.

## Independent architecture workstreams

| ID | Domain | Owns | Exposed contract | Must never own |
| --- | --- | --- | --- | --- |
| 01 | Organization | institution, hospitals, departments, cost centers | scoped org directory | authentication, contract amounts |
| 02 | Identity & Authorization | users, sessions, roles, scope grants, access policy | authoritative principal and `require_scope()` | trusting client-supplied scope |
| 03 | Frontend / UX | page layout, forms, evidence viewer, review workflow rendering, charts | versioned typed domain API client | domain arithmetic/security |
| 04 | Document Vault | original documents, immutable file versions, checksum, protected artifact references | `create_revision`, `get_authorized_revision` | inferred contract facts |
| 05 | Ingestion/AI | Docling/OCR, visual page readings, candidate facts, local model runtime | proposed fact bundle + runtime diagnostics | approving facts, financial arithmetic |
| 06 | Evidence & Review | quote/page/region grounding, source conflict, reviewer decisions, trust state | accepted fact snapshot / review queue | auto-silencing uncertainty |
| 07 | Contracts | contract identity, scope, lifecycle, supplier relationships, equipment links, revision pointer | contract detail and lifecycle APIs | OCR/model internals |
| 08 | Financials | stage prices, recurring/conditional charges, VAT representation, payment schedule, deterministic totals | calculated money projections with provenance | inventing tax rate, double-counting |
| 09 | Calendar & Obligations | term/renewal/cancellation conditions, maintenance duties, business calendars | dated obligation projections | assuming unknown service appointments |
| 10 | Notifications & Work | recipient preferences, notification outbox, email adapter, in-app inbox, escalation, task ownership | event-driven deliveries with dedupe | changing contract business state |
| 11 | Portfolio Analytics | org>hospital>department>contract drilldown, period snapshots, comparative and forecast scenarios | read-only aggregate APIs | replacing approved facts with AI estimates |
| 12 | Cross-cutting Platform | PostgreSQL/Alembic, configuration, safe job orchestration, logging, backup, metrics, security audit | interfaces shared by domains | business decisions in common utility folders |

## Deployment/data boundaries

**One PostgreSQL** instance with domain-owned table families and explicit foreign keys. **Protected local artifact store** for original PDFs/DOCX, canonical outputs and optional controlled visual crops; DB stores immutable IDs, checksum, relationships, status and evidence coordinates. Prefer DECIMAL/numeric for money calculations; adapters must make existing float-based values safe while migrating, not silently reinterpret old values. Alembic migration only after diff review, backup and rollback proof.

Minimal identity: Organization -> Hospital -> Department -> Cost Center (cost center may span and its assignment is explicit); User -> Role assignment + Scope grants, never 'hospital ID supplied by UI = authorization'. Contract -> DocumentRevision(s), ContractFactSnapshot(s), ScopeAssociation(s), Equipment links; separate PaymentSchedule, Obligation, NotificationRule and AnalysisSnapshot with organization IDs for safe scoping.

Trust states: PROPOSED_AI, SOURCE_CORROBORATED, REVIEW_REQUIRED, CONFIRMED_MANUAL, CONFIRMED_AI_AND_MANUAL, SUPERSEDED. Derived values are a **separate** provenance category and cannot be masqueraded as source quotation. `auto_confirm` applies only to explicitly allowed low-risk fields with independent evidence checks; sensitive or contradictory fields remain blocked.

Events (internal, persisted if operational side effects): `DocumentRevisionCreated`, `ExtractionFinished`, `FactSnapshotAccepted`, `ContractLifecycleChanged`, `ObligationDue`. Emit after relevant DB commit and use idempotency keys for email/task creation; processing retries must not duplicate notices.

## Cost center number search and real hospital financial data

Detailed design: [COST_CENTER_INTELLIGENCE.md](COST_CENTER_INTELLIGENCE.md). Lookup by hospital accounting number uses the existing CostCenter master and permission checks. Actual departmental budget and booked spending require versioned, approved hospital accounting data imports; contract totals alone never constitute a budget. Includes comparable monthly/yearly and before/after views, shared-contract allocation safety and drilldown to underlying sources.

## Ahmad's operational release slices

1. **Extraction / confirmation:** legal parties, dates, contract term, price stages and annual/monthly payment frequency, advance/in arrears, source VAT wording and optional comparison when tax basis/rate is actually known, price increase/fixed-price clauses; per-field AI/manual/both and original source link. Allow manual confirmation and controlled auto-confirm; no guessing missing numbers.
2. **Dates and notifications:** expiry, last cancellation, auto-renewal, scheduled payments, known maintenance appointment vs maintenance obligation; in-app and institution email options, responsible person and selected escalation recipients, idempotent delivery and audit.
3. **Management analytics:** active/expired/expiring counts, annualized contract cost where defensible, total portfolios, organization/hospital/department/supplier/type drilldown, cost rankings, renewal decisions, historical comparisons and transparent projections; never count uncertain amounts in approved totals without an explicit 'scenario' flag.

## Existing repository reuse map (observed JAMAL branch)

Existing directory families already include `backend/app/auth`, `database/models/organization_structure.py`, `documents`, `ai/harness`, `contracts/{calculation,review,detail,search,warnings}`, `contract_intelligence`, `dashboard`, `api/routes`, `database/models`, frontend Next.js `app/` and `components/`, as well as scoped `domain-api` conventions. Existing docs `CONTRACT_SCHEMA.md`, `STEP_10_DATABASE_DESIGN.md` and `FRONTEND_BACKEND_INTEGRATION_MAP.md` have useful separation/provenance guidance. They must be reconciled with current local uncommitted Visual-First experiment **before** moving implementation files.

No mechanical folder rename or database migration is implied by this design. Adopt boundaries through tests and interfaces first. Separate architecture changes from the ongoing finance audit branch.

## Per-domain definition of done

- Written inputs/outputs and exact authority/ownership.
- Failure modes/unknown state and access-control test cases.
- No direct imports of private persistence internals from other domains.
- Unit tests + integration boundary tests + end-to-end relevant path.
- No secrets/source PDF in commits or logs.
- Cleanup manifest; compile/lint/tests repeated after deleting superseded code.
- Evidence links and remaining risk recorded in the domain's checklist.
