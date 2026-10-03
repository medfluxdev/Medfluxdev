# OpenCode PRE-1 isolated test-schema repair — verification only

Branch: fix/test-schema-isolation-pre1-20260928
Assistant-authored fix: 84d731c8e39a1f118c24afbcff32dc6ea3b0c202
A2 baseline: a31e92847ab9dd9895d0db8ded3740eb2a842a15

**Scope:** only backend/conftest.py changed. No A2 application code or migration changes. The DDL engine now uses test-schema-only search_path for create_all/checkfirst. Test-facing sessions still use test-schema,public for pg_trgm. Fixture fails closed if metadata tables are missing from test schema.

**MANDATORY TEST GATES**
1. Inspect exact diff, verify branch ancestry and unchanged A2 code/migrations. Disposable PG 55432 only. Never use production DB or actual hospital data.
2. Run minimal reproducer with EMPTY public and MIGRATION-POPULATED public, independently. For both, show actual schema table counts, search_path, unqualified contract_department resolution, and unchanged public table/data checksums. The reported baseline had 44 ORM tables; compare against live metadata rather than hardcoding count. Check the relation_role column.
3. Verify pg_trgm similarity() and search functionality work with runtime test-schema,public.
4. Run full backend under baseline and separate production-shaped environment, classify inherited env posture conflict accurately. Re-run A1 hierarchy and A2 ownership/scope/contract/security/API tests against a database with populated public to prove tests use the new isolated schema. Include concurrency/role PUT and legacy PATCH if feasible.
5. Inspect pytest_sessionfinish cleanup; verify only the generated test schema is dropped, public untouched. Check that unexpected fixture errors fail closed, never silently run against public.
6. Review create_all vs migration-only indexes (three trigram indexes): if missing indexes make test DB structurally different, report this limitation and propose a separate migration-based fixture gate, do not silently claim migration parity.
7. If test schema is empty, SQL resolves to public unexpectedly, data changes public, or tests regress: STOP with minimal reproducer. Do not edit implementation yourself. Provide precise commands, results, test counts, skipped and known inherited failures.

No GitHub Actions, no deployment, no merge, no changes to PG 5432/Ollama 11434. STOP for assistant review.
