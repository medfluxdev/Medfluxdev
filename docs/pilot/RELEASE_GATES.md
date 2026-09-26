# Ahmad candidate: living engineering release gates

Date: 2026-09-26. Branch `review/ahmad-hospital-20260926`. Check only after reading actual run logs. Branch must not merge directly into JAMAL until independently accepted.

| Gate | Required result | Initial state |
|---|---|---|
| G00 protected sources | Original local Medflux-Integrated-Test + current Visual-First experiment unmodified; use only isolated checkout | Existing read-only inventory successful (original tracked changes exist) |
| G01 frontend quality | 9 focused import tests, 153 full frontend tests, TypeScript typecheck, Next production build | **Passed** on isolated self-hosted run 36244268905; HTMLCanvas jsdom warnings, no failing tests |
| G02 backend targeted | finance/Harness targeted and isolated Visual-First tests | **19 backend Harness tests passed on review branch** in 36244268905; earlier separate audit branch 25 finance and copied local Visual-First 18 passed. Full backend suite and original PDF still pending. |
| G03 scope and workflow | new import selector cannot bypass backend authority, no placeholder enabled modes | Pilot UI uses existing server scope; manual and AI direct disabled |
| G04 sensitive evidence | literal source PDF page/quote verified on nine-page Frankfurt and false-page regressions | Not yet passed |
| G05 budget realism | no fictitious budget/actual, explicit ledger source and cost-center allocations | UI explicitly marks budget/actual as unavailable |
| G06 pilot isolated runtime | separate copy and TEST DB; no touching live Postgres or original | Prepared separate Compose and local-secret generator; **unverified Docker runtime**, runner has no Docker CLI as audited in 36244336198. Do not give Ahmad a claim of executable end-to-end readiness yet. |
| G07 stakeholder acceptance | Ahmad marks keep/change/remove/defer and provides missing workflow details | Awaiting Ahmad |

No branch merges or changes to hospital databases without separate test and approval.

## Verified isolated review CI (2026-09-26)

- [Run 36244268905](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36244268905): **9 targeted import tests passed; 153 full frontend tests passed; 19 backend Harness tests passed; TypeScript noEmit passed; Next production build passed; exact owned temp clone cleanup succeeded.** Existing jsdom Canvas unsupported warnings emitted but no tests failed. No live database or original Frankfurt contract was touched.
- Source checkout preceded addition of an **independent optional** Dockerfile/Compose/launch helper, so its Docker build and runtime are *not* covered by that successful test. The frontend TypeScript edit to remove misleading admin scope IDs is present in the checked-out candidate.
- Current blocker to running the isolated Compose pilot on the connected Windows runner: [read-only audit 36244336198](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36244336198) reported no Docker CLI; use a verified alternative only after protection checks.

## Revalidation including standalone preview setup

[Isolated workflow 36244590337](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36244590337) reverified **9 focused import tests, 153 full frontend tests, 19 backend Harness tests, TypeScript, production frontend build, local-only unique credential generation inside the isolated checkout, and exact temp workspace cleanup**. The backend and PostgreSQL runtime were **not launched**. Docker Desktop and Docker CLI were independently absent on connected runner ([discovery 36244513617](https://github.com/jamallionjan-dev/JAMAL-OC-PC/actions/runs/36244513617)); installing or authorizing a safe alternative remains the live launch blocker. Jest/jsdom Canvas unsupported diagnostic logs are still emitted despite all tests passing; keep as separate test-harness hygiene work.
