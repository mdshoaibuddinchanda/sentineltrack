# Live Runtime Audit

**Audit date:** 1 September 2026
**Repository:** `C:\DR2\sentineltrack`
**Environment:** Conda `PY312`, Python 3.12
**Branch under review:** `launcher-visual-review`
**Verified commit:** `f09bfc42c8894b940829a59aae23815a9211c801`
**GitHub Actions:** [run 33501256138](https://github.com/mdshoaibuddinchanda/sentineltrack/actions/runs/33501256138) — successful

## Executive result

The software path for authenticated catalogue ingestion, protected HLS/RTSP
opening, decoded-frame health, continuous browser preview, and staged analytics
is implemented and locally testable. The organizer credential is now configured
only in the local ignored `.env`; the current portal catalogue was authenticated,
30 official sources were registered, and a clean runtime settled all 30 workers
to `ONLINE` with decoded frames.

The workstation is still not submission-ready for a designated-vehicle alert
until the challenge-authorized registration is added to the watchlist. The
application does not invent that target or fabricate alerts.

## Official operating contract

The public challenge pages describe a registry/GIS foundation, approximately 30
or more distributed simulated feeds, a designated vehicle, timestamped camera
movement history, a working-software demonstration, and an output report. The
public resource guide describes the catalogue and the RTSP, WHEP, and HLS
delivery patterns.

Primary references:

- [Problems](https://sentinel.gujarat.gov.in/problems)
- [FAQs](https://sentinel.gujarat.gov.in/faqs)
- [Resource and integration guide](https://sentinel.gujarat.gov.in/resource)
- [Phases and prizes](https://sentinel.gujarat.gov.in/phases)

The current portal redirects catalogue/media requests to a protected
`cctv.corp8.cloud` session. After authentication, the legacy `/api/ingest` route
returns `404` in the current deployment; the live registry is available at
`/cameras.json`. Each `cam01`–`cam30` source has an authenticated HLS playlist at
`/<id>/index.m3u8` and a direct RTSP/TCP inference endpoint at
`rtsp://103.250.160.189:8554/stream/<id>`.

## Local evidence at audit time

| Check | Result | Meaning |
| --- | --- | --- |
| Python | PASS — 3.12.12 | Matches the `PY312` runtime family. |
| OpenCV | PASS — 4.11.0 | Available to the stream and image paths. |
| PyTorch | PASS — 2.5.1+cu121 | Available for vehicle and appearance inference. |
| ONNX Runtime | PASS — 1.24.2 | Available for the selected OCR path. |
| GPU | PASS — NVIDIA RTX 3050 Laptop GPU | CUDA 12.1 is visible locally. |
| Model artifacts | PASS — five verified support/model SHA artifacts | Paths are checked against the manifest. |
| PostgreSQL/PostGIS | PASS — PostGIS 3.5 | Database dependency is available. |
| Camera registry | PASS — 30 `camNN` camera records | Current organizer IDs remain after stale numeric rows were removed. |
| Watchlist | BLOCKED — 0 entries | A designated authorized vehicle has not been added. |
| Catalogue authentication | PASS — 30 cameras; one in-memory session cookie | Current organizer password accepted; no secret is persisted in Git. |
| Decoded camera frames | PASS — 30/30 workers `ONLINE` after startup settle | Direct RTSP/TCP opened and decoded current frames. |
| Frontend build | PASS | Dashboard bundle is available. |
| Security/RBAC | PASS | Authentication and role boundaries remain tested. |

The camera registry contains 30 source definitions, but it is not proof of
connectivity. The records currently have textual location values in their raw
catalogue metadata, while latitude, longitude, department, and some codec or
resolution fields are missing. The UI displays missing geographic values as
`UNKNOWN`; it does not invent coordinates.

## What was corrected

| Problem observed | Correction |
| --- | --- |
| Registry rows appeared to be online without decoded video | `ONLINE` now requires a fresh decoded frame from the current worker. |
| Feed attempts repeated for a long time without a useful explanation | Catalogue authentication, DNS, and source failures receive explicit status codes and bounded recovery. |
| Browser received only a refreshed snapshot | The backend exposes an authenticated continuous MJPEG relay backed by the worker frame. |
| Protected media needed the same session as the catalogue | The in-memory catalogue session is passed to the media reader without exposing credentials in URLs or the browser. |
| HLS/RTSP source choice was unreliable | The local inference profile uses direct RTSP/TCP first and retries that source after a transient failure; authenticated HLS remains the remote/browser path. |
| Scheduler could dispatch a camera twice | Supervisor dispatch is now exactly once per scheduled camera cycle. |
| Dashboard crashed on missing coordinates or undefined values | Nullable coordinate and metric rendering now has explicit fallbacks. |
| Stored alerts disappeared whenever the current stream stopped | Historical persisted evidence remains visible and is labelled historical; it is not presented as current live activity. |
| Demo/sample records made the operational view misleading | Operational database rows were cleaned; 30 camera definitions remain, while watchlist, sightings, matches, alerts, route runs, and health-event rows are zero. |
| Invalid OCR strings could become targets | Indian registration grammar and evidence gates reject signage/noise while preserving valid partial/degraded candidates for review. |
| Route output lacked useful human-readable location context | Catalogue location labels flow into timeline, GeoJSON properties, and authenticated CSV reports. |

## Actual processing path

```text
official catalogue
  -> authorized session
  -> RTSP/TCP reader (authenticated HLS is available for remote/browser delivery)
  -> decoded FramePacket with PTS and stream epoch
  -> vehicle detector
  -> ByteTrack per camera/epoch
  -> plate detector and OCR consensus
  -> authorized watchlist matching
  -> conditional appearance fallback
  -> sightings, alerts, route evidence, audit
  -> API/WebSocket
  -> dashboard and continuous live relay
```

The model process is conditional. A quiet GPU and zero detection counters are
expected while the source is not authenticated or is not producing decoded
frames. The runtime must show decoded-frame evidence before claiming that model
inference is active.

## Pre-recording gate

Run these commands from the repository root:

```powershell
conda activate PY312
Set-Location C:\DR2\sentineltrack
python tools\doctor.py
```

Recording may begin only when the doctor reports no internal failures, the
Cameras page shows fresh decoded frames, and the designated authorized target
is present in the watchlist. The current local credential is already present;
never print it or place it in Git. A fresh workstation should set:

```dotenv
SENTINEL_HOST=https://cctv.corp8.cloud
SENTINEL_ACCESS_PASSWORD=<organizer-issued-password>
```

Never commit this file, include the password in a URL, or show it in a video.

The full run is:

```powershell
python tools\doctor.py
run.bat --full
```

On the audited workstation, `tools\doctor.py` passes runtime, model manifest,
database/PostGIS, organizer DNS, catalogue authentication, RBAC, and dashboard
checks. It reports one intentional blocker: the watchlist is empty. During the
full run, the API became healthy on port 8000, the Vite dashboard became
reachable on port 5173, and the camera registry reported 30 `ONLINE` sources
after workers completed their initial RTSP/TCP connects.

The dashboard is served at `http://127.0.0.1:5173`; the API is served at
`http://127.0.0.1:8000`. A live camera relay is available through the
authenticated application route:

```text
GET /api/v1/cameras/{camera_id}/live
```

## Validation evidence

The final local Python suite completed with **372 passed and 1 skipped**. The
exact GitHub backend command completed with **116 passed**. The frontend suite
completed with **53 passed** across 13 files; TypeScript typecheck, ESLint, and
the production Vite build also passed. The Python suite includes stream
recovery, catalogue authentication, worker integration, API health, route
reports, security, WebSocket isolation, and P6 safety contracts.

GitHub Actions run `33501256138` completed successfully for the verified commit
listed above. It ran the backend security/scale contract gate and the frontend
typecheck, lint, test, and build gate. No local result is treated as a
substitute for that remote check.

## Remaining external inputs

- Organizer-issued feed password and permitted network/VPN access.
- The designated challenge vehicle registration, entered through the protected
  watchlist workflow.
- Verified latitude/longitude and department metadata if the organizer requires
  GIS distance or department filtering for the demo.
- Final portal-only team, upload, and sharing fields.

## Claims this audit does not make

- The 30 camera definitions do not prove that all 30 feeds are reachable.
- No live government frames are claimed until authentication and decoding are
  observed.
- No statewide 80,000-camera capacity measurement is claimed.
- No true cross-camera ReID accuracy is claimed because labelled vehicle-ID
  ground truth is unavailable locally.
- P7 is chronological lower-bound feasibility, not road-level routing.
