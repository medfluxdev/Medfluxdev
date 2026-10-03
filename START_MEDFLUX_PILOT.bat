@echo off
setlocal EnableExtensions
title MedFlux PILOT Launcher (WSL 55432)
cd /d "%~dp0"
echo ================================================
echo   MedFlux PILOT launcher - isolated test DB 55432
echo ================================================
echo.

rem 1) WSL PostgreSQL 18 on 55432 (start only if not already up)
echo [1/4] PostgreSQL 55432 (WSL Ubuntu)...
powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',55432);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    wsl -d Ubuntu -u root -- su postgres -s /bin/bash -c "/usr/lib/postgresql/18/bin/pg_ctl -D /opt/medflux-test-pg/data -l /tmp/medflux-test-pg.log -o '-p 55432' start"
    powershell -NoProfile -Command "for($i=0;$i -lt 30;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('127.0.0.1',55432);$c.Close();exit 0}catch{Start-Sleep 1}};exit 1" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] PostgreSQL did not become reachable on 127.0.0.1:55432.
        echo         Check: wsl -d Ubuntu  then  cat /tmp/medflux-test-pg.log
        pause
        exit /b 1
    )
)
echo       PostgreSQL 55432 is ready.

rem 2) Backend (uses backend\.env -> DATABASE_URL = 55432)
echo [2/4] Backend on http://127.0.0.1:8000 ...
powershell -NoProfile -Command "try{$r=Invoke-RestMethod http://127.0.0.1:8000/ready -TimeoutSec 2;if($r.status -eq 'ready'){exit 0}else{exit 1}}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    if not exist "backend\.venv\Scripts\python.exe" (
        echo [ERROR] backend\.venv not found.
        pause
        exit /b 1
    )
    start "MedFlux Backend (8000)" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
    powershell -NoProfile -Command "for($i=0;$i -lt 90;$i++){try{$r=Invoke-RestMethod http://127.0.0.1:8000/ready -TimeoutSec 2;if($r.status -eq 'ready'){exit 0}}catch{};Start-Sleep 1};exit 1" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Backend did not become ready. See the "MedFlux Backend (8000)" window.
        pause
        exit /b 1
    )
)
echo       Backend is ready.

rem 3) Frontend
echo [3/4] Frontend on http://localhost:3000 ...
powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('localhost',3000);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if errorlevel 1 (
    if not exist "frontend\node_modules" (
        start "MedFlux Frontend (3000)" cmd /k "cd /d ""%~dp0frontend"" && npm install && npm run dev"
    ) else (
        start "MedFlux Frontend (3000)" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"
    )
    powershell -NoProfile -Command "for($i=0;$i -lt 120;$i++){try{$c=New-Object Net.Sockets.TcpClient;$c.Connect('localhost',3000);$c.Close();exit 0}catch{Start-Sleep 1}};exit 1" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Frontend did not become ready. See the "MedFlux Frontend (3000)" window.
        pause
        exit /b 1
    )
)
echo       Frontend is ready.

rem 4) Open the app
echo [4/4] Opening MedFlux...
start "" http://localhost:3000
echo.
echo MedFlux is running (PILOT / 55432).
echo   Frontend: http://localhost:3000
echo   Backend:  http://127.0.0.1:8000
echo Close the two server windows to stop.
timeout /t 5 /nobreak >nul
endlocal
exit /b 0
