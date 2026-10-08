# Model and Evidence Register

This document is the submission-facing model register. Metrics are copied from frozen repository artifacts and retain their evidence classification.

## Runtime environment

| Field | Value | Class |
|---|---|---|
| Environment | Conda `PY312` | `MEASURED_LOCAL` |
| Python | 3.12.12 | `MEASURED_LOCAL` |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB | `MEASURED_LOCAL` |
| CUDA / PyTorch | CUDA 12.1 / PyTorch 2.5.1+cu121 | `MEASURED_LOCAL` |
| Ultralytics / ONNX Runtime | 8.3.235 / 1.24.2 | `MEASURED_LOCAL` |
| Frozen base commit | `1f48aad81a35553ff1e80866a17b1784313efa1b` | `MEASURED_LOCAL` |

## Model chain

| Stage | Selected implementation | Evidence |
|---|---|---|
| Vehicle detection | YOLO11m baseline; no authoritative external vehicle-GT claim | `MEASURED_LOCAL / NOT_MEASURED` |
| Tracking | Per-camera ByteTrack with `camera_id + stream_epoch + track_id` | `MEASURED_LOCAL` |
| Plate detection | YOLO11s candidate: TP 300, FP 10, FN 5, F1 0.975610, mAP50-95 0.783111 | `MEASURED_TEST` |
| OCR | PP-OCRv5 Mobile ONNX; P50 10.53 ms, P95 24.85 ms, 79.54 crops/s | `MEASURED_TEST` |
| Temporal OCR | Existing five-frame temporal voting | `MEASURED_LOCAL` |
| Target matching | Controlled 100k-record Recall@100 92.0%, P95 112.55 ms | `MEASURED_TEST` |
| Route feasibility | Chronological sightings, geodesic lower bound, minimum-speed check; no road routing | `MEASURED_LOCAL` |
| Vehicle ReID fallback | MobileNetV3-Small ImageNet, 576-D L2-normalized embedding | `MEASURED_LOCAL` |

## P6 appearance evidence

- Checkpoint provenance: official torchvision MobileNetV3-Small ImageNet checkpoint, [download URL](https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth).
- Checkpoint SHA256: `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`.
- Plate masking: enabled by default; `plate_region_masked_for_reid: true`.
- Track aggregation: top-quality crops, bounded per-track cache, normalized mean, stream epoch included.
- True cross-camera vehicle-ID ground truth: **not available locally**.
- Proxy evaluation: 240 samples; 61 calibration tracks; 27 locked-test tracks; no track overlap.
- Calibration threshold: cosine `0.874001`; calibration false-match rate `0.007246`; false-non-match rate `0.458065`.
- Locked proxy: false-match rate `0`; false-non-match rate `0.459016`.
- Policy: review-only; appearance similarity cannot create an automatic exact/high/critical identity decision.

## Interpretation limits

The P6 pair experiment measures same-track appearance consistency and hard negatives, not cross-camera identity accuracy. It must not be described as Rank-1, mAP, statewide accuracy, or police identity proof. The selected checkpoint is an appearance-retrieval baseline, not a vehicle-domain-trained ReID model.

## Source register

- P6: `reports/p6/P6_REPORT.md`, `reports/p6/P6_EVALUATION.json`, `reports/p6/P6_BENCHMARK.json`
- P11.5: `reports/p11_5/FINAL_REPORT.md`, `reports/p11_5/CAPACITY_DELTA.md`, `reports/p11_5/end_to_end_evaluation.json`
- Security: `docs/security/role_permission_matrix.md`, `docs/security/data_classification.md`, `docs/security/deployment_security.md`

