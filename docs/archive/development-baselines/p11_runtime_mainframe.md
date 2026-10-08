# SentinelTrack Mainframe Runtime Architecture Map (Priority 11)

## End-to-End Pipeline Execution Trace

```
[1. Stream Sources] (RTSP / HLS / Simulated Video)
        │
        ▼ (RTSPReader / PyAVStreamReader) [00_foundation/streams/]
[2. FramePacket Ingestion] (camera_id, pts_ms, frame, stream_epoch, event_time_utc)
        │
        ▼ (StreamSupervisor / Adaptive Base+Burst Sampler) [11_scale_deployment/supervisor.py]
[3. Fair Bounded Multi-Camera Queues] (BoundedStreamQueue per camera, stale frame drops)
        │
        ▼ (Fair Batch Scheduler: round-robin / max-wait micro-batching)
[4. AnalyticsWorker / GPU Inference Engine] [08_backend/services/analytics_service.py]
        │
        ├──▶ P1: YOLO11m Vehicle Detection (torch.inference_mode(), batch inference)
        │       [01_vehicle_detection/detector.py]
        │
        ├──▶ P2: ByteTrack Multi-Camera Tracker (identity = camera_id + stream_epoch + track_id)
        │       [02_tracking/tracker.py]
        │
        ├──▶ P3: Plate Detection & Observation (YOLO11s-plate crop construction)
        │       [03_plate_detection/pipeline.py]
        │
        ├──▶ P4: PP-OCRv5 Mobile ONNX OCR & Multi-Frame Consensus Voting (min_support_count=2)
        │       [04_plate_ocr/pipeline.py, 04_plate_ocr/voting.py]
        │
        └──▶ P5: Target Matching & Event Timing Propagation
                [05_target_matching/pipeline.py, 05_target_matching/watchlist.py]
                        │
                        ▼ (PostgreSQL / PostGIS Authoritative Storage via Connection Pool)
[5. Persistence & Event Bus] (Sightings, Alerts, Targets, Audit Events)
        │       [00_foundation/registry/database.py, 05_target_matching/repository.py]
        │
        ▼ (Global In-Memory EventBus / PostgreSQL LISTEN/NOTIFY Bridge) [11_scale_deployment/event_bridge.py]
[6. WebSocket Broadcast Engine] (run_authorized_websocket, topic filters, bounded client queues)
        │       [08_backend/websocket/manager.py, 08_backend/websocket/routes.py]
        │
        ▼ (JSON over WebSocket / HTTPS API)
[7. P9 Dashboard & P7 Route Engine] (Real-time alert triage, camera deep-linking, trajectory GIS)
        [09_dashboard/src/, 07_route_engine/]
```

---

## Detailed Component & Interface Inventory

| Stage | Source Code Location | Class / Function | Input Type | Output Type | Queue / Buffer | Failure / Recovery Handling | Telemetry / Metric |
|---|---|---|---|---|---|---|---|
| **1. Stream Ingestion** | `00_foundation/streams/reader.py` | `RTSPReader` / `PyAVStreamReader` | RTSP/TCP or HLS URL | Raw decoded BGR video frames + PTS | VideoCapture / PyAV decode buffer | 2s→30s exponential backoff, automatic HLS failover, stream_epoch increment on discontinuity | `stream_connects`, `stream_errors`, `decode_fps` |
| **2. Frame Packetization** | `00_foundation/streams/models.py` | `FramePacket` | Raw frame + PTS + timestamp | `FramePacket` dataclass | In-memory packet | Wall-clock PTS preservation, UTC event-time assignment | `frames_ingested`, `pts_drift_ms` |
| **3. Stream Supervision & Sampling** | `11_scale_deployment/supervisor.py` | `StreamSupervisor` | Camera Registry records | Sampled `FramePacket` streams | Per-camera `BoundedStreamQueue` (maxsize=10) | Periodic camera health probing, automatic reconnection, adaptive Base (1 FPS) + Burst (5 FPS) dynamic rate | `cameras_active`, `cameras_degraded`, `sampled_fps` |
| **4. Fair Scheduling** | `11_scale_deployment/scheduler.py` | `FairStreamScheduler` | Multi-camera bounded queues | Micro-batch `List[FramePacket]` (B=1..8) | Micro-batch assembler (max wait ≤ 10ms) | Drops frames exceeding `max_staleness_ms` (1000ms), round-robin fairness across camera queues | `queue_age_ms`, `frames_dropped_stale`, `frames_dropped_queue`, `batch_size` |
| **5. P1 Vehicle Detection** | `01_vehicle_detection/detector.py` | `VehicleDetector.detect_batch()` | `List[FramePacket]` (B images) | `List[List[Detection]]` | GPU VRAM buffer | Catches CUDA OOM, falls back to smaller batch or CPU; confidence threshold filtering | `p1_latency_ms`, `vehicles_detected` |
| **6. P2 Vehicle Tracking** | `02_tracking/tracker.py` | `CameraTrackerRegistry.get_tracker()` | `FramePacket` + `List[Detection]` | `List[TrackedVehicle]` | Kalman state memory | Tracker per camera_id; resets on stream_epoch change | `p2_latency_ms`, `active_tracks` |
| **7. P3 Plate Detection** | `03_plate_detection/pipeline.py` | `PlateDetectionPipeline.process()` | `FramePacket` + `List[TrackedVehicle]` | `List[PlateObservation]` | Vehicle crop bounding boxes | Crop boundary validation against image dimensions | `p3_latency_ms`, `plates_detected` |
| **8. P4 OCR & Voting** | `04_plate_ocr/pipeline.py` | `PlateOCRPipeline.process_observation()` | `PlateObservation` + BGR plate crop | `TrackOCRResult` | Multi-frame consensus accumulator | Min crop quality filter (0.20), consensus voting across frames (`min_support_count=2`) | `p4_latency_ms`, `ocr_hypotheses` |
| **9. P5 Target Matching** | `05_target_matching/pipeline.py` | `TargetMatchingPipeline.process_track_ocr_result()` | `TrackOCRResult` | `Tuple[List[Cand], List[Alert], Sighting]` | Fast in-memory state & exact index | Deterministic OCR confusion candidate shortlisting, exact matching score calculation | `p5_latency_ms`, `target_matches`, `alerts_generated` |
| **10. Persistence & DB Pool** | `00_foundation/registry/database.py`, `05_target_matching/repository.py` | Bounded Connection Pool & Repositories | Sighting / Alert / Target entities | Committed DB rows | Bounded thread-safe connection pool | Automatic rollback on exception, fail-closed audit log enforcement | `db_query_time_ms`, `db_pool_active`, `db_errors` |
| **11. Event Dispatching** | `08_backend/event_bus.py`, `11_scale_deployment/event_bridge.py` | `EventBus` / `PostgresEventBridge` | Domain Events (`AlertCreatedEvent`, `SightingCreatedEvent`) | Asynchronous broadcast | Async bounded queue / Postgres `NOTIFY` | Non-blocking background worker dispatch; tolerates duplicate notifications | `events_published`, `events_lost` |
| **12. WebSocket Security & Push** | `08_backend/websocket/manager.py`, `08_backend/websocket/routes.py` | `ConnectionManager.broadcast()` | Domain Events | JSON WebSocket text messages | Per-client bounded queue (`maxsize=256`) | Drops oldest message for slow clients; disconnects on role downgrade (4403) or session expiry (4401) | `ws_active_clients`, `ws_messages_sent`, `ws_queue_drops` |
| **13. Dashboard & Route Engine** | `09_dashboard/src/`, `07_route_engine/` | React UI & `RouteService` | WebSocket events & REST APIs | Live visual control-room UI | UI state store & cache | Auto-reconnect with exponential backoff; cached trajectory calculations | `http_latency_ms`, `route_calc_time_ms` |
