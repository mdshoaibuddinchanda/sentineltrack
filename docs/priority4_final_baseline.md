# SentinelTrack Priority 4 Final Baseline Documentation

**Date:** 2026-08-28  
**Module:** Priority 4 — License Plate OCR Subsystem  
**Status:** **BASELINE FROZEN — READY FOR PRIORITY 5**

---

## 1. Dataset & Provenance
* **Dataset:** zenitsu09/indian-number-plate
* **License Status:** LICENSE_UNVERIFIED (Audited via Hugging Face REST API with no explicit license metadata; retained as development/evaluation benchmark)
* **Total Real Plate Crops:** 1,707 images
* **Unique Physical Registrations:** 963 unique plate identities
* **Split Counts (Zero Leakage):**
  * **Train:** 1,382 crops (675 unique identities)
  * **Validation:** 147 crops (144 unique identities) [100% REAL ONLY]
  * **Test (Locked):** 178 crops (144 unique identities) [100% REAL ONLY]
* **Leakage Verification:** 0% hash overlap and 0 shared identities across partitions.

---

## 2. Production OCR Engine & Authoritative Model Provenance
* **Selected Engine:** n_PP-OCRv5_mobile_rec (PaddlePaddle English PP-LCNet + CTC greedy decoding)
* **Inference Provider:** ONNX Runtime CPU (8 threads) (CUDA_PROVIDER_UNAVAILABLE)
* **Authoritative Download Source:** https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/english/rec.onnx
* **Pinned Expected SHA-256:** 4e16deb22c4da6468bdca539b2cd3c8687825538b67109177c47d359ab994cd7
* **Production Batch Size:** B=2 (Peak throughput: 109.26 crops/sec, 9.15 ms amortized latency per crop)

---

## 3. Quantitative Evaluation Summary (Raw vs Postprocessed)

Evaluated across the exact same 147 real validation and 178 locked real test crops:

### A. Real Validation Set (147 Crops)
* **n_PP-OCRv5_mobile_rec (Production Selected):**
  * **RAW Metrics:** Exact: **50.34%** (74/147) | Char Acc: **80.66%** | CER: **0.1328** | Mean Edit Dist: 0.1351
  * **POSTPROCESSED Metrics:** Exact: **61.90%** (91/147) | Char Acc: **82.44%** | CER: **0.1156** | Mean Edit Dist: 0.1183
  * **Latency & Throughput:** P50: **9.92 ms** | P95: **18.83 ms** | Throughput: **89.20 crops/s** | Empty-Read Rate: **0.00%**
* **PP-OCRv5_server_rec (Challenger):**
  * **RAW Metrics:** Exact: 57.82% (85/147) | Char Acc: 75.73% | CER: 0.1627
  * **POSTPROCESSED Metrics:** Exact: 61.90% (91/147) | Char Acc: 76.23% | CER: 0.1592
  * **Latency & Throughput:** P50: 444.26 ms | P95: 717.97 ms | Throughput: 2.15 crops/s

### B. Final Real Test Set (178 Crops - LOCKED)
* **n_PP-OCRv5_mobile_rec (Production Selected):**
  * **RAW Metrics:** Exact: **49.44%** (88/178) | Char Acc: **77.92%** | CER: **0.1782** | Mean Edit Dist: 0.1804
  * **POSTPROCESSED Metrics:** Exact: **57.30%** (102/178) | Char Acc: **78.69%** | CER: **0.1729** | Mean Edit Dist: 0.1752
  * **Latency & Throughput:** P50: **9.06 ms** | P95: **14.95 ms** | Throughput: **100.75 crops/s** | Empty-Read Rate: **0.00%**
* **PP-OCRv5_server_rec (Challenger):**
  * **RAW Metrics:** Exact: 51.69% (92/178) | Char Acc: 75.67% | CER: 0.1753
  * **POSTPROCESSED Metrics:** Exact: 53.37% (95/178) | Char Acc: 75.84% | CER: 0.1747
  * **Latency & Throughput:** P50: 439.30 ms | P95: 881.73 ms | Throughput: 2.04 crops/s

---

## 4. Multi-Frame Consensus Voting (Production Mobile)
* **Single-Frame Test Accuracy:** 61.24%
* **Multi-Frame Consensus Test Accuracy:** 62.36%
* **Consensus Accuracy Gain:** +1.12% absolute gain
* **P95 Voting Latency:** 0.55 ms
* **Resolution Policy:** Minimum support count >= 2 required for RESOLVED status.

---

## 5. Corrected True Tensor Batching Benchmark (50 Iterations)

| Batch Size | Mean Batch Latency (ms) | P50 Batch Latency (ms) | P95 Batch Latency (ms) | Mean Amortized / Crop (ms) | Throughput (crops/sec) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **B=1** | 9.84 ms | 9.70 ms | 11.40 ms | 9.84 ms | 101.62 crops/s |
| **B=2** | 18.30 ms | 16.12 ms | 29.44 ms | 9.15 ms | 109.26 crops/s |
| **B=4** | 32.60 ms | 30.89 ms | 46.31 ms | 8.15 ms | 122.70 crops/s |
| **B=8** | 101.77 ms | 98.74 ms | 126.52 ms | 12.72 ms | 78.61 crops/s |

---

## 6. Live Multi-Camera Stream Validation (Anonymized)
* **Cameras Tested:** 3 live feeds (HLS/HTTPS)
* **Total Frames Processed:** 60 frames
* **Vehicles Tracked:** 18
* **Tracks with Plate Observations:** 3
* **Tracks with >=2 Hypotheses:** 1
* **Tracks with Stable Consensus:** 0 (Distant low-resolution CCTV crops correctly marked as CANDIDATE / LOW_CONFIDENCE rather than hallucinating false strings)

---

## 7. Optimization Principles
* **Crop Deduplication:** Deduplication avoids exact repeated crop inference on stationary/idling vehicles.
* **Quality Filtering:** Quality filtering avoids processing extremely small/invalid crops.

---

## 8. Reproducibility
* **Model Setup Command:** python -m 04_plate_ocr.scripts.setup_ocr_models
* **Test Single Crop:** python -m 04_plate_ocr.scripts.test_crop <image_path>
* **Full Evaluation:** python -m 04_plate_ocr.training.evaluate
