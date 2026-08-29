# Demonstration Runbook

This runbook is for a real software demonstration. The deterministic dashboard mode is a reproducible fixture for the interface and workflow; it must be labeled as demo data. It is not a substitute for the official government-feed run.

## Preconditions

- Windows workstation with Conda environment `PY312`.
- Docker Desktop if using the container path.
- Repository checked out at the final submission commit.
- No production credentials in the repository or recording.
- Confirm the official resource contract and feed permissions before connecting any government stream.

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

## Path A: deterministic local dashboard

```powershell
conda activate PY312
cd C:\DR2\sentineltrack\09_dashboard
$env:VITE_DEMO_MODE = "true"
npm.cmd run dev
```

Open `http://localhost:5173`. Keep the visible `DEMO: ON` indicator in the recording. Use the seeded camera, target, alert, sighting, and route fixtures; show a target such as `GJ01AB1234`, but state that the data is deterministic demo data.

The fixture source is `09_dashboard/src/utils/demoData.ts`. Path A requires no
database seed process; enabling `VITE_DEMO_MODE=true` selects the source-controlled
fixtures and the dashboard displays the demo indicator.

## Path B: native API plus dashboard

Terminal 1:

```powershell
conda activate PY312
cd C:\DR2\sentineltrack
python tools\p11\preflight.py
python tools\p11\doctor.py
python -m uvicorn 08_backend.app:app --host 0.0.0.0 --port 8000
```

Terminal 2:

```powershell
conda activate PY312
cd C:\DR2\sentineltrack\09_dashboard
npm.cmd run dev
```

Use `http://localhost:5173` for the dashboard and `http://localhost:8000/docs` for API inspection. The preflight/doctor output must be shown if a dependency is unavailable; do not hide a degraded path.

## Path C: container control-plane demo

```powershell
cd C:\DR2\sentineltrack
$env:DATABASE_PASSWORD = "sentinel_dev" # disposable local demo value only
docker compose -f deploy\docker-compose.demo.yml up --build
```

The compose file starts PostgreSQL/PostGIS, the API, and the frontend. Verify the health endpoints and open the published dashboard port shown by Compose. This path demonstrates the packaged control plane. Confirm model files and analytics dependencies separately before claiming a live inference result; the deterministic dashboard remains the safe fallback. Replace the disposable local password with an approved secret before any shared deployment.

## Six-act walkthrough

1. **Catalogue** — show cameras, department/location metadata, and stream health.
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
| Dashboard has no API data | Check API port, CORS, `.env`, and browser network panel; use demo mode for the UI walkthrough. |
| Feed reconnects | Preserve camera ID, increment stream epoch, and show the reset in diagnostics. |
| Database unavailable | Do not fabricate results; use the deterministic fixture path and record the dependency failure. |
| Model/checkpoint unavailable | Keep ANPR/ReID claims disabled and show the graceful-degradation explanation. |
| Government stream unavailable | Stop and report the external feed issue; do not replace it silently with mockups. |

## Teardown

For native processes, stop the two terminals. For Compose:

```powershell
docker compose -f deploy\docker-compose.demo.yml down
```

Do not add `-v` unless disposable database volumes have been explicitly approved for deletion.
