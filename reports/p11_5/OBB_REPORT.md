# OBB Detector and Downstream Crop Report

Strict OBB derivative: 4,854 images; splits `train=3924`, `val=637`, `test=293`. The YOLO11s OBB detector was also checked downstream on the text-labelled held-out sequence test.

| path | detector P/R | OCR exact | OCR CER | decision |
| --- | --- | --- | --- | --- |
| P11.5 AABB candidate | 1.000 / 1.000 | 0.3427 | 0.2669 | retain |
| YOLO11s OBB AABB crop | 1.000 / 1.000 | 0.3287 | 0.2945 | reject |
| YOLO11s OBB perspective warp | 1.000 / 1.000 | 0.3357 | 0.2938 | reject |

OBB did not improve downstream exact accuracy or CER on the paired text-labelled test. It remains a measured experiment, not the selected production path. YOLO26-OBB architecture support is now available locally, but no YOLO26-OBB plate run is promoted.

The OBB label derivative uses polygon minimum-area rectangles where source polygons exist and axis-aligned fallback otherwise. Full evidence is in `e2e_crop_diagnosis_multiframe_test.json`.

| training candidate | status | registry decision | weight |
| --- | --- | --- | --- |
| obb-yolo11s-v2-e20-b4-640-r3-clean | TRAINED | MEASURED_ONLY | runs/p11_5/obb-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt |
