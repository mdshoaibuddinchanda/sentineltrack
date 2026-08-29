# P11.5 Requested Completion Matrix

Generated from local PY312 files and reports. A missing checkpoint or interrupted run is not reported as a model result.

| Requested item | Status | Evidence / result |
|---|---|---|
| YOLO11m/l/x plate tournament | INCOMPLETE_LOCAL_EVIDENCE | No comparable completed m/l/x plate tournament; existing YOLO11s reference end-to-end exact 0.3427. |
| YOLO26 tournament | INCOMPLETE_LOCAL_EVIDENCE | Installed Ultralytics family support: True; YOLO26m has smoke evidence, while l/x have no completed run. |
| SVTRv2 / PARSeq / MGP-STR | BLOCKED_LOCAL_RUNTIME_AND_CHECKPOINTS | No runnable local package/checkpoint for these requested candidates. |
| OCR fine-tuning | NOT_COMPLETED | Only ONNX PP-OCRv5 inference exports are available; no compatible train checkpoint/config/export toolchain is present. |
| Full-scale synthetic curriculum | CORPUS_COMPLETE_SCREENING_ONLY | 100000 generated; bounded screens only, full-scale training pending. |
| Production crop modification | EVALUATED_NO_PROMOTION | AABB 0.3427; OBB 0.3357; production left unchanged. |

## Detector candidate evidence

Smoke rows are one-epoch diagnostics; they are not a fair ranking against the completed 20-epoch YOLO11s reference.

| candidate | status | epochs | test mAP50 | test mAP50-95 | test F1 | test P50 ms |
| --- | --- | --- | --- | --- | --- | --- |
| YOLO11m plate | TRAINED_SMOKE_EVALUATED_NOT_FINAL | 1 | 0.9162 | 0.5318 | 0.5898 | 36.4070 |
| YOLO11l plate | TRAINED_SMOKE_EVALUATED_NOT_FINAL | 1 | 0.0830 | 0.0249 | 0.0538 | 42.3785 |
| YOLO11x plate | READY_FOR_ISOLATED_TRAINING | - | - | - | - | - |
| YOLO26m plate | TRAINED_SMOKE_EVALUATED_NOT_FINAL | 1 | 0.3884 | 0.1599 | 0.3910 | 35.8937 |
| YOLO26l plate | READY_FOR_ISOLATED_TRAINING | - | - | - | - | - |
| YOLO26x plate | READY_FOR_ISOLATED_TRAINING | - | - | - | - | - |

## Interpretation

The requested list was not previously completed in full. The existing work is a valid measured baseline and screening package, but it does not justify claiming a full model tournament, modern OCR integration, OCR fine-tuning, or full-scale synthetic training. The crop item is intentionally an evaluation/no-promotion decision because the measured alternative was worse.

## Reproducibility

Run `C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe tools\p11_5\requested_completion_matrix.py` from the repository root.
