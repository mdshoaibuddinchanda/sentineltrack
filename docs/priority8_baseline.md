# SentinelTrack Priority 8 — Backend API & Service Orchestration Baseline

## 1. Overview & Architectural Role

Priority 8 transforms the independent analytical capabilities of SentinelTrack (P0 Ingestion, P1 Vehicle Detection, P2 ByteTrack, P3 Plate Detection, P4 OCR Consensus, P5 Target Matching, and P7 Route Trajectory GIS) into a unified, high-performance, asynchronous REST & WebSocket product backend.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 SENTINELTRACK FRONTEND (P9)                                 │
└───────────────────────┬─────────────────────────────────────────────┬───────────────────────┘
                        │ REST API (OpenAPI 3.1)                      │ WebSockets
                        ▼                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                               FASTAPI BACKEND APPLICATION (P8)                             │
│                                                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────────────────────┐  │
│  │   Routers Layer      │  │    Services Layer    │  │       WebSocket Event Hub         │  │
│  │  • /health, /ready   │  │  • CameraService     │  │  • /ws/events (Multiplexed)       │  │
│  │  • /api/v1/cameras   │  │  • TargetService     │  │  • /ws/alerts (Incident Feed)     │  │
│  │  • /api/v1/targets   │  │  • SightingService   │  │  • /ws/sightings (Live Stream)    │  │
│  │  • /api/v1/sightings │  │  • AlertService      │  │  • Per-Client Bounded Queues      │  │
│  │  • /api/v1/alerts    │  │  • RouteService      │  │  • Keepalive Heartbeat            │  │
│  │  • /api/v1/routes    │  │  • AnalyticsWorker   │  │  • Non-blocking Broadcast Drop    │  │
│  └──────────────────────┘  └──────────────────────┘  └───────────────────────────────────┘  │
│                                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              ASYNC IN-MEMORY EVENT BUS                                │  │
│  │         (AlertCreatedEvent, SightingCreatedEvent, CameraHealthChangedEvent)           │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
┌──────────────────────────────┐                              ┌──────────────────────────────┐
│     POSTGRESQL / POSTGIS     │                              │   INFERENCE WORKER (P1-P5)   │
│  • cameras (Geometry)        │                              │  • FramePacket Ingestion     │
│  • vehicle_sightings         │                              │  • YOLO11m Vehicle Detection │
│  • watchlist_entries         │                              │  • ByteTrack Multi-Camera    │
│  • alerts                    │                              │  • YOLO11s Plate Detection   │
│  • trajectory_runs           │                              │  • PP-OCRv5 Consensus Voter  │
│  • dynamic PostGIS queries   │                              │  • P5 Target Normalization   │
└──────────────────────────────┘                              └──────────────────────────────┘
```

---

## 2. API Specifications & Endpoints

### 2.1 Health & Diagnostics
* `GET /health`: Fast liveness check returning uptime, service version (`1.0.0`), and git SHA.
* `GET /ready`: Deep readiness probe validating PostgreSQL connection, PostGIS extension version, camera registry accessibility, and sighting count. Returns `503 Service Unavailable` if database is down.
* `GET /metrics`: Operational system telemetry snapshot (total requests, active WebSocket clients, active camera workers, total inferences, sightings, alerts, and routes generated).

### 2.2 Camera Registry & PostGIS (`/api/v1/cameras`)
* `GET /api/v1/cameras`: Paginated list of cameras with optional filters (`department`, `live`, `stream_status`). Sanitizes credentials and RTSP passwords.
* `GET /api/v1/cameras/{camera_id}`: Detailed metadata for a single camera.
* `GET /api/v1/cameras/{camera_id}/health`: Real-time camera connectivity status, last PTS, and probe latency.
* `GET /api/v1/cameras/nearby`: Geospatial query finding all cameras within a geographic radius (`radius_m`) using PostGIS `ST_DWithin` over indexed geography points.

### 2.3 Target Watchlists (`/api/v1/targets`)
* `POST /api/v1/targets`: Register a vehicle plate to the active police watchlist (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`). Automatically normalizes plate string and validates format. Returns `409 Conflict` if target is already actively tracked.
* `GET /api/v1/targets`: Paginated list of targets with priority and status filters.
* `GET /api/v1/targets/{target_id}`: Retrieve single target details.
* `PATCH /api/v1/targets/{target_id}`: Update target priority, expiry, notes, or metadata.
* `DELETE /api/v1/targets/{target_id}`: Deactivate target from active monitoring (soft delete/archive).

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
* **Scheduling:** Micro-batch scheduler accepting `FramePacket` instances across multiple concurrent camera streams.
* **Pipeline:**
  $$\text{FramePacket} \xrightarrow{\text{P1}} \text{Vehicle Detections} \xrightarrow{\text{P2}} \text{ByteTrack} \xrightarrow{\text{P3}} \text{Plate BBox} \xrightarrow{\text{P4}} \text{PP-OCRv5 Consensus} \xrightarrow{\text{P5}} \text{Target Matching} \xrightarrow{\text{Bus}} \text{Event Bus}$$
* **Queue Discipline:** Per-camera bounded queue (`BoundedStreamQueue`) with oldest-frame drop policy for live real-time analysis.

---

## 5. Measured Production Latency Benchmark

The backend was benchmarked on local workstation hardware (Windows, Python 3.12, PostgreSQL 17 + PostGIS):

| Endpoint | Method | Mean Latency | P50 (Median) | P95 Latency | P99 Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Liveness (`/health`)** | `GET` | **4.81 ms** | **4.53 ms** | **7.18 ms** | **10.60 ms** |
| **Readiness (`/ready`)** | `GET` | **33.53 ms** | **31.24 ms** | **51.15 ms** | **61.52 ms** |
| **Metrics Snapshot (`/metrics`)** | `GET` | **5.17 ms** | **5.09 ms** | **7.27 ms** | **9.27 ms** |
| **List Cameras (`/api/v1/cameras`)** | `GET` | **39.44 ms** | **37.12 ms** | **52.48 ms** | **81.15 ms** |
| **List Targets (`/api/v1/targets`)** | `GET` | **19.35 ms** | **17.84 ms** | **26.84 ms** | **63.29 ms** |
| **List Sightings (`/api/v1/sightings`)** | `GET` | **36.23 ms** | **33.70 ms** | **50.27 ms** | **98.30 ms** |
| **Vehicle History (`/api/v1/vehicles/{reg}/history`)** | `GET` | **37.68 ms** | **35.39 ms** | **54.90 ms** | **59.47 ms** |
| **List Alerts (`/api/v1/alerts`)** | `GET` | **37.74 ms** | **35.62 ms** | **55.97 ms** | **64.88 ms** |
| **Target Route Kinematics (`/api/v1/routes/{reg}`)** | `GET` | **45.01 ms** | **42.28 ms** | **67.56 ms** | **88.81 ms** |
| **Route GeoJSON RFC-7946 (`/api/v1/routes/{reg}/geojson`)** | `GET` | **43.62 ms** | **40.85 ms** | **59.87 ms** | **73.28 ms** |
| **Route Summary (`/api/v1/routes/{reg}/summary`)** | `GET` | **43.69 ms** | **41.10 ms** | **61.62 ms** | **72.19 ms** |

*All endpoints achieve sub-50ms median response times, fulfilling real-time operational requirements.*

---

## 6. Freeze Status

Priority 8 Backend REST API & Service Orchestration is **100% HACKATHON ACCEPTANCE COMPLETE & BASELINE FROZEN**.
All 39 unit, integration, concurrency, and WebSocket tests pass reliably without errors.
