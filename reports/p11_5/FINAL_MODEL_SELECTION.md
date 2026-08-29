# P11.5C Model and Integration Selection

- Detector: retain the clean-data YOLO11s P3 candidate for the current measured profile. The valid text-labelled E2E test gives it 0.3427 exact accuracy, 0.2669 CER, and 35.443 FPS.
- Crop: retain the unpadded predicted AABB crop. On 143 held-out text-labelled frames, margin 0 scored 0.3427 exact; margins 2/4/6/8 scored 0.3077/0.2937/0.2517/0.2517. The GT AABB oracle reaches 0.4266, so remaining crop/recognition headroom is real but not solved by padding.
- OBB: do not promote. OBB perspective warp scored 0.3357 exact and 0.2938 CER, below the candidate AABB path.
- OCR: PP-OCRv5 mobile remains the deployable choice pending a compatible modern-recognizer environment and a valid fine-tuning checkpoint.
- Temporal: current voter with a 5-frame window is the balanced operational profile; on the fixed 24-track GT-crop population, windows 5 and 8 tie at 0.666667 exact, while window 8 has lower CER. Predicted-crop temporal evidence is available separately and is limited to six eligible tracks.
