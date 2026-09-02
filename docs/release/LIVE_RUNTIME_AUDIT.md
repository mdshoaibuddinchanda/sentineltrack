# Live Runtime Audit

**Audit date:** 2–3 September 2026

**Repository:** `C:\DR2\sentineltrack`

**Environment:** Conda `PY312`, Python 3.12.12

**Branch:** `launcher-visual-review`

**Audit base commit:** `4a4b57547cb08d04ff98423c8ee4d4f170332df3`

**Current CI:** [latest branch workflow](https://github.com/mdshoaibuddinchanda/sentineltrack/actions/workflows/ci.yml?query=branch%3Alauncher-visual-review)

## Release verdict

The release-candidate software path is internally healthy. The backend,
PostgreSQL/PostGIS registry, analytics pipeline, authenticated camera relay,
frontend, role checks, model files, and production build were exercised
together. No frontend page crash, HTTP 5xx response, horizontal overflow, or
protected-page console error was observed in the final browser audit.

External truth is deliberately kept separate from software readiness:

- The organizer catalogue authenticated and returned 30 cameras in the final
  doctor run.
- Feed delivery is intermittent. In the measured full run, 25 of 30 workers
  decoded at least one real frame; at one synchronized snapshot, 15 had a fresh
  frame and 15 were offline/retrying. Counts naturally changed during the run.
- The authorized watchlist is empty. The software therefore generated no
  target alert and the doctor correctly leaves the live-demo gate blocked until
  an approved registration is entered.
- The organizer catalogue contains location names but no verified latitude or
  longitude. GIS calculations remain unavailable until sourced coordinates are
  supplied; SentinelTrack does not invent them.

## Measured full-stack run

The launcher was started in full mode with the local ignored organizer secret,
the real API role, PostgreSQL/PostGIS, the Vite frontend, all selected models,
and the 30-camera catalogue.

| Check | Measured result |
| --- | --- |
| API readiness | HTTP 200; analytics, registry, database, OCR, plate detection, PostGIS, route engine, stream ingestion, target matching, tracking, and vehicle detection all ready |
| Model state | Vehicle detector, tracker, plate detector, OCR, appearance fallback, and target matcher loaded |
| Camera catalogue | 30 authenticated organizer camera definitions |
| Stream attempts | All 30 workers completed an attempt |
| Cameras decoding at least one frame | 25 of 30 during the bounded audit window |
| Synchronized camera snapshot | 15 fresh/online; 15 offline or in bounded retry |
| Stream telemetry | 18,709 decoded frames; 1,107 sampled frames; 15 reconnects |
| Analytics telemetry | 2,572 vehicle detections; 843 plate inferences; 841 OCR consensus operations |
| Evidence written in that run | 2 real sightings; 0 alerts; 0 dropped pipeline items |
| Latest diagnostic database state | 30 cameras; 8 sightings accumulated across audit runs; 0 watchlist entries; 0 alerts; 0 non-portal camera rows |
| JPEG preview | Valid 92,950-byte JPEG returned from `cam18` |
| Continuous video relay | Authenticated multipart MJPEG response; first 131,072-byte chunk contained real JPEG frame data |

The frontend never receives the organizer password or direct secret-bearing
media URL. It opens the protected application endpoint:

```text
GET /api/v1/cameras/{camera_id}/live
```

The backend relays the latest continuously decoded worker frames. `ONLINE`
requires a fresh frame; a configured source alone cannot produce a green
camera status.

## Stream reliability behavior

- Direct RTSP is used over TCP for inference.
- An authorized HLS URL is retained as fallback when the catalogue session is
  available.
- The current CDN-compatible media user agent is explicit.
- The worker, rather than a hidden inner OpenCV loop, owns reconnect and source
  failover decisions.
- Source opening and first-frame waits are bounded and reported as distinct
  diagnostic codes.
- Reconnect uses bounded backoff; intermittent gaps do not tight-loop.
- Invalid, negative, or non-finite OpenCV timestamps are rejected rather than
  entering tracking time calculations.
- A transient catalogue outage receives bounded startup retries. If a local
  password is configured but the catalogue is temporarily unavailable,
  persisted direct RTSP sources can still start with an explicit stale-catalogue
  diagnostic; no unauthenticated HLS fallback is claimed.
- The operator doctor uses the same bounded catalogue-attempt policy. Its final
  run authenticated 30 cameras with one in-memory session cookie.

These behaviors follow the organizer integration contract and FFmpeg's
documented RTSP/HTTP options; they do not imply that every upstream feed will be
available simultaneously.

## Browser and accessibility audit

A real Chromium session signed in through the actual API and rendered the
following application routes at 1440 × 1000:

1. Dashboard
2. Cameras overview
3. Camera list and live camera detail
4. Watchlist
5. Alerts
6. Find a vehicle / investigation
7. System status
8. User administration
9. Audit log

Observed results:

- no page exceptions or HTTP 5xx responses;
- no `Cannot read properties`, page-display, or authentication-error marker;
- no horizontal overflow on any audited route;
- dark mode and the clearly labelled `Privacy on` state both applied;
- six primary navigation choices only—there is no ambiguous **More** menu;
- readable status badges and plain-language service labels;
- live camera cards show real frames, while failed sources show the actual
  reconnect reason;
- the light-theme camera overview totals use readable foreground colors (the
  final contrast defect found during visual inspection was corrected).

The browser audit account was temporary and removed immediately after the
audit. No demo user or password is stored in the repository.

## Camera registry, GPS, GIS, and VMS readiness

The technical onboarding gap is implemented without fabricating operational
metadata:

- protected manual camera create/update;
- bounded CSV dry-run and apply workflow (maximum 500 rows);
- duplicate and coordinate-provenance validation;
- JSON and CSV gap analysis;
- sanitized GeoJSON export;
- PostGIS area-of-interest coverage planning;
- P7 camera-pair chronological/geodesic lower-bound feasibility;
- organization, source-system, external-ID, onboarding-method, coordinate
  source/accuracy, FOV, azimuth, and coverage-radius fields;
- dynamic worker synchronization when registry sources change;
- OGC API Features and ONVIF Profile T connector implementations;
- environment-only connector secrets and outbound-host allowlists.

The current 30-camera gap snapshot has 30 configured stream sources and zero
verified GPS coordinates. All 30 also need authoritative department,
organization, and azimuth metadata. Two heterogeneous connector definitions are
included but disabled because real department VMS endpoints, allowlists, and
credentials have not been supplied. This is an external integration input, not
something the repository can safely guess.

Relevant standards and primary references:

- [ONVIF Profile T](https://www.onvif.org/profiles/profile-t/)
- [ONVIF Network Interface Specifications](https://www.onvif.org/profiles/specifications/)
- [OGC API — Features](https://ogcapi.ogc.org/features/)
- [OGC API — Connected Systems](https://www.ogc.org/standards/ogc-api-connected-systems/)
- [FFmpeg protocol documentation](https://ffmpeg.org/ffmpeg-protocols.html)
- [Sentinel problem statements](https://sentinel.gujarat.gov.in/problems)
- [Sentinel FAQs](https://sentinel.gujarat.gov.in/faqs)

## Final validation matrix

| Gate | Result |
| --- | --- |
| Full Python suite | **397 passed, 1 skipped** in 56.53 s after direct dependency verification |
| Exact backend CI selection in a clean Python 3.12 virtual environment | **176 passed** in 47.79 s using only the declared CI requirements |
| Frontend Vitest | **63 passed** across 15 files |
| TypeScript | PASS |
| ESLint | PASS |
| Vite production build | PASS; 1,697 modules transformed |
| Python compilation | PASS across application modules and tools |
| Strict preflight | PASS: runtime, five model/support hashes, CUDA GPU, and database |
| Docker Compose parse | PASS |
| Declared Python requirements | PASS; every direct requirement is installed in `PY312` |
| Production npm advisory audit | PASS; 0 known vulnerabilities |
| Runtime doctor | All internal checks and organizer catalogue PASS; watchlist-only external blocker |
| Browser integration audit | PASS across all nine protected/public routes |

Vite reports a non-failing advisory that the main minified JavaScript chunk is
approximately 530 kB. This does not break the local submission demo; route-level
code splitting remains an optional deployment optimization.

## Actual processing path

```text
authorized camera catalogue
  -> RTSP/TCP reader (authorized HLS fallback)
  -> decoded frame + PTS + stream epoch
  -> vehicle detection
  -> per-camera ByteTrack tracking
  -> plate detection and OCR consensus
  -> authorized watchlist matching
  -> conservative conditional appearance fallback
  -> sightings, alerts, route evidence, and audit records
  -> authenticated API/WebSocket/MJPEG relay
  -> operator dashboard
```

## Pre-recording gate

From the repository root:

```powershell
conda activate PY312
Set-Location C:\DR2\sentineltrack
python tools\doctor.py
run.bat --full
```

Before recording, add only the challenge-authorized designated registration
through the protected watchlist workflow. Wait for at least one camera to show
a fresh frame, then open that camera. Do not expose `.env`, the organizer
password, access cookies, or direct credentials in the recording.

The doctor is intentionally strict. A temporary organizer outage or empty
watchlist produces a blocked demo verdict even when the code is healthy.

## Claims not made

- Thirty definitions are not proof of thirty simultaneously reachable feeds.
- Missing GPS is not inferred from location names.
- P7 is chronological lower-bound feasibility, not road-level navigation.
- Appearance-only ReID is review evidence, not an exact police identity claim.
- No true cross-camera ReID accuracy is claimed without labelled identity data.
- No statewide 80,000-camera throughput result is inferred from one laptop.
- Disabled VMS connector templates are not presented as completed vendor
  acceptance tests.
