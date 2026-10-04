@echo off
setlocal EnableExtensions
title MedFlux LOCAL Stop
cd /d "%~dp0"

set "RUNTIME=%LOCALAPPDATA%\MedFlux\runtime"
if not exist "%RUNTIME%" (
    echo No launcher runtime state found. Nothing was started by this launcher.
    echo Note: existing MedFlux/Ollama/PostgreSQL services are left untouched by design.
    timeout /t 3 /nobreak >nul
    endlocal
    exit /b 0
)

echo ================================================
echo   Stopping MedFlux processes started by this
echo   launcher ONLY.
echo   Existing Ollama and PostgreSQL stay running.
echo ================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_medflux_runtime.ps1"

rem clean up leftover model selection artifact
if exist "%RUNTIME%\selected_model.txt" del /q "%RUNTIME%\selected_model.txt" >nul 2>&1
if exist "%RUNTIME%\installed_models.json" del /q "%RUNTIME%\installed_models.json" >nul 2>&1

echo.
echo Done. To bring everything down completely, stop Ollama and PostgreSQL
echo via their own tools (this launcher deliberately does not touch them).
timeout /t 5 /nobreak >nul
endlocal
exit /b 0