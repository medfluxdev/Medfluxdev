# Domain-by-domain implementation plan

**Branch:** architecture/modular-domains-20260926. **This is an execution design, not work already performed.** Do not merge with OpenCode's active local experimental changes before independent review.

## Gate 0: baseline audit (NO writes to original)
- Map current backend route -> service -> persistence -> frontend domain API for each domain.
- Compare current local Visual-First experimental source and JAMAL branch without assuming they are identical.
- Capture baseline version and compile/test failures; fix CI provisioning separately from application failures.
- Protect original local Medflux-Integrated-Test, AHMAD branch, live database and contract documents. Sensitive gold standards remain local only.

## Domain work queue (independent packages with integration gates)
- [ ] D01 Organization: audit existing org/hospital/department/cost-center and contract assignments. Define `OrgScope`, enforce org/hospital/department read and write integration cases.
- [ ] D02 Users & permissions: matrix of role x scope x permitted action; validate reviewer and department lead cross-scope restrictions; safe session handling.
- [ ] D03 Document vault: immutable file revision lifecycle, SHA/size/source lineage, access and revisions.
- [ ] D04 AI extraction: analyze one real page at a time, proposed facts, measure content coverage independently of success counts. Keep vision OCR independently cross-checkable.
- [ ] D05 Evidence/review: never grant page provenance solely from Qwen uniform page offset; duplicate literal and wrong-page tests, proposed/accepted/manual state transitions and audit.
- [ ] D06 Contracts/finance: scheduled year prices, per-call charges, net/gross with explicit rate, payment and variable cost separation; Decimal computations and snapshot versioning.
- [ ] D07 Calendar/notifications: deterministic event types; owner and escalation recipients; enterprise email adapter as optional configuration, in-app guaranteed local fallback; idempotent delivery tests.
- [ ] D08 Portfolio analytics & UX: scoped org->hospital->department->contract drilldown and comparisons; only accepted facts in authoritative dashboards, uncertain facts in clearly tagged scenarios.
- [ ] D09 Security/operations: PostgreSQL launch + migration/checkpoint/rollback, fail-closed default, confidential PDF log redaction, dependency versions, observability and protected backups.

## Cross-cutting acceptance for EVERY work item
- [ ] source and dependency inspection performed by architect, not merely an agent report
- [ ] regression test that reproduces the actual defect when applicable
- [ ] bounded isolated implementation and passing relevant tests
- [ ] code cleanup with explicit deleted/retained file inventory
- [ ] rerun relevant tests after cleanup
- [ ] protected data and concurrent-work safeguards observed
- [ ] status updated only against verifiable code/test evidence

## Initial bounded implementation target

Complete `audit/finance-provenance-20260926` **separately**: obtain an actually-running test job and inspect prices, annual-rate inference and derived-vs-evidenced separation. Meanwhile use this architecture branch only for design and nonconflicting interface documentation. After approved baseline and original PDF gold review, prioritize D04/D05 (accuracy gate), then D06 and D07, then advanced dashboard.
