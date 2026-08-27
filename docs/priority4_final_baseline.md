# SentinelTrack Priority 4 Final Baseline Documentation

**Date:** 2026-08-28  
**Module:** Priority 4 — License Plate OCR Subsystem  
**Status:** **BASELINE FROZEN — READY FOR PRIORITY 5**

---

## 1. Dataset & Provenance
* **Dataset:** zenitsu09/indian-number-plate
* **License Status:** LICENSE_UNVERIFIED (Retained as development/evaluation benchmark; audited via Hugging Face API with no explicit license key)
* **Total Real Plate Crops:** 1,707 images
* **Unique Physical Registrations:** 963 unique plate identities
* **Split Counts (Zero Leakage):**
  * **Train:** 1,382 crops (675 unique identities)
  * **Validation:** 147 crops (144 unique identities) [100% REAL ONLY]
  * **Test (Locked):** 178 crops (144 unique identities) [100% REAL ONLY]
* **Leakage Verification:** 0% hash overlap and 0 shared identities across partitions.

---

## 2. Production OCR Engine Selection
* **Selected Engine:** PP-OCRv5_mobile_rec (PP-LCNet + CTC greedy decoding)
* **Inference Provider:** ONNX Runtime CPU (8 threads) (CUDA_PROVIDER_UNAVAILABLE)
* **Batch Size:** B=2 (Peak throughput: 113.66 crops/sec, 8.80 ms amortized latency per crop)

---

## 3. Quantitative Evaluation Summary

| Split / Metric | Production PP-OCRv5_mobile_rec | Baseline EasyOCR_detect_rec | Baseline EasyOCR_rec_only | Challenger PP-OCRv5_server_rec |
| :--- | :---: | :---: | :---: | :---: |
| **Val Exact Accuracy** | **61.90%** (91/147) | 8.16% | 4.76% | 61.90% |
| **Val Character Accuracy** | **82.44%** | 33.69% | 23.34% | 76.23% |
| **Val CER** | **0.1156** | 0.4875 | 0.4083 | 0.1592 |
| **Val P50 Latency** | **10.36 ms** | 17.75 ms | 12.66 ms | 432.56 ms |
| **Val Throughput** | **87.85 crops/s** | 47.57 crops/s | 63.77 crops/s | 2.34 crops/s |
| **Test Exact Accuracy (Locked)** | **57.30%** (102/178) | N/A | N/A | 53.37% |
| **Test Character Accuracy (Locked)** | **78.69%** | N/A | N/A | 75.84% |
| **Test CER (Locked)** | **0.1729** | N/A | N/A | 0.1747 |
| **Test P50 Latency** | **9.07 ms** | N/A | N/A | 407.92 ms |
| **Test Throughput** | **96.38 crops/s** | N/A | N/A | 2.35 crops/s |
| **Empty-Read Rate** | **0.00%** | 27.21% | 0.00% | 0.00% |

---

## 4. Multi-Frame Consensus Voting (Production Mobile)
* **Single-Frame Test Accuracy:** 61.24%
* **Multi-Frame Consensus Test Accuracy:** 62.36%
* **Consensus Accuracy Gain:** +1.12% absolute
* **P95 Voting Latency:** 0.55 ms
* **Resolution Policy:** Minimum support count >= 2 required for RESOLVED status.

---

## 5. Live Multi-Camera Stream Validation (Anonymized)
* **Cameras Tested:** 3 live feeds (HLS/HTTPS)
* **Total Frames Processed:** 60 frames
* **Vehicles Tracked:** 18
* **Tracks with Plate Observations:** 3
* **Tracks with >=2 Hypotheses:** 1
* **Tracks with Stable Consensus:** 0 (Distant low-resolution CCTV crops correctly marked as CANDIDATE / LOW_CONFIDENCE rather than hallucinating false strings)

---

## 6. Reproducibility
* **Model Setup Command:** python -m 04_plate_ocr.scripts.setup_ocr_models
* **Test Single Crop:** python -m 04_plate_ocr.scripts.test_crop <image_path>
* **Full Evaluation:** python -m 04_plate_ocr.training.evaluate
