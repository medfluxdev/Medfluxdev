@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Medflux Launcher

cd /d "%~dp0"

echo ========================================
echo        Starting Medflux Software
echo ========================================
echo.

rem ------------------------------------------------------------
rem 1) Docker Desktop + PostgreSQL
rem ------------------------------------------------------------
set "DATABASE_CONTAINER=medflux-runtime-database-1"
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',5432); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [1/5] PostgreSQL already running.
) else (
    echo [1/5] Starting Docker Desktop and PostgreSQL...
    docker info >nul 2>&1
    if !errorlevel! neq 0 (
        if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
            start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
        ) else (
            echo [ERROR] Docker Desktop was not found.
            pause
            exit /b 1
        )
    )
    set "DOCKER_READY="
    for /L %%I in (1,1,90) do (
        if not defined DOCKER_READY (
            docker info >nul 2>&1
            if !errorlevel! equ 0 (set "DOCKER_READY=1") else (timeout /t 1 /nobreak >nul)
        )
    )
    if not defined DOCKER_READY (
        echo [ERROR] Docker Engine did not become ready.
        pause
        exit /b 1
    )
    docker start "%DATABASE_CONTAINER%" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] PostgreSQL container "%DATABASE_CONTAINER%" was not found.
        pause
        exit /b 1
    )
    echo       Waiting for PostgreSQL...
    set "DATABASE_READY="
    for /L %%I in (1,1,60) do (
        if not defined DATABASE_READY (
            docker inspect --format "{{.State.Health.Status}}" "%DATABASE_CONTAINER%" 2>nul | findstr /x "healthy" >nul
            if !errorlevel! equ 0 (set "DATABASE_READY=1") else (timeout /t 1 /nobreak >nul)
        )
    )
    if not defined DATABASE_READY (
        echo [ERROR] PostgreSQL did not become healthy.
        pause
        exit /b 1
    )
    echo       PostgreSQL is ready.
)

rem ------------------------------------------------------------
rem 2) Ollama
rem ------------------------------------------------------------
where ollama >nul 2>&1
if %errorlevel%==0 (
    powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [2/5] Ollama already running.
    ) else (
        echo [2/5] Starting Ollama...
        start "Medflux Ollama" cmd /k "ollama serve"
    )
) else (
    echo [WARNING] Ollama was not found in PATH.
    echo           AI features may not work until Ollama is installed.
)

rem ------------------------------------------------------------
rem 3) Backend
rem ------------------------------------------------------------
if not exist "backend" (
    echo [ERROR] backend folder was not found.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [3/5] Backend already running.
) else (
    echo [3/5] Starting backend...
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
rem 4) Frontend
rem ------------------------------------------------------------
if not exist "frontend" (
    echo [ERROR] frontend folder was not found.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('localhost',3000); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [4/5] Frontend already running.
) else (
    echo [4/5] Starting frontend...
    if not exist "frontend\node_modules" (
        echo       node_modules not found - running npm install first...
        start "Medflux Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm install && npm run dev"
    ) else (
        start "Medflux Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
    )
)

echo       Waiting for frontend...
set "FRONTEND_READY=0"
for /L %%I in (1,1,90) do (
    powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('localhost',3000); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
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
rem 5) Open app
rem ------------------------------------------------------------
echo [5/5] Opening Medflux...
start "" http://localhost:3000

echo.
echo Medflux is running.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
timeout /t 2 /nobreak >nul
endlocal
exit /b 0
