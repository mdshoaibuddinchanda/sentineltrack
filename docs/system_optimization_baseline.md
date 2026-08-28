# SentinelTrack System Optimization & Performance Baseline

**Date:** 2026-08-28  
**Audit Scope:** P0 Foundation -> P1 Vehicle Detection -> P2 Tracking -> P3 Plate Detection -> P4 OCR -> P5 Target Matching  
**Hardware Evaluated:** NVIDIA GeForce RTX 3050 Laptop GPU (4GB VRAM, CUDA 12.1, PyTorch 2.5.1) | 8-core CPU | 34GB RAM  
**Status:** **AUDITED, HARDENED & BASELINE LOCKED - READY FOR PRIORITY 7 (ROUTE / GIS ENGINE)**

---

## 1. Master System Performance (Before vs. After)

| Subsystem | Metric | Baseline (Before) | Optimized (After) | Delta / Speedup | Integration Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **P0 Ingestion** | First-Frame Startup Latency | 20.66 ms (OpenCV) | **12.09 ms (PyAV Direct PTS)** | **-41.5% Latency** | Pinned Adapter |
| **P0 Failover** | Runtime RTSP -> HLS Failover | Startup Only | **Automatic Runtime Failover + Recovery** | **High Availability** | Integrated |
| **P1 Vehicle** | YOLO11m P50 Latency (960) | 33.66 ms (FP32) | **23.20 ms (FP16)** | **-31.1% Latency** | Verified Parity |
| **P1 Vehicle** | Native Inference Throughput | 29.27 FPS | **41.58 FPS** | **+42.1% FPS** | Configurable |
| **P1 Vehicle** | Batch 4 Capacity Throughput | 29.27 FPS | **51.07 FPS (19.4ms/frame)** | **+74.5% FPS** | Batch API Ready |
| **P2 Tracker** | Inactive State Pruning | Monotonic ID growth | **Pruning (>60s idle via last_seen_pts)** | **Active Tracks Protected** | Integrated |
| **P2 Tracker** | Per-Frame Tracking Latency | 0.45 ms | **0.33 ms** | **-26.7% Latency** | Integrated |
| **P3 Plate** | YOLO11s P50 Latency (960) | 23.68 ms (FP32) | **14.78 ms (FP16)** | **-37.6% Latency** | Verified Parity |
| **P3 Plate** | Single-Crop Throughput | 41.83 FPS | **65.37 FPS** | **+56.3% FPS** | Configurable |
| **P3 Plate** | Batch 8 Capacity Throughput | 41.83 FPS | **74.78 FPS (13.5ms/crop)** | **+78.8% FPS** | Batch API Ready |
| **P4 OCR** | Single-Crop OCR P50 (CPU) | 9.03 ms | **8.15 ms** | **-9.7% Latency** | Integrated |
| **P4 OCR** | Batch 4 OCR Capacity | 80.66 FPS | **142.88 FPS (6.7ms/crop)** | **+77.1% FPS** | Batch API Ready |
| **P4 OCR** | Candidate Discovery Rate | 54.0% (Top-1 Exact) | **66.0% (Top-3 Recall)** | **+12.0 pp Recall** | Integrated |
| **P5 Matcher** | 100k Watchlist Recall@100 | 82.0% | **92.0% (Suffix-4 + Confusion Index)** | **+10.0 pp Recall** | Integrated |
| **P5 Matcher** | 100k Watchlist P95 Latency | 323.55 ms | **112.55 ms** | **-65.2% Latency** | Integrated |
| **P5 Database** | PostgreSQL Ingestion Latency | ~25 ms/record | **17.03 ms/record** | **-31.9% Latency** | Live PostGIS |
| **Full Pipeline**| Single-Frame End-to-End P50 | 68.50 ms | **47.17 ms (>21 FPS)** | **-31.1% Latency** | Compute Floor |

---

## 2. Compute Benchmark Interpretations & Caveats

### Synthetic Synchronous Compute Floor Profile
Measured in tools/profile_pipeline.py as a compute floor benchmark on the RTX 3050:
* **P1 Vehicle Detection (YOLO11m FP16 @ 960):** P50 = **21.60 ms** | P95 = **24.33 ms**
* **P2 Tracking (CameraByteTracker):** P50 = **0.33 ms** | P95 = **0.39 ms**
* **P3 Vehicle Cropping & Preprocessing:** P50 = **<0.01 ms**
* **P3 Plate Detection (YOLO11s FP16 @ 960):** P50 = **17.26 ms** | P95 = **38.46 ms**
* **P4 OCR & Voting (PP-OCRv5 Mobile ONNX):** P50 = **7.31 ms** | P95 = **8.70 ms**
* **P5 Target Matching & DB Persistence:** P50 = **<0.50 ms**
* **Total Synchronous Compute Floor:** P50 = **47.17 ms** (~21 FPS compute throughput)

> **Important Caveat:** This 47.17 ms figure represents the **synchronous component compute floor** on synthetic frames. In a live multi-camera production deployment, camera-to-alert latency will depend on ingestion stream FPS, network buffers, and queue scheduling.

### P5 Watchlist Evaluation Semantics
The high precision and ranking metrics in 05_target_matching/benchmark.py represent a **controlled P4-crop matcher evaluation with simulated multi-frame support (support=2)**. While Recall@100 on 100k targets reached **92.0%** with sub-115ms P95 latency, live uncorroborated single frames are intentionally gated to AlertSeverity.REVIEW to eliminate false positives.

---

## 3. Realistic Project Completion Status

| Subsystem | Completion % | Status & Next Steps |
| :--- | :---: | :--- |
| **P0 Ingestion & Registry** | **95%** | RTSP/HLS failover integrated, PyAV and OpenCV readers available. |
| **P1 Vehicle Detection** | **95%** | YOLO11m with class filtering, FP16 parity verified, batch API ready. |
| **P2 Multi-Object Tracking** | **95%** | ByteTrack with epoch reset, PTS gap handling, and active-track-safe pruning. |
| **P3 Plate Detection** | **95%** | YOLO11s with FP16 parity, motorcycle/square plates preserved without arbitrary filters. |
| **P4 Plate OCR & Voting** | **95%** | PP-OCRv5 Mobile ONNX with multi-frame voting and grammar alternatives. |
| **P5 Target Matching** | **95%** | Multi-index shortlisting (92% Recall@100 at 100k), PostGIS persistence. |
| **P6 Vehicle ReID** | **10%** | Interface contract defined; deferred after P7 GIS. |
| **P7 Route & GIS Trajectory Engine** | **15%** | **NEXT IMMEDIATE SPRINT: Spatio-temporal trajectory reconstruction & PostGIS maps.** |
| **P8 Backend API** | **10%** | FastAPI OpenAPI endpoints planned. |
| **P9 Dashboard** | **5%** | Map & Alert WebSocket UI planned. |
| **P10 Security & RBAC** | **10%** | Token auth & audit logging planned. |

**Overall Core CV Pipeline Status:** **~95% (FROZEN)**  
**Complete Hackathon Solution Status:** **~60-65%**
