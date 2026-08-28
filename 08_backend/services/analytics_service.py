import asyncio
import importlib
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import torch

try:
    from ..config import get_backend_config
    from ..event_bus import get_event_bus, AlertCreatedEvent, SightingCreatedEvent
    from ..metrics import get_metrics_collector
except (ImportError, ValueError):
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    ev_m = importlib.import_module("08_backend.event_bus")
    get_event_bus, AlertCreatedEvent, SightingCreatedEvent = ev_m.get_event_bus, ev_m.AlertCreatedEvent, ev_m.SightingCreatedEvent
    get_metrics_collector = importlib.import_module("08_backend.metrics").get_metrics_collector

logger = logging.getLogger("sentineltrack.analytics")


class AnalyticsWorker:
    """
    Multi-camera analytics worker with genuine micro-batch inference scheduler.
    Orchestrates:
      FramePacket batch -> P1 Vehicle Detection (YOLO11m)
      -> P2 ByteTrack Multi-Camera Tracker
      -> P3 Plate Detection & Observation Pipeline (YOLO11s-plate)
      -> P4 PP-OCRv5 Consensus Voting Pipeline (min_support_count=2)
      -> P5 Target Matching & Event Timing Propagation
      -> EventBus & Telemetry.
    """

    def __init__(self, config=None, event_bus=None, metrics_collector=None):
        self.config = config or get_backend_config().analytics_worker
        self.event_bus = event_bus or get_event_bus()
        self.metrics = metrics_collector or get_metrics_collector()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        # RLock to prevent recursive deadlocks between start() and _lazy_init_models()
        self._lock = threading.RLock()
        self._camera_queues: Dict[str, Any] = {}

        # Pipeline modules
        self._detector = None
        self._tracker_registry = None
        self._plate_detector = None
        self._plate_pipeline = None
        self._ocr_pipeline = None
        self._target_pipeline = None

    def _lazy_init_models(self):
        with self._lock:
            if self._detector is not None:
                return

            cuda_available = torch.cuda.is_available()
            use_half = bool(self.config.enable_cuda_fp16 and cuda_available)
            device = "cuda" if cuda_available else "cpu"
            logger.info(f"Initializing AnalyticsWorker pipeline (device={device}, half={use_half})...")

            # 1. P1 Vehicle Detector (YOLO11m)
            try:
                p1_mod = importlib.import_module("01_vehicle_detection.detector")
                self._detector = p1_mod.VehicleDetector(half=use_half, device=device)
            except Exception as e:
                logger.exception(f"Failed to initialize P1 VehicleDetector: {e}")
                self.metrics.inc_errors()
                self._detector = None

            # 2. P2 Tracker Registry (ByteTrack)
            try:
                p2_mod = importlib.import_module("02_tracking.tracker")
                self._tracker_registry = p2_mod.CameraTrackerRegistry()
            except Exception as e:
                logger.exception(f"Failed to initialize P2 CameraTrackerRegistry: {e}")
                self.metrics.inc_errors()
                self._tracker_registry = None

            # 3. P3 Plate Detector (YOLO11s-plate) & PlateDetectionPipeline
            try:
                p3_det_mod = importlib.import_module("03_plate_detection.detector")
                p3_pipe_mod = importlib.import_module("03_plate_detection.pipeline")
                self._plate_detector = p3_det_mod.PlateDetector(half=use_half, device=device)
                self._plate_pipeline = p3_pipe_mod.PlateDetectionPipeline(plate_detector=self._plate_detector)
            except Exception as e:
                logger.exception(f"Failed to initialize P3 PlateDetectionPipeline: {e}")
                self.metrics.inc_errors()
                self._plate_detector = None
                self._plate_pipeline = None

            # 4. P4 Plate OCR Pipeline (PP-OCRv5 Mobile ONNX + Consensus Voter with frozen min_support_count=2)
            try:
                p4_pipe_mod = importlib.import_module("04_plate_ocr.pipeline")
                p4_rec_mod = importlib.import_module("04_plate_ocr.recognizers")
                p4_voter_mod = importlib.import_module("04_plate_ocr.voting")

                recognizer = p4_rec_mod.get_recognizer(engine_name="ppocr_mobile", device=device)
                voter = p4_voter_mod.MultiFramePlateVoter(min_crop_quality=0.20, min_support_count=2)
                self._ocr_pipeline = p4_pipe_mod.PlateOCRPipeline(recognizer=recognizer, voter=voter)
            except Exception as e:
                logger.exception(f"Failed to initialize P4 PlateOCRPipeline: {e}")
                self.metrics.inc_errors()
                self._ocr_pipeline = None

            # 5. P5 Target Matching Pipeline
            try:
                p5_mod = importlib.import_module("05_target_matching.pipeline")
                tgt_svc_mod = importlib.import_module("08_backend.services.target_service")
                shared_wm = tgt_svc_mod.get_shared_watchlist_manager()
                self._target_pipeline = p5_mod.TargetMatchingPipeline(watchlist_manager=shared_wm)
            except Exception as e:
                logger.exception(f"Failed to initialize P5 TargetMatchingPipeline: {e}")
                self.metrics.inc_errors()
                self._target_pipeline = None

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._lazy_init_models()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="SentinelAnalyticsWorker")
            self._thread.start()
            logger.info("SentinelTrack AnalyticsWorker started successfully.")

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            logger.info("SentinelTrack AnalyticsWorker stopped.")

    def is_running(self) -> bool:
        with self._lock:
            return self._running and self._thread is not None and self._thread.is_alive()

    def enqueue_frame(self, frame_packet: Any) -> bool:
        """Enqueues a FramePacket into the per-camera bounded queue with latest-frame drop policy."""
        self._lazy_init_models()
        cid = frame_packet.camera_id
        with self._lock:
            if cid not in self._camera_queues:
                bounded_queue_mod = importlib.import_module("00_foundation.streams.bounded_stream_queue")
                self._camera_queues[cid] = bounded_queue_mod.BoundedStreamQueue(maxsize=self.config.queue_max_size)

            bq = self._camera_queues[cid]

        ok = bq.put_latest(frame_packet)
        self.metrics.inc_frames(ingested=1, dropped=0 if ok else 1)
        return ok

    def process_batch(self, packets: List[Any]) -> List[Dict[str, Any]]:
        """
        Genuine Micro-Batch Processing across multi-camera FramePackets.
        Executes P1 batch detection -> P2 tracking -> P3 Plate Pipeline -> P4 OCR consensus -> P5 matching.
        """
        if not packets:
            return []

        self._lazy_init_models()
        if not self._detector or not self._tracker_registry:
            logger.warning("Analytics models unavailable for batch processing.")
            return [{"status": "MODELS_UNAVAILABLE", "camera_id": getattr(p, "camera_id", "unknown")} for p in packets]

        results = []
        try:
            # 1. P1 Batch Vehicle Detection
            batch_dets = self._detector.detect_batch(packets)
            total_dets = sum(len(d) for d in batch_dets)
            self.metrics.inc_analytics(vehicles=total_dets)

            # 2. P2 Tracker Update + P3 Plate Pipeline per packet
            for p_idx, packet in enumerate(packets):
                dets = batch_dets[p_idx] if p_idx < len(batch_dets) else []
                tracker = self._tracker_registry.get_tracker(packet.camera_id)
                tracks = tracker.update(packet, dets)

                if tracks and self._plate_pipeline:
                    plate_observations = self._plate_pipeline.process(packet, tracks)
                    self.metrics.inc_analytics(plates=len(plate_observations))

                    # 3. Feed Plate Observations into P4 OCR Pipeline
                    for obs in plate_observations:
                        if self._ocr_pipeline:
                            ix1, iy1 = int(round(obs.x1)), int(round(obs.y1))
                            ix2, iy2 = int(round(obs.x2)), int(round(obs.y2))
                            fh, fw = packet.frame.shape[:2]
                            ix1, iy1 = max(0, ix1), max(0, iy1)
                            ix2, iy2 = min(fw, ix2), min(fh, iy2)

                            if ix2 > ix1 and iy2 > iy1:
                                plate_crop = packet.frame[iy1:iy2, ix1:ix2]
                                if plate_crop is not None and plate_crop.size > 0:
                                    self._ocr_pipeline.process_observation(obs, plate_crop)
                                    self.metrics.inc_analytics(ocr=1)

                    # 4. Multi-Frame Track Consensus & P5 Target Matching
                    for trk in tracks:
                        if self._ocr_pipeline:
                            track_ocr = self._ocr_pipeline.get_track_result(
                                packet.camera_id, packet.stream_epoch, trk.track_id
                            )
                            if track_ocr and track_ocr.best_text:
                                # Propagate UTC event-timing contract
                                track_ocr.event_time_utc = packet.event_time_utc
                                track_ocr.event_time_source = packet.event_time_source
                                track_ocr.event_time_quality = packet.event_time_quality
                                track_ocr.ingest_time_utc = packet.ingest_time_utc

                                # 5. P5 Target Matching Pipeline
                                if self._target_pipeline:
                                    cands, alerts, sighting = self._target_pipeline.process_track_ocr_result(track_ocr)
                                    if sighting:
                                        self.metrics.inc_analytics(sightings=1)
                                        self._dispatch_event(SightingCreatedEvent(payload={
                                            "sighting_id": sighting.sighting_id,
                                            "camera_id": sighting.camera_id,
                                            "registration": sighting.registration_candidate,
                                            "match_score": sighting.match_score,
                                            "match_class": sighting.match_class.value if hasattr(sighting.match_class, "value") else str(sighting.match_class)
                                        }))

                                    for alt in alerts:
                                        self.metrics.inc_analytics(alerts=1)
                                        self._dispatch_event(AlertCreatedEvent(payload={
                                            "alert_id": alt.alert_id,
                                            "camera_id": alt.camera_id,
                                            "registration": alt.registration,
                                            "severity": alt.severity.value if hasattr(alt.severity, "value") else str(alt.severity),
                                            "match_score": alt.match_score
                                        }))

                results.append({"status": "PROCESSED", "camera_id": packet.camera_id, "pts_ms": packet.pts_ms})

        except Exception as e:
            logger.exception(f"Error during analytics batch execution: {e}")
            self.metrics.inc_errors()
            for packet in packets:
                results.append({"status": "ERROR", "camera_id": getattr(packet, "camera_id", "unknown"), "error": str(e)})

        return results

    def process_single_frame(self, frame_packet: Any) -> Dict[str, Any]:
        """Wrapper for single-frame processing delegating to micro-batch processor."""
        batch_res = self.process_batch([frame_packet])
        return batch_res[0] if batch_res else {"status": "NO_RESULT"}

    def _dispatch_event(self, event: Any):
        """Dispatches an event asynchronously to the global event bus without blocking inference."""
        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.event_bus.publish(event))
            except RuntimeError:
                threading.Thread(target=lambda: asyncio.run(self.event_bus.publish(event)), daemon=True).start()
        except Exception as e:
            logger.exception(f"Failed to dispatch event to EventBus: {e}")
            self.metrics.inc_errors()

    def _worker_loop(self):
        batch_size = max(1, self.config.micro_batch_size)
        wait_seconds = max(0.001, self.config.max_batch_wait_ms / 1000.0)

        while self._running:
            with self._lock:
                active_cameras = list(self._camera_queues.keys())
            self.metrics.set_camera_workers(len(active_cameras))

            packets_to_process: List[Any] = []

            for cid in active_cameras:
                with self._lock:
                    bq = self._camera_queues.get(cid)
                if not bq or bq.qsize() == 0:
                    continue

                try:
                    packet = bq.get(block=False)
                    packets_to_process.append(packet)
                    if len(packets_to_process) >= batch_size:
                        break
                except Exception:
                    pass

            if packets_to_process:
                self.process_batch(packets_to_process)
            else:
                time.sleep(wait_seconds)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            queue_stats = {}
            for cid, bq in self._camera_queues.items():
                queue_stats[cid] = bq.get_metrics()

            return {
                "running": self._running,
                "active_camera_count": len(self._camera_queues),
                "queues": queue_stats,
                "models_loaded": {
                    "detector": self._detector is not None,
                    "tracker": self._tracker_registry is not None,
                    "plate_detector": self._plate_detector is not None,
                    "plate_pipeline": self._plate_pipeline is not None,
                    "ocr_pipeline": self._ocr_pipeline is not None,
                    "target_pipeline": self._target_pipeline is not None
                }
            }


_GLOBAL_ANALYTICS_WORKER: Optional[AnalyticsWorker] = None
_WORKER_LOCK = threading.Lock()


def get_analytics_worker() -> AnalyticsWorker:
    global _GLOBAL_ANALYTICS_WORKER
    with _WORKER_LOCK:
        if _GLOBAL_ANALYTICS_WORKER is None:
            _GLOBAL_ANALYTICS_WORKER = AnalyticsWorker()
        return _GLOBAL_ANALYTICS_WORKER
