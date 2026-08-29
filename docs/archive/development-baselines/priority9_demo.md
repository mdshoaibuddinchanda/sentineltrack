# Priority 9: Evaluator & Operator Live Demo Walkthrough

This document guides an evaluator or operator through demonstrating SentinelTrack's end-to-end CCTV vehicle intelligence capabilities.

---

## 1. Quick Start Guide

### Step 1: Start the Backend Service
In a PowerShell terminal:
```powershell
conda activate py312
python -m uvicorn 08_backend.app:app --host 0.0.0.0 --port 8000 --reload
```

### Step 2: Start the Dashboard Frontend
In a second terminal:
```powershell
cd 09_dashboard
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## 2. Complete 5-Minute Evaluation Walkthrough

### Act I: Situational Awareness (Operations Room)
1. **Open Dashboard (`/`):**
   - Note the top header status: `ONLINE`, `LIVE WS`, UTC and IST live wall-clock timers.
   - Observe the 6 KPI metric cards: Online Cameras, Offline/Degraded Cameras, Active Watchlist Targets, Unacknowledged Alerts, Today's Sightings, and Active Analytics Workers.
   - Interact with the **CCTV Geospatial Map**: click on camera markers (e.g. `cam_sg_highway_01`) to inspect junction name, department, measured FPS, and coordinates.

### Act II: Target Watchlist Intelligence
2. **Navigate to `TARGETS` (`/targets`):**
   - Click **`REGISTER TARGET`**.
   - Input:
     - License Plate: `GJ 01 AB 1234`
     - Priority: `CRITICAL`
     - Case Reference: `FIR-2026-881`
     - Notes: `Suspect vehicle in commercial robbery case`
   - Notice the live plate normalization preview: `GJ01AB1234`.
   - Click **`REGISTER TARGET`**. Target is immediately saved with transactional database persistence.

### Act III: Real-Time Incident Alert Triage
3. **Trigger / Observe Live Alert (`/alerts` & `/`):**
   - An instant incident alert is received via WebSocket.
   - A pulsing high-urgency toast notification appears: `TARGET ALERT: GJ01AB1234 (CRITICAL)`.
   - In the Alert Feed:
     - View Match Score (`0.98`), Match Class (`EXACT MATCH`), and explainable multi-frame consensus rationale.
   - Click **`Acknowledge`**: status immediately changes to `Ack by operator`.

### Act IV: Spatio-Temporal Trajectory Investigation
4. **Navigate to `INVESTIGATION` (`/investigation`):**
   - Target `GJ01AB1234` is pre-populated (or click sample plate chip `GJ01AB1234`).
   - Observe the **Chronological Trajectory Map**:
     - Sequential numbered nodes (`1`, `2`, `3`, `4`) representing camera sightings from Vastrapur $\to$ Ashram Road $\to$ SG Highway ISCON $\to$ SG Highway Pakwan.
     - Click Node `2` on the map; notice the Sighting Timeline synchronizes and highlights the exact observation time and quality.
   - Inspect the **Kinematic Segment Table**:
     - Lower-bound distances ($4.35\text{ km}, 6.72\text{ km}, 2.45\text{ km}$).
     - Minimum required speeds ($71\text{ km/h}, 121\text{ km/h}, 22\text{ km/h}$).
     - Feasibility classifications (`FEASIBLE`, `QUESTIONABLE`).
   - Read the explainability warnings panel detailing transit speed justifications.

### Act V: System Architecture & Deep Readiness Inspection
5. **Navigate to `SYSTEM` (`/system`):**
   - Inspect the **Subsystem & Model Readiness Matrix**:
     - PostgreSQL 17 Database: `READY`
     - PostGIS Spatial Engine: `READY`
     - P1 Vehicle Detector (YOLO11m FP16): `READY`
     - P2 Multi-Camera Tracker (ByteTrack): `READY`
     - P3 Plate Detector (YOLO11s FP16): `READY`
     - P4 OCR Recognizer (PP-OCRv5 ONNX): `READY`
     - P5 Target Matcher & Alert Engine: `READY`
     - P7 GIS Trajectory Pipeline: `READY`
   - Inspect the **Operational Telemetry Grid**: Total requests, active workers, vehicle detections, plate inferences, and uptime.

---

## 3. Demo Toggle & Air-Gapped Mode

- **Demo Toggle (`DEMO: ON / DEMO: OFF`):** Click the top header toggle to instantly switch between live backend database data and simulated Ahmedabad CCTV network demo fixtures.
- **Privacy Redaction Mode (`Redact / Masked`):** Click the top lock icon to enable plate masking (`GJ01****34`) for public/privacy-safe presentations.
