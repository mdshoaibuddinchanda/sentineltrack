# SentinelTrack Testing and Workspace Guide

This repository contains maintained source code, automated tests, operational tools, archived experiments, and locally generated caches. They have different purposes and should not be treated as interchangeable.

## Start here

Use the `PY312` Conda environment for backend work:

```powershell
conda activate PY312
python --version
```

The repository is organized as numbered implementation stages:

| Area | Purpose | Test location |
| --- | --- | --- |
| `00_foundation` | stream readers, catalogue, registry | `00_foundation/tests/` |
| `01_vehicle_detection` | vehicle detector and detection pipeline | `01_vehicle_detection/tests/` |
| `02_tracking` | ByteTrack-style tracking and track models | `02_tracking/tests/` |
| `03_plate_detection` | plate detector, cropper, quality checks | `03_plate_detection/tests/` |
| `04_plate_ocr` | OCR preprocessing, recognition, normalization, voting | `04_plate_ocr/tests/` |
| `05_target_matching` | watchlist matching, scoring, alerts, history | `05_target_matching/tests/` |
| `06_vehicle_reid` | conservative vehicle-appearance fallback | `tests/test_p6_vehicle_reid.py` |
| `07_route_engine` | chronological route and travel-feasibility evidence | `07_route_engine/tests/` |
| `08_backend` | API, services, workers, lifecycle | `08_backend/tests/` |
| `09_dashboard` | frontend application | `09_dashboard/src/tests/` |
| `10_security` | authentication, authorization, audit, abuse controls | `10_security/tests/` |
| `11_scale_deployment` | capacity, sharding, scheduling, supervision, health, resource monitoring | `11_scale_deployment/tests/` |
| `12_submission` | final hackathon package and runbooks | documentation, not runtime tests |

The root `tests/` directory contains cross-stage contracts and integration checks. It is intentionally small and should remain separate from subsystem tests.

## What the Python files mean

- Python files inside a `tests/` directory, plus root `tests/`, are automated tests. Keep them.
- Implementation Python files outside `tests/` are runtime modules.
- `benchmark*.py` measures performance; it does not normally belong in the default test run.
- `validate_*.py` and `run_*.py` are explicit operational or manual validation tools. Run them only when their input data and purpose are clear.
- `experiments/archive/` contains historical P11.5 and baseline work for provenance. It is not part of the normal runtime path.
- `tools/` contains current operational tools. The P11.5 experiment scripts are intentionally under `experiments/archive/p11_5/`.

## The scale-deployment folder

`11_scale_deployment/` is useful and active; it is not a leftover experiment. Backend lifecycle and analytics code import it directly, `tools/doctor.py` checks it, and CI runs its tests.

Its responsibilities are deliberately bounded:

- `capacity.py` and `config.py`: capacity and scale configuration.
- `scheduler.py`: fair stream scheduling.
- `shard.py`: deterministic camera-to-shard assignment.
- `supervisor.py`: stream-worker supervision.
- `resource_monitor.py`: resource health and pressure signals.
- `health.py` and `event_bridge.py`: operational health and event integration.
- `profiling.py`: bounded profiling support.
- `tests/`: regression and integration coverage for these behaviors.

This folder does not claim to provide road-level routing or prove 80,000-camera performance. Those limitations remain documented in the P7 and submission materials.

## Recommended checks

Fast backend smoke checks:

```powershell
python -m pytest 11_scale_deployment/tests/ -q
python -m pytest tests/ -q
```

The backend portion of GitHub Actions runs the security and scale gates:

```powershell
python -m pytest 10_security/tests/ 11_scale_deployment/tests/ tests/test_ci_contract.py -v --timeout=30
```

Frontend checks run from `09_dashboard/`:

```powershell
npm ci
npm run typecheck
npm run lint
npx vitest run
npm run build
```

## Caches and generated files

These are disposable and ignored by Git:

- `__pycache__/`, `*.pyc`, and `*.pyo`
- `.pytest_cache*`, `.coverage*`, `.mypy_cache/`, `.ruff_cache/`, and `htmlcov/`
- frontend `node_modules/`, `dist/`, and `.vite/`
- local logs, scratch data, MLflow output, runs, and downloaded model/data artifacts

They may reappear after running Python, pytest, or frontend commands. Their presence is not a source-code change. Some old root `.pytest_*` directories are OS-locked on the local Windows machine; they are ignored cache residue and are not tracked or used by the application.

## Safe cleanup rule

Do not delete a Python file merely because its name contains `test`. First check whether it is under a test directory, referenced by CI, or used as an explicit validation tool. Delete only confirmed generated output or an empty/untracked directory.
