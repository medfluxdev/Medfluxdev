# Ahmad — hospital pilot decision sheet

**Candidate branch:** `review/ahmad-hospital-20260926`. **Not production-approved.** This sheet is intended for Ahmad to decide what MedFlux should keep, change, add or remove based on actual hospital workflows. Use anonymized/synthetic contracts for initial review; never upload real hospital financial/contract material to GitHub Actions.

## What came directly from Ahmad's 26 September brief

1. **Contract capture:** vendor, term dates/duration, price, cancellation deadline, auto-renewal, billing interval and prepaid/postpaid, gross vs net (compute both if the tax rule is known), escalators vs fixed-price period. Allow manual verification before recording, optional automatic acceptance by permitted policy; show per-field origin AI/manual/both.
2. **Obligations and alerts:** end date, cancellation last day, impending auto-renewal, planned payment/maintenance. Notify responsible person and configurable extra recipients or department lead; in-app and optional institution email delivery. This is a risk-management control, not a decorative bell.
3. **Finance dashboard:** number of active/expired/expiring contracts; annual and total costs, organization/hospital/department/vendor/type drilldown, highest contract costs, imminent renewal decisions, comparisons with past, transparent planning forecasts.

## Additional owner requirements after Ahmad's brief

- **Import wizard before processing:** choose permitted organization/hospital/department (optional cost center), then one of (a) user manual entry, (b) policy-governed AI-only acceptance, or (c) AI + human review. All selected choices must be genuinely implemented before enabling their buttons.
- **Financial-number search:** enter `Kostenstellennummer` to retrieve permitted department/cost-center records, associated contracts, verified budget, actuals, and month-over-month/year-over-year comparable periods.
- **Future cost projections:** 3/6/12/24/36 months as justified by contractual obligations and imported finance history. Clearly separate deterministic contractual commitments from modeled operating-cost forecasts, tax basis, coverage and uncertainty.

## Pilot review board (what is really present vs pending)

| Area | Available in the candidate branch | What must be demonstrated | Current gate |
|---|---|---|---|
| Upload/local AI | Existing production import and review path reused | Run source-based real-PDF acceptance including Frankfurt | Pending E2E |
| Destination/workflow | Pilot import page now asks for current work area confirmation and displays three modes | Persisted and independently secured owner selection; genuine independent manual and AI-direct flows | Only AI + review path usable; other modes disabled |
| Financial calculator | Existing calculation and review services; finance unit regression isolated and successful | Validate complete real contract price schedule and VAT/renewal conditions with original pages | Pending original contract acceptance |
| Cost center search | Scoped GET from real existing cost-center API, lookup view by code | Correct department association, scoped tenancy and E2E | Candidate UI implemented; live end-to-end pending |
| Budget and accounting actuals | No approved hospital ledger dataset | Versioned monthly/annual ERP or agreed CSV/XLSX, imports, reconciliation | Unavailable |
| Forecasts | Written architecture specification | Historical data, agreed scenarios, temporal backtesting, no double-counting | Not implemented |
| Alerts | Existing notifications/work queue API/UI families | Recipient choice, delivery channel, institution mail credentials and real due-event tests | Needs hospital review/UAT |
| Security | Existing scope-aware endpoint infrastructure | Full role x scope matrix, read/write isolation, audit and confidential-log QA | Requires audit |
| Feedback | `/ahmad-review` in-product per-feature decisions and copyable notes | Ahmad provides accept/change/remove comments, ideally observed walkthrough | Reviewable, local unsaved feedback |

## Ahmad walkthrough, 45–75 minutes

1. Explain real organizational ownership: which department receives a contract, can a contract cover multiple cost centers, and who is responsible for reminders?
2. Open `/import` and choose the **current** authorized header scope. Confirm the available AI-assisted human review path. Show the disabled unimplemented modes and ask which steps are mandatory at the hospital.
3. With only approved dummy data, import a PDF/DOCX and inspect source citations, amount units, tax basis, term and deadline before confirming a fact. Flag every missing/uncertain field.
4. Search `/kostenstellen-suche` with an approved sample code; verify results are scoped. **Do not mistake 'budget unavailable' for zero**. Ask Ahmad for a synthetic/sample budget and expense import schema.
5. Explore existing `/analysen` and `/work-queue` through normal permissions, then note missing procurement/accounting/alert workflows.
6. Use `/ahmad-review` to mark each capability as retain/change/remove/defer and copy notes **before leaving the page**.

## Requests for Ahmad (not a release blocker for basic UI review)
- Redacted/synthetic example of maintenance agreement and a validated expected output row for every critical field.
- Legal ownership / approval route, role and escalation policy, threshold for fully automatic approval.
- Cost center numbering conventions, budget and booked expense export column definitions, fiscal-year policy, shared contract allocation convention.
- Confirmed internal email/notification delivery policies, cancellation lead times, and whether contract values or actual ledger amounts govern monthly analyses.

## Stop/go for any 'ready for Ahmad' message

A **source UI review candidate** can be shared after the isolated frontend lint/type/test/build gate passes, with limitations prominently disclosed. A **fully functioning UAT build** additionally requires a clean isolated working copy, backend install and migration checks, real end-to-end original PDF testing, security/role tests, and a launch artifact that uses a separate test DB. Do not market the former as the latter.

No sensitive contract PDF, hospital ledger, credential or production DB snapshot is part of any GitHub artifact.
