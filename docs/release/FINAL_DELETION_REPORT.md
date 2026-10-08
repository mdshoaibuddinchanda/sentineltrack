# Final deletion and archival report

This report records the final repository-polish actions on branch `final-repository-polish`, starting from `7d7aa4be79b9d3b6df4853f3cdc6423b6d0e122b`.

## Regenerable junk deleted

- 809 `.pyc`/`.pyo` files across the pre- and post-validation sweeps, totaling 6,853,632 bytes.
- 87 `__pycache__/` directories.
- 18 accessible root pytest cache/scratch directories, totaling 126,817 bytes.
- Three generated catalogue JSON snapshots, totaling 41,988 bytes.
- Empty generated `.paddlex-ocr/`, `logs/`, `data/`, `video_images/`, and `weights/` directory trees.
- One duplicate Torch cache file, `C:\Users\SHOAIB-CHANDA\.cache\torch\hub\checkpoints\mobilenet_v3_small-047dcff4.pth`, 10,306,551 bytes, SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`.

Eleven empty root pytest paths and one generated P11.5 report-temp path remain OS-inaccessible (`WinError 5`) and are listed in `FINAL_HYGIENE_AUDIT.md`; they are ignored and not part of the commit.

## Models deleted

No model binary was irreversibly deleted. Unpromoted and optional model files were moved intact to the external archive because historical registry entries still reference them.

## Empty folders removed

Removed accessible empty legacy model subdirectories under `models/plate/`, the old `tools/p11/` directory, `configs/experiments/`, `experiments/p11_5/`, and local generated output directories. Active `tools/p11/` and `tools/p11_5/` no longer exist.

## Legacy tools removed

- `tools/p11/preflight.py` — compatibility wrapper, no remaining references.
- `tools/p11/profile_pipeline.py` — superseded by the authoritative current `tools/profile_pipeline.py`, no remaining references.

## Legacy tools renamed/promoted

- `tools/p11/init_schema.py` → `tools/init_schema.py`
- `tools/p11/doctor.py` → `tools/doctor.py`
- `tools/p11/api_load.py` → `tools/benchmark_api.py`

The promoted schema and doctor tools were corrected from `parents[2]` to `parents[1]` so they resolve the repository root from `tools/`.

## Experiment files archived

- 33 historical P11.5 reproducibility scripts moved to `experiments/archive/p11_5/`.
- The generic experiment runner moved from `tools/experiments/run.py` to `experiments/archive/run.py`.
- Three experiment configuration files moved to `experiments/archive/configs/`.
- P11.5 README and registry moved to `reports/p11_5/provenance/`.
- The 2,895-file, 1.59 GB ignored `runs/` tree moved to `C:\DR2\sentineltrack_archive\runs`.

## Source files deleted (zero-reference proof)

The two retired P11 tool files above were removed only after a working-tree scan returned zero references to `tools/p11` and the active profiler comparison confirmed the top-level version is the current AnalyticsWorker implementation. No numbered subsystem source or automated test was deleted.

## Documentation moved

Nine historical priority/development baselines moved to `docs/archive/development-baselines/`, with the active index updated. Current security, deployment, reproducibility, performance, P6, P11.5, and submission documentation remains in primary locations.

## Local-only clutter removed

- Sensitive plate sample `video_images/car-wbs-MH03AR5549_00000.jpg`, 2,708,918 bytes, SHA-256 `75a3933904200f80e22f640dd37e947d7428937877306623cecc46086b7782c6`, was inspected and deleted rather than committed or exported.
- Seven root/unpromoted YOLO downloads were moved to `C:\DR2\sentineltrack_archive\models\unpromoted`.
- Optional PP-OCRv5 Server files were moved to `C:\DR2\sentineltrack_archive\models\ocr_optional`.
- No screenshot was fabricated; `docs/assets/README.md` documents the required redaction/provenance process.
