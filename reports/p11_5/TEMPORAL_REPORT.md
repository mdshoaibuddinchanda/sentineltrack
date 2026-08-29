# Temporal Report

True sequence/registration-identity tracks only; no random equal-text grouping.

| window | method | eligible | exact | char | CER |
| --- | --- | --- | --- | --- | --- |
| 1 | single_best | 88 | 0.215909 | 0.577143 | 0.24 |
| 1 | current_voter | 88 | 0.329545 | 0.593143 | 0.250286 |
| 1 | weighted_vote | 88 | 0.215909 | 0.577143 | 0.24 |
| 1 | character_fusion | 88 | 0.215909 | 0.577143 | 0.24 |
| 3 | single_best | 64 | 0.296875 | 0.665094 | 0.204403 |
| 3 | current_voter | 64 | 0.515625 | 0.742138 | 0.127358 |
| 3 | weighted_vote | 64 | 0.328125 | 0.691824 | 0.194969 |
| 3 | character_fusion | 64 | 0.34375 | 0.713836 | 0.190252 |
| 5 | single_best | 38 | 0.342105 | 0.806878 | 0.124339 |
| 5 | current_voter | 38 | 0.631579 | 0.835979 | 0.108466 |
| 5 | weighted_vote | 38 | 0.368421 | 0.81746 | 0.10582 |
| 5 | character_fusion | 38 | 0.342105 | 0.804233 | 0.121693 |
| 8 | single_best | 24 | 0.25 | 0.782427 | 0.150628 |
| 8 | current_voter | 24 | 0.666667 | 0.90795 | 0.075314 |
| 8 | weighted_vote | 24 | 0.291667 | 0.803347 | 0.146444 |
| 8 | character_fusion | 24 | 0.291667 | 0.807531 | 0.129707 |

Logit fusion is unavailable because the PP-OCRv5 ONNX interface exposes decoded text and character confidence, not timestep logits.
