# OpenCode Phase A2 — isolated integration and security verification

**Scope:** assistant-authored Phase A2 foundation only. **TESTING ONLY**; report defects and minimal reproducer, do not independently rewrite code. Do not merge or deploy.

**Base:** verified A1 branch feature/org-tree-a1-20260927 at 3dc1161f50e61ec7a8af40c23ee9213d3e4ee184.
**A2 branch:** feature/contract-department-roles-a2-20260928.
**Architecture:** reuse existing ContractDepartment, Contract, Hospital, Department, ownership API, scope queries, ActivityLog. New nullable relation_role (NULL = historic unclassified, never guess), responsible/beneficiary, unique partial index for one responsible department per contract. Existing contract responsible_account_id is a *person*, NOT the responsible department.

**Implementation intentionally bounded:**
- New PUT/GET /api/ownership/contracts/{id}/department-roles. PUT requires exactly one active same-org/same-hospital responsible department; zero or more distinct beneficiaries; serializes on contract row; keeps historical NULL associations and removes explicitly deselected classified associations. No hospital auto-selection.
- Existing PATCH ownership refuses to replace a contract's links once any link is classified (409). Existing legacy GET and scoped_contract_ids continue seeing both classified and historic links. Merely being a beneficiary DOES NOT create a new global permission; existing scoped ACL remains unchanged. Any wider ACL change requires a separate reviewed phase.
- Do not invent historic roles, change extraction evidence, rewrite cost-center logic, or change contract scope_type in this phase.

**Mandatory gates before approval:**
1. Compare exact branch diff to A1; verify migration revision a2b4c6d80928 follows a1d3e5f70927 and there are no other heads. Disposable isolated PostgreSQL 55432 only: upgrade/downgrade/re-upgrade and unchanged historical NULL rows, constraints, and contracts.
2. Execute targeted new tests, existing ownership/scope/contract/department hierarchy tests, full backend under correct baseline environment, frontend 152 tests/lint/build. Record every command/exit code; do not hide pre-existing env artifact.
3. Real authenticated API: two orgs/two hospitals, admin and contract_manager vs unauthorized actor, nonvisible contract 404, cross-hospital/org/disabled department 422, duplicates 422, one responsible, 0..N beneficiaries, replacement, detach/legacy 409, historic NULL preserved, same-hospital reparented hierarchy.
4. Direct SQL: partial unique constraint blocks second responsible per contract, invalid roles rejected, duplicate pair rejected; verify migration downgrade only removes A2 additions.
5. Race at least 50 authenticated conflicting role PUT pairs against same contract, assert one canonical responsible, no duplicates or lost historic NULL links, no hangs/deadlocks. Check behavior under actual READ COMMITTED and alternate isolation if configured.
6. **Security write-path audit:** find every call to assign_contract_ownership and every direct write/delete of ContractDepartment (including imports/background tasks). If any bypass can overwrite classified links, STOP and report as release blocker. Also audit scope_queries: do NOT assume beneficiaries confer permission beyond existing ACL; report pre-existing behavior separately.
7. Check concurrent legacy PATCH vs role PUT, including scenario where PATCH obtains contract row before role PUT. If classified roles can be silently destroyed, FAIL and report minimal reproducer. Do not call A2 approved.
8. Inspect response serialization, rollback after validation errors, audit context (no sensitive data), and SQLAlchemy mapper/index compatibility.
9. No GitHub Actions, no changes to PG 5432 or Ollama 11434, no merges to JAMAL/integration, no Phase A3/UI, no unauthorized changes. STOP with full report, exact SHA, PASS/FAIL/NOT RUN and proposed minimal corrections.

**Important:** These commits have NOT been locally tested by the assistant. Treat every gate as open until verified. A2 foundation is not an Ahmad pilot or production release.
