# SentinelTrack High-Level Design

## 1. Purpose and selected challenge architecture

SentinelTrack is a hybrid architecture aligned to the official framework:

- Model 1: central camera registry and GIS foundation.
- Model 2/3-compatible integration: direct catalogue/stream consumption with
  adapter boundaries for heterogeneous departmental VMS systems.
- Selective analytics: vehicle detection, tracking, ANPR, target matching and
  cross-camera investigative intelligence.

It is not a claim that SentinelTrack replaces every departmental VMS or stores
all continuous video centrally. Existing VMS platforms remain authoritative for
their recordings; SentinelTrack consumes permitted feeds and centralizes
metadata, events, alerts and selected evidence.

## 2. Inputs and integration contracts

The official integration guide defines the catalogue as the contract. The
platform should start with:

```text
GET /api/ingest
```

The catalogue provides camera IDs, location, codec, live status, stream
properties and available endpoints. The current supported stream patterns are:

| Use | Endpoint pattern |
|---|---|
| AI inference | `rtsp://<host>:8554/stream/<id>` |
| Browser preview | `http://<host>:8889/stream/<id>/whep` |
| Dashboard/mobile/restricted networks | `http://<host>/live/stream/<id>/index.m3u8` |

The resolver prefers RTSP over TCP for inference, uses HLS as a fallback,
preserves source PTS, and carries `camera_id`, `stream_epoch`, ingest time and
best-estimate UTC event time in each `FramePacket`. Reconnect backoff is bounded
from approximately 2 to 30 seconds in the operational design. A stream
discontinuity, abnormal PTS reset or reconnect increments the stream epoch and
resets per-stream tracking and ReID state so stale identities cannot cross the
boundary.

The design accepts analog cameras through the department's encoder/VMS gateway;
SentinelTrack does not pretend to decode an arbitrary analog signal directly.
Vendor SDKs, ONVIF and other adapters can feed the same normalized catalogue
contract without changing downstream analytics.

## 3. End-to-end processing chain

```text
Camera Registry
  -> Stream Resolver / Ingestion
  -> Vehicle Detection (P1 YOLO11m)
  -> Per-camera ByteTrack (P2)
  -> Vehicle Crop
  -> Plate Detection (P3 YOLO11s)
  -> AABB Plate Crop
  -> PP-OCRv5 Mobile (P4)
  -> 5-frame OCR Consensus
  -> P5 Target Matching / Watchlist / Alerts
  -> Conditional P6 Appearance ReID fallback
  -> Cross-camera Sightings
  -> P7 GIS / Temporal Feasibility
  -> Alert Engine
  -> FastAPI / WebSocket
  -> Control-room Dashboard
```

P6 is conditional and uses the existing P5 `MatchCandidate.reid_score`
contract. Its identity policy is fixed:

| Plate evidence | Decision policy |
|---|---|
| Strong/full plate | ANPR identity dominates; ReID is skipped or diagnostic and cannot override. |
| Partial/degraded plate | Plate evidence is combined with appearance, temporal compatibility and optional P7 feasibility; ReID can support but cannot manufacture an exact identity. |
| No usable plate | Appearance is fallback-only and remains `REVIEW`/`POSSIBLE`; it cannot create an automatic HIGH/CRITICAL alert or exact identity claim. |

When a plate box is available, P6 blurs it before embedding. OCR text is never
passed to the appearance model. Track-level profiles retain the best five
quality crops, aggregate a normalized 576-D vector and are bounded by camera,
stream epoch, TTL and gallery size.

## 4. Runtime layers

### Ingestion and scheduling

`00_foundation` normalizes camera metadata and stream timing. `11_scale_deployment`
provides per-camera bounded queues, stale-frame dropping, fair scheduling,
adaptive base/burst sampling and deterministic camera sharding. The operational
default is base 1 FPS with a 5 FPS burst mode; these are control parameters, not
an 80k-camera capacity measurement.

### Analytics

`08_backend.services.analytics_service.AnalyticsWorker` performs staged batch
inference with P1 vehicle detection and P2–P5 processing. P6 is a bounded
service at the same identity boundary and is invoked only for partial/no-plate
evidence. A model loading failure returns no ReID result and leaves ANPR
operation intact.

### Persistence and events

PostgreSQL/PostGIS stores camera metadata, sightings, targets, alerts,
trajectory runs, route segments and audit records. The event bus and optional
PostgreSQL LISTEN/NOTIFY bridge deliver authoritative alert/sighting events to
the secured WebSocket layer. Database writes use rollback/error handling; the
dashboard never invents authoritative alert fields after a failed fetch.

### API and operator surface

The existing API surface includes:

| Area | Existing interface |
|---|---|
| Health/telemetry | `GET /health`, `GET /ready`, `GET /metrics` |
| Cameras | `GET /api/v1/cameras`, detail, health and nearby search |
| Targets | `POST/GET /api/v1/targets`, `PATCH`, `DELETE` |
| Sightings | `GET /api/v1/sightings`, `GET /api/v1/vehicles/{registration}/history` |
| Alerts | `GET /api/v1/alerts`, detail and `POST /api/v1/alerts/{id}/ack` |
| Routes | `GET /api/v1/routes/{registration}`, `/geojson`, `/summary` |
| Real time | `WS /ws/events`, `WS /ws/alerts`, `WS /ws/sightings` |

All protected mutations follow P10 authentication, CSRF, permission and audit
controls. The exact endpoint permissions are listed in
`docs/security/p10_endpoint_inventory.md`.

## 5. Timing and identity integrity

Raw PTS is stream-local and is never compared directly between cameras. P7
prefers source wall-clock time, can use PTS anchored to a stream start and uses
database persistence time only as a low-quality fallback. Cross-camera segments
use chronological ordering, geodesic lower-bound distance and minimum required
speed. The resulting polyline connects observed camera locations; it is not a
road-level route.

Identity provenance is explicit: `ANPR`, `ANPR_REID_SUPPORT` or `REID_REVIEW`.
Stream epochs are part of tracking/ReID keys. Strong ANPR cannot be overridden,
and a missing ReID model degrades to the existing ANPR path.

## 6. Failure and recovery boundaries

- A camera disconnect triggers bounded reconnect backoff and health state.
- A stale queue frame is dropped rather than allowing unbounded latency.
- A stream epoch reset clears camera-local tracker and ReID identity state.
- A worker can be restarted and reassigned cameras by the supervisor/shard
  layer.
- A database error is visible as degraded readiness and does not become a fake
  successful persistence result.
- A slow WebSocket client receives bounded queue behavior and cannot block
  inference.
- A P6 load/crop failure produces no confident ReID output; P5/ANPR continues.

## 7. Evidence and limits

Measured values, proxy results and planning assumptions are indexed in
[`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md) and
[`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md). No local measurement supports a safe
statewide camera capacity, true cross-camera ReID accuracy or a road-level
route claim.
