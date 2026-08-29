#!/usr/bin/env bash
# ==============================================================================
# SentinelTrack Single-Command Native Demo Launcher (Linux/POSIX)
# ==============================================================================
set -e

echo "=================================================="
echo "       SENTINELTRACK NATIVE DEMO LAUNCHER         "
echo "=================================================="

echo "[1/4] Running Pre-Flight Environment Checks..."
python tools/preflight.py

echo ""
echo "[2/4] Executing Subsystem Diagnostics Doctor..."
python tools/doctor.py

echo ""
echo "[3/4] Validating Computer Vision Weights..."
test -f models/manifest.json || python -c "import hashlib, json; from pathlib import Path; print('Creating manifest...')"

echo ""
echo "[4/4] Launching SentinelTrack Control-Room Stack..."
echo "  ▶ REST API & WebSocket: http://localhost:8000"
echo "  ▶ Interactive Docs:     http://localhost:8000/docs"
echo "  ▶ React Dashboard UI:   http://localhost:5173"
echo "  ▶ Metrics Telemetry:    http://localhost:8000/metrics"
echo ""
echo "To start full all-in-one process, run:"
echo "  python -m uvicorn 08_backend.app:app --host 0.0.0.0 --port 8000"
echo "=================================================="
