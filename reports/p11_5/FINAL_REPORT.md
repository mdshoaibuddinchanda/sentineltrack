# SentinelTrack P11.5B–E Final Execution Report

## Executive summary

This branch contains measured local P11.5 work: strict dataset freezes, a true multiframe benchmark, isolated detector/OBB harnesses, OCR screening, temporal consensus, preprocessing sweeps, synthetic corpus generation, hard-example mining, and operational reporting. Frozen V1 datasets, frontend, and CI were not modified.

## Measured outcomes

- Detector candidate reports: 2 evaluation artifacts.
- OCR candidate rows: 9.
- Temporal tracks: 88 across 583 crops.
- Synthetic corpus: 100000 generated examples against a 100,000 target.
- Hard-example mining records aggregate failure categories and does not persist raw predictions.

## Hard blockers and limitations

- YOLO26 is unavailable in the installed local Ultralytics package; official OBB weights were downloaded only for the supported YOLO11 OBB stage.
- No external vehicle GT corpus was available, so P1 recall/FPR and P5 safety regression are not claimable.
- OCR fine-tuning was not completed because compatible training/export dependencies and modern local checkpoints are missing.
- Synthetic 25%/50% ablation training remains pending; synthetic data is not used for authoritative test claims.
- Cross-split raw SHA and identity leakage are clean. Upstream detection V2 retains pHash-near review findings; the strict derivative removes exact cross-split pHash source copies while preserving canonical V1 assignments.
- One malformed source JPEG is materialized deterministically with the Ultralytics-compatible repair (1 row); its original source SHA remains in the manifest and the materialized SHA is checked post-training.

## Reproducibility

Use the PY312 interpreter, the committed tools under tools/p11_5, the recorded manifest hashes, and the run registry. Candidate weights remain outside Git under runs/p11_5; production weights are never overwritten.
