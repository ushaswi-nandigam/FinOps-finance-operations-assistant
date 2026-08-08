# Stop Agentic FinOps Assistant backend (FastAPI) and frontend (Vite) and clear ports 8000 and 5173.
$ErrorActionPreference = "SilentlyContinue"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Stopping Agentic FinOps Assistant..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Terminate titled CMD windows if any
Get-CimInstance Win32_Process | Where-Object { $_.Title -like "*finops-api*" -or $_.Title -like "*finops-web*" } | Stop-Process -Force

# 2. Terminate uvicorn / python API and node / vite processes
Get-CimInstance Win32_Process | Where-Object { 
    $cmd = $_.CommandLine
    $cmd -match 'services\.api\.main' -or $cmd -match 'uvicorn' -or ($cmd -match 'node' -and $cmd -match 'vite')
} | Stop-Process -Force

# 3. Clear listening sockets on ports 8000 and 5173
$connections = Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue
if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        if ($p -gt 0 -and $p -ne $PID) {
            Stop-Process -Id $p -Force
        }
    }
}

Write-Host "[OK] Ports 8000 and 5173 cleared. All services stopped." -ForegroundColor Green
Write-Host ""
