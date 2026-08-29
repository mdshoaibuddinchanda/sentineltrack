# End-to-End Detector → OCR Report

The earlier strict-detection E2E OCR table is retired: that manifest has incomplete OCR supervision (only 37 of its 293 test rows have non-empty text). The benchmark now refuses such a manifest and uses the fully text-labelled held-out sequence test (`multiframe_ocr_v1`, 143 test frames).

Pipeline: detector → predicted AABB crop → PP-OCRv5 mobile → existing structural decoder metrics.

| model | det P/R | OCR exact | OCR CER | P50 ms | P95 ms | FPS |
| --- | --- | --- | --- | --- | --- | --- |
| production | 1.000 / 1.000 | 0.3287 (47/143) | 0.3143 | 28.358 | 97.062 | 22.688 |
| P11.5 candidate | 1.000 / 1.000 | 0.3427 (49/143) | 0.2669 | 26.045 | 36.038 | 35.443 |

On this valid text-labelled held-out set, the candidate improves exact accuracy by 1.40 percentage points and CER by 0.0474 while reducing measured mean latency from 44.076 ms to 28.215 ms. There are no negative vehicle/background examples in this set, so safety FPR is not claimable here.

The corresponding machine-readable evidence is `end_to_end_evaluation.json` and `end_to_end_leaderboard.csv`.
