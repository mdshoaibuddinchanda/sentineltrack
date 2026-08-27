# SentinelTrack Performance & Scale Backlog (P11)

**Date:** 2026-08-28  
**Scope:** Roadmap for multi-node distribution, hardware acceleration, and 80,000-camera statewide scaling.

---

## 1. Edge & Multi-Camera Ingestion Architecture
* **Hardware Video Decoding:** Integrate NVIDIA DeepStream / NVDEC (via PyAV or FFmpeg HWACCEL) to offload H.264/H.265 RTSP decoding from CPU to dedicated GPU silicon.
* **Per-Camera Ingestion Workers:** Isolated worker processes per RTSP stream with IPC ring buffers preventing any single stream failure from impacting neighboring cameras.
* **Dynamic Frame Sampling:** Automatically drop analytical frame rate during low-traffic periods and increase to full cadence when active vehicles enter the FOV.

---

## 2. Deep Learning & Tensor Acceleration
* **TensorRT FP16 / INT8 Quantization:** Export YOLO11m (P1) and YOLO11s (P3) to TensorRT engines with calibration caches for 2x additional inference acceleration on datacenter GPUs (NVIDIA L4 / A10G / T4).
* **Multi-GPU Worker Scheduling:** Dynamic load-balancer distributing vehicle crops and OCR requests across available GPU devices.
* **Batched Micro-Queues:** Micro-batch scheduler grouping plate crops across concurrent cameras into Batches of 8 or 16 within a 15ms latency window.

---

## 3. Distributed Persistence & Statewide Search (80k Scale)
* **Redis In-Memory Candidate Cache:** Distributed in-memory cache for statewide watchlists (N >= 1,000,000) with sub-millisecond cluster hashing.
* **PostgreSQL Table Partitioning:** Partition vehicle_sightings and target_matches by date range (daily/weekly partitions) to maintain constant query performance over billions of rows.
* **Kafka Event Bus:** Decouple CV inference workers from database persistence workers via Apache Kafka event streaming.
