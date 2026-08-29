# SentinelTrack P11.5B–E Final Execution Report

## Executive summary

This branch is the bounded P11.5 freeze: strict dataset freezes, same-manifest detector comparison, corrected all-detection recognition-chain accounting, isolated detector/OBB harnesses, OCR screening, one bounded official OCR fine-tuning attempt, temporal consensus, preprocessing sweeps, synthetic bounded screening, hard-example mining, frontend lifecycle hardening, CI repair, and operational reporting. Frozen V1 datasets and production model paths were not modified.

## Measured outcomes

- Authoritative same-manifest detector reports: 2; diagnostic architecture smoke reports: 3.
- OCR candidate rows: 9; fine-tuning attempt: INTERRUPTED_RESOURCE_LIMITED_NO_CHECKPOINT with no promoted replacement.
- Temporal tracks: 88 across 583 crops; selected operational window: 5.
- Synthetic corpus: 100000 generated examples; bounded screens completed: 3; decision: REJECTED_BY_BOUNDED_SCREEN.
- Hard-example mining records aggregate failure categories and does not persist raw predictions.
- Production runtime is pinned to Ultralytics 8.3.235; YOLO26 remains experiment-only in requirements-experiments-yolo26.txt.

## Freeze decisions and limitations

- Full YOLO11m/l/x and YOLO26m/l/x architecture tournaments are deferred and explicitly not required for this P11.5 freeze; clean YOLO11s is the selected high-accuracy real-time detector based on completed evidence.
- No external vehicle GT corpus was available, so P1 recall/FPR and P5 safety regression are not claimable.
- SVTRv2/PARSeq/MGP-STR were not promoted; the official PP-OCRv5 mobile fine-tuning attempt was resource-limited before checkpoint/metric output, so existing PP-OCRv5 Mobile remains selected.
- The bounded synthetic screens reject adding synthetic data for the current detector decision; no full-scale 100,000-example training was started.
- Cross-split raw SHA and identity leakage are clean. Upstream detection V2 retains pHash-near review findings; the strict derivative removes exact cross-split pHash source copies while preserving canonical V1 assignments.
- One malformed source JPEG is materialized deterministically with the Ultralytics-compatible repair (1 row); its original source SHA remains in the manifest and the materialized SHA is checked post-training.

## Reproducibility

Use the PY312 interpreter, the committed tools under tools/p11_5, the recorded manifest hashes, and the run registry. Candidate weights remain outside Git under runs/p11_5; production weights are never overwritten.
The final freeze is complete when the local checks pass and the exact pushed commit's backend and frontend GitHub Actions jobs are green.
