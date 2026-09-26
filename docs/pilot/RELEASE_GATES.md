# Ahmad candidate: living engineering release gates

Date: 2026-09-26. Branch `review/ahmad-hospital-20260926`. Check only after reading actual run logs. Branch must not merge directly into JAMAL until independently accepted.

| Gate | Required result | Initial state |
|---|---|---|
| G00 protected sources | Original local Medflux-Integrated-Test + current Visual-First experiment unmodified; use only isolated checkout | Existing read-only inventory successful (original tracked changes exist) |
| G01 frontend quality | import regression, TS typecheck, Next production build | In progress |
| G02 backend targeted | finance/Harness targeted and isolated Visual-First tests | 25 + 18 targeted passes on prior isolated source snapshots |
| G03 scope and workflow | new import selector cannot bypass backend authority, no placeholder enabled modes | Pilot UI uses existing server scope; manual and AI direct disabled |
| G04 sensitive evidence | literal source PDF page/quote verified on nine-page Frankfurt and false-page regressions | Not yet passed |
| G05 budget realism | no fictitious budget/actual, explicit ledger source and cost-center allocations | UI explicitly marks budget/actual as unavailable |
| G06 pilot isolated runtime | separate copy and TEST DB; no touching live Postgres or original | Not yet verified |
| G07 stakeholder acceptance | Ahmad marks keep/change/remove/defer and provides missing workflow details | Awaiting Ahmad |

No branch merges or changes to hospital databases without separate test and approval.
