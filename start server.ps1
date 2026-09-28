$backend = "D:\QOMASH\site working\site 3 open code\backend"
$frontend = "D:\QOMASH\site working\site 3 open code\frontend"

$backendPort = 8001
$frontendPort = 9012

# =========================
# Check Backend - Port 8001
# =========================
$backendRunning = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue

if ($backendRunning) {
    Write-Host "Backend is already running on port $backendPort" -ForegroundColor Green
}
else {
    Write-Host "Starting Django Backend on port $backendPort..." -ForegroundColor Cyan

    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "Set-Location '$backend'; .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:$backendPort --noreload"
}

# =========================
# Check Frontend - Port 9012
# =========================
$frontendRunning = Get-NetTCPConnection -LocalPort $frontendPort -State Listen -ErrorAction SilentlyContinue

if ($frontendRunning) {
    Write-Host "Frontend is already running on port $frontendPort" -ForegroundColor Green
}
else {
    Write-Host "Starting Next.js Frontend on port $frontendPort..." -ForegroundColor Cyan

    Start-Process powershell -ArgumentList "-NoExit", "-Command", `
        "Set-Location '$frontend'; npm run dev -- -p $frontendPort"
}

Write-Host ""
Write-Host "====================================" -ForegroundColor Yellow
Write-Host " Almorooj / Qomash Project Status" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Yellow
Write-Host "Backend : http://127.0.0.1:8001" -ForegroundColor White
Write-Host "Frontend: http://localhost:9012" -ForegroundColor White
Write-Host "API     : http://127.0.0.1:8001/api" -ForegroundColor White
Write-Host "====================================" -ForegroundColor Yellow