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
current organizer deployment redirects the catalogue and HLS resources to a
restricted feed portal, so the platform starts by creating an authorized
session. For backward compatibility it first probes the older contract:

```text
GET /api/ingest
```

The current portal deployment returns `404` for that legacy route after
authentication and publishes the live registry at `GET /cameras.json`; this is
the active catalogue used by the audited runtime. The client supports both
routes without hard-coding the camera list. For each
catalogue record (`cam01` through `cam30` in the current grant), the portal
publishes HLS at `https://cctv.corp8.cloud/<id>/index.m3u8` and the direct media
gateway publishes RTSP at `rtsp://103.250.160.189:8554/stream/<id>`.

The catalogue provides camera IDs, location labels, codec, live status, stream
properties and available endpoints. It does not currently provide authoritative
latitude/longitude or department ownership, so those fields remain `UNKNOWN`
until an official GIS/VMS record is imported. The current supported stream
patterns are:

| Use | Endpoint pattern |
|---|---|
| AI inference | `rtsp://103.250.160.189:8554/stream/<id>` over TCP |
| Browser preview | `http://103.250.160.189:8889/stream/<id>/whep` |
| Dashboard/mobile/restricted networks | `https://cctv.corp8.cloud/<id>/index.m3u8` with the organizer session |

The local inference profile uses RTSP-first ordering and forces TCP. It retries
the direct source after a transient failure; the portal HLS path remains the
authenticated remote/browser delivery path and can be selected explicitly for
environments whose decoder supports it. The resolver passes the protected
session directly to FFmpeg (never in a URL or browser),
preserves source PTS, and carries `camera_id`, `stream_epoch`, ingest time and
best-estimate UTC event time in each `FramePacket`. Reconnect backoff is bounded
from approximately 2 to 30 seconds in the operational design. A stream
discontinuity, abnormal PTS reset or reconnect increments the stream epoch and
resets per-stream tracking and ReID state so stale identities cannot cross the
boundary.

The design accepts analog cameras through the department's encoder/VMS gateway;
SentinelTrack does not pretend to decode an arbitrary analog signal directly.
Two heterogeneous integration paths now feed the same normalized registry
contract without changing downstream analytics:

| Organization path | Implemented adapter | Boundary |
|---|---|---|
| GIS/catalogue-oriented department | OGC API Features GeoJSON `FeatureCollection` | Contract tested; real endpoint/token requires department approval |
| Device/VMS-oriented traffic department | ONVIF Profile T Device + Media/Media2 discovery and RTSP profile selection | Contract tested; real device/credentials require department approval |

Manual registration and bounded CSV import use the same validation path. GPS
requires coordinate source and quality; credentials in URLs/metadata are
rejected. Disabled templates are in `configs/vms_connectors.json`, and the full
contract is [`../docs/CAMERA_REGISTRY_GIS_VMS.md`](../docs/CAMERA_REGISTRY_GIS_VMS.md).

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
| Cameras | List/detail/health/nearby, authenticated `/live`, manual create/update, bulk dry-run/apply, gap CSV, and safe GeoJSON |
| VMS integration | Secret-free connector readiness and operator-triggered validate/sync for OGC API Features and ONVIF Profile T |
| GIS planning | Operator AOI coverage estimate plus non-persisting camera-pair lower-bound feasibility check |
| Targets | `POST/GET /api/v1/targets`, `PATCH`, `DELETE` |
| Sightings | `GET /api/v1/sightings`, `GET /api/v1/vehicles/{registration}/history` |
| Alerts | `GET /api/v1/alerts`, detail and `POST /api/v1/alerts/{id}/ack` |
| Routes | `GET /api/v1/routes/{registration}`, `/geojson`, `/summary`, `/report.csv` |
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
- Missing organizer access reports `AUTH_REQUIRED`; it does not launch 30
  endless connection loops or label registry rows online.
- Catalogue DNS failure is reported separately from model/application health.
- A stale queue frame is dropped rather than allowing unbounded latency.
- A stream epoch reset clears camera-local tracker and ReID identity state.
- A worker can be restarted and reassigned cameras by the supervisor/shard
  layer.
- A database error is visible as degraded readiness and does not become a fake
  successful persistence result.
- A slow WebSocket client receives bounded queue behavior and cannot block
  inference.
- A P6 load/crop failure produces no confident ReID output; P5/ANPR continues.
- A VMS discovery failure rolls back the import and reports a secret-free
  connector error; it does not remove the prior camera registry.
- An ONVIF device cannot redirect service discovery to an unapproved host.

## 7. Evidence and limits

Measured values, proxy results and planning assumptions are indexed in
[`EVIDENCE_INVENTORY.md`](EVIDENCE_INVENTORY.md) and
[`MODEL_EVIDENCE.md`](MODEL_EVIDENCE.md). No local measurement supports a safe
statewide camera capacity, true cross-camera ReID accuracy or a road-level
route claim. The current Model 1 data gaps and their owners are recorded in
[`../reports/model1/MODEL1_GAP_ANALYSIS.md`](../reports/model1/MODEL1_GAP_ANALYSIS.md).
