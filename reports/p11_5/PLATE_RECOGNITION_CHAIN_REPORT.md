# Plate Recognition Chain Report

This is a plate recognition-chain benchmark, not a complete SentinelTrack or P5 safety benchmark. The earlier strict-detection table is retired because its manifest had incomplete OCR supervision (only 37 of its 293 test rows had non-empty text). The benchmark now uses the fully text-labelled held-out sequence test (`multiframe_ocr_v1`, 143 test frames).

Pipeline: detector → predicted AABB crop → PP-OCRv5 mobile → existing structural decoder metrics. Dataset: datasets/experiments/multiframe_ocr_v1 (source images; test sequences).

Matching: all class-0 predictions and all GT boxes are greedily matched one-to-one at IoU >= 0.5.

| model | det P/R | OCR exact | OCR CER | P50 ms | P95 ms | FPS |
| --- | --- | --- | --- | --- | --- | --- |
| models/plate/production/best.pt | 0.979 / 1.000 | 0.3287 (47/143) | 0.3143 | 29.121 | 92.295 | 22.371 |
| runs/p11_5/p3-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt | 0.973 / 1.000 | 0.3427 (49/143) | 0.2662 | 27.927 | 37.431 | 33.51 |

Recognition-chain categories are recorded in each result as GT count, detector-matched GT count, DETECTOR_MISS, OCR_WRONG, OCR_EXACT, conditional OCR exact, complete-chain exact, raw/postprocessed exact, character accuracy, CER, and empty-read rate. There are no negative vehicle/background examples in this set, so safety/P5 FPR is not claimable here.

The corresponding machine-readable evidence is `end_to_end_evaluation.json` and `end_to_end_leaderboard.csv`.
