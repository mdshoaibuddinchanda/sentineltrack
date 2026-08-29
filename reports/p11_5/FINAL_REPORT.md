# SentinelTrack P11.5C OCR Recovery Report

## Executive summary

P11.5C corrected the detector-to-OCR evaluation, diagnosed crop geometry, proved AABB versus OBB downstream behavior, added paired same-track temporal evaluation, audited modern OCR availability, and staged an isolated synthetic screening experiment. Frozen V1 datasets, frontend, CI, P6, P12, production weights, and the existing production code path were not overwritten.

## Key correction

The prior strict E2E OCR result was invalid for OCR claims: `plate_detection_v2_strict` contains plate boxes but empty OCR text labels. The corrected benchmark now rejects manifests without non-empty text ground truth and evaluates the 143 text-labelled test frames from `multiframe_ocr_v1`.

## Measured results

- Candidate predicted AABB E2E: exact `0.3427`, CER `0.2669`, detector P/R `1.000/1.000`, 35.443 FPS.
- Production predicted AABB E2E: exact `0.3287`, CER `0.3143`, detector P/R `1.000/1.000`, 22.688 FPS.
- Candidate crop diagnosis: no-padding AABB `0.3427` exact; GT AABB oracle `0.4266`; OBB perspective warp `0.3357`.
- Paired GT-crop current voter: `0.416667 → 0.541667 → 0.666667 → 0.666667` exact for windows 1/3/5/8 on the same 24 tracks.
- Paired predicted-crop current voter: `0.166667 → 0.166667 → 0.500000 → 0.500000` exact for windows 1/3/5/8 on the same six tracks.
- Synthetic screening on a deterministic 500-real-image subset: real-only mAP50-95 `0.732293`, +25% synthetic `0.726403`, +50% synthetic `0.698319`; no mixed variant is promoted.

## Remaining blockers

- Paddle/PaddleOCR imports are unavailable in PY312 because of a protobuf descriptor incompatibility; no package downgrade was applied.
- PaddleOCR documents modern SVTR-family support, but no local SVTRv2 checkpoint is cached. OpenOCR, PARSeq, and MGP-STR are not installed.
- OCR fine-tuning is not complete: the available PP-OCRv5 artifacts are ONNX inference exports, not a matching train checkpoint/config.
- YOLO26/YOLO26-OBB is unavailable locally; a full YOLO11m/l/x and YOLO26 tournament remains an explicit follow-up, not a claimed result here.
- Synthetic results are screening evidence only and do not change the authoritative real-data selection.

## Reproducibility

Run the committed tools with the PY312 interpreter. Aggregate evidence is stored under `reports/p11_5`; candidate weights remain outside Git under `runs/p11_5`, and production weights are never overwritten.
