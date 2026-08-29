# P3 Tournament

## Outcome

The candidate runs below are measured on the strict detection V2 test split. Production weights were never overwritten.

| run | imgsz | P | R | F1 | mAP50 | mAP50-95 | tiny R | square/tall R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline-production-strict-640 | 640 | 0.940984 | 0.940984 | 0.940984 | 0.9772707266590659 | 0.6461673770900098 | 0.8 | 0.987342 |
| p3-yolo11s-v2-e20-b4-640-r3-clean-authoritative | 640 | 0.967742 | 0.983607 | 0.97561 | 0.9927233410046997 | 0.7827292419538258 | 0.8 | 0.974684 |

## Required candidates and blockers

YOLO11s transfer was run and will be promoted only from an authoritative clean-data evaluation. YOLO11m and YOLO26 were not run in this local pass; YOLO26 was not present in the installed Ultralytics 8.3.235 model/config package, so no unsupported checkpoint or score was fabricated. YOLO11s/YOLO11m OBB support is handled separately in OBB_REPORT.md.

Historical production baseline reference: not available F1 on the earlier canonical test; it is not directly interchangeable with the strict derivative test.
