@echo off
setlocal EnableExtensions
rem Apply pending Alembic migrations to the database configured in backend\.env (55432 trial DB). Output -> local-archive\test-results\migration.txt
cd /d "%~dp0..\backend"
set "OUT=%CD%\..\local-archive\test-results"
if not exist "%OUT%" mkdir "%OUT%"
set "PYTHONPATH=%CD%"
title MedFlux migrate trial DB
(
  echo == identity guard ==
  .venv\Scripts\python.exe -c "from app.core.config import settings; from sqlalchemy.engine import make_url; u=make_url(settings.database_url); print('target', u.host, u.port, u.database); assert u.port==55432, 'refusing: not the 55432 trial cluster'"
  if errorlevel 1 ( echo REFUSED & exit /b 2 )
  echo == before ==
  .venv\Scripts\python.exe -m alembic current
  echo == upgrade head ==
  .venv\Scripts\python.exe -m alembic upgrade head
  echo upgrade exit=%errorlevel%
  echo == after ==
  .venv\Scripts\python.exe -m alembic current
  echo == column check ==
  .venv\Scripts\python.exe -c "from app.core.config import settings; from sqlalchemy import create_engine, inspect; e=create_engine(settings.database_url); print('department.unit_type present:', any(c['name']=='unit_type' for c in inspect(e).get_columns('department')))"
) > "%OUT%\migration.txt" 2>&1
echo MIGRATION_DONE >> "%OUT%\migration.txt"
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
