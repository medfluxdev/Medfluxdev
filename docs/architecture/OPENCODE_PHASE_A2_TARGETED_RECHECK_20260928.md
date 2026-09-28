# OpenCode A2 targeted recheck after assistant test fix

Target implementation unchanged; only A2 test expectation fixed at commit 8e8b13496509b0a584b78b628687d925308af583.

1. Fetch the A2 branch into a fresh isolated worktree. Confirm the only diff since f5e95f3 is the assertion in backend/tests/test_contract_department_roles_a2.py.
2. Run targeted A2 test and relevant ownership regression with disposable isolated DB only. Confirm ORM constraint name matches migrated PostgreSQL name; do not change schema.
3. Run full backend in correctly configured baseline env, distinguish inherited security-posture conflict from regressions. Frontend may reuse previous results only if no frontend changes, clearly label reused.
4. PRE-1 remains an INDEPENDENT RELEASE CONFIDENCE BLOCKER: per-test schema fixture search_path=test,public incorrectly lets create_all see public tables. DO NOT modify conftest or public schema as part of A2 recheck. Instead, collect exact conftest file path, relevant lines, effective search_path, engine setup, and a minimal disposable DB reproducer. Report the safest independent fixture repair plan for assistant implementation on a separate branch. Existing DB-backed results are conditional until isolation is fixed and gates rerun.
5. Record any remaining REPEATABLE READ 500 risk as conditional; document import 422 needs UI workflow follow-up. Do not claim full production readiness.
6. No implementation changes, no Actions, no merge, no production PostgreSQL 5432 or Ollama 11434 access. STOP and report.
