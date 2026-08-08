@echo off
REM Stop the Agentic FinOps Assistant backend + frontend.
echo Stopping Agentic FinOps Assistant...

REM Close the titled windows.
taskkill /FI "WINDOWTITLE eq finops-api*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq finops-web*" /F >nul 2>&1

REM Kill any orphaned project processes by command line.
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'services\.api\.main:app' -or ($_.CommandLine -match 'node' -and $_.CommandLine -match 'vite') }; foreach ($x in $p) { Stop-Process -Id $x.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Stopped.
