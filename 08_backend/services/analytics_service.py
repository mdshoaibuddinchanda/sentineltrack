import asyncio
import importlib
import threading
import time
from typing import Any, Dict, List, Optional
import numpy as np

try:
    from ..config import get_backend_config
    from ..event_bus import get_event_bus, AlertCreatedEvent, SightingCreatedEvent
    from ..metrics import get_metrics_collector
except (ImportError, ValueError):
    get_backend_config = importlib.import_module("08_backend.config").get_backend_config
    ev_m = importlib.import_module("08_backend.event_bus")
    get_event_bus, AlertCreatedEvent, SightingCreatedEvent = ev_m.get_event_bus, ev_m.AlertCreatedEvent, ev_m.SightingCreatedEvent
    get_metrics_collector = importlib.import_module("08_backend.metrics").get_metrics_collector


class AnalyticsWorker:
    """
    Multi-camera analytics worker with bounded micro-batch inference scheduler.
    Orchestrates: FramePacket -> P1 Vehicle Detection -> P2 Tracking -> P3 Plate Detection -> P4 OCR -> P5 Target Matching -> EventBus.
    """

    def __init__(self, config=None, event_bus=None, metrics_collector=None):
        self.config = config or get_backend_config().analytics_worker
        self.event_bus = event_bus or get_event_bus()
        self.metrics = metrics_collector or get_metrics_collector()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._camera_queues: Dict[str, Any] = {}

        # Pipeline modules
        self._detector = None
        self._tracker_registry = None
        self._plate_detector = None
        self._plate_recognizer = None
        self._target_pipeline = None

    def _lazy_init_models(self):
        with self._lock:
            if self._detector is not None:
                return

            # P1 Detector
            try:
                p1_mod = importlib.import_module("01_vehicle_detection.detector")
                self._detector = p1_mod.VehicleDetector()
            except Exception:
                self._detector = None

            # P2 Tracker Registry
            try:
                p2_mod = importlib.import_module("02_tracking.tracker")
                self._tracker_registry = p2_mod.CameraTrackerRegistry()
            except Exception:
                self._tracker_registry = None

            # P3 Plate Detector
            try:
                p3_mod = importlib.import_module("03_plate_detection.detector")
                self._plate_detector = p3_mod.PlateDetector()
            except Exception:
                self._plate_detector = None

            # P4 Plate Recognizer / Consensus
            try:
                p4_mod = importlib.import_module("04_plate_ocr.recognizer")
                self._plate_recognizer = p4_mod.PlateRecognizer()
            except Exception:
                self._plate_recognizer = None

            # P5 Target Matching Pipeline
            try:
                p5_mod = importlib.import_module("05_target_matching.pipeline")
                self._target_pipeline = p5_mod.TargetMatchingPipeline()
            except Exception:
                self._target_pipeline = None

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._lazy_init_models()
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="SentinelAnalyticsWorker")
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def is_running(self) -> bool:
        return self._running

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

    def process_single_frame(self, frame_packet: Any) -> Dict[str, Any]:
        """Synchronous single-frame processing for direct API evaluation and testing."""
        self._lazy_init_models()
        if not self._detector or not self._tracker_registry:
            return {"status": "MODELS_UNAVAILABLE", "detections": 0, "tracks": 0, "alerts": 0}

        # 1. P1 Vehicle Detection
        dets = self._detector.detect(frame_packet)
        self.metrics.inc_analytics(vehicles=len(dets))

        # 2. P2 Tracking
        tracker = self._tracker_registry.get_tracker(frame_packet.camera_id)
        tracks = tracker.update(frame_packet, dets)

        alerts_generated = []
        sightings_persisted = []

        # 3. P3 Plate Detection & P4 OCR for active tracks
        for trk in tracks:
            if not self._plate_detector or not self._plate_recognizer:
                continue

            # Extract vehicle crop
            x1, y1, x2, y2 = [int(v) for v in trk.current_box]
            h, w = frame_packet.frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            v_crop = frame_packet.frame[y1:y2, x1:x2]
            plates = self._plate_detector.detect(v_crop)
            self.metrics.inc_analytics(plates=len(plates))

            if not plates:
                continue

            p_box = plates[0].box
            px1, py1, px2, py2 = [int(v) for v in p_box]
            vh, vw = v_crop.shape[:2]
            px1, py1 = max(0, px1), max(0, py1)
            px2, py2 = min(vw, px2), min(vh, py2)
            if px2 <= px1 or py2 <= py1:
                continue

            plate_crop = v_crop[py1:py2, px1:px2]
            ocr_res = self._plate_recognizer.recognize(plate_crop)
            self.metrics.inc_analytics(ocr=1)

            if not ocr_res or not ocr_res.text:
                continue

            # Multi-frame track consensus result
            p4_models = importlib.import_module("04_plate_ocr.models")
            track_ocr = p4_models.TrackOCRResult(
                camera_id=frame_packet.camera_id,
                track_id=trk.track_id,
                stream_epoch=frame_packet.stream_epoch,
                first_pts_ms=trk.first_seen_pts_ms,
                last_pts_ms=trk.last_seen_pts_ms,
                best_text=ocr_res.text,
                confidence=ocr_res.confidence,
                support_count=trk.age_frames,
                total_hypotheses=trk.age_frames,
                status="RESOLVED"
            )
            track_ocr.event_time_utc = frame_packet.event_time_utc
            track_ocr.event_time_source = frame_packet.event_time_source
            track_ocr.event_time_quality = frame_packet.event_time_quality
            track_ocr.ingest_time_utc = frame_packet.ingest_time_utc

            # 4. P5 Target Matching
            if self._target_pipeline:
                cands, alerts, sighting = self._target_pipeline.process_track_ocr_result(track_ocr)
                if sighting:
                    sightings_persisted.append(sighting)
                    self.metrics.inc_analytics(sightings=1)
                    # Publish sighting event
                    try:
                        asyncio.run(self.event_bus.publish(SightingCreatedEvent(payload={
                            "sighting_id": sighting.sighting_id,
                            "camera_id": sighting.camera_id,
                            "registration": sighting.registration_candidate,
                            "match_score": sighting.match_score,
                            "match_class": sighting.match_class.value if hasattr(sighting.match_class, "value") else str(sighting.match_class)
                        })))
                    except Exception:
                        pass

                for alt in alerts:
                    alerts_generated.append(alt)
                    self.metrics.inc_analytics(alerts=1)
                    # Publish alert event
                    try:
                        asyncio.run(self.event_bus.publish(AlertCreatedEvent(payload={
                            "alert_id": alt.alert_id,
                            "camera_id": alt.camera_id,
                            "registration": alt.registration,
                            "severity": alt.severity.value if hasattr(alt.severity, "value") else str(alt.severity),
                            "match_score": alt.match_score
                        })))
                    except Exception:
                        pass

        return {
            "status": "PROCESSED",
            "camera_id": frame_packet.camera_id,
            "detections": len(dets),
            "tracks": len(tracks),
            "sightings": len(sightings_persisted),
            "alerts": len(alerts_generated)
        }

    def _worker_loop(self):
        while self._running:
            active_cameras = list(self._camera_queues.keys())
            self.metrics.set_camera_workers(len(active_cameras))

            processed_any = False
            for cid in active_cameras:
                bq = self._camera_queues.get(cid)
                if not bq or bq.qsize() == 0:
                    continue

                try:
                    packet = bq.get(block=False)
                    self.process_single_frame(packet)
                    processed_any = True
                except Exception:
                    pass

            if not processed_any:
                time.sleep(self.config.max_batch_wait_ms / 1000.0)

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
                    "plate_recognizer": self._plate_recognizer is not None,
                    "target_pipeline": self._target_pipeline is not None
                }
            }


_GLOBAL_ANALYTICS_WORKER: Optional[AnalyticsWorker] = None


def get_analytics_worker() -> AnalyticsWorker:
    global _GLOBAL_ANALYTICS_WORKER
    if _GLOBAL_ANALYTICS_WORKER is None:
        _GLOBAL_ANALYTICS_WORKER = AnalyticsWorker()
    return _GLOBAL_ANALYTICS_WORKER
