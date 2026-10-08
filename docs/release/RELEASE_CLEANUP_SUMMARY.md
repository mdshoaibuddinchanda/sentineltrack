# Release cleanup summary

## Scope

This document records the preceding repository presentation cleanup from frozen P12 commit `6cf9bd5421eccc854be02957b064f0319fbeafbb`. The final hygiene pass is on branch `final-repository-polish`, based on release-cleanup commit `7d7aa4be79b9d3b6df4853f3cdc6423b6d0e122b`. P11.5 and P6 algorithms, thresholds, training, and evidence were not reopened.

## Completed

- Established `models/manifest.json` as the only operational model manifest with four selected model entries plus the required P4 dictionary support asset, all with SHA-256 values.
- Promoted the selected P11.5 plate artifact to `models/plate/yolo11s_plate_v2.pt`; P1, P3, P4, and P6 runtime paths are canonical and repository-root resolved.
- Made P6 live in `08_backend/services/analytics_service.py` with strong-plate gating, partial/no-plate fallback, local plate masking coordinates, epoch-safe track keys, and graceful model failure.
- Added worker-level P6 integration tests proving ANPR authority, masking, review-only no-plate behavior, and P5 preservation.
- Added canonical `tools/preflight.py`; promoted the operational schema, doctor, and API benchmark tools to `tools/` and removed the retired P11 compatibility directory.
- Reworked `scripts/setup_models.py` to verify the manifest, use direct verified public downloads, avoid CWD side effects, and report custom/optional artifacts explicitly. Server OCR is optional.
- Consolidated dependencies into root `requirements.txt`/`requirements-dev.txt` plus `requirements/api.txt`, `requirements/analytics.txt`, `requirements/ci.txt`, and optional files. Docker and CI references were updated; Ultralytics `8.3.235` remains the production pin.
- Renamed manual test-like utilities to `validate_*`/`run_*` and preserved their contents/history. No manual utility was deleted.
- Moved historical `configs/model_manifest.yaml` into P11.5 evidence and updated submission references.
- Replaced the root README with a presentation-ready architecture, setup, stage status, safety boundaries, repo tree, model register, testing, and evidence navigation.
- Added `docs/README.md` and the release audit/inventory documents.

## Before/after discovery

| Measure | Before | After |
| --- | ---: | ---: |
| Python files | 309 | 309 plus the release P6 integration test included in the automated test set |
| Automated test files | 78 | 79 |
| Misleading test-like files outside test dirs | 12 | 0 |
| Operational model manifests | 2 competing locations | 1 (`models/manifest.json`) |
| Root split requirement files | 8 | 2 entry points plus structured `requirements/` files |
| Runtime P3 source | old `production/best.pt` default | selected `models/plate/yolo11s_plate_v2.pt` |
| Runtime P1 source | CWD-sensitive `yolo11m.pt` default | `models/vehicle/yolo11m.pt` |
| Live P6 worker integration | absent | conditional, safety-gated integration |

Large datasets, ignored model binaries, `runs/`, caches, and dependency directories were not counted as distributable source. No tracked evidence was deleted.

## Validation record

- `scripts/setup_models.py --verify-only`: passed all four locally provisioned manifest entries.
- `tools/preflight.py`: passed Python, directories, model hashes, and CUDA; returned `PASS WITH WARNINGS` only because local PostgreSQL was unavailable.
- P6 plus worker integration tests: 18 passed.
- Full pytest collection: 351 tests.
- Foundation/P1/P3 validation: 35 passed, 1 skipped; P2/P4 validation: 41 passed.
- Full suite, frontend gates, compile checks, exact commit, and GitHub Actions result are recorded at final handoff after the release commit is pushed.

## Final hygiene pass

- Historical P11.5 scripts moved to `experiments/archive/p11_5/`; experiment configs moved to `experiments/archive/configs/`; provenance metadata moved to `reports/p11_5/provenance/`.
- Historical priority baselines moved to `docs/archive/development-baselines/`; active documentation now starts at `docs/README.md` and the submission package.
- Canonical `models/` now contains the operational manifest, selected P1/P3/P4/P6 assets, and the example manifest only. Optional server OCR and unpromoted YOLO files were moved to `C:\DR2\sentineltrack_archive\models\`.
- Local `runs/` (2,895 files, 1.59 GB) moved intact to `C:\DR2\sentineltrack_archive\runs`; generated catalogues, accessible Python caches, empty local output directories, and one sensitive sample image were removed from the checkout. A small set of empty pytest paths with an OS-level ACL denial is recorded in the final hygiene audit.
- Added `docs/assets/README.md` with screenshot redaction/provenance requirements; no unredacted or fabricated screenshot was added.
