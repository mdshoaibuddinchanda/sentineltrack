# SentinelTrack — Full System Demo Launcher Script (Windows PowerShell)
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   SENTINELTRACK — REAL-TIME CCTV VEHICLE INTELLIGENCE     " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$PythonExe = "C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe"

# 1. Probe Backend API
Write-Host "[1/3] Checking Backend Health..." -ForegroundColor Yellow
try {
    $res = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 3
    Write-Host "   -> Backend ONLINE (Version: $($res.version), SHA: $($res.git_sha))" -ForegroundColor Green
} catch {
    Write-Host "   -> Backend is NOT running on port 8000." -ForegroundColor Red
    Write-Host "   -> Launch Backend with:" -ForegroundColor White
    Write-Host "      & `"$PythonExe`" -m uvicorn 08_backend.app:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Yellow
}

# 2. Check Database & PostGIS Readiness
try {
    $ready = Invoke-RestMethod -Uri "http://localhost:8000/ready" -Method Get -TimeoutSec 4
    Write-Host "[2/3] Backend Readiness: $($ready.status.ToUpper())" -ForegroundColor Green
} catch {
    Write-Host "[2/3] Backend Readiness: UNKNOWN / DEGRADED" -ForegroundColor Yellow
}

# 3. Frontend Instructions
Write-Host ""
Write-Host "[3/3] Frontend Dashboard:" -ForegroundColor Yellow
Write-Host "   -> URL: http://localhost:5173" -ForegroundColor Cyan
Write-Host "   -> Start Dev Server: cd 09_dashboard; npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "Demo Scenario Instructions:" -ForegroundColor Cyan
Write-Host "   1. Open http://localhost:5173" -ForegroundColor White
Write-Host "   2. Go to 'TARGETS' -> Click 'REGISTER TARGET' -> Enter 'GJ01AB1234' (Priority: CRITICAL)" -ForegroundColor White
Write-Host "   3. Go to 'OPERATIONS' -> View live CCTV map & real-time alerts" -ForegroundColor White
Write-Host "   4. Go to 'INVESTIGATION' -> Search 'GJ01AB1234' -> View chronological trajectory & kinematic speeds" -ForegroundColor White
Write-Host "   5. Go to 'ALERTS' -> Acknowledge incident alert" -ForegroundColor White
Write-Host "   6. Go to 'SYSTEM' -> Inspect sub-system readiness matrix & telemetry" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
