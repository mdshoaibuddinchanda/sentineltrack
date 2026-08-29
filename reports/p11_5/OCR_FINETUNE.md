# OCR Fine-Tuning and Modern Recognizer Audit

Status: NOT_COMPLETED_LOCALLY; blocker verified in PY312.

The environment has inference-ready PP-OCRv5 ONNX artifacts, but the installed Paddle/PaddleOCR imports fail with a protobuf descriptor incompatibility. No package downgrade or environment mutation was applied. PaddleOCR source/docs expose SVTR-family support, but no local SVTRv2 checkpoint is cached. OpenOCR, PARSeq, and MGP-STR are not installed.

The ONNX PP-OCRv5 files are inference exports rather than a matching train checkpoint/config, so they cannot be fine-tuned through the project’s current local training path. The probe and its exact error are recorded in `modern_ocr_probe.json`; no modern-recognizer score is claimed. Existing zero-shot OCR results remain the valid baseline.
