# OpenCode handoff — canonical MedFlux development FIRST

**OWNER CORRECTION (2026-09-26):** Do **not** build or maintain a parallel Ahmad application now. **Work on the established MedFlux project and its canonical integration branch/workflow.** Only AFTER integrated work is accepted, derive a separate distribution/reviewer copy for Ahmad. This instruction supersedes earlier instructions in this file.

## Resolve current canonical workspace before writing
1. Inspect the existing local `Medflux-Integrated-Test` (JAMAL branch, previously 6 tracked modifications) and `Medflux-VisualFirst-Experiment` (previously master, live experimental work), their real HEADs, modifications INCLUDING untracked, and any running agents. Determine where active OpenCode work resides; do not automatically switch branch, reset, clean, or overwrite.
2. Canonical GitHub integration target is `medfluxdev/Medfluxdev` branch `main` unless owner has since designated another existing branch. Treat the local working copy as authoritative for its uncommitted work; preserve its changes and integrate only reviewed improvements.
3. The isolated `audit/finance-provenance-20260926`, `architecture/modular-domains-20260926` and `review/ahmad-hospital-20260926` branches are **sources of reviewed patches/design** only. Do not merge an entire branch blindly. Draft PR #10 stays unmerged. Cherry-pick or adapt only verified changes after conflict and regression inspection.
4. Report canonical working location, branch and conflicts to the architect. If the user-designated canonical workspace isn't determinable, perform read-only audit rather than write into a guessed directory.

## Shared core development objective
Implement Ahmad's hospital workflows in **the canonical project** through a sequenced integration plan; no separate Ahmad product stream:
- Stabilize original-PDF extraction and page provenance, finance schedule and review gates. Current evidence: isolated targeted 25 finance/Harness and 18 Visual-First tests passed on prior snapshots. This is not full Frankfurt E2E acceptance.
- Modular domain boundaries without a disruptive folder rewrite. Reuse existing auth, institution, hospital, department, cost center, import and document processing, calculation, notifications, reporting and frontend APIs.
- Before a contract is uploaded: explicit destination department/cost center and 3 genuine alternative workflows — manual entry, AI with authorized policy-governed auto-acceptance, AI + human fact review. Do not enable incomplete modes; backend must enforce scope/mode and per-field provenance, actor audit, retries.
- Search by cost center number, permitted organizational data, related contracts/equipment, historical approved budget/actual and monthly/yearly comparisons once hospital financial input exists. Without approved budget/actual, mark unavailable and never substitute contract total.
- Future costs: separate accepted deterministic contractual commitments and backtested statistical projection using approved hospital history, assumptions and uncertainty; absent data => only contractual commitments.
- Real reminder recipient selection, escalation and in-app/institution email integration when configured and verified.

## Work rules
- Coordinate concurrent work. Work in the owner-confirmed existing canonical development workflow, preserving uncommitted local changes and the experimental bridge. Before editing overlapping files, identify owner and existing edits; use short isolated commits/feature worktrees only as temporary engineering tools when needed, merging reviewed patches BACK into the canonical branch — not as a separate Ahmad application.
- Never overwrite project data, alter live database, launch colliding GPU/Ollama work, merge to JAMAL without reviewing actual tests, or expose private source contract.
- Follow sequence: inventory -> one bounded change -> targeted regressions -> broader integration checks -> cleanup manifest -> next change. Document actual pass/fail, exact commits and blockers.
- Keep `docs/architecture` and `docs/pilot` specifications as requirement references. The draft review branch currently has a candidate UI and feedback form; those are potential patches for main MedFlux after code review, NOT a parallel development destination.

## Only at final acceptance
Once canonical MedFlux has passed security, UI/backend, financial and source-evidence gates, create an Ahmad reviewer copy from a verified canonical commit/tag, with isolated database and synthetic fixture, launch instructions and in-product keep/change/remove feedback. Record what is finished, experimental or missing. Do not create or deploy that final copy early.

## First report (before edits)
Canonical project path/branch and status incl. untracked; OpenCode active work; incoming patches worth integrating; blocked ownership/conflicts; precise first bounded fix and test plan.
