# P11.5C Model and Integration Selection

- Detector: retain the clean-data YOLO11s P3 candidate for the current measured profile. The valid text-labelled plate-recognition chain gives it 0.342657 complete-chain exact, 0.2662 CER, and 33.51 FPS.
- Crop: retain the unpadded predicted AABB crop. The selected candidate margin-0 path scores 0.3427 exact; the GT AABB oracle scores 0.4266 and remains an upper bound, not a deployable path.
- OBB: do not promote. OBB perspective warp scored 0.3357 exact and 0.2938 CER, below the candidate AABB path.
- OCR: retain PP-OCRv5 mobile. The one bounded official fine-tuning attempt produced no checkpoint or metric, so no OCR replacement is promoted.
- Temporal: current voter with a 5-frame window is the balanced operational profile; the paired GT-crop result is 0.666667 exact on the fixed eligible population. Predicted-crop temporal evidence remains available separately.
