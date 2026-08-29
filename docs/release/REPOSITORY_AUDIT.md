# SentinelTrack repository audit

Audit performed on branch `release-cleanup`, from frozen P12 baseline commit `6cf9bd5421eccc854be02957b064f0319fbeafbb`. This document describes the checkout as it exists locally; ignored datasets, model binaries, caches, and generated runs are not assumed to be present on GitHub.

## Inventory summary

| Area | Observed local inventory | Release treatment |
| --- | ---: | --- |
| Python source files | 309 before cleanup | Numbered subsystem code retained |
| Automated pytest files | 78 before cleanup; 79 after P6 integration tests | Kept under configured test paths |
| Test-like files outside test directories | 12 before cleanup; 0 after cleanup | Renamed to `validate_*` or `run_*` |
| `datasets/` files | 429,608 | Ignored/local; provenance summarized, not committed |
| `runs/` files | 2,893 | Ignored experiment/evidence output; never runtime source |
| tracked `reports/` files | 278 | Evidence retained |
| model/checkpoint artifacts found | 74 | Selected runtime set separated from historical/experimental files |
| `09_dashboard/` visible files | 13,480 including installed dependency material | Source/package lock retained; `node_modules` ignored |

The broader local scan found 446,673 visible files after excluding Git internals, Python caches, temporary pytest directories, and dashboard `node_modules`. The large count is data/dependency volume, not application source.

## Top-level structure

The numbered implementation remains intact: `00_foundation` through `12_submission`. Supporting areas are `configs`, `data`, `datasets`, `deploy`, `docs`, `experiments`, `logs`, `models`, `reports`, `runs`, `scripts`, `tests`, `tools`, `video_images`, and `weights`.

Tracked root control files include `.env.example`, `.gitignore`, `pytest.ini`, `constraints-ci.txt`, `docker-compose.yml`, the two canonical root requirement entry points, and the GitHub workflow. The operational model manifest is `models/manifest.json`; historical model-selection evidence is `reports/p11_5/model_manifest_evidence.yaml`.

## Tracked versus ignored

- Tracked: source, tests, configuration, documentation, reports, workflow, Docker definitions, package lock, and operational manifest.
- Ignored: `.env`, datasets, raw media, model binaries, `runs/`, frontend build/dependency output, logs, caches, and generated image/video files.
- A local artifact being present under `models/` or `runs/` does not mean it is distributed by GitHub. The model inventory records this distinction explicitly.

## Suspicious or misleading artifact decisions

| Artifact class | Decision | Reason |
| --- | --- | --- |
| Root YOLO downloads | Archive locally if present | Prevent CWD ambiguity; canonical P1 path is under `models/vehicle/` |
| `models/plate/production/best.pt` and baseline duplicate | Archive locally if present | Superseded by selected P11.5 clean candidate; no evidence deletion |
| Selected P11.5 plate run | Promote a copy to canonical `models/plate/yolo11s_plate_v2.pt` | Runtime must not depend on ignored `runs/` |
| `runs/mlflow/` and P11.5 runs | Keep as ignored provenance/experiment output | Historical evidence; not production inputs |
| Python/test caches | Ignore and exclude from inventory conclusions | Regenerable and not application source |
| Manual `test_*.py` utilities | Rename to `validate_*`/`run_*` | Prevent pytest discovery confusion without deleting utility behavior |
| Root split requirement files | Consolidate under `requirements/` | One clear production/dev/CI/optional dependency layout |
| `configs/model_manifest.yaml` | Move to P11.5 evidence | Avoid two competing operational manifests |

No tracked evidence, test, dataset manifest, or historical report was deleted. The cleanup is a naming, source-of-truth, and documentation pass.

## Test discovery audit

`pytest.ini` intentionally limits `testpaths` to numbered subsystem test directories and `tests/`, and excludes `scripts`, `reports`, `datasets`, `models`, `.git`, and `.pytest_cache`. The manual utilities formerly named `test_stream.py`, `test_image.py`, `test_track.py`, `test_crop.py`, `test_watchlist.py`, `test_match.py`, `test_fp16_parity.py`, and `soak_test.py` are now named according to their actual roles. Automated tests remain unchanged except for the new worker-level P6 contract coverage.

## Release interpretation

The repository is suitable for submission when the exact pushed commit has green GitHub Actions. Local model binaries and the large dataset are provisioning inputs, not hidden claims about what the public repository distributes.
