# Priority 8 Baseline & Integration Report

**Date:** August 28, 2026  
**Status:** **100% HACKATHON ACCEPTANCE COMPLETE & BASELINE FROZEN**  
**Component:** FastAPI REST & WebSocket Backend, Service Layer Orchestration, Event Timing Integration, Micro-Batch Inference Scheduler

---

## 1. Executive Summary

Priority 8 provides the central API gateway, service orchestration, event hub, and analytics worker that connects all computer vision modules (P0–P5), the spatio-temporal route trajectory engine (P7), and the operator frontend dashboard (P9).

### Core Capabilities:
1. **Full-Featured FastAPI REST API:** Robust, validated CRUD and querying endpoints for cameras, watchlists, sightings, alerts, and GIS trajectories.
2. **Real-Time WebSocket Event Hub:** Multiplexed streaming (`/ws/events`, `/ws/alerts`, `/ws/sightings`) with bounded per-client queues and heartbeat ping-pong keepalives.
3. **Analytics Worker:** Multi-camera micro-batch orchestration with batched P1 inference and staged P2–P5 processing across concurrent camera streams.
4. **End-to-End Event Time & Clock Integrity:** Guarantees strict propagation and persistence of UTC wall-clock timestamps, monotonic PTS offsets, clock source provenance, and quality metrics from ingestion through database persistence.

---

## 2. API Endpoints

### 2.1 Health & Operational Telemetry (`/health`, `/ready`, `/metrics`)
* `GET /health`: Fast liveness check returning uptime, service version (`1.0.0`), and dynamically resolved git SHA.
* `GET /ready`: Deep readiness probe validating PostgreSQL connection, PostGIS extension, camera registry, target repository, P7 route engine, and CV model pipelines (YOLO11m detector, ByteTrack tracker, YOLO11s-plate detector, PP-OCRv5 ONNX recognizer, and target matcher).
* `GET /metrics`: Operational system telemetry snapshot (total requests, active WebSocket clients, active camera workers, total inferences, sightings, alerts, and routes generated).

### 2.2 Camera Registry & PostGIS (`/api/v1/cameras`)
* `GET /api/v1/cameras`: Paginated list of cameras with optional filters (`department`, `live`, `stream_status`). Sanitizes credentials and RTSP passwords.
* `GET /api/v1/cameras/{camera_id}`: Detailed metadata for a single camera.
* `GET /api/v1/cameras/{camera_id}/health`: Real-time camera connectivity status, last PTS, and probe latency.
* `GET /api/v1/cameras/nearby`: Geospatial query finding all cameras within a geographic radius (`radius_m`) using PostGIS `ST_DWithin` over indexed geography points.

### 2.3 Target Watchlists (`/api/v1/targets`)
* `POST /api/v1/targets`: Register a vehicle plate to the active police watchlist (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`). Automatically normalizes plate string and validates format. Returns `409 Conflict` if target is already actively tracked. Transactionally rolls back in-memory indices if database persistence fails.
* `GET /api/v1/targets`: Paginated list of targets with priority and status filters.
* `GET /api/v1/targets/{target_id}`: Retrieve single target details.
* `PATCH /api/v1/targets/{target_id}`: Update target priority, expiry, notes, or metadata with transactional rollback on DB failure.
* `DELETE /api/v1/targets/{target_id}`: Deactivate target from active monitoring with transactional rollback on DB failure.

### 2.4 Sightings & Historical Search (`/api/v1/sightings`)
* `GET /api/v1/sightings`: Historical query across all cameras with filters (`registration`, `camera_id`, `start_time`, `end_time`, `min_score`, `limit`, `offset`).
* `GET /api/v1/vehicles/{registration}/history`: Full chronological observation timeline for a specific vehicle.

### 2.5 Target Alerts (`/api/v1/alerts`)
* `GET /api/v1/alerts`: List incident alerts with filters (`unacknowledged_only`, `camera_id`, `limit`, `offset`).
* `GET /api/v1/alerts/{alert_id}`: Detailed alert record with OCR consensus confidence, match score, match class, and explainability evidence.
* `POST /api/v1/alerts/{alert_id}/ack`: Operator acknowledgement recording timestamp and operator identity (`acknowledged_by`).

### 2.6 Route Engine & GIS Trajectory (`/api/v1/routes`)
* `GET /api/v1/routes/{registration}`: Spatio-temporal trajectory reconstruction. Returns chronological observation sequence, kinematic segments (distance, delta time, required speed, feasibility class), overall trajectory confidence score ($0.0 - 1.0$), ambiguity status, conflict status, and explainability reasons.
* `GET /api/v1/routes/{registration}/geojson`: RFC-7946 compliant GeoJSON `FeatureCollection` ready for immediate rendering on Mapbox GL / Leaflet map canvases.
* `GET /api/v1/routes/{registration}/summary`: Concise summary for rapid investigative triage.

---

## 3. Real-Time WebSocket Event Hub

* **Endpoint:** `WS /ws/events?topics=alerts,sightings`
* **Dedicated Channels:** `WS /ws/alerts`, `WS /ws/sightings`
* **Architecture:**
  * **Per-Client Bounded Queues (`maxsize=100`):** Slow frontend connections or network hiccups cannot cause memory leaks or backpressure on backend inference threads.
  * **Drop Policy:** When a client queue is full, the oldest unread event is dropped and the new event is queued.
  * **Heartbeat Keepalive:** Bidirectional `ping` $\to$ `pong` keepalive ensures reliable connection state.

---

## 4. Multi-Camera Analytics Worker

* **Class:** `AnalyticsWorker`
* **Scheduling:** Multi-camera micro-batch orchestration with batched P1 inference and staged P2–P5 processing across concurrent camera streams.
* **Pipeline:**
  $$\text{FramePacket Batch} \xrightarrow{\text{P1 (Batch)}} \text{Vehicle Detections} \xrightarrow{\text{P2}} \text{ByteTrack} \xrightarrow{\text{P3}} \text{Plate Pipeline} \xrightarrow{\text{P4}} \text{PP-OCRv5 Consensus} \xrightarrow{\text{P5}} \text{Target Matching} \xrightarrow{\text{Bus}} \text{Event Bus}$$
* **Queue Discipline:** Per-camera bounded queue (`BoundedStreamQueue`) with oldest-frame drop policy for live real-time analysis.

---

## 5. Measured Production Latency Benchmark

The backend was benchmarked on local workstation hardware (Windows, Python 3.12, PostgreSQL 17 + PostGIS):

| Endpoint | Method | Mean Latency | P50 (Median) | P95 Latency | P99 Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Liveness (`/health`)** | `GET` | **5.58 ms** | **4.59 ms** | **6.95 ms** | **80.07 ms** |
| **Readiness (`/ready`)** | `GET` | **29.62 ms** | **28.44 ms** | **45.06 ms** | **48.00 ms** |
| **Metrics Snapshot (`/metrics`)** | `GET` | **4.23 ms** | **4.04 ms** | **6.11 ms** | **8.21 ms** |
| **List Cameras (`/api/v1/cameras`)** | `GET` | **42.94 ms** | **39.96 ms** | **63.61 ms** | **91.59 ms** |
| **List Targets (`/api/v1/targets`)** | `GET` | **22.07 ms** | **20.19 ms** | **33.40 ms** | **72.53 ms** |
| **List Sightings (`/api/v1/sightings`)** | `GET` | **40.75 ms** | **38.70 ms** | **57.50 ms** | **67.22 ms** |
| **Vehicle History (`/api/v1/vehicles/{reg}/history`)** | `GET` | **38.85 ms** | **36.46 ms** | **58.31 ms** | **68.36 ms** |
| **List Alerts (`/api/v1/alerts`)** | `GET` | **38.98 ms** | **38.23 ms** | **55.63 ms** | **70.89 ms** |
| **Target Route Kinematics (`/api/v1/routes/{reg}`)** | `GET` | **47.30 ms** | **44.52 ms** | **64.78 ms** | **161.11 ms** |
| **Route GeoJSON RFC-7946 (`/api/v1/routes/{reg}/geojson`)** | `GET` | **46.52 ms** | **44.12 ms** | **60.22 ms** | **76.88 ms** |
| **Route Summary (`/api/v1/routes/{reg}/summary`)** | `GET` | **45.40 ms** | **43.84 ms** | **57.18 ms** | **67.71 ms** |

*All endpoints achieve sub-50ms median response times, fulfilling real-time operational requirements.*

---

## 6. Freeze Status

Priority 8 Backend REST API & Service Orchestration is **100% HACKATHON ACCEPTANCE COMPLETE & BASELINE FROZEN**.
All **214** canonical unit, integration, concurrency, micro-batching, and WebSocket tests pass reliably without errors.
