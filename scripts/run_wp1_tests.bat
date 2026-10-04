@echo off
setlocal EnableExtensions
rem WP1 test runner: backend (pytest, isolated 55432 test schema) + frontend (vitest). Results -> local-archive\test-results\
cd /d "%~dp0.."
set "OUT=%CD%\local-archive\test-results"
if not exist "%OUT%" mkdir "%OUT%"
title MedFlux WP1 tests

rem The isolated test database URL is the 55432 DSN in backend\.env (DATABASE_URL); never printed.
for /f "usebackq delims=" %%L in (`powershell -NoProfile -Command "((Get-Content backend\.env | Select-String '^DATABASE_URL=' | Select-Object -First 1) -replace '^DATABASE_URL=','').Trim()"`) do set "MEDFLUX_TEST_DATABASE_URL=%%L"
set "PYTHONPATH=%CD%\backend"
set "APP_ENV=test"
set "AUTH_ENABLED=false"
set "MEDFLUX_INSECURE_DEV=true"
set "APP_SECRET_KEY=test-only-secret"

echo [0/3] test database guard diagnostics ...
pushd backend
.venv\Scripts\python.exe -m app.testing.test_database status > "%OUT%\db_guard_status.txt" 2>&1
echo status exit=%errorlevel% >> "%OUT%\db_guard_status.txt"
.venv\Scripts\python.exe -m app.testing.test_database verify > "%OUT%\db_guard_verify.txt" 2>&1
echo verify exit=%errorlevel% >> "%OUT%\db_guard_verify.txt"
echo [1/3] backend WP1 tests (database-backed) ...
.venv\Scripts\python.exe -m pytest -q tests\test_org_structure_search_wp1.py tests\test_cost_center_patch_and_search_api_wp1.py tests\test_department_tree_a1.py tests\test_contract_department_roles_api.py > "%OUT%\backend_wp1.txt" 2>&1
echo backend_wp1 exit=%errorlevel% >> "%OUT%\backend_wp1.txt"
echo [2/3] backend full regression ...
.venv\Scripts\python.exe -m pytest -q > "%OUT%\backend_full.txt" 2>&1
echo backend_full exit=%errorlevel% >> "%OUT%\backend_full.txt"
popd

echo [3/3] frontend vitest (organization tests) ...
pushd frontend
call npx vitest run test/organization-structure-wp1.test.tsx test/organization-structure-manager.test.tsx test/organization-tree.test.ts > "%OUT%\frontend_wp1.txt" 2>&1
echo frontend_wp1 exit=%errorlevel% >> "%OUT%\frontend_wp1.txt"
call npx tsc --noEmit -p tsconfig.json > "%OUT%\frontend_tsc.txt" 2>&1
echo frontend_tsc exit=%errorlevel% >> "%OUT%\frontend_tsc.txt"
popd

echo DONE > "%OUT%\DONE.txt"
echo Results written to %OUT%
timeout /t 3 /nobreak >nul
endlocal
exit /b 0
