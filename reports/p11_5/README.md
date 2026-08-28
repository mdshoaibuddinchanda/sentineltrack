# SentinelTrack P11.5 evidence pack

This directory contains the isolated P11.5 audit, baseline evidence, derivative
dataset reports, profile resolution, and benchmark outputs. The work preserves
the existing production modules and the frozen `datasets/plate_detection` and
`datasets/plate_ocr` corpora.

Measured artifacts are labelled `PASS` or `MEASURED`. Work that needs a missing
ground-truth set, a trained model, or a target cloud machine is labelled
`NOT_EVALUATED`, `DERIVATIVE_READY_NOT_TRAINED`, or `UNAVAILABLE`; these states
are intentional and must not be read as performance claims.

Key entry points:

- `DATASET_REPORT.md` — source inventory, file structure, duplicate/leakage findings, and V2 counts.
- `MODEL_REPORT.md` — detector evidence and model-artifact manifest.
- `OCR_REPORT.md` — fresh mobile/server OCR baseline comparison.
- `TEMPORAL_REPORT.md` — temporal implementation and evaluation blocker.
- `CAPACITY_DELTA.md` — local measured latency and capacity limitations.
- `FINAL_REPORT.md` — the P11.5 requested final format with open blockers.
- `html/report.html` — self-contained portable technical report; structural verification passed, but browser interaction QA was unavailable because Chromium is not installed.
- `html/artifact.json` — canonical report artifact used to build the portable HTML.
- `../suite/` — one-command suite outputs.
- `../profiles/` — hardware benchmark outputs.

Reproducible commands, from the repository root, using the `PY312` interpreter:

```text
C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe tools\p11_5\audit_dataset.py
C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe tools\p11_5\build_v2.py
C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe tools\p11_5\run_accuracy_suite.py --profile --profile-name auto --baseline --temporal
C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe -m pytest -p no:cacheprovider tests\test_p11_5_tools.py -q
```
