# Start Agentic FinOps Assistant backend (FastAPI) and frontend (React/Vite).
$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot | Split-Path -Parent
$WebDir = Join-Path $Root "web"
$StopScript = Join-Path $PSScriptRoot "stop_services.ps1"

# 1. Clear any active services or busy ports first
if (Test-Path $StopScript) {
    & $StopScript
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Starting Agentic FinOps Assistant..." -ForegroundColor Cyan
Write-Host "  Backend : http://localhost:8000 (FastAPI / uvicorn)" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173 (React / Vite)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# 2. Check and install frontend dependencies if needed
if (-not (Test-Path (Join-Path $WebDir "node_modules"))) {
    Write-Host "[1/3] Installing frontend dependencies (first run)..." -ForegroundColor Yellow
    Set-Location $WebDir
    Start-Process npm -ArgumentList "install" -Wait -NoNewWindow
    Set-Location $Root
} else {
    Write-Host "[1/3] Frontend dependencies verified." -ForegroundColor Green
}

# 3. Start Backend in separate window
Write-Host "[2/3] Launching backend (uvicorn) & frontend (vite)..." -ForegroundColor Green
$backendCmd = "title finops-api && cd /d `"$Root`" && python -m uvicorn services.api.main:app --reload --port 8000"
Start-Process cmd -ArgumentList "/k", $backendCmd -WorkingDirectory $Root

# 4. Start Frontend in separate window
$frontendCmd = "title finops-web && cd /d `"$WebDir`" && npm run dev"
Start-Process cmd -ArgumentList "/k", $frontendCmd -WorkingDirectory $WebDir

# 5. Wait for servers to spin up and open default browser
Write-Host "[3/3] Waiting for servers to initialize..." -ForegroundColor Green
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "  [OK] Services launched successfully!" -ForegroundColor Green
Write-Host "  Web App : http://localhost:5173" -ForegroundColor Green
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "  Run stop_finops.bat to stop all servers." -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""
