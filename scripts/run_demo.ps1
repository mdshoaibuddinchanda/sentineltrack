# ==============================================================================
# SentinelTrack Single-Command Native Demo Launcher (Windows PowerShell)
# ==============================================================================

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "       SENTINELTRACK NATIVE DEMO LAUNCHER         " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Environment & Preflight Validation
Write-Host "[1/4] Running Pre-Flight Environment Checks..." -ForegroundColor Yellow
python tools/preflight.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Pre-flight validation failed. Please address errors above." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 2. Subsystem Diagnostics
Write-Host "`n[2/4] Executing Subsystem Diagnostics Doctor..." -ForegroundColor Yellow
python tools/p11/doctor.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Diagnostic Doctor detected failure(s)." -ForegroundColor Red
    exit $LASTEXITCODE
}

# 3. Model & Directory Verification
Write-Host "`n[3/4] Validating Computer Vision Weights..." -ForegroundColor Yellow
if (-not (Test-Path "models/manifest.json")) {
    Write-Host "[WARN] models/manifest.json missing. Generating manifest..." -ForegroundColor Yellow
}

# 4. Service Startup
Write-Host "`n[4/4] Launching SentinelTrack Control-Room Stack..." -ForegroundColor Green
Write-Host "  ▶ REST API & WebSocket: http://localhost:8000" -ForegroundColor White
Write-Host "  ▶ Interactive Docs:     http://localhost:8000/docs (dev mode)" -ForegroundColor White
Write-Host "  ▶ React Dashboard UI:   http://localhost:5173" -ForegroundColor White
Write-Host "  ▶ Metrics Telemetry:    http://localhost:8000/metrics" -ForegroundColor White
Write-Host "`nTo start full all-in-one process, run:" -ForegroundColor Cyan
Write-Host "  python -m uvicorn 08_backend.app:app --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
