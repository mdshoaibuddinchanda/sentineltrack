# Final Repository Hygiene Audit

## Safety record

- Branch: `final-repository-polish`
- Starting branch: `release-cleanup`
- Starting commit: `7d7aa4be79b9d3b6df4853f3cdc6423b6d0e122b`
- Baseline worktree: clean apart from inaccessible local pytest cache directories reported by Git's scanner; no tracked changes were present.
- Scope: local artifact cleanup, active-tool promotion, historical experiment archiving, configuration/documentation organization, and release validation.

This audit records every material move, deletion, or retention decision made during the final polish. Generated caches and local model/output artifacts are not part of the Git release. Historical evidence is retained in the repository's reports or in the external local archive `C:\\DR2\\sentineltrack_archive` when it is not needed at runtime.

## Local-only cleanup ledger

| Item | Before | Action | Result |
| --- | ---: | --- | --- |
| `runs/` | 2,895 files / 1,594,837,295 bytes | Moved intact | `C:\\DR2\\sentineltrack_archive\\runs` |
| Root YOLO11/YOLO26 downloads and `weights/yolo26n.pt` | 7 files / 186,733,651 bytes | Moved intact | `C:\\DR2\\sentineltrack_archive\\models\\unpromoted` |
| Optional PP-OCRv5 Server ONNX + dictionary | 2 files / 84,579,517 bytes | Moved intact | `C:\\DR2\\sentineltrack_archive\\models\\ocr_optional` |
| Generated catalogue snapshots | 3 files / 41,988 bytes | Deleted exactly | `data/` became empty and was removed |
| Python bytecode across pre- and post-validation sweeps | 809 files / 6,853,632 bytes | Deleted exactly | 87 `__pycache__/` directories removed |
| Accessible root pytest caches | 18 directories / 126,817 bytes | Removed | Regenerable |
| Exposed sample image | 1 file / 2,708,918 bytes | Deleted after inspection | Registration plate was visible; not referenced by release |
| Empty Paddle OCR cache, logs, video sample, and weights directories | 0-byte generated directories | Removed | No source or evidence content |
| Duplicate Torch ReID cache | 1 file / 10,306,551 bytes | Deleted after SHA-256 verification | Canonical `models/reid/` copy remains |

The root YOLO hashes were recorded before archival: YOLO11l `9ebd0e09…`, YOLO11m `d5ffc1a6…`, YOLO11n `0ebbc80d…`, YOLO11s-OBB `43fa6310…`, YOLO11s `85a76fe8…`, YOLO26m `401cea9a…`, and YOLO26n `9b09cc8b…`. The optional server OCR hashes were recorded as PP-OCRv5 Server `13d0dda2…` and dictionary `d1979e9f…`. Full canonical model hashes remain in `models/manifest.json` and `docs/release/MODEL_INVENTORY.md`.

## Active repository boundary

- `models/` contains the operational manifest, example manifest, and selected P1/P3/P4/P6 runtime assets only; empty legacy model subdirectories were removed.
- `configs/` contains live runtime YAML only. Historical experiment configurations are under `experiments/archive/configs/`.
- `tools/` contains active preflight, doctor, schema, benchmark, validation, and profiling utilities. There is no active `tools/p11/` or `tools/p11_5/`.
- Historical P11.5 reproducibility scripts are under `experiments/archive/p11_5/`; provenance metadata is under `reports/p11_5/provenance/`.
- Historical priority documents are under `docs/archive/development-baselines/`; `docs/README.md` leads with current runtime, evidence, security, and submission guidance.
- `docs/assets/README.md` defines the redacted screenshot contract. No unredacted or fabricated image was added.

## Reference and source checks

- Working-tree scan found zero references to `tools/p11`, `tools/p11_5`, `configs/experiments`, or `experiments/p11_5` after path updates.
- The active profiler is `tools/profile_pipeline.py`; the obsolete P11 copy was removed.
- `tools/doctor.py` and `tools/init_schema.py` were updated for their promoted location and now resolve the repository root correctly.
- No tracked tests, source datasets, model manifest, security evidence, or authoritative reports were deleted.

## OS-level exception

The following eleven empty root paths are visible to Git's scanner but deny enumeration/removal to the execution account (`WinError 5`):

```text
.pytest_cache_local
.pytest_cache_p115
.pytest_cache_p6_relevant
.pytest_cache_p6_unit
.pytest_cache_p6_unit2
.pytest_tmp_final
.pytest_tmp_local
.pytest_tmp_p115
.pytest_tmp_p115c
.pytest_tmp_p6_full
.pytest_tmp_release_run
```

The generated `reports/p11_5/_pytest_tmp_final/` path has the same denial. No files could be enumerated from these paths, and they are ignored/untracked. They do not enter the Git release; manual deletion by the workspace owner or an administrator is the only remaining local action.

## Validation record

- `scripts/setup_models.py --verify-only`: passed all five manifest entries.
- `tools/preflight.py`: passed Python 3.12.12, required directories, model hashes, and CUDA on the NVIDIA GeForce RTX 3050 Laptop GPU; PostgreSQL was unavailable locally, so status was `PASS WITH WARNINGS`.
- `tools/doctor.py`: all mandatory diagnostics passed, including OpenCV/PyAV, PyTorch/ONNX, security, scale, and frontend asset checks.
- Full collection: 351 tests collected.
- Archived-tool, P6, worker-integration, and CI-contract tests: 30 passed.
- P0/P1/P3 regression group: 35 passed, 1 skipped. P2/P4 regression group: 41 passed.
- Frontend: typecheck passed, lint passed, 12 Vitest files / 48 tests passed, and production build passed.
- `docker compose config`: passed. `nginx` is not installed in this local Windows environment, so no native Nginx syntax check was available.
- The complete local suite and the exact CI backend scope were attempted with `--timeout=30`; both stopped at PostgreSQL-backed tests because no local database was listening. The prior exact release-cleanup commit was green on GitHub; the final branch's exact commit must be checked after push.

The release gate is based on the pushed commit and its GitHub Actions result, not on ignored local artifacts.
