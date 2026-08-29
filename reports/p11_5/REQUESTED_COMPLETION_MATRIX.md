# P11.5 Requested Completion Matrix

Generated from local PY312 files and reports. A missing checkpoint or interrupted run is not reported as a model result.

| Requested item | Status | Evidence / result |
|---|---|---|
| YOLO11m/l/x plate tournament | FULL_ARCHITECTURE_TOURNAMENT_DEFERRED_NOT_REQUIRED_FOR_P11_5_FREEZE | No comparable completed m/l/x plate tournament; existing YOLO11s reference end-to-end exact 0.3427. |
| YOLO26 tournament | FULL_ARCHITECTURE_TOURNAMENT_DEFERRED_NOT_REQUIRED_FOR_P11_5_FREEZE | YOLO26m smoke evidence remains diagnostic; l/x are intentionally not started. Production runtime remains pinned and the YOLO26 dependency is isolated. |
| SVTRv2 / PARSeq / MGP-STR | DEFERRED_NOT_REQUIRED_FOR_P11_5_FREEZE | No comparable local production integration/checkpoint was evaluated; these are optional future candidates. |
| OCR fine-tuning | INTERRUPTED_RESOURCE_LIMITED_NO_CHECKPOINT | Official PaddleOCR training was attempted in an isolated environment, but the CPU run did not reach its first logging interval and produced no checkpoint or metric. PP-OCRv5 Mobile ONNX remains selected. |
| Full-scale synthetic curriculum | REJECTED_BY_BOUNDED_SCREEN | 100000 generated; real-only won the bounded screen, so synthetic addition is rejected. |
| Production crop modification | EVALUATED_NO_PROMOTION | AABB 0.3427; OBB 0.3357; production left unchanged. |

## Detector candidate evidence

Smoke rows are one-epoch diagnostics; they are not a fair ranking against the completed 20-epoch YOLO11s reference.

| candidate | status | epochs | test mAP50 | test mAP50-95 | test F1 | test P50 ms |
| --- | --- | --- | --- | --- | --- | --- |
| YOLO11m plate | TRAINED_SMOKE_EVALUATED_NOT_FINAL | 1 | 0.9162 | 0.5318 | 0.5898 | 36.4070 |
| YOLO11l plate | TRAINED_SMOKE_EVALUATED_NOT_FINAL | 1 | 0.0830 | 0.0249 | 0.0538 | 42.3785 |
| YOLO11x plate | READY_FOR_ISOLATED_TRAINING | - | - | - | - | - |
| YOLO26m plate | TRAINED_SMOKE_EVALUATED_NOT_FINAL | 1 | 0.3884 | 0.1599 | 0.3910 | 35.8937 |
| YOLO26l plate | BLOCKED_PACKAGE | - | - | - | - | - |
| YOLO26x plate | BLOCKED_PACKAGE | - | - | - | - | - |

## Interpretation

P11.5 freeze decision: all locally feasible evidence and accounting work is complete. Full architecture tournaments, modern OCR alternatives, longer OCR optimization, and full-scale synthetic training are optional future research—not blockers for this freeze. The crop item is an evaluation/no-promotion decision because the measured alternative was worse.

## Reproducibility

Run `C:\Users\SHOAIB-CHANDA\miniconda3\envs\py312\python.exe experiments\archive\p11_5\requested_completion_matrix.py` from the repository root.
