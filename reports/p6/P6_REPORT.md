# SentinelTrack Priority 6 — Vehicle ReID Fallback

> **P6_APPEARANCE_PROXY_EVALUATION** — NO TRUE CROSS_CAMERA IDENTITY GT — METRICS ARE APPEARANCE PROXY EVIDENCE ONLY

## Decision

Vehicle ReID is a fallback appearance signal when ANPR is partial or unavailable. Strong ANPR remains authoritative; appearance-only results remain REVIEW/POSSIBLE and cannot produce an automatic HIGH or CRITICAL alert.

## Selected appearance model

- Architecture: `torchvision.mobilenet_v3_small` with ImageNet weights; appearance-retrieval baseline, not vehicle-domain ReID.
- Model/version: `mobilenet_v3_small_imagenet` / `torchvision-0.20.1`.
- Checkpoint URL: `https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth`.
- Checkpoint SHA-256: `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`.
- Input: `224x224`, BGR-to-RGB, area resize, ImageNet mean/std normalization.
- Embedding dimension: `576`; L2 normalization: `true`.
- Plate masking: `True` whenever a local plate box is available; OCR text is never input.
- Runtime/device: `cuda`.

## Evaluation provenance

- Source: `datasets/experiments/multiframe_ocr_v1/frames.csv and datasets/video_images`.
- Population: `Verified ByteTrack track sequences; vehicle-region proxies expanded from plate-labelled frames; no camera IDs or same-vehicle cross-camera links.`.
- Samples: `240`; calibration tracks `61`, locked test tracks `27`.
- Track leakage check: `True`.
- There is no camera ID or verified same-vehicle cross-camera annotation, so Rank-1, Rank-5, mAP, and cross-camera accuracy are intentionally not reported.

## Threshold and proxy evidence

- Calibration threshold: `0.874001`; selected using calibration only with maximum false-match rate `0.007246`.
- Calibration ROC-AUC: `0.90173`; false-match `0.007246`; false-non-match `0.458065`.
- Locked proxy ROC-AUC: `0.964794`; false-match `0.0`; false-non-match `0.459016`.
- Similarity distributions: calibration positive p50 `0.883`, negative p50 `0.7218`; locked positive p50 `0.8809`, negative p50 `0.7247`.
- Automatic appearance escalation: `False` (P6 remains review-safe because true cross-camera identity ground truth is unavailable).

## Fusion and safety

- `STRONG_PLATE`: skip candidate search; `identity_source=ANPR`; ReID cannot override; disagreements are diagnostics only.
- `PARTIAL_PLATE`: `plate_score + reid_score + temporal compatibility + optional route feasibility` can support a plausible P5 candidate; it cannot create EXACT from an unrelated plate.
- `NO_USABLE_PLATE`: `identity_source=REID_REVIEW`; `POSSIBLE/REVIEW` only; no automatic HIGH/CRITICAL alert or exact identity claim.
- Candidates are pruned by camera, stream epoch, vehicle class, chronological window, and optional P7 feasibility callback. Same-camera epoch changes cannot reuse stale track identity.
- Track cache is keyed by `(camera_id, stream_epoch, track_id)`, retains the top five quality crops, and has bounded TTL/capacity.

## Hardware and gallery benchmark

- Batch 1: `{'p50_latency_ms': 9.0376, 'p95_latency_ms': 10.6913, 'embeddings_per_second': 110.6488}`.
- Batch 4: `{'p50_latency_ms': 13.6531, 'p95_latency_ms': 14.4735, 'embeddings_per_second': 292.9738}`.
- Batch 8: `{'p50_latency_ms': 20.4159, 'p95_latency_ms': 24.3476, 'embeddings_per_second': 391.8514}`.
- Track aggregation: `{'gallery_tracks': 100, 'top_k_crops': 5, 'p50_add_observation_ms': 0.0642, 'p95_add_observation_ms': 0.0979}`.
- In-memory cosine search: `{'100': {'gallery_embeddings': 100, 'p50_search_ms': 1.6155, 'p95_search_ms': 1.8469}, '1000': {'gallery_embeddings': 1000, 'p50_search_ms': 13.6102, 'p95_search_ms': 16.7317}, '10000': {'gallery_embeddings': 10000, 'p50_search_ms': 166.5587, 'p95_search_ms': 240.6022}}`.
- Memory: `{'cpu_rss_mb': 976.41, 'gpu_vram_total_mb': 4095.5, 'gpu_vram_allocated_mb': 3.64, 'gpu_vram_reserved_mb': 136.0}`.
- ReID runs conditionally for partial/no-plate tracks; strong ANPR tracks skip the expensive search.

## Limitations

- The proxy crops are expanded from plate-labelled frames and do not establish cross-camera identity. A verified multi-camera vehicle-ID dataset is required before making ReID accuracy or automatic identity claims.
- The selected ImageNet backbone is not fine-tuned for Indian traffic or cross-camera domain shift.
- P7 remains a chronological lower-bound feasibility signal; this module does not implement road-level routing.

## Reproducibility

```text
python -m 06_vehicle_reid.benchmark
```
