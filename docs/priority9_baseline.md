# Priority 9: Frontend Intelligence & Control Room Dashboard — Baseline Report (P9B Hardened)

## 1. Executive Summary & Architectural Overview

Priority 9 delivers the primary operational cockpit for **SentinelTrack**: a high-density, real-time police control room vehicle intelligence dashboard. Built with React 18, TypeScript, Vite, Tailwind CSS, Leaflet, and React Router, the application interfaces directly with the Priority 8 FastAPI backend and real-time WebSocket hub.

Following the **P9B Hardening Pass**, all P8 API contracts, URL routing paths, WebSocket evidence integrity mechanisms, air-gapped styling, and TypeScript repository tracking have been strictly verified and hardened.

---

## 2. Core Functional Views & URL Routing Architecture

The dashboard implements true client-side URL routing via `react-router-dom`, supporting bookmarkable paths, deep linking, and browser navigation history:

| URL Route | Component | Key Operational Capabilities |
| :--- | :--- | :--- |
| `/` & `/operations` | `OperationsPage` | Situational awareness KPI strip (persisted sightings, active worker count), real-time alert feed, multi-camera Leaflet GIS map with stream health markers, recent sightings stream. |
| `/cameras` & `/cameras/:cameraId` | `CamerasPage` | Camera registry table, search & filter by department/status, hardware telemetry (measured FPS, coordinates, azimuth), PostGIS 5 km radius nearby camera discovery (`GET /api/v1/cameras/nearby?lat=...&lon=...`). |
| `/targets` | `TargetsPage` | Active target watchlist management, target registration modal with real-time plate normalization preview (`GJ 01 AB 1234` $\to$ `GJ01AB1234`), priority badges, deactivate actions with transactional rollback. |
| `/alerts` & `/alerts/:alertId` | `AlertsPage` | Incident triage feed, severity filters (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`), unacknowledged toggle, match class badges, one-click operator acknowledgement with optimistic UI & rollback, deep link to route trace. |
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

## 4. WebSocket Evidence Integrity (No Fabricated Data)

When real-time WebSocket events arrive, the frontend enforces strict evidence integrity:
1. **`ALERT_CREATED` Events:** The client reads the incoming `alert_id` and immediately fetches the authoritative database record via `GET /api/v1/alerts/{alert_id}` before prepending to the feed. Missing or unverified fields are never manufactured.
2. **`SIGHTING_CREATED` Events:** The client triggers an authoritative refetch of the database recent sightings query.
3. **Resilience Hub:** Exponential reconnection backoff ($1\text{s}, 2\text{s}, 4\text{s}, 8\text{s}, \dots, \max 30\text{s}$), bidirectional 15s ping/pong keepalive, deduplication by event ID, and bounded 200-event buffers.

---

## 5. Air-Gapped & Self-Contained Offline Operation

- **Local CSS & Fonts:** Remote unpkg and Google Fonts links removed from `index.html`. Leaflet CSS imported locally via `import "leaflet/dist/leaflet.css"`.
- **Offline Vector Overlay:** If tile servers or internet connectivity fail, the GIS map automatically switches to vector mode over a tactical dark grid canvas without crashing or throwing errors.

---

## 6. Verification & Quality Gates

| Verification Step | Command | Result | Status |
| :--- | :--- | :--- | :--- |
| **TypeScript Typecheck** | `npm run typecheck` | `0 errors` (Strict mode verified) | **PASS** |
| **ESLint Standards** | `npm run lint` | `0 errors` across all TypeScript modules | **PASS** |
| **Frontend Test Suite** | `npm test` (Vitest) | `7 test files passed, 26 / 26 tests passed` | **PASS** |
| **Production Build** | `npm run build` | `Built in 5.22s, Bundle: 132.95 kB gzip` | **PASS** |
| **Backend Test Suite** | `pytest` | `214 / 214 tests passed in 22.00s` | **PASS** |
| **Git Tracking** | `git status` | All `.ts` source files tracked; `.gitignore` scoped | **VERIFIED** |

---

## 7. Baseline Status: FROZEN & HACKATHON-ACCEPTANCE COMPLETE

Priority 9B resolves all audit items, ensures 100% clean-clone reproducibility, adheres strictly to P8 database contracts, and provides a polished, operational vehicle intelligence control room.
