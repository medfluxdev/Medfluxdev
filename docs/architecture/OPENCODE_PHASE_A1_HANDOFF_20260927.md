# MedFlux Phase A1 — Department hierarchy patch and local acceptance

Base: design/secure-ai-assistant-20260927. Scope: **backend additive organization tree foundation only**. NOT complete Phase A, not a frontend tree editor, not contract responsible/beneficiary relationships.

## Why this is first
Hospital, Department, CostCenter and ContractDepartment already exist. This patch adds an optional Department.parent_id to the EXISTING models/routes. Existing flat departments remain roots (NULL parent). It does not alter contract access rights: hierarchical ancestry must NOT implicitly grant access to descendant departments or their contracts.

## Authored implementation
- New Alembic migration adds nullable parent_id, index, scoped composite FK (same org/hospital), and direct self-parent CHECK. No data backfill, no deletion.
- Existing Department ORM maps the new field and constraints.
- Existing POST /api/organization-structure/departments optionally accepts parent_id; existing PATCH permits explicit parent_id=null to detach and rejects cross-scope parents and cycles. Existing GET includes optional parent_id for authorized department rows, but no ancestor information is leaked to restricted users.
- Unit tests cover valid nesting, invalid scope, self-parent, missing parent, indirect and preexisting cycles.
- No UI changes, no change to ContractDepartment semantics, no automatic inheritance of permissions, no modifications to finance.

## OpenCode: APPLY AND VERIFY, DO NOT REDESIGN
1. Preserve current worktrees, dirty changes, PG 5432 and Ollama 11434. Fetch feature/org-tree-a1-20260927 into a fresh separate worktree. Confirm exact diff vs its parent branch and inspect current Alembic HEAD(s). If migration ancestry is incompatible, STOP and report before touching code.
2. Use disposable isolated PostgreSQL only (55432 if free). Run migration upgrade, verify all existing departments still have parent_id NULL and contract counts/links unchanged, then downgrade/upgrade on a disposable snapshot; do not run downgrade against any persistent database.
3. Compile; run pytest -q tests/test_department_tree_a1.py and existing organization, auth, scope and contract suites; run full backend suite under correctly isolated environment. Separate production-posture tests without MEDFLUX_INSECURE_DEV=true. Run frontend npm run verify baseline.
4. Real authenticated API tests with two orgs and two hospitals: authorized admin creates a three-level hierarchy; non-admin cannot mutate; cross-org and cross-hospital parent IDs return no sensitive data; explicit detach works; self-parent and indirect cycles fail; old clients omitting parent_id still work; restricted GET does not reveal other departments or ancestors.
5. **Concurrency safety gate:** Test two simultaneous admin reparent requests attempting A->B and B->A. Current application validation is not a proven serialization mechanism. If a cycle can be committed, STOP and report minimal reproducer and proposed transaction-scoped locking or database-level fix. Do NOT approve A1 as complete without this gate.
6. Validate schema constraints through direct SQL attempts against disposable DB: cross-org/cross-hospital parent and self-parent must fail; note indirect cycles require application/transaction protection.
7. No production DB, no GitHub Actions, no deployment, no merge to JAMAL/integration. No new UI or Phase A2 implementation. Do not modify code unless returning a proposed minimal patch for my review.

## Required report
Exact branch and SHA, migration heads and upgrade/downgrade results, commands, pass/fail/skips, SQL constraint results, concurrent race result, route auth/scope results, unchanged contract semantics, and any defects. Stop for review.

## Next (NOT INCLUDED)
A2: one explicit responsible department and multiple beneficiary departments per contract with same-hospital/org checks and safe historical migration. A3: admin tree UI, full paths, cost center and contract selectors. Then manual no-AI contract creation, secure assistant gateway, vision qualification, evidence retrieval, and floating chat UI.
