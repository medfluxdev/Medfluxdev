@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Medflux Launcher

cd /d "%~dp0"

echo ========================================
echo        Starting Medflux Software
echo ========================================
echo.

rem ------------------------------------------------------------
rem 1) Ollama
rem ------------------------------------------------------------
where ollama >nul 2>&1
if %errorlevel%==0 (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [1/4] Ollama already running.
    ) else (
        echo [1/4] Starting Ollama...
        start "Medflux Ollama" cmd /k "ollama serve"
    )
) else (
    echo [WARNING] Ollama was not found in PATH.
    echo           AI features may not work until Ollama is installed.
)

rem ------------------------------------------------------------
rem 2) Backend
rem ------------------------------------------------------------
if not exist "backend" (
    echo [ERROR] backend folder was not found.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [2/4] Backend already running.
) else (
    echo [2/4] Starting backend...
    if exist "backend\.venv\Scripts\python.exe" (
        start "Medflux Backend" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
    ) else (
        echo [WARNING] backend virtual environment .venv was not found.
        echo           Trying the system Python environment...
        start "Medflux Backend" cmd /k "cd /d ""%~dp0backend"" && python -m uvicorn app.main:app --reload --port 8000"
    )
)

echo       Waiting for backend health check...
set "BACKEND_READY=0"
for /L %%I in (1,1,30) do (
    powershell -NoProfile -Command "try { $r = Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 2; if ($r.status -eq 'ok') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        set "BACKEND_READY=1"
        goto :backend_ready
    )
    timeout /t 1 /nobreak >nul
)

:backend_ready
if "%BACKEND_READY%"=="1" (
    echo       Backend is ready.
) else (
    echo [ERROR] Backend did not become ready on http://localhost:8000
    echo         Check the "Medflux Backend" window for the actual error.
    pause
    exit /b 1
)

rem ------------------------------------------------------------
rem 3) Frontend
rem ------------------------------------------------------------
if not exist "frontend" (
    echo [ERROR] frontend folder was not found.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000 -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [3/4] Frontend already running.
) else (
    echo [3/4] Starting frontend...
    if not exist "frontend\node_modules" (
        echo       node_modules not found - running npm install first...
        start "Medflux Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm install && npm run dev"
    ) else (
        start "Medflux Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
    )
)

echo       Waiting for frontend...
set "FRONTEND_READY=0"
for /L %%I in (1,1,45) do (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:3000 -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        set "FRONTEND_READY=1"
        goto :frontend_ready
    )
    timeout /t 1 /nobreak >nul
)

:frontend_ready
if "%FRONTEND_READY%"=="1" (
    echo       Frontend is ready.
) else (
    echo [ERROR] Frontend did not become ready on http://localhost:3000
    echo         Check the "Medflux Frontend" window for the actual error.
    pause
    exit /b 1
)

rem ------------------------------------------------------------
rem 4) Open app
rem ------------------------------------------------------------
echo [4/4] Opening Medflux...
start "" http://localhost:3000

echo.
echo Medflux is running.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
