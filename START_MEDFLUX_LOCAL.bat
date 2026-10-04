@echo off
setlocal EnableExtensions EnableDelayedExpansion
title MedFlux LOCAL Launcher
cd /d "%~dp0"

set "RUNTIME=%LOCALAPPDATA%\MedFlux\runtime"
if not exist "%RUNTIME%" mkdir "%RUNTIME%"

echo ================================================
echo   MedFlux LOCAL launcher (no cloud, local AI)
echo ================================================
echo.

rem 1) PostgreSQL - existing local cluster first, Docker fallback (reuses project's own script)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_local_postgres.ps1"
if !errorlevel! equ 0 (
    echo [1/6] PostgreSQL is ready.
) else (
    if exist "%ProgramData%\MedFlux\postgres18\data\PG_VERSION" (
        echo [ERROR] The managed MedFlux PostgreSQL service exists but did not become ready.
        echo         Check Windows service MedFluxPostgres18 and its Windows Event Log.
        echo         Existing database files have NOT been removed or modified by this launcher.
        pause
        exit /b 1
    )
    echo [1/6] No usable local PostgreSQL cluster; trying Docker...
    docker info >nul 2>&1
    if !errorlevel! neq 0 (
        if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
            start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
        ) else (
            echo [ERROR] PostgreSQL is not reachable and Docker Desktop was not found.
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
    docker compose up -d postgres
    if !errorlevel! neq 0 (
        echo [ERROR] Docker PostgreSQL could not be started.
        pause
        exit /b 1
    )
    powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',5432); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] PostgreSQL did not become reachable on 127.0.0.1:5432.
        pause
        exit /b 1
    )
    echo       PostgreSQL is ready.
)

rem 2) Ollama - must already be running; never started/stopped by this launcher
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Ollama is not running on http://127.0.0.1:11434.
    echo         Start local Ollama first using the Ollama app or ollama serve.
    echo         then run this launcher again. This launcher never downloads models.
    pause
    exit /b 1
)
echo [2/6] Ollama is running.

rem 3) List installed models and let the user choose a local one
echo [3/6] Detecting installed local models...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ollama_models.ps1"
set "MODEL_EXIT=!errorlevel!"
if "!MODEL_EXIT!"=="2" (
    echo [ERROR] No local models installed. Install one manually, e.g.:
    echo         ollama pull qwen3-vl:8b-instruct
    pause
    exit /b 1
)
if "!MODEL_EXIT!"=="3" (
    echo [ERROR] Ollama is not reachable anymore.
    pause
    exit /b 1
)
if "!MODEL_EXIT!"=="4" (
    echo [ERROR] Invalid model selection.
    pause
    exit /b 1
)
if "!MODEL_EXIT!"=="6" (
    echo [ERROR] Could not write the model list.
    pause
    exit /b 1
)

set "CHOSEN="
if exist "%RUNTIME%\selected_model.txt" (
    set /p CHOSEN=<"%RUNTIME%\selected_model.txt"
)

rem 4) Persist the selected local model in MedFlux (provider pinned to ollama)
if defined CHOSEN if not "!CHOSEN!"=="KEEP" (
    echo [4/6] Configuring MedFlux to use local model: !CHOSEN!
    pushd "%~dp0backend"
    ".venv\Scripts\python.exe" "%~dp0scripts\set_local_model.py" "!CHOSEN!"
    set "PERSIST_EXIT=!errorlevel!"
    popd
    if "!PERSIST_EXIT!"=="2" (
        echo [WARNING] Could not persist the selection now - select it once in the MedFlux UI.
    ) else if "!PERSIST_EXIT!"=="3" (
        echo [WARNING] Database not ready for the selection - select it once in the MedFlux UI.
    )
) else (
    echo [4/6] Keeping the existing MedFlux model selection.
)

rem 5) Backend
if not exist "backend" (
    echo [ERROR] backend folder was not found.
    pause
    exit /b 1
)
powershell -NoProfile -Command "try { $r = Invoke-RestMethod http://127.0.0.1:8000/ready -TimeoutSec 2; if ($r.status -eq 'ready') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [5/6] Backend already running.
) else (
    echo [5/6] Starting backend...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\spawn_medflux_backend.ps1" "%CD%"
    if !errorlevel! neq 0 (
        echo [ERROR] Backend could not be started.
        pause
        exit /b 1
    )
    set "BACKEND_READY=0"
    for /L %%I in (1,1,60) do (
        powershell -NoProfile -Command "try { $r = Invoke-RestMethod http://127.0.0.1:8000/ready -TimeoutSec 2; if ($r.status -eq 'ready') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
        if !errorlevel! equ 0 (
            set "BACKEND_READY=1"
            goto :backend_ready
        )
        timeout /t 1 /nobreak >nul
    )
    :backend_ready
    if "!BACKEND_READY!"=="1" (
        echo       Backend is ready.
    ) else (
        echo [ERROR] Backend did not become ready on http://localhost:8000
        echo         Check "%RUNTIME%\backend.log"
        pause
        exit /b 1
    )
)

rem 6) Frontend
if not exist "frontend" (
    echo [ERROR] frontend folder was not found.
    pause
    exit /b 1
)
powershell -NoProfile -Command "try { $c=New-Object Net.Sockets.TcpClient; $c.Connect('localhost',3000); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo [6/6] Frontend already running.
) else (
    echo [6/6] Starting frontend...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\spawn_medflux_frontend.ps1" "%CD%"
    if !errorlevel! neq 0 (
        echo [ERROR] Frontend could not be started.
        pause
        exit /b 1
    )
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
    if "!FRONTEND_READY!"=="1" (
        echo       Frontend is ready.
    ) else (
        echo [ERROR] Frontend did not become ready on http://localhost:3000
        echo         Check "%RUNTIME%\frontend.log"
        pause
        exit /b 1
    )
)

rem 7) Done
echo.
echo ================================================
echo   MedFlux is running - LOCAL ONLY.
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   AI:       local Ollama http://127.0.0.1:11434
echo   Stop:     double-click STOP_MEDFLUX_LOCAL.bat
echo ================================================
echo.
start "" http://localhost:3000

endlocal
exit /b 0