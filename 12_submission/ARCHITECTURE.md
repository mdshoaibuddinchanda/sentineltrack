# SentinelTrack Architecture Communication Guide

## Design principles

1. Registry-first: camera identity, ownership, location, stream metadata and
   health are normalized before analytics.
2. Adapter-based: departmental VMS differences stop at a documented boundary.
3. Locality-aware: ingest and analytics sit near regional/VMS networks where
   possible; central services receive events and selected evidence.
4. Evidence-preserving: source PTS, UTC provenance, model hashes, alert reasons
   and audit events travel with decisions.
5. Human-supervised identity: ANPR is authoritative when strong; appearance is
   conservative support/review evidence.
6. Bounded operations: queues, batches, caches, gallery size, TTL and route
   lookback are finite and observable.
7. Graceful degradation: loss of a camera, GPU, worker, database replica or
   dashboard connection has an explicit operating mode.

## Logical component map

| Layer | Responsibility | Repository evidence |
|---|---|---|
| Source/VMS | Government and permitted public-facing feeds | Official catalogue plus contract-tested OGC API Features and ONVIF Profile T adapters |
| Registry/GIS | Camera metadata, provenance, manual/CSV onboarding, gap/GeoJSON exports, health | `00_foundation/`, `07_route_engine/`, `docs/CAMERA_REGISTRY_GIS_VMS.md` |
| Ingestion | RTSP/TCP, HLS fallback, PTS and epoch management | `00_foundation/streams/` |
| Scheduling | Sampling, burst mode, queues, sharding and stale drops | `11_scale_deployment/` |
| Vision | P1 vehicle detection, P2 tracking, P3 plate detection | `01_vehicle_detection/`, `02_tracking/`, `03_plate_detection/` |
| Recognition | AABB crop, PP-OCRv5 Mobile and temporal consensus | `04_plate_ocr/` |
| Identity | P5 watchlist scoring plus P6 appearance fallback | `05_target_matching/`, `06_vehicle_reid/` |
| Investigation | Chronological trajectory, pair feasibility and bounded planning coverage | `07_route_engine/`, `08_backend/services/camera_service.py` |
| Control plane | FastAPI, WebSocket, event bus and persistence | `08_backend/` |
| Operator UI | Cameras, targets, alerts, investigation and readiness | `09_dashboard/` |
| Trust layer | Auth, RBAC, CSRF, audit and rate limits | `10_security/`, `docs/security/` |

## Deployment modes

### Sandbox / evaluator mode

One API, one database, one analytics worker and the React dashboard can run on
one host. The release launcher uses persisted records and configured permitted
sources; it does not insert dashboard fixtures or synthetic alerts.

### Pilot mode

Regional ingestion gateways connect to departmental VMS systems. GPU analytics
workers are assigned camera shards. PostgreSQL/PostGIS is authoritative for
metadata and events; object storage is used only for selected evidence where
policy permits.

### Statewide concept

State command services provide registry, policy, cross-region search and
operations. Zones/ranges and districts own ingestion/analytics fault domains.
Regional clusters forward metadata, alerts and selected evidence rather than
all full-resolution continuous video. The 80k plan is scenario-based and
explicitly not a measured capacity claim.

## Decision provenance

Every operator-visible identity should be explainable through:

```text
source camera + stream epoch + track
  -> crop/plate/OCR evidence
  -> P5 match class and corroboration
  -> optional P6 reid_score and temporal/route evidence
  -> P7 trajectory/feasibility
  -> alert severity, provenance and audit event
```

The system avoids an appearance-only police identity claim. P6 is a fallback
signal, never an authority above a strong plate.

Camera-location provenance follows the same evidence principle. A textual
location label is useful to an operator but is not promoted to WGS84 geometry.
Only supplied coordinates with an explicit source enter PostGIS route and
coverage calculations. Current gaps are exported rather than hidden.

## Diagram index

- [`diagrams/A_end_to_end_architecture.mmd`](diagrams/A_end_to_end_architecture.mmd)
- [`diagrams/B_realtime_inference_flow.mmd`](diagrams/B_realtime_inference_flow.mmd)
- [`diagrams/C_regional_deployment.mmd`](diagrams/C_regional_deployment.mmd)
- [`diagrams/D_80k_hierarchical_deployment.mmd`](diagrams/D_80k_hierarchical_deployment.mmd)
- [`diagrams/E_ha_dr.mmd`](diagrams/E_ha_dr.mmd)
- [`diagrams/F_alert_investigation_workflow.mmd`](diagrams/F_alert_investigation_workflow.mmd)
- [`diagrams/G_identity_fusion.mmd`](diagrams/G_identity_fusion.mmd)

These Mermaid files are the canonical diagram sources. A local Mermaid renderer
was not assumed; SVG/PNG exports should be produced by the submission owner
with `mmdc` or the organizer's document tooling if a binary deck requires them.
