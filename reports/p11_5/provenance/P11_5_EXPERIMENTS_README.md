# SentinelTrack P11.5 Experiments

This directory contains reproducibility metadata for the maximum-accuracy
optimization work. It is intentionally separated from the frozen P0-P11
production data and model artifacts.

The frozen datasets remain:

- `datasets/plate_detection/`
- `datasets/plate_ocr/`

The read-only dataset audit is run with:

```text
python experiments/archive/p11_5/audit_dataset.py
```

It writes derived manifests under `datasets/experiments/manifests/` and audit
summaries under `reports/p11_5/dataset/`. It does not modify source images,
labels, or canonical split directories.

Large generated data, predictions, caches, checkpoints, and model weights are
local experiment artifacts and must not be committed to ordinary Git.
