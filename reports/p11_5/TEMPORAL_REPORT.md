# Temporal OCR Report

The original table is retained as a historical cohort-shifting benchmark: each window had a different eligible-track denominator. The paired companion fixes the population to the same 24 tracks with at least 8 observations.

## Paired GT-crop evaluation

| window | method | eligible tracks | exact | character | CER |
| --- | --- | --- | --- | --- | --- |
| 1 | current_voter | 24 | 0.416667 | 0.60251 | 0.284519 |
| 3 | current_voter | 24 | 0.541667 | 0.774059 | 0.117155 |
| 5 | current_voter | 24 | 0.666667 | 0.874477 | 0.09205 |
| 8 | current_voter | 24 | 0.666667 | 0.90795 | 0.075314 |

## Paired predicted-crop evaluation

The detector-predicted AABB evaluation has a smaller fixed population: 6 test tracks with at least 8 source frames.

| window | method | eligible tracks | exact | character | CER |
| --- | --- | --- | --- | --- | --- |
| 1 | current_voter | 6 | 0.166667 | 0.55 | 0.466667 |
| 3 | current_voter | 6 | 0.166667 | 0.666667 | 0.333333 |
| 5 | current_voter | 6 | 0.5 | 0.833333 | 0.233333 |
| 8 | current_voter | 6 | 0.5 | 0.916667 | 0.2 |

The paired results show temporal voting helps, but the predicted-crop integration remains materially weaker than the GT-crop upper-bound path. Machine-readable companions: `temporal_paired_evaluation.json` and `temporal_predicted_e2e.json`.

Logit fusion remains unavailable because the PP-OCRv5 ONNX interface exposes decoded text and character confidence, not timestep logits.
