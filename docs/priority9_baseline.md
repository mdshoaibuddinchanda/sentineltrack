# Priority 9: Frontend Intelligence & Control Room Dashboard — Baseline Report

## 1. Executive Summary & Architectural Overview

Priority 9 delivers the primary operational user interface for **SentinelTrack**: a high-density, real-time police control room intelligence dashboard. Built with React 18, TypeScript, Vite, Tailwind CSS, and Leaflet, the frontend interfaces directly with the Priority 8 FastAPI backend and WebSocket hub.

The dashboard translates low-level multi-stage computer vision outputs (P1 vehicle detection, P2 tracking, P3 plate detection, P4 OCR consensus, P5 target matching, and P7 spatio-temporal trajectory inference) into an actionable, serious operational cockpit for police operators and evaluators.

---

## 2. Core Functional Views & Pages

| Page Route | Component | Key Operational Capabilities |
| :--- | :--- | :--- |
| `/` | `OperationsPage` | Situational awareness KPI cards, real-time alert feed with sound/toast notification, multi-camera Leaflet GIS map with color-coded stream health markers, recent sightings stream. |
| `/cameras` | `CamerasPage` | Camera registry table, search & filter by department/status, hardware telemetry (measured FPS, coordinates, azimuth), PostGIS 5 km radius nearby camera discovery. |
| `/targets` | `TargetsPage` | Active target watchlist management, target registration modal with real-time plate normalization preview (`GJ 01 AB 1234` $\to$ `GJ01AB1234`), priority badges, deactivate actions. |
| `/alerts` | `AlertsPage` | Incident triage feed, severity filters (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`), match class badges, one-click operator acknowledgement with optimistic UI & rollback, deep link to route trace. |
| `/investigation` | `InvestigationPage` | Plate search, chronological sighting timeline, P7 GeoJSON LineString trajectory visualization, kinematic segment table (lower-bound distance, transit duration, minimum required speed, feasibility classification), physical conflict & ambiguity explanation alerts. |
| `/system` | `SystemPage` | Central API health, Git commit SHA, deep subsystem readiness matrix (PostgreSQL, PostGIS, Camera Registry, Target DB, P1–P5 CV models, P7 Route Engine), live operational telemetry. |

---

## 3. Real-Time WebSocket Hub Integration

The WebSocket hook (`useWebSocket`) provides enterprise-grade resilience:
1. **Topic Subscriptions:** Connects to `/ws/events?topics=*` with real-time routing of `ALERT_CREATED` and `SIGHTING_CREATED` events.
2. **Exponential Reconnection Backoff:** Automatically handles disconnections by retrying at $1\text{s}, 2\text{s}, 4\text{s}, 8\text{s}, \dots, \max 30\text{s}$.
3. **Heartbeat Keepalive:** Sends bidirectional `"ping"` frames every 15s to keep connections alive through proxies and firewalls.
4. **Deduplication:** Maintains an in-memory hash ring of seen event IDs to prevent duplicate alerts from flooding the feed.
5. **Bounded Buffer:** Limits in-memory event queues to the latest 200 items to prevent client-side memory leakage.

---

## 4. GIS Mapping & Trajectory Visualization

- **Leaflet & React-Leaflet:** Zero-cost, vendor-neutral map engine (no paid Google Maps API keys required).
- **Offline Map Resilience:** In air-gapped or disconnected environments where OpenStreetMap tiles fail to load, the dashboard automatically activates vector mode on a tactical dark grid canvas, keeping all camera nodes, sightings, and trajectory polylines 100% interactive.
- **Visual Trajectory Sequence:** Numbered sequence node icons (`1`, `2`, `3`, `4`) with interactive click-to-sync between map popups and the chronological timeline.
- **Kinematic Feasibility Badges:** Segments are color-coded by kinematic feasibility:
  - `FEASIBLE` (emerald): Required speed is plausible for urban/highway conditions.
  - `QUESTIONABLE` (amber): High transit speed requiring highway bypass or expressway traversal.
  - `IMPOSSIBLE SPEED` (rose): Required velocity exceeds physical thresholds, indicating cloned plates or clock skew.
- **Legal & Scientific Honesty:** Prominently displays disclaimers that LineStrings represent chronological camera sightings, not reconstructed road-level turns.

---

## 5. Verification & Test Metrics

### Automated Suite Results
- **TypeScript Typecheck (`npm run typecheck`):**
  - Result: `0 errors` (strict mode verified).
- **Frontend Test Suite (`npm test` / Vitest):**
  - Result: `3 test files passed, 13/13 tests passed` in 55.7s.
  - Coverage: Formatters, API client error envelope parsing, UI badges, MetricCards, OfflineBanner.
- **Production Build (`npm run build`):**
  - Result: Build completed in 4.08s.
  - Bundle sizes: `dist/index.html` (1.29 kB), `dist/assets/index-*.css` (30.1 kB), `dist/assets/index-*.js` (412.1 kB / 119.3 kB gzipped).
- **Backend Canonical Test Suite:**
  - Result: `214 passed in 20.91s` across P0–P5, P7, and P8.

---

## 6. Baseline Status: FROZEN & HACKATHON-READY

Priority 9 fulfills all dashboard requirements, connecting every underlying computer vision and spatio-temporal subsystem into one cohesive, production-grade intelligence application.
