# D10A — Cost Center Intelligence (Hospital Finance)

**Status:** design specification, not implemented. Requirement supplied by owner after Ahmad's hospital brief. The search key is a hospital accounting/cost-center number (German `Kostenstellennummer`), not a contract number. The example radiology code below is fictitious; do not treat mock data as hospital data.

## Goal
Authorized staff enter a cost-center/accounting number and receive scoped department / organization / hospital matches, an accurate budget-vs-actual overview, linked contracts/equipment and month-over-month/year-over-year comparisons, with drilldowns to source-backed rows. Never imply contract price totals equal financial department budget or actual spending.

## Ownership and interfaces
- **D01 Organization** owns CostCenter master, organization/hospital/department mappings and effective dating. Store normalized display code as **string** preserving leading zeros and local formatting. Scope lookup by institution and validity period; duplicates across institutions are legal and must return scoped candidate list.
- **D02 IAM** checks budget/actuals/contract rights independently: user's right to see a cost center does not automatically authorize all purchase records or supplier confidential terms.
- **D06 Financials** owns contract price schedules, supported projections and classification (net/gross, fixed/variable, committed vs realized); NEVER fabricate budgets or ERP actual expenditure from contract PDFs.
- **D10A Cost Center Intelligence** is an authorized read-model / aggregation service, not a second financial system of record. Read source-specific, versioned financial ledger/budget snapshots via import adapters from approved CSV/XLSX or later hospital ERP, with as_of, source_system, revision, currency, period, data freshness and audit trail.
- **D11 Analytics** renders comparisons and organization -> hospital -> cost center -> department -> contract/equipment drilldown; no recalculation of core finance in frontend.

## Search API (proposal)
`GET /api/cost-centers/search?number=<opaque-string>&hospital_id=<optional>` -> authorized matches [{cost_center_id, code, name, hospital_id, department_ids, validity_period}]. Server-side identity/scope gates BEFORE search result or counts. Parameterized lookup, rate limiting and pagination; never raw unrestricted directory search.

`GET /api/cost-centers/{id}/overview?from=YYYY-MM&to=YYYY-MM&basis=net|gross&comparison=previous_year|previous_period` returns:
- identifying metadata and period/authorized scope;
- `budget`, `actual`, `committed`, `forecast`, `remaining_budget` as distinct optional measures, exact currency and basis, completeness and sources;
- monthly series for selected and comparable windows, YoY/MoM absolute and percent deltas only when denominator and scope are compatible;
- linked contract/equipment list, contract count, upcoming installments/expiry events, expense categories and top drivers;
- `data_status` for each metric: real source-backed, calculated, partial, stale, unavailable, scenario.

## Source data and schema boundaries (proposal)
`CostCenter` already exists under `backend/app/database/models/organization_structure.py` with code/name/org/hospital/optional department; **extend** it rather than create duplicate master records.

Versioned ledger or import references:
- `BudgetAllocation(cost_center_id, fiscal_year, period, amount NUMERIC, currency, tax_basis, scenario, revision_id, approved_at)`;
- `ActualExpense(cost_center_id, booked_at, period, amount NUMERIC, currency, tax_basis, expense_category, supplier_id?, contract_id?, equipment_id?, source_line_id, import_revision_id)`;
- `Commitment(contract_id, cost_center_id, valid_from, valid_to, allocated_share, explicit_amount?, cost_type, source_revision)`;
- `FinancialImportRevision(source_system, imported_at, source_checksum, imported_by, fiscal_calendar_id, status, superseded_by?)`.

Never casually allocate an institution-wide contract fully to each linked cost center. Shared contract allocations need explicit approved amounts or percent that reconcile; otherwise show **unallocated** costs separately and do not count them in departmental totals. Store source and correction history; imports idempotent on source identity and revision.

## UI
Single prominent exact `Kostenstelle` number input with authorized ambiguous-result picker, organizational breadcrumb and selectable fiscal period. Four primary KPIs: approved budget, booked actual, committed obligations and remaining budget, clearly distinguishing unknown and zero. Charts: monthly budget vs actual, year-on-year normalized comparison, supplier/category distribution, before/after selected contract or acquisition event, and future obligations (scenario explicitly tagged). Row-level explanations and drilldown to approved source evidence. Allow side-by-side date ranges and consistent cost base, filters by hospital, department, supplier, contract/equipment and spending type.

## Non-negotiable calculations
- Remaining = approved budget - booked actual - explicit approved commitments **only if** institution's finance policy defines that treatment; otherwise display actual remaining and prospective free balance separately. No universal double-counting of already booked commitment payments.
- EUR calculations using Decimal/NUMERIC; source-specific tax basis explicit, NEVER assume a 19% rate or pretend a net/gross transformation is sourced when it is calculated.
- YoY compares aligned fiscal months/days and consistent scope/currency/tax treatment; present unavailable when previous year absent. Percentage delta omitted or marked not comparable for zero previous value.
- Before/after comparisons show observed changes, NOT causal attribution: seasonality, service volume, changed assets and accounting classification can contribute.
- With contracts but **without** approved hospital budget/expense import, show `budget: unavailable`, `actual: unavailable`, and explicitly labeled **contractual forecast/commitments only**. Never populate budget from sum of contract values.

## Required future-cost forecasting engine (core feature, not optional)

**Purpose:** Forecast future cost center outflows month-by-month and year-by-year using approved historical financial actuals together with future contract obligations, payment timing, supplier price escalators, expiration and explicitly modeled renewals, expected maintenance or equipment costs (only if supported). Deliver confidence intervals where statistically meaningful, plus editable scenario assumptions; never represent AI-generated guesses as booked expenses or contractual facts.

### Forecast horizons and outputs
- Selectable next 3, 6, 12, 24, 36 months and annual planning horizon, aligned to the hospital fiscal calendar.
- Per center: projected contractual commitments, forecast variable operating spend, expected aggregate spend, approved budget when imported, projected budget variance, future cash-flow due dates and source coverage/uncertainty indicators.
- Compare prior comparable months and years, growth, seasonality, trends and before/after selected documented organizational or contract event. Breakdown to supplier, contract, equipment, spending category, hospital and department. Distinguish planned/provisional/new equipment scenarios.
- Every future month reconciles components once: historical modeled operating spend adjusted for any contract-backed fixed costs already included; **never add the same fixed contract charges twice**.

### Forecasting method and safety
1. **Certain contractual base:** deterministic engine builds versioned future per-contract price/payment schedules from accepted start/end dates, staged price rows, billing frequency, advance vs arrears wording, supported indexation and approved renewal decisions. If due date is not actually stated, mark payment month approximate or unknown (do not fabricate an exact date).
2. **Observed operations:** when sufficient imported budget and actual ledger history exists, fit a reproducible baseline time-series model per cost center/category. Start with seasonal naive and rolling-trend alternatives; choose methods only through temporal backtesting (e.g. rolling holdouts / MAPE caveat with near-zero actuals, WAPE/MAE); report seasonality and data sufficiency.
3. **Scenarios:** baseline / higher cost / lower cost; explicit adjustable assumptions for annual price increases, energy/inflation sensitivity **only if institution approves assumption sources**, additional device purchase/repair, supplier change, occupancy or case volume where supplied. Provide driver attribution and sensitivity, not invented economic forecasts.
4. **Risk/uncertainty:** separate confirmed commitments, statistically estimated variable expense, unknown renewals, unallocated contracts and unsupported assumptions. When history is too short, only present accepted contract-backed deterministic projections and clearly label missing actuals; no fabricated confidence interval.
5. **Review and governance:** forecast snapshots reference input revision IDs, model/config version, as-of date, fiscal calendar, scenario and reviewer. Material assumption overrides require permitted role and audit trail. Current financial dashboard never conflates budget, actual, commitments, forecast or what-if scenario.

### Proposed API and persistence boundaries
- `GET /api/cost-centers/{id}/forecast?from=YYYY-MM&months=12&scenario=baseline` returns 1 row per month with separately typed commitments, operating projection, projected total, available approved budget, projected delta, data quality and method.
- `POST /api/cost-centers/{id}/forecast-scenarios` persists scoped scenario assumptions with permission and audit; forecast runs immutable and reproducible.
- Versioned `ForecastRun(cost_center_id, as_of, horizon, actual_revision_id?, accepted_fact_snapshot_ids, model_method, model_version, assumptions_json, data_quality, created_by)` plus `ForecastPeriod(run_id, year_month, contractual_amount?, variable_estimate?, expected_total?, lower_bound?, upper_bound?, projected_budget_gap?, currency, tax_basis)`.
- Forecast calculations belong to the financial forecast application service. AI may produce explanations or suggest candidate drivers, but cannot invent financial inputs, bypass review, or authoritatively calculate totals.

### Forecast-specific acceptance tests
- No historical actuals: show available contract-backed future commitments only and state missing components.
- At least 24 months of monthly actuals: compare seasonal vs simpler baseline using chronological out-of-sample backtests; report observed errors and fallback safely on sparse series.
- Step-price change or confirmed renewal changes only relevant future periods; rejected/uncertain renewal remains scenario, never baseline certainty.
- Each planned charge counted once even if in both contract schedule and imported actual/spend-plan data.
- Missing tax basis/currency, unsigned assumptions, insufficient history and changing org scope result in explicit partial/unavailable statuses.
- Same versioned data, config and as-of date produce identical forecast; unauthorized users cannot retrieve source series, forecasts or scenarios.

## Acceptance cases
- [ ] Number with leading zeros preserved, no unauthorized data leakage and multi-hospital ambiguity resolved.
- [ ] Authorized exact lookup -> correct scoped cost center and related contracts.
- [ ] No budget import -> financial metrics unavailable, not zero or guessed.
- [ ] Two budget revisions -> use approved applicable revision and retain audit trail.
- [ ] Imported actuals corrected/reimported -> no duplicate spend.
- [ ] Multi-cost-center/shared contract -> allocation sums without duplicate cost.
- [ ] Mismatched periods, VAT bases and currencies -> do not silently aggregate.
- [ ] Month/year/before-after comparisons reflect aligned periods, zero denominator handled explicitly.
- [ ] Invoice actual vs future installment vs recurring annual contract display distinctly.
- [ ] Cleanup manifest, access tests, financial regression tests, frontend integration and scoped E2E test before marking implemented.

## Delivery stages
1. Audit actual CostCenter, cost-center API and scope implementation on the current local baseline. Avoid interfering with concurrent experimental work.
2. Implement scoped exact search + contract-only preview (clearly identified, no fictional budget amounts).
3. Add approved, versioned budget/actual import adapter and financial reconciliation tests.
4. Add monthly/yearly comparisons, drilldown and evidence-backed dashboards.
5. Connect approved hospital ERP via explicit contract when credentials/API and institutional authorization are available; never mandate an ERP integration to complete stages 1–4.
