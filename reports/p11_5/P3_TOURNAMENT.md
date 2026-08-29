# P3 Tournament

## Outcome

The candidate runs below are measured on the strict detection V2 test split. Production weights were never overwritten.

| run | imgsz | P | R | F1 | mAP50 | mAP50-95 | tiny R | square/tall R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline-production-strict-640 | 640 | 0.940984 | 0.940984 | 0.940984 | 0.9772707266590659 | 0.6461673770900098 | 0.8 | 0.987342 |
| p3-yolo11s-v2-e20-b4-640-r3-clean-authoritative | 640 | 0.967742 | 0.983607 | 0.97561 | 0.9927233410046997 | 0.7827292419538258 | 0.8 | 0.974684 |

## Architecture smoke coverage

These one-epoch runs are diagnostic only and are not comparable to the 20-epoch selected YOLO11s run or eligible for promotion.

| run | P | R | F1 | mAP50 | mAP50-95 |
| --- | --- | --- | --- | --- | --- |
| p11-5-yolo11l-plate-smoke-e1-b2 | 0.149254 | 0.032787 | 0.053763 | 0.08301076201991683 | 0.024925264226786557 |
| p11-5-yolo11m-plate-smoke-e1-b4 | 0.428148 | 0.947541 | 0.589796 | 0.9162220584466226 | 0.5317659132691813 |
| p11-5-yolo26m-plate-smoke-e1-b4-net2 | 0.516129 | 0.314754 | 0.391039 | 0.38837430114465127 | 0.1598797289206316 |

## Required candidates and blockers

YOLO11s remains the only completed authoritative plate detector candidate. YOLO11m and YOLO26m have one-epoch smoke evidence; YOLO11l/x and YOLO26l/x still require comparable full training. YOLO26 support is available only after the Ultralytics dependency update recorded in requirements.txt. YOLO11s/YOLO11m OBB support is handled separately in OBB_REPORT.md.

Historical production baseline reference: not available F1 on the earlier canonical test; it is not directly interchangeable with the strict derivative test.
