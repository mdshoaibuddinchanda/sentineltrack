# Priority 9: Frontend Intelligence & Control Room Dashboard — Baseline Report (P9C Final Frozen)

## 1. Executive Summary & Architectural Overview

Priority 9 delivers the primary operational cockpit for **SentinelTrack**: a high-density, real-time police control room vehicle intelligence dashboard. Built with React 18, TypeScript, Vite, Tailwind CSS, Leaflet, and React Router, the application interfaces directly with the Priority 8 FastAPI backend and real-time WebSocket hub.

Following the **P9C Final Correctness Pass**, all WebSocket connection lifecycles, evidence-integrity guarantees, alert store idempotency, camera/alert deep linking, privacy masking, and telemetry readiness evaluations have been strictly hardened and verified.

---

## 2. Core Functional Views & URL Routing Architecture

The dashboard implements true client-side URL routing via `react-router-dom`, supporting bookmarkable paths, deep linking, and browser navigation history:

| URL Route | Component | Key Operational Capabilities |
| :--- | :--- | :--- |
| `/` & `/operations` | `OperationsPage` | Situational awareness KPI strip (persisted sightings from telemetry, active worker count), real-time alert feed, multi-camera Leaflet GIS map with stream health markers, recent sightings stream. |
| `/cameras` & `/cameras/:cameraId` | `CamerasPage` | Camera registry table, search & filter by department/status, hardware telemetry (measured FPS, coordinates, azimuth), PostGIS 5 km radius nearby camera discovery (`GET /api/v1/cameras/nearby?lat=...&lon=...`). Handles asynchronous loading and truthful not-found states. |
| `/targets` | `TargetsPage` | Active target watchlist management, target registration modal with real-time plate normalization preview (`GJ 01 AB 1234` $\to$ `GJ01AB1234`), priority badges, deactivate actions with transactional rollback. |
| `/alerts` & `/alerts/:alertId` | `AlertsPage` | Incident triage feed, bookmarkable alert inspection by ID, severity filters (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`), unacknowledged toggle, match class badges, one-click operator acknowledgement with optimistic UI & rollback, deep link to route trace. |
| `/investigation` & `/investigation/:registration` | `InvestigationPage` | Bookmarkable plate search, chronological sighting timeline, P7 GeoJSON LineString trajectory visualization, kinematic segment table (lower-bound distance, transit duration, minimum required speed, feasibility classification), physical conflict & ambiguity explanation alerts. |
| `/system` | `SystemPage` | Central API health, Git commit SHA, deep subsystem readiness matrix (PostgreSQL, PostGIS, Camera Registry, Target DB, P1–P5 CV models, P7 Route Engine), live operational telemetry. |

---

## 3. P8 API Contract Alignment & Verification

All API clients strictly conform to the authoritative Priority 8 FastAPI schemas:

1. **Target Watchlists (`/api/v1/targets`):** Uses query parameter `enabled` (boolean).
2. **Alert Responses (`/api/v1/alerts`):** Uses query parameter `unacknowledged` (boolean).
3. **Route Engine (`/api/v1/routes`):** Uses query parameter `min_match_score` (float $0.0 - 1.0$) across route, geojson, and summary endpoints.
4. **PostGIS Nearby Cameras (`/api/v1/cameras/nearby`):** Passes `lat` and `lon` query parameters and handles raw `CameraResponse[]` array response.

---

## 4. WebSocket Lifecycle Stability & Evidence Integrity

1. **Zero Connection Churn:** Topic configuration uses a stable `topicKey` (`"*"`) so that component rerenders, state updates, alert arrivals, or navigation changes never recreate or reconnect the WebSocket.
2. **Idempotent Alert Store:** `useAlerts.prependLiveAlert` atomically verifies alert ID presence before incrementing `total` or `unackCount`, preventing duplicate increments on replay or reconnection.
3. **Zero Evidence Fabrication:** When `ALERT_CREATED` arrives via WebSocket, the client requests the authoritative database record via `GET /api/v1/alerts/{alert_id}`. If the GET fails, the UI keeps the lightweight notification and schedules a background list refresh; it **never synthesizes** fake alert objects, fake match classes, fake track IDs, or fake OCR consensus values.
4. **Resilience Hub:** Exponential reconnection backoff ($1\text{s}, 2\text{s}, 4\text{s}, 8\text{s}, \dots, \max 30\text{s}$), bidirectional 15s ping/pong keepalive, deduplication by event ID, and bounded 200-event buffers.

---

## 5. Strict Telemetry Truth & Privacy Protection

- **Tri-State Readiness:** Subsystem components are evaluated strictly: `true` $\to$ `READY`, `false` $\to$ `OFFLINE`, and `undefined`/`null` $\to$ `UNKNOWN`. Absent telemetry is never interpreted as healthy.
- **Privacy Mode Masking:** When Privacy Mode is active, all representations of license plates (raw registration, normalized registration, timeline cards, map popups, summary headers, and toasts) are masked (`GJ01****34`).
- **Air-Gapped Operation:** Leaflet CSS is imported locally. Core vector overlays remain functional when external basemap raster tiles are unavailable.
- **Chronological Observed Trajectory:** Trajectory vector polylines explicitly represent chronological observed camera-sighting sequences, not road routing networks.

---

## 6. Comprehensive Verification Matrix

| Verification Step | Command | Result | Status |
| :--- | :--- | :--- | :--- |
| **TypeScript Typecheck** | `npm run typecheck` | `0 errors` (Strict mode verified) | **PASS** |
| **ESLint Standards** | `npm run lint` | `0 errors` across all TypeScript modules | **PASS** |
| **Frontend Test Suite** | `npm test` (Vitest) | `11 test files passed, 39 / 39 tests passed` | **PASS** |
| **Production Build** | `npm run build` | `Built in 4.51s, Bundle: 133.41 kB gzip` | **PASS** |
| **Backend Test Suite** | `pytest` | `214 / 214 tests passed in 23.21s` | **PASS** |
| **Git Tracking** | `git status` | Clean working tree; all `.ts` files tracked | **VERIFIED** |

---

## 7. Baseline Status: FINAL-FROZEN & HACKATHON-ACCEPTANCE COMPLETE

Priority 9C resolves all remaining audit items, guarantees strict evidence integrity and WebSocket stability, satisfies 100% clean-clone reproducibility, and provides a dependable, operational vehicle intelligence control room.
