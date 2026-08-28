# SentinelTrack — Non-Blocking Performance & Engineering Backlog

## 1. Context & Purpose

This document catalogues genuine engineering optimizations, architectural scale improvements, and secondary feature enhancements that are **explicitly non-blocking for Hackathon Acceptance** but documented for future enterprise-grade scale deployment.

---

## 2. Component Backlog

### P0 — Foundation & Ingestion
* **Hardware Video Acceleration:** Add NVIDIA NVDEC hardware-accelerated decode (`h264_cuvid`, `hevc_cuvid`) via PyAV/FFmpeg for multi-hundred camera concurrency on dedicated GPU nodes.
* **Dynamic Stream Reconnection Mesh:** Implement exponential jittered reconnect backoff with DNS round-robin resolution.

### P1 — Vehicle Detection
* **TensorRT INT8 Quantization:** Export YOLOv8n to TensorRT engine with calibration dataset to achieve sub-millisecond per-frame inference on RTX/Tesla GPUs.
* **Adaptive Frame Skipping:** Skip detector inference on static backgrounds using fast optical flow or frame difference heuristics.

### P2 — Tracking
* **ByteTrack Low-Confidence Score Recovery:** Tune low-confidence threshold association matrix for occluded vehicles in dense urban congestion.
* **Appearance Feature Association:** Add lightweight 128-d ReID embedding extractor into track association cost matrix (P6 handoff).

### P3 — License Plate Detection
* **Specialized Vehicle Crop Augmentation:** Train custom YOLOv8n-plate model on Indian high-security registration plates (HSRP) with night-time IR glare.

### P4 — Plate OCR & Consensus
* **Edge-case Character Fine-Tuning:** Fine-tune CTC decoder language models specifically for Indian regional state prefixes (e.g. GJ, MH, DL, KA, UP).

### P5 — Target Matching & Watchlists
* **Distributed Exact Match Index:** Replace Python thread-safe in-memory cache with Redis/KeyDB cluster for horizontal multi-instance scaling across 1,000,000+ watchlist entries.
* **Approximate String Matching SIMD:** Implement AVX2/NEON SIMD Levenshtein distance calculations for sub-microsecond candidate scoring.

### P6 — Vehicle ReID (Deferred)
* **OSNet Appearance Embeddings:** Implement deep metric learning embedding extractor as an auxiliary feature when plate OCR confidence is degraded.

### P7 — Route Engine & GIS Trajectory
* **Road Network Snapping:** Integrate OpenStreetMap / Valhalla routing engine to snap raw camera-to-camera LineString trajectories onto physical road segments.
* **Spatial Trajectory Clustering:** Group recurring vehicle paths into frequent commute patterns and identify anomalous deviations.

### P8 — Backend REST API
* **Distributed Task Queue:** Migrate in-memory `AnalyticsWorker` to Celery / Redis Streams / Kafka when scaling across multiple GPU worker nodes.
* **FastAPI Response Caching:** Add Redis-backed HTTP caching for static camera catalog and historical route queries.

### P9 — Frontend Dashboard
* **WebGPU Map Rendering:** Utilize deck.gl / Mapbox GL GPU layers for real-time visualization of 10,000+ vehicle trajectories simultaneously.

### P10 — Security & RBAC
* **Full OIDC / JWT Auth:** Replace operator header placeholder with full Keycloak / Auth0 OAuth2 JWT token validation with role-based endpoint permissions (`SUPER_ADMIN`, `INVESTIGATOR`, `OPERATOR`, `AUDITOR`).
* **Cryptographic Tamper-Evident Audit Ledger:** Chain audit log records using SHA-256 Merkle trees.
