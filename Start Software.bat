@echo off
setlocal
title Medflux Launcher

cd /d "%~dp0"

echo ========================================
echo        Starting Medflux Software
echo ========================================
echo.

where ollama >nul 2>&1
if %errorlevel%==0 (
    echo [1/4] Starting Ollama...
    start "Medflux Ollama" cmd /k "ollama serve"
) else (
    echo [WARNING] Ollama was not found in PATH.
    echo           AI features may not work until Ollama is installed.
)

timeout /t 2 /nobreak >nul

echo [2/4] Starting backend...
if not exist "backend" (
    echo [ERROR] backend folder was not found.
    pause
    exit /b 1
)

if exist "backend\.venv\Scripts\activate.bat" (
    start "Medflux Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"
) else (
    echo [WARNING] backend virtual environment .venv was not found.
    echo           Trying to start with the system Python environment...
    start "Medflux Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --port 8000"
)

timeout /t 3 /nobreak >nul

echo [3/4] Starting frontend...
if not exist "frontend" (
    echo [ERROR] frontend folder was not found.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [INFO] node_modules not found. Running npm install first...
    start "Medflux Frontend" cmd /k "cd /d "%~dp0frontend" && npm install && npm run dev"
) else (
    start "Medflux Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
)

timeout /t 5 /nobreak >nul

echo [4/4] Opening Medflux...
start "" http://localhost:3000

echo.
echo Medflux startup commands have been launched.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
