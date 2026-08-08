@echo off
setlocal enableextensions
cd /d "%~dp0"
set "ROOT=%cd%"
set "WEB=%cd%\web"

echo ===================================================
echo   Starting Agentic FinOps Assistant...
echo   Backend : http://localhost:8000 (FastAPI / uvicorn)
echo   Frontend: http://localhost:5173 (React / Vite)
echo ===================================================
echo.

echo [1/4] Clearing stale processes and ports 8000 and 5173...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_services.ps1" >nul 2>&1

echo [2/4] Checking frontend dependencies...
if not exist "%WEB%\node_modules" (
    echo   Installing frontend dependencies for the first run...
    pushd "%WEB%"
    call npm install
    popd
) else (
    echo   Frontend dependencies verified.
)

echo [3/4] Launching Backend and Frontend...
start "finops-api" cmd /k "title finops-api && cd /d ""%ROOT%"" && python -m uvicorn services.api.main:app --reload --port 8000"
start "finops-web" cmd /k "title finops-web && cd /d ""%WEB%"" && npm run dev"

echo [4/4] Waiting for servers to initialize...
ping 127.0.0.1 -n 6 >nul

start http://localhost:5173

echo.
echo ===================================================
echo   [OK] Services launched successfully!
echo   Web App : http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo.
echo   Run stop_finops.bat to stop all servers.
echo ===================================================
