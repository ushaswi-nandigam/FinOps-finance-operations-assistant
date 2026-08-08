@echo off
REM Start the Agentic FinOps Assistant backend + frontend, then open the console.
cd /d "%~dp0"

echo Starting Agentic FinOps Assistant...
echo   Backend : uvicorn services.api.main:app --reload
echo   Frontend: npm run dev  (http://localhost:5173)

REM Install frontend deps on first run if node_modules is missing.
if not exist "web\node_modules" (
    echo Installing frontend dependencies (first run)...
    pushd web
    call npm install
    popd
)

start "finops-api" cmd /k "python -m uvicorn services.api.main:app --reload"
start "finops-web" cmd /k "cd /d ""%~dp0web"" && npm run dev"

timeout /t 6 /nobreak >nul
start http://localhost:5173
echo Done. Use stop_finops.bat to stop everything.
