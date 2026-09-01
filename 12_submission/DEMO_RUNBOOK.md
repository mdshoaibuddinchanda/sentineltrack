# Demonstration Runbook

This runbook is for a real software demonstration using permitted live camera
sources. The current checkout intentionally has no runtime fixture or sample
data mode. If official sources are unavailable, record that dependency
failure rather than presenting invented detections. The live-runtime evidence
and current blockers are summarized in
[`docs/release/LIVE_RUNTIME_AUDIT.md`](../docs/release/LIVE_RUNTIME_AUDIT.md).

## Preconditions

- Windows workstation with Conda environment `PY312`.
- Docker Desktop if using the container path.
- Repository checked out on the reviewed `launcher-visual-review` branch (or
  the exact commit being demonstrated).
- No production credentials in the repository or recording.
- Confirm the official resource contract and feed permissions before connecting any government stream.
- Organizer-issued restricted-feed password stored only in local `.env` as
  `SENTINEL_ACCESS_PASSWORD`.
- Working DNS resolution for the configured organizer portal
  (`cctv.corp8.cloud` in the current grant) and direct access to the published
  RTSP gateway at `103.250.160.189:8554`.
- The designated registration from the evaluator statement added to the
  watchlist; an empty watchlist cannot generate an alert.

## PostgreSQL option

For the native API path, start the local PostGIS database first:

```powershell
docker run -d --name sentinel-postgres -p 5432:5432 `
  -e POSTGRES_USER=sentinel `
  -e POSTGRES_PASSWORD=sentinel_dev `
  -e POSTGRES_DB=sentinel `
  postgis/postgis:16-3.4
```

Use a disposable local password only. The Compose path starts its own
PostgreSQL/PostGIS service and receives `DATABASE_PASSWORD` from the shell or
`.env`; it does not require a separate database container.

## Path A: full local runtime

The repository-root launcher is the preferred Windows live-runtime path:

```bat
conda activate PY312
cd C:\DR2\sentineltrack
python tools\preflight.py --strict-database
python tools\doctor.py
run.bat --full
```

The full launcher starts the API and dashboard on ports 8000 and 5173, loads
the configured model artifacts, and connects the persisted permitted camera
sources. It prints no temporary credentials; use the configured operator or
administrator account. A camera is shown as online only after the worker has
decoded a real frame.

The launcher message `APPLICATION STARTED` only means that the local processes
started. It is not proof that the external cameras are online. The readiness
gate is the combination of `tools\doctor.py`, fresh decoded frames on the
Cameras page, and an authorized watchlist target.

Do not begin recording unless `tools\doctor.py` ends with `READY FOR LIVE
DEMO`. If it reports `AUTH_REQUIRED`, add the organizer-issued password to
`.env`. If it reports a DNS blocker, repair the workstation/network DNS first;
restarting SentinelTrack cannot repair an operating-system resolver failure.

## Path B: native API plus dashboard

Terminal 1:

```powershell
conda activate PY312
cd C:\DR2\sentineltrack
python tools\preflight.py
python tools\doctor.py
python -m uvicorn 08_backend.app:app --host 0.0.0.0 --port 8000
```

Terminal 2:

```powershell
conda activate PY312
cd C:\DR2\sentineltrack\09_dashboard
npm.cmd run dev
```

Use `http://localhost:5173` for the dashboard and `http://localhost:8000/docs` for API inspection. The preflight/doctor output must be shown if a dependency is unavailable; do not hide a degraded path.

## Path C: container database dependency

```powershell
cd C:\DR2\sentineltrack
$env:DATABASE_PASSWORD = "sentinel_dev" # disposable local value only
docker compose up -d postgres
```

The root Compose file starts PostgreSQL/PostGIS only. Start the native API
and frontend using Path A after the database is healthy. Model files and
permitted camera sources remain local provisioning inputs.

## Six-act walkthrough

1. **Catalogue** — open **Cameras → Overview** to show every permitted camera in one screen; point out the latest authenticated snapshot, online state, FPS, decoded-frame count, freshness, and any real connection error. Select one tile to open its continuous live relay and full telemetry.
2. **Observe** — show a sighting with camera, timestamp, stream epoch, vehicle/plate evidence, and model provenance.
3. **Identify** — search the target/watchlist and show normalized plate matching.
4. **Corroborate** — show chronological sightings and the P7 lower-bound feasibility explanation.
5. **Review safely** — show a partial/no-plate case labeled `ANPR_REID_SUPPORT` or `REID_REVIEW`; explain that ReID cannot override strong ANPR or create an automatic high-severity identity claim.
6. **Investigate/export** — acknowledge an alert, open evidence, show the audit trail, and produce the timestamped output report.

## Official-feed procedure

Before the official run, obtain the organizer-provided catalogue, credentials, allowed network path, and retention instructions. Register stable camera IDs and verify clock/epoch behavior. Run the same six acts on the government feeds and export a report containing vehicle/plate result, camera, timestamp, evidence source, and confidence/provenance. Record only permitted material.

## Troubleshooting

| Symptom | Action |
|---|---|
| Dashboard has no API data | Check API port, CORS, `.env`, and browser network panel; do not replace the live path with invented records. |
| Feed says Access required | Set the organizer-issued `SENTINEL_ACCESS_PASSWORD` in local `.env`, then restart; never put it in Git or a URL. |
| Feed is configured but no live video appears | Check the camera's decoded-frame count and latest error. `source_configured` is metadata; `ONLINE` requires a fresh decoded frame. |
| Need browser video | Use the Cameras page or the authenticated `/api/v1/cameras/{id}/live` relay; upstream feed URLs are never exposed to the browser. |
| Organizer DNS blocked | Verify `Resolve-DnsName cctv.corp8.cloud`; correct the workstation/VPN DNS before restarting. |
| Feed reconnects | Preserve camera ID, increment stream epoch, and show the reset in diagnostics. |
| Database unavailable | Do not fabricate results; record the dependency failure and stop the run. |
| Model/checkpoint unavailable | Keep ANPR/ReID claims disabled and show the graceful-degradation explanation. |
| Government stream unavailable | Stop and report the external feed issue; do not replace it silently with mockups. |

## Teardown

For native processes, stop the two terminals. For Compose:

```powershell
docker compose down
```

Do not add `-v` unless disposable database volumes have been explicitly approved for deletion.
